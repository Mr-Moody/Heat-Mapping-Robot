import logging
import os
import asyncio
import threading
from contextlib import asynccontextmanager
from queue import Queue

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.models import ArduinoReadingsPayload
from src.arduino_connection import get_connection
from src.fake_sensors import generate_fake_payload
from src.path_planning import RobotState
from src.serial_reader import run_serial_reader, find_arduino_uno_port

logger = logging.getLogger(__name__)


def _robot_state_from_connection(conn) -> RobotState:
    rs = conn.robot_state
    return RobotState(
        x=rs.x, y=rs.y, heading_deg=rs.heading_deg,
        speed=rs.speed, action=rs.action,
        distance_travelled=getattr(rs, "distance_travelled", 0.0),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start demo simulator if SIMULATE=1, or USB serial reader (auto-detect or SERIAL_PORT)."""
    simulate = os.environ.get("SIMULATE", "0").lower() in ("1", "true", "yes")
    serial_port = os.environ.get("SERIAL_PORT")
    if not serial_port and not simulate:
        serial_port = find_arduino_uno_port()
    serial_baud = int(os.environ.get("SERIAL_BAUD", "115200"))

    running = True
    sim_task = None
    serial_task = None
    serial_stop = threading.Event()
    serial_thread = None

    if simulate:
        async def _demo_loop():
            conn = get_connection()
            ts = 0
            while running:
                robot = _robot_state_from_connection(conn)
                payload = generate_fake_payload(robot, timestamp_ms=ts, include_thermal=True)
                update = conn.receive_readings(payload)
                msg = update.model_dump_json()
                for ws in list(ws_connections):
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        pass
                ts += 500
                await asyncio.sleep(0.5)

        sim_task = asyncio.create_task(_demo_loop())

    elif serial_port:
        update_queue: Queue = Queue()
        conn = get_connection()
        serial_stop = threading.Event()
        serial_thread = threading.Thread(
            target=run_serial_reader,
            args=(serial_port, serial_baud, conn, update_queue, serial_stop),
            daemon=True,
        )
        serial_thread.start()
        logger.info("Serial reader started on %s", serial_port)

        async def _serial_broadcast_loop():
            while running:
                try:
                    msg = await asyncio.to_thread(update_queue.get)
                    for ws in list(ws_connections):
                        try:
                            await ws.send_text(msg)
                        except Exception:
                            pass
                except asyncio.CancelledError:
                    break

        serial_task = asyncio.create_task(_serial_broadcast_loop())

    yield

    running = False
    if sim_task is not None:
        sim_task.cancel()
        try:
            await sim_task
        except asyncio.CancelledError:
            pass
    if serial_task is not None:
        serial_task.cancel()
        try:
            await serial_task
        except asyncio.CancelledError:
            pass
    if serial_thread is not None:
        serial_stop.set()
        serial_thread.join(timeout=2.0)


app = FastAPI(lifespan=lifespan)

# CORS for frontend (Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
ws_connections: list[WebSocket] = []


@app.get("/")
def root():
    return {"message": "Hello from backend!"}


@app.post("/arduino/readings")
async def arduino_readings(payload: ArduinoReadingsPayload):
    """Receive sensor readings from Arduino, process, and broadcast to frontend."""
    conn = get_connection()
    update = conn.receive_readings(payload)

    # Broadcast to all connected WebSocket clients
    msg = update.model_dump_json()

    for ws in list(ws_connections):
        try:
            await ws.send_text(msg)
        except Exception:
            pass

    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    ws_connections.append(websocket)

    try:
        # Send current state to new client
        conn = get_connection()
        state = conn.get_current_state()

        await websocket.send_text(state.model_dump_json())

        # Keep connection open (client may disconnect)
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        if websocket in ws_connections:
            ws_connections.remove(websocket)


def main():
    import uvicorn
    # Use 0.0.0.0 so Arduino on same network can reach the backend
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
