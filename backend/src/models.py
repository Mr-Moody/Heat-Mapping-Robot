"""Pydantic models for API request/response and WebSocket payloads."""

from pydantic import BaseModel


class ReadingPoint(BaseModel):
    """Single polar reading from ultrasonic sensor."""
    angle: float   # degrees, 0 = forward
    distance: float  # cm


class ArduinoReadingsPayload(BaseModel):
    """Payload from Arduino HTTP POST. Thermal fields optional (from MLX90614 + DHT22)."""
    readings: list[ReadingPoint]
    timestamp_ms: int
    surface_temp_c: float | None = None  # MLX90614 IR surface temp
    air_temp_c: float | None = None      # DHT22 ambient
    humidity_pct: float | None = None    # DHT22


class RobotPose(BaseModel):
    """Robot position and heading for frontend."""
    x: float
    y: float
    heading_deg: float


class ThermalPoint(BaseModel):
    """Single point for heat map: position + temperature."""
    x_m: float
    y_m: float
    surface_temp_c: float
    air_temp_c: float
    room_id: int
    is_overheated: bool


class AnalyticsSummary(BaseModel):
    """Sustainability and thermal analytics."""
    wasted_power_w: float       # ~60W per 3°C over setpoint per 100m³
    hot_zone_count: int         # Count of readings above threshold
    max_temp_c: float
    avg_temp_c: float
    setpoint_c: float = 19.0
    overheat_threshold_c: float = 22.0


class FrontendUpdate(BaseModel):
    """WebSocket broadcast to frontend clients."""
    points: list[list[float]]  # [[x, y, z], ...] in metres
    robot: RobotPose
    action: str
    sweep_cm: list[float]  # 12 distances for path planner compatibility
    thermal_points: list[dict] | None = None   # For heat map: [{x_m, y_m, surface_temp_c, ...}]
    analytics: dict | None = None              # {wasted_power_w, hot_zone_count, ...}
