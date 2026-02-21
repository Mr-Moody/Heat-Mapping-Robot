"""
Arduino connection handler: receives readings, processes point cloud, runs path planning,
and produces FrontendUpdate for WebSocket broadcast.
"""

import math
from typing import Callable

from .models import ArduinoReadingsPayload, FrontendUpdate, RobotPose
from .point_cloud import readings_to_points, add_to_ring_buffer
from .path_planning import PathPlanner, RobotState, SensorReading

# Sweep bins: 12 sectors, each 30°. Index 0 = 0°, 3 = 90° left, 6 = 180°, 9 = 270° right.
SWEEP_BINS = 12
BIN_ANGLE = 360.0 / SWEEP_BINS
MAX_POINT_CLOUD_SIZE = 2000


def _bin_readings_to_sweep(readings: list[tuple[float, float]]) -> list[float]:
    """Bin (angle, distance) readings into 12 sectors. Use nearest or average."""
    sweep = [0.0] * SWEEP_BINS
    counts = [0] * SWEEP_BINS

    for angle_deg, distance_cm in readings:
        if distance_cm <= 0 or distance_cm > 400:
            continue

        angle_norm = (angle_deg % 360 + 360) % 360
        idx = int(round(angle_norm / BIN_ANGLE)) % SWEEP_BINS
        sweep[idx] += distance_cm
        counts[idx] += 1

    for i in range(SWEEP_BINS):
        if counts[i] > 0:
            sweep[i] /= counts[i]
        else:
            sweep[i] = 150.0  # Default far when no reading

    return sweep


class ArduinoConnection():
    """Manages robot state, point cloud, and path planning."""

    def __init__(self):
        self.robot_state = RobotState()
        self.planner = PathPlanner()
        self.point_cloud: list[list[float]] = []
        self.last_sweep_cm: list[float] = [150.0] * SWEEP_BINS
        self.last_action = "IDLE"
        self._timestamp_ms = 0

    def receive_readings(self, payload: ArduinoReadingsPayload) -> FrontendUpdate:
        """
        Process incoming Arduino readings, update point cloud and robot state,
        run path planner, and return update for frontend broadcast.
        """
        self._timestamp_ms = payload.timestamp_ms

        # Build readings list
        readings = [(r.angle, r.distance) for r in payload.readings]

        # Merge into sweep (accumulate with existing for smoother data)
        new_sweep = _bin_readings_to_sweep(readings)
        # Blend with previous sweep for stability
        sweep_cm = [
            0.5 * self.last_sweep_cm[i] + 0.5 * new_sweep[i]
            for i in range(SWEEP_BINS)
        ]
        self.last_sweep_cm = sweep_cm

        # Convert to 3D points and append to point cloud
        new_points = readings_to_points(
            readings,
            self.robot_state.x,
            self.robot_state.y,
            self.robot_state.heading_deg,
        )

        self.point_cloud = add_to_ring_buffer(
            self.point_cloud, new_points, MAX_POINT_CLOUD_SIZE
        )

        # Build SensorReading for path planner (no DHT11 from Arduino yet)
        forward_cm = sweep_cm[0]
        reading = SensorReading(
            forward_cm=forward_cm,
            sweep_cm=sweep_cm,
            temperature=20.0,
            humidity=50.0,
            timestamp_ms=payload.timestamp_ms,
        )

        # Run path planner
        action, speed, turn_deg = self.planner.decide(reading, self.robot_state)

        # Update robot state (simulate movement)
        self.robot_state.heading_deg = (self.robot_state.heading_deg + turn_deg) % 360

        move = PathPlanner.STEP_SIZE_M * speed
        rad = math.radians(90 - self.robot_state.heading_deg)

        self.robot_state.x += move * math.cos(rad)
        self.robot_state.y += move * math.sin(rad)
        self.robot_state.distance_travelled += move
        self.robot_state.action = action
        self.robot_state.speed = speed
        self.last_action = action

        return FrontendUpdate(
            points=self.point_cloud,
            robot=RobotPose(
                x=self.robot_state.x,
                y=self.robot_state.y,
                heading_deg=self.robot_state.heading_deg,
            ),
            action=action,
            sweep_cm=sweep_cm,
        )

    def get_current_state(self) -> FrontendUpdate:
        """Return current state for new WebSocket clients."""
        return FrontendUpdate(
            points=self.point_cloud,
            robot=RobotPose(
                x=self.robot_state.x,
                y=self.robot_state.y,
                heading_deg=self.robot_state.heading_deg,
            ),
            action=self.last_action,
            sweep_cm=self.last_sweep_cm,
        )


# Singleton instance
_connection: ArduinoConnection | None = None


def get_connection() -> ArduinoConnection:
    global _connection
    if _connection is None:
        _connection = ArduinoConnection()

    return _connection
