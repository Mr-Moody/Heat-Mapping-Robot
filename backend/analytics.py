"""
Analytics: one set of metrics per space. Only spaces present in the layout are included.
"""
from simulation.floorplan import ROOM_CONFIGS, SPACES, CellType

SETPOINT_C = 19.0  # Typical UK campus heating setpoint
HEAT_LOSS_FACTOR = 0.2  # W/m³°C


def _cell_types_in_grid(grid: list[list[int]]) -> set[int]:
    """Cell types that appear at least once in the grid."""
    present = set()
    for row in grid:
        for cell in row:
            if cell != 0:
                present.add(cell)
    return present


def compute_room_analytics(
    heatmap_data: dict[tuple[int, int], list[float]],
    grid: list[list[int]],
    room_configs: dict = None,
    heatmap_subdiv: int = 1,
    spaces: list[dict] = None,
) -> list[dict]:
    """
    One analytics entry per space that is present in the layout.
    Aggregates temperature only from cells belonging to that space.
    """
    room_configs = room_configs or ROOM_CONFIGS
    spaces = spaces or SPACES
    rows, cols = len(grid), len(grid[0]) if grid else 0
    present_cell_types = _cell_types_in_grid(grid)

    # Which spaces are present (have at least one cell type in the grid)
    space_cell_types = {s["id"]: set(s["cell_types"]) for s in spaces}
    present_space_ids = [
        s["id"] for s in spaces
        if present_cell_types & set(s["cell_types"])
    ]

    # Aggregate temps by cell type (coarse cell -> list of temps)
    cell_temps: dict[int, list[float]] = {}
    for (row, col), temps in heatmap_data.items():
        if not temps:
            continue
        r = row // heatmap_subdiv
        c = col // heatmap_subdiv
        if r >= rows or c >= cols:
            continue
        cell = grid[r][c]
        if cell == 0:
            continue
        if cell not in cell_temps:
            cell_temps[cell] = []
        cell_temps[cell].extend(temps)

    results = []
    for space in spaces:
        if space["id"] not in present_space_ids:
            continue
        ct_set = set(space["cell_types"])
        # All temps from cells that belong to this space
        temps = []
        for ct in ct_set:
            temps.extend(cell_temps.get(int(ct), []))
        first_ct = next((ct for ct in space["cell_types"] if ct in room_configs), None)
        if first_ct is None:
            continue
        room = room_configs[first_ct]
        if not room:
            continue
        if not temps:
            avg_temp = room.base_temp
            variance = 0.0
        else:
            avg_temp = sum(temps) / len(temps)
            variance = sum((t - avg_temp) ** 2 for t in temps) / len(temps)
        delta_t = avg_temp - SETPOINT_C
        wasted_power = max(0, delta_t * room.volume_m3 * HEAT_LOSS_FACTOR)
        sustainability_score = max(0, 100 - abs(delta_t) * 10 - variance * 2)
        overheating = delta_t > 2.0
        ventilation_risk = variance > 1.0
        results.append({
            "room_id": room.id,
            "room_name": room.name,
            "avg_temperature_c": round(avg_temp, 2),
            "delta_t_from_setpoint": round(delta_t, 2),
            "wasted_power_w": round(wasted_power, 1),
            "humidity_percent": room.base_humidity,
            "sustainability_score": round(min(100, sustainability_score), 1),
            "overheating": overheating,
            "energy_waste_risk": overheating,
            "ventilation_quality_flag": ventilation_risk,
        })
    return results
