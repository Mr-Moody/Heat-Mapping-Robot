"""
Main simulation loop: robot + sensors + waypoint patrol + real-time SLAM.
Robot only uses bounding region; interior map and obstacles (including moving) are
built and avoided via SLAM from sensor data.
"""
import time
import asyncio
import math
import random
from dataclasses import dataclass
from .floorplan import Floorplan
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


class SimulationEngine:
    def __init__(self):
        self.floorplan = Floorplan()
        self.robot = Robot(x=14.5, y=5.0, theta=0.0)  # Start mid-floor
        self.sensors = SensorSimulator(self.floorplan)
        self.controller = WaypointController()
        self.dt = 0.05
        self._running = False
        self._state_queue: asyncio.Queue[RobotState] = asyncio.Queue(maxsize=1000)
        self._last_state: RobotState | None = None
        self._trail: list[tuple[float, float]] = []
        self._heatmap_data: dict[tuple[int, int], list[float]] = {}
        self._last_recorded_temp: float = 20.0
        self._heatmap_subdiv = HEATMAP_SUBDIV
        # SLAM: only bounding region known; map built in real time from sensor rays
        self.slam = OccupancyGrid(
            self.floorplan.rows, self.floorplan.cols,
            cell_size=1.0, subdiv=HEATMAP_SUBDIV,
        )
        self._moving_obstacles = make_default_moving_obstacles(14.5, 5.0)
        self._avoidance_until = 0.0  # commit to avoidance until this time
        self._avoidance_since = 0.0   # when we last entered avoidance
        self._stuck_advance_interval = 2.0  # advance waypoint if avoiding this long

    def get_current_state(self) -> RobotState | None:
        while True:
            try:
                s = self._state_queue.get_nowait()
                self._last_state = s
            except asyncio.QueueEmpty:
                break
        return self._last_state

    def get_trail(self) -> list[tuple[float, float]]:
        return list(self._trail)

    def get_heatmap_data(self) -> dict[tuple[int, int], list[float]]:
        return dict(self._heatmap_data)

    def _fine_cells_under_footprint(self, x: float, y: float) -> list[tuple[int, int]]:
        """Current fine cell + adjacent fine cells (sensor footprint ~1m + neighbors)."""
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
        """
        Fine grid (0.5m): explored cells only, most recent reading. Keys "row,col" in fine indices.
        """
        result = {}
        for (row, col), temps in self._heatmap_data.items():
            if not temps:
                continue
            result[f"{row},{col}"] = temps[-1]
        return result

    def get_heatmap_shape(self) -> tuple[int, int]:
        """(fine_rows, fine_cols) for frontend."""
        r = self.floorplan.rows * self._heatmap_subdiv
        c = self.floorplan.cols * self._heatmap_subdiv
        return r, c

    def get_grid(self) -> list[list[int]]:
        return self.floorplan.grid

    def get_simulated_point_cloud(
        self,
        num_rays: int = 72,
        max_range: float = 8.0,
        dist_noise_std: float = 0.03,
        angle_noise_std: float = 0.008,
        height_noise_std: float = 0.01,
    ) -> list[list[float]]:
        """Simulate a 2D LIDAR-style point cloud from the current robot pose.
        Returns list of [x, y, z] in world coords (y = height above floor, small noise).
        Adds Gaussian noise to distance, angle, and height for realism."""
        points: list[list[float]] = []
        x0, y0 = self.robot.x, self.robot.y
        theta0 = self.robot.theta
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
        while self._running:
            t0 = time.time()

            # Update moving obstacles (they don't require knowing the map)
            for obs in self._moving_obstacles:
                obs.step(self.dt)

            now = time.time()

            # Ultrasonic first (needed for SLAM update)
            dist = self.sensors.ultrasonic(
                self.robot.x, self.robot.y, self.robot.theta,
                moving_obstacles=self._moving_obstacles,
            )
            dist_m = dist / 100.0

            # SLAM: integrate ray (mapping)
            self.slam.update_ray(
                self.robot.x, self.robot.y, self.robot.theta, dist_m
            )

            obstacle_near = self.slam.is_obstacle_ahead(
                self.robot.x, self.robot.y, self.robot.theta,
                distance=0.55, cone_half_rad=0.3
            )

            # Commitment: stay in avoidance mode for a short period to avoid oscillation
            if obstacle_near:
                self._avoidance_since = now if self._avoidance_until <= now else self._avoidance_since
                self._avoidance_until = now + 0.7

            in_avoidance = now < self._avoidance_until

            if in_avoidance:
                # Explore while avoiding: prefer direction with more unknown (SLAM exploration)
                steer_explore = self.slam.get_exploration_steer(
                    self.robot.x, self.robot.y, self.robot.theta, look_dist=0.7
                )
                steer_clear = self.slam.get_clear_steer(
                    self.robot.x, self.robot.y, self.robot.theta, look_dist=0.5
                )
                # Blend: respect clear (don't hit) but bias toward exploration
                steer = steer_clear if abs(steer_clear) > 0.5 else steer_explore
                v_base = 0.28
                omega = steer * 1.0
                wheel_base = 0.2
                v_left = v_base - 0.5 * wheel_base * omega
                v_right = v_base + 0.5 * wheel_base * omega
                # If stuck avoiding same area, advance waypoint to improve coverage
                if now - self._avoidance_since >= self._stuck_advance_interval:
                    self.controller.advance_waypoint()
                    self._avoidance_until = 0.0
            else:
                v_left, v_right = self.controller.compute(
                    self.robot.x, self.robot.y, self.robot.theta, self.dt
                )

            self.robot.step(v_left, v_right, self.dt)

            row, col = self.floorplan.world_to_cell(self.robot.x, self.robot.y)
            if self.floorplan.is_traversable(row, col):
                room_id = self.floorplan.get_room_id_at(self.robot.x, self.robot.y)
                temp = self.sensors.temperature(
                    self.robot.x, self.robot.y, room_id
                )
                hum = self.sensors.humidity(
                    self.robot.x, self.robot.y, room_id, temp
                )
            else:
                self.robot.x -= 0.1  # Bounce back
                room_id = None
                temp = 18.0
                hum = 50.0

            self._last_recorded_temp = temp

            state = RobotState(
                timestamp=time.time(),
                x=self.robot.x,
                y=self.robot.y,
                theta=self.robot.theta,
                ultrasonic_distance_cm=dist,
                temperature_c=temp,
                humidity_percent=hum,
                room_id=room_id,
            )

            try:
                self._state_queue.put_nowait(state)
            except asyncio.QueueFull:
                try:
                    self._state_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                self._state_queue.put_nowait(state)

            self._trail.append((self.robot.x, self.robot.y))
            if len(self._trail) > 500:
                self._trail.pop(0)

            if self.floorplan.is_traversable(row, col):
                for (fr, fc) in self._fine_cells_under_footprint(self.robot.x, self.robot.y):
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
