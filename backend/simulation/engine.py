"""
Main simulation loop: robots + sensors + waypoint patrol + real-time SLAM.
Each robot has own Robot, trail, SLAM grid. Shared floorplan and aggregate heatmap.
"""
import time
import asyncio
import math
import random
from dataclasses import dataclass
from .floorplan import Floorplan, OBSTACLE_CELLS
from .robot import Robot
from .sensors import SensorSimulator
from .waypoint_controller import WaypointController
from .slam import OccupancyGrid
from .moving_obstacles import make_default_moving_obstacles


@dataclass
class RobotState:
    timestamp: float
    x: float
    y: float
    theta: float
    ultrasonic_distance_cm: float
    temperature_c: float
    humidity_percent: float
    room_id: str | None

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "position": {"x": self.x, "y": self.y, "theta": self.theta},
            "ultrasonic_distance_cm": self.ultrasonic_distance_cm,
            "temperature_c": self.temperature_c,
            "humidity_percent": self.humidity_percent,
            "room_id": self.room_id or "corridor",
        }


HEATMAP_SUBDIV = 4  # 4x4 per 1m cell -> 0.25m resolution for higher area resolution
ACTIVE_TIMEOUT = 60.0  # seconds; robot is "active" if state within this

ROBOT_IDS = ["robot-1", "robot-2", "robot-3"]
ROBOT_NAMES = {
    "robot-1": "Scout Alpha",
    "robot-2": "Scout Beta",
    "robot-3": "Scout Gamma",
}
ROBOT_ROOM_ASSIGNMENTS = {
    "robot-1": "floor_5",
    "robot-2": "floor_6",
    "robot-3": "floor_8",
}
# Distinct start positions for each robot
ROBOT_STARTS = [
    (14.5, 5.0),
    (10.5, 4.0),
    (18.5, 6.0),
]


class SimulationEngine:
    def __init__(self):
        self.floorplan = Floorplan()
        self.sensors = SensorSimulator(self.floorplan)
        self.dt = 0.05
        self._running = False
        self._heatmap_data: dict[tuple[int, int], list[float]] = {}
        self._heatmap_subdiv = HEATMAP_SUBDIV
        self._moving_obstacles = make_default_moving_obstacles(14.5, 5.0)

        # Per-robot structures
        self._robots: dict[str, Robot] = {}
        self._controllers: dict[str, WaypointController] = {}
        self._slams: dict[str, OccupancyGrid] = {}
        self._state_queues: dict[str, asyncio.Queue[RobotState]] = {}
        self._last_states: dict[str, RobotState | None] = {}
        self._trails: dict[str, list[tuple[float, float]]] = {}
        self._avoidance_until: dict[str, float] = {}
        self._avoidance_since: dict[str, float] = {}
        self._last_recorded_temp: dict[str, float] = {}

        for i, rid in enumerate(ROBOT_IDS):
            x, y = ROBOT_STARTS[i % len(ROBOT_STARTS)]
            self._robots[rid] = Robot(x=x, y=y, theta=0.0)
            self._controllers[rid] = WaypointController()
            self._slams[rid] = OccupancyGrid(
                self.floorplan.rows, self.floorplan.cols,
                cell_size=1.0, subdiv=HEATMAP_SUBDIV,
            )
            self._state_queues[rid] = asyncio.Queue(maxsize=1000)
            self._last_states[rid] = None
            self._trails[rid] = []
            self._avoidance_until[rid] = 0.0
            self._avoidance_since[rid] = 0.0
            self._last_recorded_temp[rid] = 20.0

        # Backward compat: expose first robot as .robot, first slam as .slam
        self.robot = self._robots[ROBOT_IDS[0]]
        self.slam = self._slams[ROBOT_IDS[0]]

    def get_robot_ids(self) -> list[str]:
        return list(ROBOT_IDS)

    def get_robot_names(self) -> dict[str, str]:
        return dict(ROBOT_NAMES)

    def is_robot_active(self, robot_id: str) -> bool:
        """True if robot has state within ACTIVE_TIMEOUT."""
        s = self._last_states.get(robot_id)
        if s is None:
            return False
        return (time.time() - s.timestamp) < ACTIVE_TIMEOUT

    def get_current_state(self, robot_id: str | None = None) -> RobotState | None:
        """Get latest state for robot_id. If None, use first robot (backward compat)."""
        rid = robot_id or ROBOT_IDS[0]
        if rid not in self._state_queues:
            return None
        q = self._state_queues[rid]
        while True:
            try:
                s = q.get_nowait()
                self._last_states[rid] = s
            except asyncio.QueueEmpty:
                break
        return self._last_states.get(rid)

    def get_trail(self, robot_id: str | None = None) -> list[tuple[float, float]]:
        rid = robot_id or ROBOT_IDS[0]
        return list(self._trails.get(rid, []))

    def get_heatmap_data(self) -> dict[tuple[int, int], list[float]]:
        return dict(self._heatmap_data)

    def _fine_cells_under_footprint(self, x: float, y: float) -> list[tuple[int, int]]:
        r0, c0 = self.floorplan.world_to_fine_cell(x, y, self._heatmap_subdiv)
        out = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                out.append((r0 + dr, c0 + dc))
        for dr in (-2, 0, 2):
            if dr == 0:
                for dc in (-2, 2):
                    out.append((r0 + dr, c0 + dc))
            else:
                out.append((r0 + dr, c0))
        return out

    def get_heatmap_cells(self) -> dict[str, float]:
        result = {}
        for (row, col), temps in self._heatmap_data.items():
            if not temps:
                continue
            result[f"{row},{col}"] = temps[-1]
        return result

    def get_heatmap_shape(self) -> tuple[int, int]:
        r = self.floorplan.rows * self._heatmap_subdiv
        c = self.floorplan.cols * self._heatmap_subdiv
        return r, c

    def get_grid(self) -> list[list[int]]:
        return self.floorplan.grid

    def get_obstacle_points(self, robot_id: str | None = None) -> list[list[float]]:
        rid = robot_id or ROBOT_IDS[0]
        slam = self._slams.get(rid)
        if not slam:
            return []
        return slam.get_obstacle_points()

    def get_obstacle_cells(self) -> list[list[int]]:
        """Static floorplan obstacles as [row, col] for 2D/3D visualization."""
        return [[r, c] for r, c in OBSTACLE_CELLS]

    def get_simulated_point_cloud(
        self,
        robot_id: str | None = None,
        num_rays: int = 72,
        max_range: float = 8.0,
        dist_noise_std: float = 0.03,
        angle_noise_std: float = 0.008,
        height_noise_std: float = 0.01,
    ) -> list[list[float]]:
        rid = robot_id or ROBOT_IDS[0]
        r = self._robots.get(rid)
        if not r:
            return []
        points: list[list[float]] = []
        x0, y0 = r.x, r.y
        theta0 = r.theta
        for i in range(num_rays):
            angle = 2 * math.pi * i / num_rays + random.gauss(0, angle_noise_std)
            ray_angle = theta0 + angle
            dist = self.floorplan.raycast(x0, y0, ray_angle, max_range)
            if dist is None:
                continue
            dist_noisy = max(0.05, dist + random.gauss(0, dist_noise_std))
            wx = x0 + math.cos(ray_angle) * dist_noisy
            wy = y0 + math.sin(ray_angle) * dist_noisy
            h = 0.02 + random.gauss(0, height_noise_std)
            points.append([wx, h, wy])
        return points

    async def run_loop(self):
        self._running = True
        stuck_advance_interval = 2.0

        while self._running:
            t0 = time.time()

            for obs in self._moving_obstacles:
                obs.step(self.dt)

            now = time.time()

            for rid in ROBOT_IDS:
                robot = self._robots[rid]
                slam = self._slams[rid]
                controller = self._controllers[rid]

                dist = self.sensors.ultrasonic(
                    robot.x, robot.y, robot.theta,
                    moving_obstacles=self._moving_obstacles,
                )
                dist_m = dist / 100.0

                slam.update_ray(robot.x, robot.y, robot.theta, dist_m)

                obstacle_near = slam.is_obstacle_ahead(
                    robot.x, robot.y, robot.theta,
                    distance=0.55, cone_half_rad=0.3,
                )

                if obstacle_near:
                    self._avoidance_since[rid] = now if self._avoidance_until[rid] <= now else self._avoidance_since[rid]
                    self._avoidance_until[rid] = now + 0.7

                in_avoidance = now < self._avoidance_until[rid]

                if in_avoidance:
                    steer_explore = slam.get_exploration_steer(
                        robot.x, robot.y, robot.theta, look_dist=0.7
                    )
                    steer_clear = slam.get_clear_steer(
                        robot.x, robot.y, robot.theta, look_dist=0.5
                    )
                    steer = steer_clear if abs(steer_clear) > 0.5 else steer_explore
                    v_base = 0.28
                    omega = steer * 1.0
                    wheel_base = 0.2
                    v_left = v_base - 0.5 * wheel_base * omega
                    v_right = v_base + 0.5 * wheel_base * omega
                    if now - self._avoidance_since[rid] >= stuck_advance_interval:
                        controller.advance_waypoint()
                        self._avoidance_until[rid] = 0.0
                else:
                    v_left, v_right = controller.compute(
                        robot.x, robot.y, robot.theta, self.dt
                    )

                robot.step(v_left, v_right, self.dt)

                row, col = self.floorplan.world_to_cell(robot.x, robot.y)
                if self.floorplan.is_traversable(row, col):
                    room_id = self.floorplan.get_room_id_at(robot.x, robot.y)
                    temp = self.sensors.temperature(robot.x, robot.y, room_id)
                    hum = self.sensors.humidity(robot.x, robot.y, room_id, temp)
                else:
                    robot.x -= 0.1
                    room_id = None
                    temp = 18.0
                    hum = 50.0

                self._last_recorded_temp[rid] = temp

                display_room_id = ROBOT_ROOM_ASSIGNMENTS.get(rid, room_id)
                state = RobotState(
                    timestamp=time.time(),
                    x=robot.x,
                    y=robot.y,
                    theta=robot.theta,
                    ultrasonic_distance_cm=dist,
                    temperature_c=temp,
                    humidity_percent=hum,
                    room_id=display_room_id,
                )

                q = self._state_queues[rid]
                try:
                    q.put_nowait(state)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    q.put_nowait(state)
                self._last_states[rid] = state

                self._trails[rid].append((robot.x, robot.y))
                if len(self._trails[rid]) > 500:
                    self._trails[rid].pop(0)

                if self.floorplan.is_traversable(row, col):
                    for (fr, fc) in self._fine_cells_under_footprint(robot.x, robot.y):
                        if not self.floorplan.fine_cell_traversable(fr, fc, self._heatmap_subdiv):
                            continue
                        key = (fr, fc)
                        if key not in self._heatmap_data:
                            self._heatmap_data[key] = []
                        self._heatmap_data[key].append(temp)
                        if len(self._heatmap_data[key]) > 15:
                            self._heatmap_data[key].pop(0)

            elapsed = time.time() - t0
            await asyncio.sleep(max(0, self.dt - elapsed))

    def stop(self):
        self._running = False
