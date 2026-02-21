# Heat Mapping Robot — Arduino

Sketch that sweeps an ultrasonic sensor and sends readings to the Python backend via **USB Serial** or **WiFi**.

## Requirements

- **Board:** Any (Arduino Uno, ESP32, etc.) — Serial mode works on all; WiFi needs ESP32
- **Libraries:** ArduinoJson (install via Library Manager)
- **Hardware:** HC-SR04 ultrasonic, continuous rotation servo

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

## Setup

1. Open `heat_mapping_robot/heat_mapping_robot.ino` in Arduino IDE
2. Install **ArduinoJson** (Sketch → Include Library → Manage Libraries)
3. Set `USE_SERIAL` (1 for USB, 0 for WiFi)
4. If WiFi: edit `WIFI_SSID`, `WIFI_PASSWORD`, `BACKEND_URL`
5. Set correct pins: `TRIG_PIN`, `ECHO_PIN`, `SERVO_PIN`
6. Upload

## Wiring

- HC-SR04: VCC→5V, GND→GND, TRIG→GPIO5, ECHO→GPIO18
- Servo: Signal→GPIO13, VCC→5V, GND→GND

## Data Flow

The sketch sweeps the servo, buffers distance readings, and sends JSON chunks (same format for Serial and WiFi) when the buffer is full.
