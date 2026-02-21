"""
ThermalScout — Fake Sensor Data Generator
───────────────────────────────────────────────────────────────────────────────
Simulates Arduino/ESP32 sensor output for demo mode (no hardware).

Generates:
  • Ultrasonic polar readings (angle, distance) — same format as Arduino POST
  • MLX90614 surface temp, DHT22 air temp/humidity — optional thermal extension

Pipeline: FakeSensorReader → polar readings + thermal → ArduinoReadingsPayload
"""

import time
import random
from .models import ArduinoReadingsPayload, ReadingPoint
from .path_planning import FakeSensorReader, RobotState

SWEEP_BINS = 12
BIN_ANGLE = 30.0  # degrees per bin


def generate_fake_payload(
    robot_state: RobotState,
    timestamp_ms: int | None = None,
    include_thermal: bool = True,
) -> ArduinoReadingsPayload:
    """
    Simulate one Arduino POST: polar ultrasonic readings + optional thermal.

    Uses FakeSensorReader to get sweep_cm and temp/humidity, then converts
    sweep to polar readings (angle, distance) to match Arduino format.
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    reader = FakeSensorReader()
    reading = reader.read(robot_state)

    # Convert sweep_cm to polar readings (inverse of binning)
    # Each bin i → angle = i * 30°, distance = sweep_cm[i] + noise
    readings = []
    for i in range(SWEEP_BINS):
        angle = i * BIN_ANGLE
        dist = reading.sweep_cm[i] + random.uniform(-1.5, 1.5)
        dist = max(2.0, min(400.0, dist))  # Clamp to sensor range
        readings.append(ReadingPoint(angle=angle, distance=round(dist, 1)))

    payload_dict = {"readings": readings, "timestamp_ms": timestamp_ms}

    if include_thermal:
        payload_dict["surface_temp_c"] = round(reading.temperature, 1)
        payload_dict["air_temp_c"] = round(reading.temperature + random.uniform(-0.5, 0.5), 1)
        payload_dict["humidity_pct"] = round(reading.humidity, 1)

    return ArduinoReadingsPayload(**payload_dict)
