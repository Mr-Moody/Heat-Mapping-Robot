"""
Probabilistic occupancy grid for single-point "Lidar" mapping.
Uses Bresenham's line algorithm and Bayesian log-odds update.
"""

import math
from typing import Iterator

import numpy as np


def _log_odds(p: float) -> float:
    """Convert probability to log-odds: L = log(p / (1-p))."""
    p = max(1e-6, min(1 - 1e-6, p))
    return math.log(p / (1 - p))


def _prob_from_log_odds(L: float) -> float:
    """Convert log-odds back to probability."""
    return 1.0 / (1.0 + math.exp(-L))


def bresenham_line(
    x0: int, y0: int, x1: int, y1: int,
) -> Iterator[tuple[int, int]]:
    """
    Bresenham's line algorithm. Yields (x, y) cell indices along the ray.
    Excludes the endpoint (hit cell) - caller adds it separately for hit update.
    """
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    x, y = x0, y0
    while True:
        if x == x1 and y == y1:
            break
        yield (x, y)
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


class OccupancyGrid:
    """
    Probabilistic 2D occupancy grid. Each cell in [0, 1]: 0=empty, 0.5=unknown, 1=occupied.
    Uses log-odds internally for Bayesian updates.
    """

    def __init__(
        self,
        width_m: float = 10.0,
        height_m: float = 10.0,
        resolution_m: float = 0.05,
        p_hit: float = 0.7,
        p_miss: float = 0.4,
        p_prior: float = 0.5,
    ):
        self.resolution = resolution_m
        self.width_m = width_m
        self.height_m = height_m
        self.cols = int(width_m / resolution_m)
        self.rows = int(height_m / resolution_m)
        self.x_min = -width_m / 2
        self.y_min = -height_m / 2
        self.p_hit = p_hit
        self.p_miss = p_miss
        L_prior = _log_odds(p_prior)
        L_hit = _log_odds(p_hit)
        L_miss = _log_odds(p_miss)
        self._L_hit = L_hit
        self._L_miss = L_miss
        self.grid = np.full((self.rows, self.cols), L_prior, dtype=np.float32)

    def _world_to_cell(self, x_m: float, y_m: float) -> tuple[int, int] | None:
        """Convert world coords (metres) to grid cell. Returns None if out of bounds."""
        cx = int((x_m - self.x_min) / self.resolution)
        cy = int((y_m - self.y_min) / self.resolution)
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            return (cx, cy)
        return None

    def update_ray(self, robot_x: float, robot_y: float, hit_x: float, hit_y: float) -> None:
        """
        Update grid for one ultrasonic ray: cells along path get p_miss (empty),
        hit cell gets p_hit (occupied).
        """
        c0 = self._world_to_cell(robot_x, robot_y)
        c1 = self._world_to_cell(hit_x, hit_y)
        if c0 is None and c1 is None:
            return
        if c0 is None:
            c0 = c1
        if c1 is None:
            c1 = c0

        x0, y0 = c0
        x1, y1 = c1

        for (cx, cy) in bresenham_line(x0, y0, x1, y1):
            if 0 <= cx < self.cols and 0 <= cy < self.rows:
                self.grid[cy, cx] += self._L_miss
                self.grid[cy, cx] = max(-10.0, min(10.0, self.grid[cy, cx]))

        if 0 <= x1 < self.cols and 0 <= y1 < self.rows:
            self.grid[y1, x1] += self._L_hit
            self.grid[y1, x1] = max(-10.0, min(10.0, self.grid[y1, x1]))

    def get_grid_prob(self) -> np.ndarray:
        """Return grid as probabilities [0, 1]. Shape (rows, cols)."""
        return np.vectorize(_prob_from_log_odds)(self.grid)

    def get_grid_for_frontend(self) -> list[list[float]]:
        """Return grid as nested list of probabilities for JSON serialization."""
        p = self.get_grid_prob()
        return p.tolist()

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Return (x_min, x_max, y_min, y_max) in metres."""
        x_max = self.x_min + self.width_m
        y_max = self.y_min + self.height_m
        return (self.x_min, x_max, self.y_min, y_max)

    def is_cell_free(self, cx: int, cy: int, free_threshold: float = 0.4) -> bool:
        """True if cell is likely free (occupancy < threshold)."""
        if not (0 <= cx < self.cols and 0 <= cy < self.rows):
            return False
        p = _prob_from_log_odds(float(self.grid[cy, cx]))
        return p < free_threshold

    def is_cell_occupied(self, cx: int, cy: int, occupied_threshold: float = 0.6) -> bool:
        """True if cell is likely occupied."""
        if not (0 <= cx < self.cols and 0 <= cy < self.rows):
            return True
        p = _prob_from_log_odds(float(self.grid[cy, cx]))
        return p > occupied_threshold

    def get_best_direction(
        self, robot_x: float, robot_y: float, heading_deg: float, look_ahead_cells: int = 3
    ) -> tuple[str, float]:
        """
        Return (command, turn_deg) for occupancy-based navigation.
        Prefer forward if clear, else turn toward most open direction.
        """
        c = self._world_to_cell(robot_x, robot_y)
        if c is None:
            return ("F", 0.0)
        cx, cy = c

        def cells_ahead(angle_offset_deg: float, n: int) -> list[tuple[int, int]]:
            a = np.radians(heading_deg + angle_offset_deg)
            cells = []
            for step in range(1, n + 1):
                dx = step * self.resolution * np.sin(a)
                dy = step * self.resolution * np.cos(a)
                wx = robot_x + dx
                wy = robot_y + dy
                cc = self._world_to_cell(wx, wy)
                if cc:
                    cells.append(cc)
            return cells

        def path_clear(angle_offset: float) -> bool:
            for (px, py) in cells_ahead(angle_offset, look_ahead_cells):
                if self.is_cell_occupied(px, py):
                    return False
            return True

        if path_clear(0):
            return ("F", 0.0)
        for angle in [45, -45, 90, -90, 135, -135]:
            if path_clear(angle):
                return ("L" if angle < 0 else "R", angle)
        return ("S", 0.0)
