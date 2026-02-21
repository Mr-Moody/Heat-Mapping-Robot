#!/usr/bin/env python3
"""
Verify distance sensing and point cloud conversion.

Reads raw JSON lines from Arduino serial and prints:
  - angle (deg), distance (cm)
  - converted Cartesian (x, y, z) in metres
  - distance range stats

Usage:
  python scripts/verify_distance.py
  (connects to auto-detected Arduino port, or set SERIAL_PORT)

  Or pipe JSON lines:
  type COM3 | python scripts/verify_distance.py   # Windows
  cat /dev/ttyUSB0 | python scripts/verify_distance.py  # Linux
"""
import json
import math
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.point_cloud import polar_to_cartesian


def process_line(line: str) -> None:
    try:
        data = json.loads(line.strip())
    except json.JSONDecodeError:
        return
    readings = data.get("readings", [])
    if not readings:
        return
    dists = []
    for r in readings:
        angle = r.get("angle", 0)
        dist = r.get("distance", 0)
        dists.append(dist)
        x, y, z = polar_to_cartesian(angle, dist, 0, 0, 0)
        print(f"  angle={angle:6.1f}  dist={dist:6.1f} cm  ->  x={x:6.3f} y={y:6.3f} z={z:6.3f} m")
    if dists:
        print(f"  range: {min(dists):.1f} - {max(dists):.1f} cm")


def main():
    port = os.environ.get("SERIAL_PORT")
    if port:
        import serial
        ser = serial.Serial(port, 115200)
        print(f"Reading from {port}. Ctrl+C to stop.\n")
        for line in ser:
            line = line.decode("utf-8", errors="ignore").strip()
            if line.startswith("{"):
                process_line(line)
    else:
        print("Reading JSON from stdin (pipe from serial, or set SERIAL_PORT)")
        for line in sys.stdin:
            if line.strip().startswith("{"):
                process_line(line)


if __name__ == "__main__":
    main()
