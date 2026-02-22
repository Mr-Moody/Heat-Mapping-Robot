"""
Real-time SLAM: occupancy grid built from sensor rays. Exploration + avoidance;
optimized ray checks for smooth loop performance.
"""
import math

FREE, OCCUPIED, UNKNOWN = 0.0, 1.0, 0.5


class OccupancyGrid:
    """
    Occupancy grid at fine resolution. Bounding box only; interior updated from rays.
    Supports obstacle check and exploration (prefer unknown direction).
    """

    def __init__(self, rows: int, cols: int, cell_size: float = 1.0, subdiv: int = 4):
        self.rows = rows * subdiv
        self.cols = cols * subdiv
        self.cell_size = cell_size
        self.subdiv = subdiv
        self.resolution = cell_size / subdiv
        self._grid = [[UNKNOWN] * self.cols for _ in range(self.rows)]
        self._bounds_rows = rows
        self._bounds_cols = cols

    def _world_to_grid(self, x: float, y: float) -> tuple[int, int]:
        gcol = int(x * self.subdiv / self.cell_size)
        grow = int(y * self.subdiv / self.cell_size)
        return grow, gcol

    def _in_bounds(self, gr: int, gc: int) -> bool:
        return 0 <= gr < self.rows and 0 <= gc < self.cols

    def _set(self, gr: int, gc: int, value: float) -> None:
        if self._in_bounds(gr, gc):
            self._grid[gr][gc] = value

    def _get(self, gr: int, gc: int) -> float:
        if self._in_bounds(gr, gc):
            return self._grid[gr][gc]
        return OCCUPIED

    def update_ray(self, ox: float, oy: float, theta: float, range_m: float) -> None:
        grow0, gcol0 = self._world_to_grid(ox, oy)
        end_x = ox + math.cos(theta) * range_m
        end_y = oy + math.sin(theta) * range_m
        grow1, gcol1 = self._world_to_grid(end_x, end_y)
        cells = self._bresenham(grow0, gcol0, grow1, gcol1)
        for i, (gr, gc) in enumerate(cells):
            if not self._in_bounds(gr, gc):
                continue
            if i < len(cells) - 1:
                self._set(gr, gc, FREE)
            else:
                self._set(gr, gc, OCCUPIED)

    def _bresenham(self, r0: int, c0: int, r1: int, c1: int) -> list[tuple[int, int]]:
        out = []
        dr = abs(r1 - r0)
        dc = abs(c1 - c0)
        sr = 1 if r0 < r1 else -1
        sc = 1 if c0 < c1 else -1
        err = dr - dc
        r, c = r0, c0
        for _ in range(dr + dc + 1):
            out.append((r, c))
            if r == r1 and c == c1:
                break
            e2 = 2 * err
            if e2 > -dc:
                err -= dc
                r += sr
            if e2 < dr:
                err += dr
                c += sc
        return out

    def _ray_walk_occupied(self, wx: float, wy: float, theta: float, max_dist_m: float) -> bool:
        """Early-exit: True if any occupied cell along ray within max_dist_m."""
        step_m = self.resolution * 0.8
        x, y = wx, wy
        dist = 0.0
        while dist < max_dist_m:
            gr, gc = self._world_to_grid(x, y)
            if self._get(gr, gc) >= 0.9:
                return True
            x += math.cos(theta) * step_m
            y += math.sin(theta) * step_m
            dist += step_m
        return False

    def _ray_count_unknown(self, wx: float, wy: float, theta: float, max_dist_m: float) -> int:
        """Count unknown cells along ray (for exploration)."""
        step_m = self.resolution * 1.2
        x, y = wx, wy
        dist = 0.0
        count = 0
        while dist < max_dist_m:
            gr, gc = self._world_to_grid(x, y)
            if not self._in_bounds(gr, gc):
                break
            if self._grid[gr][gc] == UNKNOWN:
                count += 1
            elif self._grid[gr][gc] >= 0.9:
                break
            x += math.cos(theta) * step_m
            y += math.sin(theta) * step_m
            dist += step_m
        return count

    def is_obstacle_ahead(
        self, wx: float, wy: float, theta: float, distance: float, cone_half_rad: float = 0.3
    ) -> bool:
        """True if occupied cell within distance in a narrow cone. Uses 3 rays, early-exit."""
        for i in (-1, 0, 1):
            t = theta + i * cone_half_rad
            if self._ray_walk_occupied(wx, wy, t, distance):
                return True
        return False

    def get_clear_steer(self, wx: float, wy: float, theta: float, look_dist: float = 0.55) -> float:
        """Prefer left or right that is clear. Two rays only."""
        left_clear = not self._ray_walk_occupied(wx, wy, theta + 0.45, look_dist)
        right_clear = not self._ray_walk_occupied(wx, wy, theta - 0.45, look_dist)
        if left_clear and not right_clear:
            return 0.75
        if right_clear and not left_clear:
            return -0.75
        if left_clear and right_clear:
            return 0.0
        return -0.5 if not left_clear else 0.5

    def get_exploration_steer(
        self, wx: float, wy: float, theta: float, look_dist: float = 0.8
    ) -> float:
        """
        Prefer turning toward direction with most unknown cells (explore while SLAM).
        Returns steer: positive = right, negative = left.
        """
        best_steer = 0.0
        best_count = -1
        for i, rel in enumerate([-0.7, -0.35, 0.0, 0.35, 0.7]):
            t = theta + rel
            n = self._ray_count_unknown(wx, wy, t, look_dist)
            if n > best_count:
                best_count = n
                best_steer = 0.6 if rel > 0 else (-0.6 if rel < 0 else 0.0)
        return best_steer

    def get_occupancy_for_viz(self) -> dict[str, float]:
        out = {}
        for r in range(self.rows):
            for c in range(self.cols):
                v = self._grid[r][c]
                if v != UNKNOWN:
                    out[f"{r},{c}"] = v
        return out
