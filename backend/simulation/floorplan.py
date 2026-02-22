"""
2D floorplan: single space (floor 8). Layout from public venue/floor guides.
"""
from dataclasses import dataclass
from enum import IntEnum


class CellType(IntEnum):
    WALL = 0
    FLOOR = 1  # Single space: whole floor


@dataclass
class Room:
    """Space metadata for temperature and humidity simulation."""
    id: str
    name: str
    cell_type: CellType
    base_temp: float
    temp_range: tuple[float, float]
    base_humidity: float
    humidity_range: tuple[float, float]
    volume_m3: float


# Floor 8: one open space (North + South combined). Grid [row][col], origin top-left.
# Single contiguous area with central corridor strip; walls around.
DEFAULT_GRID = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]

# Single space: one analytics entry for the whole floor.
SPACES = [
    {"id": "floor_8", "name": "Floor 8", "cell_types": [CellType.FLOOR]},
]

ROOM_CONFIGS = {
    CellType.FLOOR: Room(
        id="floor_8",
        name="Floor 8",
        cell_type=CellType.FLOOR,
        base_temp=20.0,
        temp_range=(18.0, 22.5),
        base_humidity=48.0,
        humidity_range=(42, 56),
        volume_m3=280,
    ),
}

OBSTACLE_CELLS = frozenset({
    (3, 8), (4, 14), (5, 20), (6, 10), (6, 18),
})


class Floorplan:
    """Manages the 2D grid and space metadata."""

    def __init__(self, grid: list[list[int]] = None):
        self.grid = grid or DEFAULT_GRID
        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.grid else 0
        self.cell_size = 1.0

    def get_cell(self, row: int, col: int) -> int:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.grid[row][col]
        return 0

    def is_traversable(self, row: int, col: int) -> bool:
        return self.get_cell(row, col) != 0

    def get_room_at(self, row: int, col: int) -> Room | None:
        ct = self.get_cell(row, col)
        return ROOM_CONFIGS.get(ct)

    def world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        col = int(x / self.cell_size)
        row = int(y / self.cell_size)
        return row, col

    def cell_to_world(self, row: int, col: int) -> tuple[float, float]:
        x = (col + 0.5) * self.cell_size
        y = (row + 0.5) * self.cell_size
        return x, y

    def get_room_id_at(self, x: float, y: float) -> str | None:
        row, col = self.world_to_cell(x, y)
        room = self.get_room_at(row, col)
        return room.id if room else None

    def is_obstacle(self, row: int, col: int) -> bool:
        return (row, col) in OBSTACLE_CELLS

    def world_to_fine_cell(self, x: float, y: float, subdiv: int = 2) -> tuple[int, int]:
        col = int(x * subdiv / self.cell_size)
        row = int(y * subdiv / self.cell_size)
        return row, col

    def fine_cell_traversable(self, fine_row: int, fine_col: int, subdiv: int = 2) -> bool:
        r = fine_row // subdiv
        c = fine_col // subdiv
        return self.is_traversable(r, c)
