"""
FastAPI backend: REST + WebSocket for ThermalScout.
Supports simulation mode (default) or Arduino mode (SIMULATE=1 or SERIAL_PORT set).
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time

# Ensure INFO logs are visible (uvicorn may set WARNING by default)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
from contextlib import asynccontextmanager
from queue import Queue

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from simulation.engine import SimulationEngine, ROBOT_IDS
from simulation.floorplan import get_room_name
from analytics import compute_room_analytics
from src.models import ArduinoReadingsPayload

logger = logging.getLogger(__name__)

# Shared robot constants: 3 simulated + 1 physical slot
DEFAULT_ROBOT_IDS = ["robot-1", "robot-2", "robot-3", "robot-4"]
PHYSICAL_ROBOT_ID = "robot-4"
DEFAULT_ROBOT_NAMES = {
    "robot-1": "Scout Alpha",
    "robot-2": "Scout Beta",
    "robot-3": "Scout Gamma",
    "robot-4": "Physical Robot",
}
ARDUINO_ACTIVE_TIMEOUT = 10.0  # seconds; physical robot active if Arduino data within this

# Simulation mode
engine: SimulationEngine | None = None
_sim_task: asyncio.Task | None = None

# Arduino mode
_arduino_sim_task: asyncio.Task | None = None
_arduino_serial_task: asyncio.Task | None = None
_arduino_serial_thread: threading.Thread | None = None
_arduino_serial_stop: threading.Event | None = None
ws_connections: list[WebSocket] = []

# Arduino mode: latest update for /ws/live bridge
_arduino_last_update: float | None = None
_latest_arduino_update: dict | None = None


def _use_arduino_mode() -> bool:
    """Use Arduino mode if SIMULATE=1, SERIAL_PORT is set, or Arduino auto-detected."""
    simulate = int(os.environ.get("SIMULATE", "0"))
    if simulate == 1:
        return True
    if os.environ.get("SERIAL_PORT"):
        return True
    try:
        from src.serial_reader import find_arduino_uno_port
        if find_arduino_uno_port():
            return True
    except Exception:
        pass
    return False


def _robot_state_from_connection(conn):
    from src.path_planning import RobotState

    rs = conn.robot_state
    return RobotState(
        x=rs.x,
        y=rs.y,
        heading_deg=rs.heading_deg,
        speed=rs.speed,
        action=rs.action,
        distance_travelled=getattr(rs, "distance_travelled", 0.0),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, _sim_task, _arduino_sim_task, _arduino_serial_task
    global _arduino_serial_thread, _arduino_serial_stop
    global _arduino_last_update, _latest_arduino_update

    # Always run simulation engine (robots 1, 2, 3)
    engine = SimulationEngine()
    _sim_task = asyncio.create_task(engine.run_loop())
    logger.info("Simulation engine started (3 robots)")

    running = True
    if _use_arduino_mode():
        from src.arduino_connection import get_connection
        from src.fake_sensors import generate_fake_payload
        from src.serial_reader import run_serial_reader, find_arduino_uno_port

        serial_port = os.environ.get("SERIAL_PORT") or find_arduino_uno_port()
        serial_baud = int(os.environ.get("SERIAL_BAUD", "115200"))
        running = True

        logger.info("Arduino mode: SERIAL_PORT=%s, SIMULATE=%s", serial_port or "(auto)", os.environ.get("SIMULATE", "0"))

        if int(os.environ.get("SIMULATE", "0")) == 1:
            async def _demo_loop():
                global _arduino_last_update, _latest_arduino_update
                conn = get_connection()
                ts = 0
                while running:
                    robot = _robot_state_from_connection(conn)
                    payload = generate_fake_payload(robot, timestamp_ms=ts, include_thermal=True)
                    update = conn.receive_readings(payload)
                    _latest_arduino_update = update.model_dump()
                    _arduino_last_update = time.time()
                    msg = json.dumps(_latest_arduino_update)
                    for ws in list(ws_connections):
                        try:
                            await ws.send_text(msg)
                        except Exception:
                            pass
                    ts += 500
                    await asyncio.sleep(0.5)

            _arduino_sim_task = asyncio.create_task(_demo_loop())
            logger.info("Arduino demo (SIMULATE=1) started")

        elif serial_port:
            update_queue: Queue = Queue()
            conn = get_connection()
            _arduino_serial_stop = threading.Event()
            _arduino_serial_thread = threading.Thread(
                target=run_serial_reader,
                args=(serial_port, serial_baud, conn, update_queue, _arduino_serial_stop),
                daemon=True,
            )
            _arduino_serial_thread.start()
            logger.info("Serial reader started on %s (sending commands to Arduino)", serial_port)

            async def _serial_broadcast_loop():
                global _arduino_last_update, _latest_arduino_update
                while running:
                    try:
                        msg = await asyncio.to_thread(update_queue.get)
                        try:
                            _latest_arduino_update = json.loads(msg)
                            _arduino_last_update = time.time()
                        except (json.JSONDecodeError, TypeError):
                            pass
                        for ws in list(ws_connections):
                            try:
                                await ws.send_text(msg)
                            except Exception:
                                pass
                    except asyncio.CancelledError:
                        break

            _arduino_serial_task = asyncio.create_task(_serial_broadcast_loop())
        else:
            logger.warning(
                "SERIAL_PORT not set and no Arduino found. "
                "Set SERIAL_PORT=COM3 (Windows) or SERIAL_PORT=/dev/ttyACM0 (Linux) and restart."
            )

    yield

    # Shutdown
    running = False
    if _arduino_sim_task is not None:
        _arduino_sim_task.cancel()
        try:
            await _arduino_sim_task
        except asyncio.CancelledError:
            pass
    if _arduino_serial_task is not None:
        _arduino_serial_task.cancel()
        try:
            await _arduino_serial_task
        except asyncio.CancelledError:
            pass
    if _arduino_serial_thread is not None and _arduino_serial_stop is not None:
        _arduino_serial_stop.set()
        _arduino_serial_thread.join(timeout=2.0)
    if engine:
        engine.stop()
    if _sim_task:
        _sim_task.cancel()
        try:
            await _sim_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="ThermalScout API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Hello from backend!"}


def _arduino_connected() -> bool:
    """True if physical Arduino has sent data within ARDUINO_ACTIVE_TIMEOUT."""
    if _arduino_last_update is None:
        return False
    return (time.time() - _arduino_last_update) < ARDUINO_ACTIVE_TIMEOUT


@app.get("/api/robots")
def get_robots():
    names = engine.get_robot_names()
    robots = []
    for rid in engine.get_robot_ids():
        state = engine.get_current_state(rid)
        active = _arduino_connected() if rid == PHYSICAL_ROBOT_ID else engine.is_robot_active(rid)
        last_seen = state.timestamp if state else None
        if rid == PHYSICAL_ROBOT_ID and _arduino_connected():
            last_seen = time.time()
        robots.append({
            "id": rid,
            "name": names.get(rid, rid),
            "active": active,
            "last_seen": last_seen,
        })
    robots.sort(key=lambda r: (0 if r["active"] else 1, -(r["last_seen"] or 0)))
    return {"robots": robots}


@app.get("/api/current")
def get_current(robot_id: str | None = None):
    if robot_id and robot_id not in engine.get_robot_ids():
        return {"error": f"Unknown robot_id: {robot_id}"}
    rid = robot_id
    if not rid:
        for r in engine.get_robot_ids():
            if r == PHYSICAL_ROBOT_ID and _arduino_connected():
                rid = r
                break
            if r != PHYSICAL_ROBOT_ID and engine.is_robot_active(r):
                rid = r
                break
        rid = rid or engine.get_robot_ids()[0]
    if rid == PHYSICAL_ROBOT_ID and _latest_arduino_update:
        u = _latest_arduino_update
        robot = u.get("robot") or {}
        # Physical robot is stationary; fix 3D position to arena center
        floor_x, floor_y = _arduino_to_floor_position(0, 0)
        return {
            "robot_id": rid,
            "position": {"x": floor_x, "y": floor_y, "theta": robot.get("heading_deg", 0) * 3.14159 / 180},
            "temperature_c": u.get("air_temp_c"),
            "humidity_percent": u.get("humidity_pct"),
            "room_id": "corridor",
            "room_name": "Corridor",
        }
    s = engine.get_current_state(rid)
    if s:
        d = s.to_dict()
        d["robot_id"] = rid
        d["room_name"] = get_room_name(d.get("room_id"))
        return d
    return {"message": "No data yet"}


@app.get("/api/rooms")
def get_rooms():
    grid = engine.get_grid()
    heatmap = engine.get_heatmap_data()
    rooms = compute_room_analytics(heatmap, grid, heatmap_subdiv=4)
    return {"rooms": rooms}


def _arduino_map_response(robot_id: str | None = None) -> dict:
    """Build /api/map response from Arduino connection when in Arduino mode."""
    from simulation.floorplan import DEFAULT_GRID, OBSTACLE_CELLS
    empty = {
        "grid": DEFAULT_GRID,
        "trail": [],
        "heatmap_cells": {},
        "heatmap_rows": 0,
        "heatmap_cols": 0,
        "occupancy_grid": None,
        "occupancy_bounds": None,
        "obstacle_points": [],
        "obstacle_cells": [[r, c] for r, c in OBSTACLE_CELLS],
        "point_cloud": [],
        "rows": len(DEFAULT_GRID),
        "cols": len(DEFAULT_GRID[0]) if DEFAULT_GRID else 0,
    }
    if robot_id != PHYSICAL_ROBOT_ID or not _latest_arduino_update:
        return empty
    u = _latest_arduino_update
    occ = u.get("occupancy_grid")
    bounds = u.get("occupancy_bounds") or (-5.0, 5.0, -5.0, 5.0)
    occ_bounds = list(bounds) if bounds else [-5.0, 5.0, -5.0, 5.0]
    heatmap_cells = u.get("heatmap_cells")
    if not isinstance(heatmap_cells, dict):
        thermal = u.get("thermal_grid")
        heatmap_cells = {}
        if isinstance(thermal, list):
            for r, row in enumerate(thermal):
                if isinstance(row, (list, tuple)):
                    for c, val in enumerate(row):
                        if isinstance(val, (int, float)):
                            heatmap_cells[f"{r},{c}"] = float(val)
    hr = len(occ) if isinstance(occ, list) and occ else 0
    hc = len(occ[0]) if isinstance(occ, list) and occ and occ[0] else 0
    obstacle_points = []
    if isinstance(occ, list) and occ and len(bounds) >= 4:
        x_min, x_max, y_min, y_max = bounds[0], bounds[1], bounds[2], bounds[3]
        res = (x_max - x_min) / hc if hc else 0.2
        for r, row in enumerate(occ):
            if not isinstance(row, (list, tuple)):
                continue
            for c, val in enumerate(row):
                if isinstance(val, (int, float)) and val > 0.7:
                    wx = x_min + (c + 0.5) * res
                    wy = y_min + (r + 0.5) * res
                    fx, fy = _arduino_to_floor_position(wx, wy)
                    obstacle_points.append([fx, 0.15, fy])
    raw_points = u.get("points") or []
    point_cloud = []
    for p in raw_points:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            fx, fy = _arduino_to_floor_position(float(p[0]), float(p[2]))
            point_cloud.append([fx, float(p[1]), fy])
    return {
        "grid": DEFAULT_GRID,
        "trail": [],
        "heatmap_cells": heatmap_cells or {},
        "rows": len(DEFAULT_GRID),
        "cols": len(DEFAULT_GRID[0]) if DEFAULT_GRID else 0,
        "heatmap_rows": hr,
        "heatmap_cols": hc,
        "occupancy_grid": occ,
        "occupancy_bounds": occ_bounds,
        "obstacle_points": obstacle_points,
        "obstacle_cells": [[r, c] for r, c in OBSTACLE_CELLS],
        "point_cloud": point_cloud,
    }


@app.get("/api/map")
def get_map(robot_id: str | None = None):
    if robot_id and robot_id not in engine.get_robot_ids():
        robot_id = engine.get_robot_ids()[0]
    rid = robot_id or engine.get_robot_ids()[0]
    if rid == PHYSICAL_ROBOT_ID and _latest_arduino_update:
        return _arduino_map_response(rid)
    hr, hc = engine.get_heatmap_shape()
    slam = engine._slams[rid]
    occ_bounds = slam.get_occupancy_bounds()
    return {
        "grid": engine.get_grid(),
        "trail": engine.get_trail(rid),
        "heatmap_cells": engine.get_heatmap_cells(),
        "rows": engine.floorplan.rows,
        "cols": engine.floorplan.cols,
        "heatmap_rows": hr,
        "heatmap_cols": hc,
        "occupancy_grid": slam.get_occupancy_grid(),
        "occupancy_bounds": list(occ_bounds),
        "obstacle_points": engine.get_obstacle_points(rid),
        "obstacle_cells": engine.get_obstacle_cells(),
        "point_cloud": engine.get_simulated_point_cloud(rid),
    }


@app.post("/arduino/readings")
async def arduino_readings(payload: ArduinoReadingsPayload):
    from src.arduino_connection import get_connection

    conn = get_connection()
    update = conn.receive_readings(payload)

    msg = update.model_dump_json()
    for ws in list(ws_connections):
        try:
            await ws.send_text(msg)
        except Exception:
            pass

    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_arduino(websocket: WebSocket):
    await websocket.accept()

    ws_connections.append(websocket)

    try:
        from src.arduino_connection import get_connection

        conn = get_connection()
        state = conn.get_current_state()
        await websocket.send_text(state.model_dump_json())

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        if websocket in ws_connections:
            ws_connections.remove(websocket)


def _arduino_to_floor_position(arduino_x: float, arduino_y: float) -> tuple[float, float]:
    """Map Arduino meter coords [-5,5] to floor grid coords [0,cols] x [0,rows].
    Center (0,0) in Arduino space maps to arena center (cols/2, rows/2)."""
    from simulation.floorplan import DEFAULT_GRID
    rows = len(DEFAULT_GRID)
    cols = len(DEFAULT_GRID[0]) if DEFAULT_GRID else 1
    floor_x = (arduino_x + 5.0) / 10.0 * cols
    floor_y = (arduino_y + 5.0) / 10.0 * rows
    return floor_x, floor_y


def _frontend_update_to_robot_update(update: dict) -> dict:
    """Map Arduino FrontendUpdate dict to robot_update schema for /ws/live."""
    robot = update.get("robot") or {}
    heading_deg = robot.get("heading_deg", 0)
    theta = heading_deg * 3.14159265359 / 180.0  # deg to rad
    heatmap_cells = update.get("heatmap_cells")
    if not isinstance(heatmap_cells, dict):
        heatmap_cells = {}
    thermal_grid = update.get("thermal_grid")
    if isinstance(thermal_grid, list) and thermal_grid and not heatmap_cells:
        for r, row in enumerate(thermal_grid):
            if isinstance(row, (list, tuple)):
                for c, val in enumerate(row):
                    if isinstance(val, (int, float)):
                        heatmap_cells[f"{r},{c}"] = float(val)
    occ = update.get("occupancy_grid")
    hr, hc = 0, 0
    if isinstance(occ, list) and occ:
        hr = len(occ)
        hc = len(occ[0]) if occ[0] else 0
    bounds = update.get("occupancy_bounds") or update.get("thermal_grid_bounds")
    x_min, x_max, y_min, y_max = -5.0, 5.0, -5.0, 5.0
    if bounds and len(bounds) >= 4:
        x_min, x_max, y_min, y_max = bounds[0], bounds[1], bounds[2], bounds[3]
    res = 0.2 if (hr and hc) else 0.2
    if hr and hc:
        res = (x_max - x_min) / hc if hc else 0.2
    raw_points = update.get("points") or []
    obstacle_points = []
    if isinstance(occ, list) and occ:
        for r, row in enumerate(occ):
            if not isinstance(row, (list, tuple)):
                continue
            for c, val in enumerate(row):
                if isinstance(val, (int, float)) and val > 0.7:
                    wx = x_min + (c + 0.5) * res
                    wy = y_min + (r + 0.5) * res
                    fx, fy = _arduino_to_floor_position(wx, wy)
                    obstacle_points.append([fx, 0.15, fy])
    # Transform point cloud from Arduino meter space to floor grid coords (relative to robot)
    point_cloud = []
    for p in raw_points:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            fx, fy = _arduino_to_floor_position(float(p[0]), float(p[2]))
            point_cloud.append([fx, float(p[1]), fy])
    trail: list[list[float]] = []
    # Physical robot is stationary; fix 3D position to arena center
    floor_x, floor_y = _arduino_to_floor_position(0, 0)
    return {
        "type": "robot_update",
        "robot_id": PHYSICAL_ROBOT_ID,
        "position": {"x": floor_x, "y": floor_y, "theta": theta},
        "ultrasonic_distance_cm": (update.get("sweep_cm") or [150])[0] if update.get("sweep_cm") else 150,
        "temperature_c": update.get("air_temp_c"),
        "humidity_percent": update.get("humidity_pct"),
        "room_id": "corridor",
        "room_name": "Corridor",
        "trail": trail,
        "obstacle_points": obstacle_points,
        "point_cloud": point_cloud,
        "heatmap_cells": heatmap_cells,
        "heatmap_rows": hr,
        "heatmap_cols": hc,
        "timestamp": time.time(),
    }


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            grid = engine.get_grid()
            heatmap = engine.get_heatmap_data()
            rooms = compute_room_analytics(heatmap, grid, heatmap_subdiv=4)
            await ws.send_json({"type": "analytics", "rooms": rooms})
            for rid in ROBOT_IDS:
                if rid == PHYSICAL_ROBOT_ID:
                    if _latest_arduino_update:
                        msg = _frontend_update_to_robot_update(_latest_arduino_update)
                        await ws.send_json(msg)
                    continue
                state = engine.get_current_state(rid)
                slam = engine._slams.get(rid)
                if state and slam:
                    d = state.to_dict()
                    d["room_name"] = get_room_name(d.get("room_id"))
                    msg = {
                        "type": "robot_update",
                        "robot_id": rid,
                        **d,
                        "trail": engine.get_trail(rid),
                        "obstacle_points": engine.get_obstacle_points(rid),
                        "point_cloud": engine.get_simulated_point_cloud(rid),
                        "heatmap_cells": engine.get_heatmap_cells(),
                        "heatmap_rows": engine.get_heatmap_shape()[0],
                        "heatmap_cols": engine.get_heatmap_shape()[1],
                    }
                    await ws.send_json(msg)
            await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn

    # Use 0.0.0.0 so Arduino host can reach the backend
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
