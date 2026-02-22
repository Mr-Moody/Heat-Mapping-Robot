"""
Waypoint-based patrol: full coverage of floor 8 (single space).
"""
import math

# Floor 8: rows 2-7, cols 2-25. (x=col, y=row)
PATROL_WAYPOINTS = [
    (14.5, 5.0),
    (8.5, 2.5),
    (2.5, 2.5),
    (2.5, 4.5),
    (8.5, 4.5),
    (14.5, 4.5),
    (20.5, 4.5),
    (25.5, 2.5),
    (25.5, 4.5),
    (25.5, 6.5),
    (20.5, 6.5),
    (14.5, 6.5),
    (8.5, 6.5),
    (2.5, 6.5),
    (2.5, 5.5),
    (8.5, 5.5),
    (14.5, 5.5),
    (20.5, 5.5),
    (20.5, 3.5),
    (14.5, 3.5),
    (8.5, 3.5),
    (14.5, 5.0),
]


class WaypointController:
    def __init__(
        self,
        waypoints: list[tuple[float, float]] = None,
        arrival_dist: float = 0.4,
        v_base: float = 0.35,
        k_steer: float = 2.0,
    ):
        self.waypoints = waypoints or PATROL_WAYPOINTS
        self.arrival_dist = arrival_dist
        self.v_base = v_base
        self.k_steer = k_steer
        self.wheel_base = 0.2
        self._idx = 0

    def advance_waypoint(self) -> None:
        """Skip to next waypoint (e.g. when path blocked for a while)."""
        self._idx = (self._idx + 1) % len(self.waypoints)

    def compute(self, x: float, y: float, theta: float, dt: float) -> tuple[float, float]:
        wx, wy = self.waypoints[self._idx]
        dx = wx - x
        dy = wy - y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist < self.arrival_dist:
            self._idx = (self._idx + 1) % len(self.waypoints)
            wx, wy = self.waypoints[self._idx]
            dx = wx - x
            dy = wy - y
            dist = (dx * dx + dy * dy) ** 0.5

        if dist < 0.01:
            return self.v_base * 0.5, self.v_base * 0.5

        target_theta = math.atan2(dy, dx)
        error = target_theta - theta
        error = math.atan2(math.sin(error), math.cos(error))
        omega = self.k_steer * error
        omega = max(-1.2, min(1.2, omega))

        v_left = self.v_base - 0.5 * self.wheel_base * omega
        v_right = self.v_base + 0.5 * self.wheel_base * omega
        return v_left, v_right
