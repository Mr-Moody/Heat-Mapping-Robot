#!/usr/bin/env python3
"""
Run backend in Arduino mode. Auto-detects port if SERIAL_PORT not set.
Usage: uv run python run_arduino.py [COM3]
       or set SERIAL_PORT=COM3 in env
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Set SERIAL_PORT from argv if provided
if len(sys.argv) > 1:
    os.environ["SERIAL_PORT"] = sys.argv[1]
    print(f"Using SERIAL_PORT={sys.argv[1]}")
elif not os.environ.get("SERIAL_PORT"):
    try:
        from src.serial_reader import find_arduino_uno_port
        port = find_arduino_uno_port()
        if port:
            os.environ["SERIAL_PORT"] = port
            print(f"Auto-detected Arduino on {port}")
        else:
            print("No Arduino found. Set SERIAL_PORT=COM3 (Windows) or pass as arg: python run_arduino.py COM3")
    except Exception as e:
        print(f"Could not auto-detect: {e}")

import uvicorn
uvicorn.run("main:app", host="0.0.0.0", port=8000)
