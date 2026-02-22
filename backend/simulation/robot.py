"""
Differential drive robot with position (x, y, theta).
"""
import math


class Robot:
    def __init__(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0):
        self.x = x
        self.y = y
        self.theta = theta
        self.wheel_base = 0.2
        self.max_speed = 0.3

    def step(self, v_left: float, v_right: float, dt: float):
        """Apply differential drive kinematics."""
        v = (v_left + v_right) / 2
        omega = (v_right - v_left) / self.wheel_base

        self.x += v * math.cos(self.theta) * dt
        self.y += v * math.sin(self.theta) * dt
        self.theta += omega * dt

        # Normalize theta to [-pi, pi]
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))

    def to_dict(self):
        return {"x": self.x, "y": self.y, "theta": self.theta}
