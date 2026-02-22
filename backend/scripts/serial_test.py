#!/usr/bin/env python3
"""
Serial diagnostic: list ports, test Arduino communication.
Run from backend/: python scripts/serial_test.py [COM3]
"""
import json
import sys
import time

def main():
    try:
        import serial
        import serial.tools.list_ports as list_ports
    except ImportError:
        print("Install pyserial: pip install pyserial")
        sys.exit(1)

    # List all COM ports
    print("=== COM ports ===")
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
    for p in ports:
        print(f"  {p.device}: {p.description} (VID={p.vid or '?'} PID={p.pid or '?'})")

    port = sys.argv[1] if len(sys.argv) > 1 else None
    if not port and ports:
        port = ports[0].device
        print(f"\nUsing first port: {port}")

    if not port:
        print("\nUsage: python scripts/serial_test.py COM3")
        sys.exit(1)

    print(f"\n=== Opening {port} @ 115200 ===")
    try:
        ser = serial.Serial(port, 115200, timeout=0.5)
        print("Opened OK. Waiting for data (5s)...")
    except Exception as e:
        print(f"Failed to open: {e}")
        print("Close Arduino Serial Monitor and any other program using the port.")
        sys.exit(1)

    buffer = ""
    start = time.monotonic()
    line_count = 0

    while time.monotonic() - start < 5:
        chunk = ser.read(ser.in_waiting or 100)
        if chunk:
            buffer += chunk.decode("utf-8", errors="ignore")

        while "\n" in buffer:
            line, _, buffer = buffer.partition("\n")
            line = line.strip().rstrip("\r")
            if not line:
                continue
            line_count += 1
            print(f"\n--- Line {line_count} ({len(line)} chars) ---")
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    print(f"JSON OK: timestamp_ms={data.get('timestamp_ms')}, readings={len(data.get('readings', []))}")
                    # Send command back
                    ser.write(b"F\n")
                    print("-> Sent: F")
                except json.JSONDecodeError as e:
                    print(f"JSON error: {e}")
            else:
                print(f" (not JSON): {line[:80]}...")

        time.sleep(0.05)

    ser.close()
    print(f"\nDone. Received {line_count} lines.")
    if line_count == 0:
        print("No data received. Check: Arduino running? Correct port? Baud 115200?")

if __name__ == "__main__":
    main()
