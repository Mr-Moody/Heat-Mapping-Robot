"""
Simulated sensors: ultrasonic, temperature, humidity.
UK campus building environment with obstacles.
"""
import math
import random
import time
from .floorplan import Floorplan, ROOM_CONFIGS, CellType


class SensorSimulator:
    """Generates synthetic ultrasonic, temperature, and humidity readings."""

    def __init__(self, floorplan: Floorplan):
        self.floorplan = floorplan
        self.ultrasonic_max_cm = 400
        self._temp_noise = 0.15
        self._humidity_noise = 2.5
        self._t0 = time.time()

    def _raycast_ultrasonic(self, x: float, y: float, theta: float) -> float:
        """Raycast to nearest static obstacle or wall."""
        dx = math.cos(theta)
        dy = math.sin(theta)
        step = 0.05
        dist = 0.0
        max_dist = self.ultrasonic_max_cm / 100

        while dist < max_dist:
            dist += step
            px = x + dx * dist
            py = y + dy * dist
            row, col = self.floorplan.world_to_cell(px, py)
            if self.floorplan.is_obstacle(row, col):
                dist_cm = dist * 100
                noise = random.gauss(0, 1.5)
                return max(8.0, min(self.ultrasonic_max_cm, dist_cm + noise))
            if not self.floorplan.is_traversable(row, col):
                dist_cm = dist * 100
                noise = random.gauss(0, 1.0)
                return max(2.0, min(self.ultrasonic_max_cm, dist_cm + noise))
        return self.ultrasonic_max_cm

    def _distance_to_moving_obstacle(
        self, ox: float, oy: float, theta: float, mx: float, my: float, radius: float
    ) -> float | None:
        """Distance along ray (ox,oy,theta) to circle (mx,my,radius), or None if no hit."""
        dx = math.cos(theta)
        dy = math.sin(theta)
        cx = ox - mx
        cy = oy - my
        a = dx * dx + dy * dy
        b = 2 * (cx * dx + cy * dy)
        c = cx * cx + cy * cy - radius * radius
        disc = b * b - 4 * a * c
        if disc < 0:
            return None
        sqrt_d = math.sqrt(disc)
        t1 = (-b - sqrt_d) / (2 * a)
        t2 = (-b + sqrt_d) / (2 * a)
        t = None
        if t1 >= 0:
            t = t1
        if t2 >= 0 and (t is None or t2 < t):
            t = t2
        return t if t is not None and t >= 0 else None

    def ultrasonic(
        self,
        x: float,
        y: float,
        theta: float,
        moving_obstacles: list | None = None,
    ) -> float:
        """Min of static raycast and distances to any moving obstacles along the ray."""
        static_dist_m = self._raycast_ultrasonic(x, y, theta) / 100.0
        min_dist_m = static_dist_m
        if moving_obstacles:
            for obs in moving_obstacles:
                d = self._distance_to_moving_obstacle(
                    x, y, theta, obs.x, obs.y, getattr(obs, "radius", 0.35)
                )
                if d is not None and 0 < d < min_dist_m:
                    min_dist_m = d
        return min_dist_m * 100.0

    def _radiator_gradient(self, x: float, y: float, room_id: str | None) -> float:
        """Single floor: warmer toward south (terrace/windows), cooler at north."""
        if not room_id or room_id != "floor_8":
            return 0.0
        row, col = self.floorplan.world_to_cell(x, y)
        rows = self.floorplan.rows
        return 0.5 * (1.0 - row / max(1, rows)) + 0.2 * math.sin(col * 0.2)

    def _subcell_variation(self, x: float, y: float) -> float:
        """Smooth spatial variation along hallway: cold spots near walls, slight run of pipe."""
        return (
            0.35 * math.sin(x * 0.8) * math.cos(y * 0.6)
            + 0.25 * math.sin(x * 1.8 + 0.5) * math.cos(y * 1.2)
            + 0.2 * (math.sin((x + y) * 1.2) + 0.2)
        )

    def _time_drift(self) -> float:
        """Very slow drift so heatmap feels slightly dynamic."""
        t = time.time() - self._t0
        return 0.15 * math.sin(t * 0.02) + 0.1 * math.sin(t * 0.07 + 1)

    def _temperature_at(self, x: float, y: float, room_id: str | None) -> float:
        """Single-point temperature (internal)."""
        if room_id and room_id in [r.id for r in ROOM_CONFIGS.values()]:
            room = next(r for r in ROOM_CONFIGS.values() if r.id == room_id)
            lo, hi = room.temp_range
            base = random.uniform(lo, hi)
            base += self._radiator_gradient(x, y, room_id)
            base += self._subcell_variation(x, y)
            base += self._time_drift()
            if room_id == "floor_8":
                t = time.time() - self._t0
                if 20 < (t % 200) < 70:
                    base += random.uniform(0.3, 1.2)
        else:
            base = random.uniform(17.2, 18.8)
            base += self._subcell_variation(x, y)
            base += self._time_drift()
        return base + random.gauss(0, self._temp_noise)

    def temperature(self, x: float, y: float, room_id: str | None) -> float:
        """Realistic sensor: weighted average over current + adjacent 1m + next ring (simulates FOV)."""
        offsets = [
            (0, 0, 1.0),
            (-0.5, 0, 0.6), (0.5, 0, 0.6), (0, -0.5, 0.6), (0, 0.5, 0.6),
            (-0.5, -0.5, 0.4), (-0.5, 0.5, 0.4), (0.5, -0.5, 0.4), (0.5, 0.5, 0.4),
            (-1, 0, 0.25), (1, 0, 0.25), (0, -1, 0.25), (0, 1, 0.25),
        ]
        total = 0.0
        weight = 0.0
        for dx, dy, w in offsets:
            px, py = x + dx, y + dy
            row, col = self.floorplan.world_to_cell(px, py)
            if not self.floorplan.is_traversable(row, col):
                continue
            rid = self.floorplan.get_room_id_at(px, py)
            total += self._temperature_at(px, py, rid) * w
            weight += w
        if weight < 1e-6:
            return self._temperature_at(x, y, room_id)
        return total / weight

    def humidity(self, x: float, y: float, room_id: str | None, temp: float) -> float:
        """UK indoor: 40–60% typical; higher when overheated and stuffy."""
        if room_id and room_id in [r.id for r in ROOM_CONFIGS.values()]:
            room = next(r for r in ROOM_CONFIGS.values() if r.id == room_id)
            lo, hi = room.humidity_range
            base = random.uniform(lo, hi)
        else:
            base = random.uniform(48.0, 55.0)
        if temp > 22:
            base = min(65, base + (temp - 22) * 1.5)
        return base + random.gauss(0, self._humidity_noise)
