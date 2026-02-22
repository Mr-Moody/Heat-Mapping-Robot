"""
Inverse Distance Weighting (IDW) interpolation for thermal mapping.
Fills gaps between sparse temperature samples for smooth heatmap display.
"""

import math
from typing import Sequence

import numpy as np


def idw_interpolate(
    samples: Sequence[tuple[float, float, float]],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    resolution_m: float = 0.1,
    power: float = 2.0,
    max_dist_m: float = 2.0,
) -> tuple[np.ndarray, float, float, float, float]:
    """
    Compute IDW interpolation over a 2D grid.

    Args:
        samples: List of (x_m, y_m, temp_c)
        x_min, x_max, y_min, y_max: Grid bounds in metres
        resolution_m: Cell size
        power: IDW exponent (default 2)
        max_dist_m: Max distance for weighting; cells farther get no influence

    Returns:
        (grid, x_min, x_max, y_min, y_max) where grid is (rows, cols) with NaN for no data
    """
    if not samples:
        cols = max(1, int((x_max - x_min) / resolution_m))
        rows = max(1, int((y_max - y_min) / resolution_m))
        return (np.full((rows, cols), float("nan")), x_min, x_max, y_min, y_max)

    cols = max(1, int((x_max - x_min) / resolution_m))
    rows = max(1, int((y_max - y_min) / resolution_m))
    grid = np.full((rows, cols), float("nan"), dtype=np.float32)

    xs = np.array([s[0] for s in samples])
    ys = np.array([s[1] for s in samples])
    ts = np.array([s[2] for s in samples])

    for i in range(rows):
        for j in range(cols):
            cx = x_min + (j + 0.5) * resolution_m
            cy = y_min + (i + 0.5) * resolution_m
            dx = xs - cx
            dy = ys - cy
            d = np.sqrt(dx * dx + dy * dy)
            d = np.maximum(d, 0.05)  # avoid division by zero
            mask = d <= max_dist_m
            if not np.any(mask):
                continue
            w = np.where(mask, 1.0 / (d ** power), 0.0)
            wsum = np.sum(w)
            if wsum > 0:
                grid[i, j] = float(np.sum(w * ts) / wsum)

    return (grid, x_min, x_max, y_min, y_max)


def idw_grid_for_frontend(
    thermal_history: Sequence[object],
    x_min: float = -5.0,
    x_max: float = 5.0,
    y_min: float = -5.0,
    y_max: float = 5.0,
    resolution_m: float = 0.2,
) -> tuple[list[list[float]], tuple[float, float, float, float]]:
    """
    Produce thermal grid for frontend from thermal_history (ThermalReading objects).
    Returns (grid as list of lists, bounds tuple).
    """
    samples = [
        (r.x_m, r.y_m, r.air_temp_c)
        for r in thermal_history
        if hasattr(r, "x_m") and hasattr(r, "y_m") and hasattr(r, "air_temp_c")
    ]
    grid, x_min, x_max, y_min, y_max = idw_interpolate(
        samples, x_min, x_max, y_min, y_max, resolution_m=resolution_m
    )
    # Convert NaN to sentinel -999 (no data); JSON doesn't support NaN
    NO_DATA = -999.0
    grid_list: list[list[float]] = []
    for row in grid:
        r = []
        for v in row:
            val = float(v)
            r.append(NO_DATA if (val != val or val == float("inf") or val == float("-inf")) else val)
        grid_list.append(r)
    return (grid_list, (x_min, x_max, y_min, y_max))
