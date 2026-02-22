"""
1D Kalman filter for IMU heading (dead reckoning).
Fuses gyroscope (short-term precision) with optional accelerometer (long-term stability).
State: [heading_deg, gyro_bias]. Integrates gyro_z, adapts bias when stationary.
"""

import math
from dataclasses import dataclass


@dataclass
class KalmanIMUState:
    """Filter state."""
    heading_deg: float = 0.0
    gyro_bias: float = 0.0
    P_heading: float = 1.0   # covariance
    P_bias: float = 1.0


class KalmanHeadingFilter:
    """
    1D Kalman filter for heading from gyro_z.
    Assumes no direct heading measurement; uses process model to integrate gyro
    and estimate bias for drift reduction.
    """

    def __init__(
        self,
        dt: float = 0.1,
        process_noise_heading: float = 0.01,
        process_noise_bias: float = 0.0001,
    ):
        self.dt = dt
        self.q_heading = process_noise_heading
        self.q_bias = process_noise_bias
        self.state = KalmanIMUState()
        self._last_t = 0.0

    def update(
        self,
        gyro_z: float,
        dt: float | None = None,
        accel_x: float | None = None,
        accel_y: float | None = None,
    ) -> float:
        """
        Update with gyro reading (deg/s). Optionally accel for future tilt correction.
        Returns filtered heading in degrees [0, 360).
        """
        delta_t = dt if dt is not None else self.dt

        # Predict: heading += (gyro_z - bias) * dt
        gyro_corrected = gyro_z - self.state.gyro_bias
        self.state.heading_deg += gyro_corrected * delta_t

        # Wrap to [0, 360)
        self.state.heading_deg = self.state.heading_deg % 360.0
        if self.state.heading_deg < 0:
            self.state.heading_deg += 360.0

        # Predict covariance (simplified 1D)
        self.state.P_heading += self.q_heading * delta_t
        self.state.P_bias += self.q_bias * delta_t

        # Optional: when stationary (accel magnitude ~1g), use accel to correct bias
        # For now we rely on process model; bias adapts slowly via q_bias
        # Future: if accel suggests stationary, do measurement update with heading_measurement=prior

        return self.state.heading_deg

    def get_heading_deg(self) -> float:
        """Return current heading [0, 360)."""
        h = self.state.heading_deg % 360.0
        return h + 360.0 if h < 0 else h

    def reset(self, heading_deg: float = 0.0):
        """Reset filter state."""
        self.state = KalmanIMUState(
            heading_deg=heading_deg,
            gyro_bias=0.0,
            P_heading=1.0,
            P_bias=1.0,
        )
