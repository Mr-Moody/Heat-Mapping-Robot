# Arduino ↔ Python Backend Serial Communication

## Confirmed flow

### Arduino → Backend (sensor data)

| Component | Location | Behavior |
|-----------|----------|----------|
| **Send** | `robot_physical.ino` `sendBackendPayload()` | Builds JSON with `StaticJsonDocument<384>`, up to 8 readings |
| **Format** | `Serial.println(body)` | One JSON line per payload: `{timestamp_ms, air_temp_c?, humidity_pct?, readings:[{angle, distance},...]}` |
| **Receive** | `serial_reader.py` `run_serial_reader()` | Reads chunks, splits on `\n`, strips `\r` |
| **Parse** | `json.loads(line)` | Parses line into dict |
| **Validate** | `ArduinoReadingsPayload(**data)` | Requires `readings`, `timestamp_ms`; optional `air_temp_c`, `humidity_pct` |
| **Process** | `connection.receive_readings(payload)` | SLAM, occupancy grid, path planning |
| **Broadcast** | `update_queue.put(update.model_dump_json())` | WebSocket clients receive `FrontendUpdate` |

### Backend → Arduino (motor commands)

| Component | Location | Behavior |
|-----------|----------|----------|
| **Decide** | `arduino_connection.py` `_action_to_motor_cmd()` | Maps planner action to F/B/L/R/S |
| **Send** | `serial_reader.py` after parse | `ser.write(cmd.encode() + b"\n")` |
| **Receive** | `robot_physical.ino` `readBackendCommand()` | Blocks up to 3s, reads single char F/B/L/R/S |
| **Execute** | `applyMotorCmd(cmd)` | Calls `moveForward()`, `turnLeft()`, etc. |

### Timing

- Arduino sends one JSON line per sweep completion (~9 s per sweep).
- Backend parses, processes, sends one command per JSON.
- Arduino waits for command after `Serial.flush()` before next sweep.

### Baud rate

- Both sides: **115200** (Arduino `Serial.begin(115200)`, backend `serial.Serial(port, 115200)`).
