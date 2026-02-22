"""
FastAPI backend: REST + WebSocket for ThermalScout.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from simulation.engine import SimulationEngine, RobotState, ROBOT_IDS
from analytics import compute_room_analytics

engine: SimulationEngine | None = None
_sim_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, _sim_task
    engine = SimulationEngine()
    _sim_task = asyncio.create_task(engine.run_loop())
    yield
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


@app.get("/api/robots")
def get_robots():
    """List all robots, sorted: active first, then inactive."""
    if not engine:
        return {"robots": []}
    names = engine.get_robot_names()
    robots = []
    for rid in engine.get_robot_ids():
        state = engine.get_current_state(rid)
        active = engine.is_robot_active(rid)
        last_seen = state.timestamp if state else None
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
    """Latest robot state. Optional robot_id query; defaults to first active robot."""
    if not engine:
        return {"error": "Engine not ready"}
    if robot_id and robot_id not in engine.get_robot_ids():
        return {"error": f"Unknown robot_id: {robot_id}"}
    rid = robot_id
    if not rid:
        for r in engine.get_robot_ids():
            if engine.is_robot_active(r):
                rid = r
                break
        rid = rid or engine.get_robot_ids()[0]
    s = engine.get_current_state(rid)
    if s:
        d = s.to_dict()
        d["robot_id"] = rid
        return d
    return {"message": "No data yet"}


@app.get("/api/rooms")
def get_rooms():
    """Room analytics with sustainability metrics."""
    if not engine:
        return {"rooms": []}
    grid = engine.get_grid()
    heatmap = engine.get_heatmap_data()
    rooms = compute_room_analytics(heatmap, grid, heatmap_subdiv=4)
    return {"rooms": rooms}


@app.get("/api/map")
def get_map(robot_id: str | None = None):
    """Floorplan grid, trail, heatmap, and SLAM occupancy for robot_id."""
    if not engine:
        return {
            "grid": [], "trail": [], "heatmap_cells": {}, "heatmap_rows": 0, "heatmap_cols": 0,
            "occupancy_grid": None, "occupancy_bounds": None, "obstacle_points": [],
            "point_cloud": [], "rows": 0, "cols": 0,
        }
    if robot_id and robot_id not in engine.get_robot_ids():
        robot_id = engine.get_robot_ids()[0]
    rid = robot_id or engine.get_robot_ids()[0]
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
        "point_cloud": engine.get_simulated_point_cloud(rid),
    }


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            if not engine:
                await asyncio.sleep(0.1)
                continue
            grid = engine.get_grid()
            heatmap = engine.get_heatmap_data()
            rooms = compute_room_analytics(heatmap, grid, heatmap_subdiv=4)
            await ws.send_json({"type": "analytics", "rooms": rooms})

            for rid in ROBOT_IDS:
                state = engine.get_current_state(rid)
                slam = engine._slams[rid]
                if state:
                    msg = {
                        "type": "robot_update",
                        "robot_id": rid,
                        **state.to_dict(),
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

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
