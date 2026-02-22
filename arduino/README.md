# Heat Mapping Robot — Arduino

Sketch that sweeps an ultrasonic sensor and sends readings to the Python backend via **USB Serial** or **WiFi**.

## Requirements

- **Board:** Any (Arduino Uno, ESP32, etc.) — Serial mode works on all; WiFi needs ESP32
- **Libraries:** ArduinoJson, DHT sensor library; Modulino (optional, for IMU when `USE_IMU=1`)
- **Hardware:** HC-SR04 ultrasonic, 180° micro servo, DHT11 temp/humidity; Modulino Movement (optional, I2C/Qwiic)

## Communication Modes

### USB Serial (default)

Works with any Arduino-compatible board. Connect via USB to the computer running the Python backend.

1. Set `#define USE_SERIAL 1` in the sketch
2. Upload to board
3. Run backend with serial port:
   - **Windows:** `$env:SERIAL_PORT="COM3"; python main.py`
   - **Linux/Mac:** `SERIAL_PORT=/dev/ttyUSB0 python main.py`
4. Baud rate: 115200 (override with `SERIAL_BAUD` if needed)

### WiFi (ESP32 only)

1. Set `#define USE_SERIAL 0` in the sketch
2. Edit `WIFI_SSID`, `WIFI_PASSWORD`, `BACKEND_URL`
3. Upload to ESP32
4. Arduino POSTs to `POST /arduino/readings`

## Distance Calibration (HC-SR04 ultrasonic)

To verify and calibrate distance sensing for accurate point clouds:

1. Open `distance_calibrate/distance_calibrate.ino`, upload, open Serial Monitor at 115200
2. Place a flat object at a **known distance** (e.g. 50 cm) in front of the sensor
3. Compare `adjusted_cm` with your ruler measurement
4. Adjust `MICROSEC_PER_CM` (default 58.2): increase if sensor reads too high, decrease if too low
5. Adjust `DISTANCE_OFFSET_CM` for additive correction (e.g. -1.5 if consistently 1.5 cm high)
6. Copy the values into `heat_mapping_robot.ino`

**Backend verification:** Run `python scripts/verify_distance.py` (with SERIAL_PORT set) to see raw angle/distance and the resulting Cartesian (x, y, z) points. Confirms the full pipeline from serial → point cloud.

## Servo Calibration (180° micro servo)

Before running the main sketch, calibrate `SERVO_AT_MIN` and `SERVO_AT_MAX`:

1. Open `servo_calibrate/servo_calibrate.ino` in Arduino IDE
2. Upload, open Serial Monitor at 115200
3. Use `a`/`d` to move the servo until the sensor points at your **left limit** (−90°), press `1` to save
4. Use `a`/`d` to move to your **right limit** (+90°), press `2` to save
5. Press `p` to print the values — copy them into `heat_mapping_robot.ino` as `SERVO_AT_MIN` and `SERVO_AT_MAX`

## Setup

1. Open `heat_mapping_robot/heat_mapping_robot.ino` in Arduino IDE
2. Install **ArduinoJson** (Sketch → Include Library → Manage Libraries)
3. Set `USE_SERIAL` (1 for USB, 0 for WiFi)
4. If WiFi: edit `WIFI_SSID`, `WIFI_PASSWORD`, `BACKEND_URL`
5. Set correct pins: `TRIG_PIN`, `ECHO_PIN`, `SERVO_PIN`, `DHT_PIN` (default 8)
6. Copy `SERVO_AT_MIN` and `SERVO_AT_MAX` from servo calibration
7. Copy `MICROSEC_PER_CM` and `DISTANCE_OFFSET_CM` from distance calibration (if tuned)
8. Upload

## Wiring

- HC-SR04: VCC→5V, GND→GND, TRIG→5, ECHO→7
- Servo: Signal→9, VCC→5V, GND→GND
- DHT11: Data→8, VCC→5V, GND→GND (4.7kΩ pull-up on data to VCC). Run `dht_test/dht_test.ino` first to verify.
- **Motors (USE_MOTORS=1):** L298N style — IN1→13, IN2→12 (Motor A), IN3→10, IN4→11 (Motor B). Same as `motor_test`.

## Navigation Modes

- **COMMAND_MODE=1 (default):** Backend drives navigation via probabilistic occupancy grid. Arduino receives F/B/L/R/S over serial and streams sensor data continuously. Ultrasonic used for mapping and obstacle avoidance; no valid-reading gate.
- **COMMAND_MODE=0:** Legacy move–stop–sweep: move 20 cm, stop 2 s, sweep 180°, send, repeat.

## Data Flow

The sketch sweeps the servo, buffers distance readings, and sends JSON chunks (same format for Serial and WiFi) when the buffer is full.
