"""
ThermalScout — Analytics
───────────────────────────────────────────────────────────────────────────────
Sustainability and thermal analytics for the heat mapping robot.

Metrics:
  • Wasted power: °C above setpoint × room volume → watts (heating waste)
  • Hot zones: count of readings above overheat threshold
  • Temperature stats: max, avg across mapped area
"""

from dataclasses import dataclass

SETPOINT_C = 19.0
OVERHEAT_THRESHOLD_C = 22.0
ROOM_VOLUME_M3 = 100.0  # Assumed room volume for wasted power estimate
# ~0.6 W per °C per m³ overtemperature (rough heuristic)
WATT_PER_DEGREE_PER_M3 = 0.6


@dataclass
class ThermalReading:
    """Single thermal reading at a position."""
    x_m: float
    y_m: float
    surface_temp_c: float
    air_temp_c: float
    room_id: int


def wasted_power_w(air_temp_c: float, volume_m3: float = ROOM_VOLUME_M3) -> float:
    """
    Sustainability: wasted heating power (Watts).
    A 3°C overtemperature in 100m³ wastes ~60W continuously.
    """
    over = max(0.0, air_temp_c - SETPOINT_C)
    return over * volume_m3 * WATT_PER_DEGREE_PER_M3


def compute_analytics(thermal_history: list[ThermalReading]) -> dict:
    """
    Compute analytics from accumulated thermal readings.
    Returns dict suitable for FrontendUpdate.analytics.
    """
    if not thermal_history:
        return {
            "wasted_power_w": 0.0,
            "hot_zone_count": 0,
            "max_temp_c": 0.0,
            "avg_temp_c": 0.0,
            "setpoint_c": SETPOINT_C,
            "overheat_threshold_c": OVERHEAT_THRESHOLD_C,
        }

    temps = [r.air_temp_c for r in thermal_history]
    hot_count = sum(1 for t in temps if t > OVERHEAT_THRESHOLD_C)
    avg_temp = sum(temps) / len(temps)
    max_temp = max(temps)

    # Wasted power: use max overtemperature in room as proxy for worst zone
    worst_over = max(0.0, max_temp - SETPOINT_C)
    wasted = wasted_power_w(SETPOINT_C + worst_over, ROOM_VOLUME_M3)

    return {
        "wasted_power_w": round(wasted, 1),
        "hot_zone_count": hot_count,
        "max_temp_c": round(max_temp, 1),
        "avg_temp_c": round(avg_temp, 1),
        "setpoint_c": SETPOINT_C,
        "overheat_threshold_c": OVERHEAT_THRESHOLD_C,
    }


def thermal_to_frontend_points(
    thermal_history: list[ThermalReading],
    max_points: int = 500,
) -> list[dict]:
    """Convert thermal history to list of dicts for heat map display."""
    recent = thermal_history[-max_points:] if len(thermal_history) > max_points else thermal_history
    return [
        {
            "x_m": r.x_m,
            "y_m": r.y_m,
            "surface_temp_c": r.surface_temp_c,
            "air_temp_c": r.air_temp_c,
            "room_id": r.room_id,
            "is_overheated": r.air_temp_c > OVERHEAT_THRESHOLD_C,
        }
        for r in recent
    ]
