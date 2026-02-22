"""
Moving obstacles: positions updated each frame so SLAM can detect and avoid them.
"""
import math
import time


class MovingObstacle:
    """Single moving obstacle: (x, y) and radius in metres. Position updates each step."""

    def __init__(self, x: float, y: float, radius: float = 0.35, speed: float = 0.4):
        self.x = x
        self.y = y
        self.radius = radius
        self.speed = speed
        self._t0 = time.time()
        self._path_center_x = x
        self._path_center_y = y
        self._path_radius = 2.5  # circular path radius

    def step(self, dt: float) -> None:
        t = time.time() - self._t0
        self.x = self._path_center_x + self._path_radius * math.cos(t * self.speed)
        self.y = self._path_center_y + self._path_radius * math.sin(t * self.speed)


def make_default_moving_obstacles(bounds_center_x: float, bounds_center_y: float) -> list:
    """Two obstacles moving on circular paths within the floor bounds."""
    return [
        MovingObstacle(bounds_center_x - 3, bounds_center_y, radius=0.35, speed=0.25),
        MovingObstacle(bounds_center_x + 2, bounds_center_y + 1.5, radius=0.35, speed=0.2),
    ]
