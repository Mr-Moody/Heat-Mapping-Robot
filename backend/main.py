"""
FastAPI backend: REST + WebSocket for ThermalScout.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from simulation.engine import SimulationEngine, RobotState
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


@app.get("/api/current")
def get_current():
    """Latest robot state."""
    if not engine:
        return {"error": "Engine not ready"}
    s = engine.get_current_state()
    if s:
        return s.to_dict()
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
def get_map():
    """Floorplan grid, trail, heatmap, and SLAM occupancy for visualization."""
    if not engine:
        return {
            "grid": [], "trail": [], "heatmap_cells": {}, "heatmap_rows": 0, "heatmap_cols": 0,
            "occupancy_grid": None, "occupancy_bounds": None, "obstacle_points": [],
            "point_cloud": [],
        }
    hr, hc = engine.get_heatmap_shape()
    slam = engine.slam
    occ_bounds = slam.get_occupancy_bounds()
    return {
        "grid": engine.get_grid(),
        "trail": engine.get_trail(),
        "heatmap_cells": engine.get_heatmap_cells(),
        "rows": engine.floorplan.rows,
        "cols": engine.floorplan.cols,
        "heatmap_rows": hr,
        "heatmap_cols": hc,
        "occupancy_grid": slam.get_occupancy_grid(),
        "occupancy_bounds": list(occ_bounds),
        "obstacle_points": slam.get_obstacle_points(),
        "point_cloud": engine.get_simulated_point_cloud(),
    }


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            if not engine:
                await asyncio.sleep(0.1)
                continue
            state = engine.get_current_state()
            if state:
                await ws.send_json(state.to_dict())
            grid = engine.get_grid()
            heatmap = engine.get_heatmap_data()
            rooms = compute_room_analytics(heatmap, grid, heatmap_subdiv=4)
            hr, hc = engine.get_heatmap_shape()
            slam = engine.slam
            await ws.send_json({
                "type": "analytics",
                "rooms": rooms,
                "trail": engine.get_trail(),
                "heatmap_cells": engine.get_heatmap_cells(),
                "heatmap_rows": hr,
                "heatmap_cols": hc,
                "occupancy_grid": slam.get_occupancy_grid(),
                "occupancy_bounds": list(slam.get_occupancy_bounds()),
                "obstacle_points": slam.get_obstacle_points(),
                "point_cloud": engine.get_simulated_point_cloud(),
            })
            await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
