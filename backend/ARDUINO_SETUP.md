# Arduino ↔ Backend Communication

## Quick start

1. **Upload** `arduino/robot_physical/robot_physical.ino` to your Arduino (BACKEND_MODE=1).
2. **Close** the Arduino IDE Serial Monitor (only one program can use the port).
3. **Run** the backend:
   ```bash
   cd backend
   uv run python run_arduino.py
   ```
   Or with a specific port: `uv run python run_arduino.py COM3`

## Test communication

```bash
cd backend
python scripts/serial_test.py COM3
```

- Lists COM ports
- Opens port, waits 5s for data
- Parses JSON and sends `F` back
- Verifies Arduino ↔ Python link

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| "No serial ports found" | Arduino not connected or drivers not installed |
| "Failed to open port" | Close Arduino Serial Monitor, close other programs using the port |
| "SERIAL_PORT not set and no Arduino found" | Set `SERIAL_PORT=COM3` (Windows) or `SERIAL_PORT=/dev/ttyACM0` (Linux) |
| Robot not moving | Backend must be running with Arduino mode. Check logs for `Serial reader started on COMx` |
