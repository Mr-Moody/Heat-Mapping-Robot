"""
Arduino connection handler: receives readings, processes point cloud, runs path planning,
and produces FrontendUpdate for WebSocket broadcast.
"""

import math
from typing import Callable

from .models import ArduinoReadingsPayload, FrontendUpdate, RobotPose
from .point_cloud import polar_to_cartesian, readings_to_points, add_to_ring_buffer
from .occupancy_grid import OccupancyGrid
from .idw_interpolation import idw_grid_for_frontend
from .path_planning import PathPlanner, RobotState, SensorReading
from .kalman_imu import KalmanHeadingFilter
from .analytics import (
    ThermalReading,
    compute_analytics,
    thermal_to_frontend_points,
)

# Cart stationary: False = robot moves via dead reckoning + backend commands
CART_STATIONARY = False

# Sweep bins: 12 sectors, each 30°. Index 0 = 0°, 3 = 90° left, 6 = 180°, 9 = 270° right.
BIN_ANGLE = 10.0
SWEEP_BINS = int(180.0 / BIN_ANGLE)

MAX_POINT_CLOUD_SIZE = 2000
DISPLAY_POINT_LIMIT = 2 * SWEEP_BINS


def _bin_readings_to_sweep(readings: list[tuple[float, float]]) -> list[float]:
    """Bin (angle, distance) readings into 12 sectors. Invalid = 400 (far) for nav."""
    sweep = [0.0] * SWEEP_BINS
    counts = [0] * SWEEP_BINS

    for angle_deg, distance_cm in readings:
        d = distance_cm if 0 < distance_cm <= 400 else 400.0
        angle_norm = (angle_deg % 360 + 360) % 360
        idx = int(round(angle_norm / BIN_ANGLE)) % SWEEP_BINS
        sweep[idx] += d
        counts[idx] += 1

    for i in range(SWEEP_BINS):
        if counts[i] > 0:
            sweep[i] /= counts[i]
        else:
            sweep[i] = 150.0

    return sweep


class ArduinoConnection():
    """Manages robot state, point cloud, and path planning."""

    def __init__(self):
        self.robot_state = RobotState()
        self.planner = PathPlanner()
        self._pending_motor_cmd: str | None = None
        self.kalman_heading = KalmanHeadingFilter(dt=0.5)
        self.occupancy_grid = OccupancyGrid(
            width_m=10.0, height_m=10.0, resolution_m=0.1,
        )
        self.point_cloud: list[list[float]] = []
        self.last_sweep_cm: list[float] = [150.0] * SWEEP_BINS
        self.last_action = "IDLE"
        self._timestamp_ms = 0
        self._last_timestamp_ms = 0
        self.thermal_history: list[ThermalReading] = []
        self.last_air_temp_c: float | None = None
        self.last_humidity_pct: float | None = None
        self.last_gyro_z: float | None = None

    def receive_readings(self, payload: ArduinoReadingsPayload) -> FrontendUpdate:
        """
        Process incoming Arduino readings, update point cloud and robot state,
        run path planner, and return update for frontend broadcast.
        """
        dt_ms = payload.timestamp_ms - self._last_timestamp_ms
        if self._last_timestamp_ms == 0 or dt_ms <= 0:
            dt_ms = 500  # first packet, assume ~500ms
        self._last_timestamp_ms = payload.timestamp_ms
        dt_s = max(0.01, min(2.0, dt_ms / 1000.0))

        # Extract gyro_z from first reading with IMU data
        gyro_z_val: float | None = None
        for r in payload.readings:
            if r.gyro_z is not None:
                gyro_z_val = r.gyro_z
                break
        if gyro_z_val is not None:
            self.last_gyro_z = gyro_z_val
            if not CART_STATIONARY:
                self.kalman_heading.update(gyro_z_val, dt=dt_s)
                self.robot_state.heading_deg = self.kalman_heading.get_heading_deg()

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

        # Update occupancy grid: use all readings (invalid = max range for mapping)
        rx = self.robot_state.x
        ry = self.robot_state.y
        hd = self.robot_state.heading_deg
        for angle_deg, distance_cm in readings:
            d = min(400.0, max(1.0, distance_cm)) if distance_cm else 400.0
            wx, _, wz = polar_to_cartesian(angle_deg, d, rx, ry, hd)
            self.occupancy_grid.update_ray(rx, ry, wx, wz)

        # Store latest DHT readings for frontend
        if payload.air_temp_c is not None:
            self.last_air_temp_c = payload.air_temp_c
        if payload.humidity_pct is not None:
            self.last_humidity_pct = payload.humidity_pct

        # Build SensorReading for path planner (use thermal from payload if present)
        forward_cm = sweep_cm[0]
        temp = payload.air_temp_c if payload.air_temp_c is not None else 20.0
        humidity = payload.humidity_pct if payload.humidity_pct is not None else 50.0
        reading = SensorReading(
            forward_cm=forward_cm,
            sweep_cm=sweep_cm,
            temperature=temp,
            humidity=humidity,
            timestamp_ms=payload.timestamp_ms,
        )

        # Append thermal to history for analytics (use surface or air temp)
        if payload.air_temp_c is not None or payload.surface_temp_c is not None:
            surface = payload.surface_temp_c or payload.air_temp_c or 20.0
            air = payload.air_temp_c or payload.surface_temp_c or 20.0
            room_id = int(self.robot_state.x / 1.5)  # ~1.5m per room
            self.thermal_history.append(
                ThermalReading(
                    x_m=self.robot_state.x,
                    y_m=self.robot_state.y,
                    surface_temp_c=surface,
                    air_temp_c=air,
                    room_id=max(0, room_id),
                )
            )
            if len(self.thermal_history) > 500:
                self.thermal_history = self.thermal_history[-500:]

        # Occupancy-grid navigation
        occupancy_cmd, occupancy_turn = self.occupancy_grid.get_best_direction(
            rx, ry, self.robot_state.heading_deg,
        )
        occupancy_best = (occupancy_cmd, occupancy_turn)

        # Run path planner (occupancy takes priority; ultrasonic for obstacle override)
        action, speed, turn_deg = self.planner.decide(
            reading, self.robot_state, occupancy_best=occupancy_best,
        )

        self.robot_state.action = action
        self.robot_state.speed = speed
        self.last_action = action

        if not CART_STATIONARY:
            # Update robot state (simulate movement)
            self.robot_state.heading_deg = (self.robot_state.heading_deg + turn_deg) % 360
            move = PathPlanner.STEP_SIZE_M * speed
            rad = math.radians(90 - self.robot_state.heading_deg)
            self.robot_state.x += move * math.cos(rad)
            self.robot_state.y += move * math.sin(rad)
            self.robot_state.distance_travelled += move

        analytics = compute_analytics(self.thermal_history)
        thermal_points = thermal_to_frontend_points(self.thermal_history)
        thermal_grid, thermal_bounds = idw_grid_for_frontend(
            self.thermal_history,
            x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0,
            resolution_m=0.2,
        )
        display_points = self.point_cloud[-DISPLAY_POINT_LIMIT:]
        motor_cmd = self._action_to_motor_cmd(action, turn_deg)
        self._pending_motor_cmd = motor_cmd
        return FrontendUpdate(
            points=display_points,
            robot=RobotPose(
                x=self.robot_state.x,
                y=self.robot_state.y,
                heading_deg=self.robot_state.heading_deg,
            ),
            action=action,
            sweep_cm=sweep_cm,
            thermal_points=thermal_points,
            analytics=analytics,
            air_temp_c=self.last_air_temp_c,
            humidity_pct=self.last_humidity_pct,
            gyro_z=self.last_gyro_z,
            occupancy_grid=self.occupancy_grid.get_grid_for_frontend(),
            occupancy_bounds=self.occupancy_grid.get_bounds(),
            thermal_grid=thermal_grid,
            thermal_grid_bounds=thermal_bounds,
        )

    def _action_to_motor_cmd(self, action: str, turn_deg: float) -> str:
        """Convert planner action to Arduino single-char command: F, B, L, R, S."""
        if "STOP" in action or "IDLE" in action:
            return "S"
        if "FORWARD" in action or "LAWNMOWER_FORWARD" in action:
            return "F"
        if "BACK" in action or "LAWNMOWER_BACK" in action:
            return "B"
        if "LEFT" in action or turn_deg < 0:
            return "L"
        if "RIGHT" in action or turn_deg > 0:
            return "R"
        return "F"

    def pop_pending_motor_cmd(self) -> str | None:
        """Return and clear the next motor command for Arduino. Call after send."""
        cmd = self._pending_motor_cmd
        self._pending_motor_cmd = None
        return cmd

    def get_current_state(self) -> FrontendUpdate:
        """Return current state for new WebSocket clients."""
        analytics = compute_analytics(self.thermal_history)
        thermal_points = thermal_to_frontend_points(self.thermal_history)
        thermal_grid, thermal_bounds = idw_grid_for_frontend(
            self.thermal_history,
            x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0,
            resolution_m=0.2,
        )
        display_points = self.point_cloud[-DISPLAY_POINT_LIMIT:]
        return FrontendUpdate(
            points=display_points,
            robot=RobotPose(
                x=self.robot_state.x,
                y=self.robot_state.y,
                heading_deg=self.robot_state.heading_deg,
            ),
            action=self.last_action,
            sweep_cm=self.last_sweep_cm,
            thermal_points=thermal_points,
            analytics=analytics,
            air_temp_c=self.last_air_temp_c,
            humidity_pct=self.last_humidity_pct,
            gyro_z=self.last_gyro_z,
            occupancy_grid=self.occupancy_grid.get_grid_for_frontend(),
            occupancy_bounds=self.occupancy_grid.get_bounds(),
            thermal_grid=thermal_grid,
            thermal_grid_bounds=thermal_bounds,
        )


# Singleton instance
_connection: ArduinoConnection | None = None


def get_connection() -> ArduinoConnection:
    global _connection
    if _connection is None:
        _connection = ArduinoConnection()

    return _connection
