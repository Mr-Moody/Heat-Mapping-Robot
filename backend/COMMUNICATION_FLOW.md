# Arduino ↔ Backend Communication Verification

## Flow Comparison: Old vs Current

### Backend (main.py)

| Step | Old main.py | Current main.py | ✓ |
|------|-------------|-----------------|---|
| Arduino mode check | `serial_port = SERIAL_PORT or find_arduino_uno_port()` | `_use_arduino_mode()` + `serial_port = SERIAL_PORT or find_arduino_uno_port()` | ✓ |
| Serial thread | `run_serial_reader(port, baud, conn, update_queue, stop)` | Same | ✓ |
| Broadcast loop | `update_queue.get` → `ws.send_text(msg)` | Same | ✓ |

### Serial Reader (serial_reader.py)

| Step | Function | Called |
|------|----------|--------|
| 1 | `ser.read()` | Receives raw bytes from Arduino |
| 2 | Split on `\n` | Extracts JSON lines |
| 3 | `json.loads(line)` | Parses JSON |
| 4 | `ArduinoReadingsPayload(**data)` | Validates payload |
| 5 | `connection.receive_readings(payload)` | Processes, updates state, returns FrontendUpdate |
| 6 | `connection.pop_pending_motor_cmd()` | Gets F/B/L/R/S |
| 7 | `ser.write(cmd + b"\n")` | Sends command to Arduino |

### Arduino → Backend (Send)

| Sketch | Send function | Format | When |
|--------|---------------|--------|------|
| heat_mapping_robot | `sendReadings(buffer, 8)` | `{timestamp_ms, readings:[{angle, distance}], air_temp_c?, humidity_pct?}` | Every 8 readings |
| robot_physical | `sendBackendPayload()` | Same | After full sweep (19 readings) |

Both use `Serial.println(body)` → one JSON object per line.

### Backend → Arduino (Receive)

| Sketch | Read location | Format expected |
|--------|---------------|-----------------|
| heat_mapping_robot | `loop()` top: `if (Serial.available()) { c = Serial.read(); ... }` | Single char: F, B, L, R, S |
| robot_physical | `readBackendCommand()` after send | Same (blocks up to 3s) |

Backend sends: `ser.write(cmd.encode() + b"\n")` → e.g. `"F\n"`

### Model Compatibility

`ArduinoReadingsPayload` requires:
- `readings`: list of `{angle, distance}` (or `dist`)
- `timestamp_ms`: int

Optional: `air_temp_c`, `humidity_pct`, `surface_temp_c`

Both sketches send compatible JSON.
