"""Pydantic models for API request/response and WebSocket payloads."""

from pydantic import BaseModel


class ReadingPoint(BaseModel):
    """Single polar reading from ultrasonic sensor."""
    angle: float   # degrees, 0 = forward
    distance: float  # cm


class ArduinoReadingsPayload(BaseModel):
    """Payload from Arduino HTTP POST."""
    readings: list[ReadingPoint]
    timestamp_ms: int


class RobotPose(BaseModel):
    """Robot position and heading for frontend."""
    x: float
    y: float
    heading_deg: float


class FrontendUpdate(BaseModel):
    """WebSocket broadcast to frontend clients."""
    points: list[list[float]]  # [[x, y, z], ...] in metres
    robot: RobotPose
    action: str
    sweep_cm: list[float]  # 12 distances for path planner compatibility
