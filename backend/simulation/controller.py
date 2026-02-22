"""
PID wall-following controller and obstacle avoidance.
"""
import math


class WallFollowingController:
    def __init__(
        self,
        target_distance_cm: float = 30.0,
        kp: float = 0.5,
        ki: float = 0.01,
        kd: float = 0.1,
        wall_side: int = 1,
    ):
        self.target = target_distance_cm
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.wall_side = wall_side  # 1 = wall on left, -1 = wall on right
        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, distance_cm: float, dt: float) -> tuple[float, float]:
        """
        Returns (v_left, v_right) for differential drive.
        Wall on left: positive turn = turn left.
        error = target - measured: if too close, error negative, turn away (right).
        """
        error = self.target - distance_cm

        # Obstacle avoidance: very close -> strong turn away
        if distance_cm < 15:
            omega = -self.wall_side * 1.5
        elif distance_cm < 25:
            omega = -self.wall_side * 0.8
        elif distance_cm > 50:
            # Too far from wall, turn toward it
            omega = self.wall_side * 0.4
        else:
            self.integral += error * dt
            self.integral = max(-10, min(10, self.integral))
            derivative = (error - self.prev_error) / dt if dt > 0 else 0
            omega = self.kp * error + self.ki * self.integral + self.kd * derivative
            omega *= -self.wall_side
            self.prev_error = error

        omega = max(-1.5, min(1.5, omega))
        v_base = 0.25
        wheel_base = 0.2
        v_left = v_base - 0.5 * wheel_base * omega
        v_right = v_base + 0.5 * wheel_base * omega
        return v_left, v_right
