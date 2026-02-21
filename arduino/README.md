# Heat Mapping Robot — Arduino

ESP32 sketch that sweeps an ultrasonic sensor and sends readings to the Python backend over WiFi.

## Requirements

- **Board:** ESP32 (WiFi built-in)
- **Libraries:** ArduinoJson (install via Library Manager)
- **Hardware:** HC-SR04 ultrasonic, continuous rotation servo

## Setup

1. Open `heat_mapping_robot/heat_mapping_robot.ino` in Arduino IDE
2. Install **ArduinoJson** (Sketch → Include Library → Manage Libraries)
3. Edit config in the sketch:
   - `WIFI_SSID` — your WiFi network name
   - `WIFI_PASSWORD` — your WiFi password
   - `BACKEND_URL` — Python backend URL (e.g. `http://192.168.1.100:8000`)
4. Set correct pins for your wiring:
   - `TRIG_PIN`, `ECHO_PIN` — HC-SR04
   - `SERVO_PIN` — servo signal
5. Upload to ESP32

## Wiring

- HC-SR04: VCC→5V, GND→GND, TRIG→GPIO5, ECHO→GPIO18
- Servo: Signal→GPIO13, VCC→5V, GND→GND

## Data Flow

The sketch continuously sweeps the servo, takes distance readings at each angle step, buffers them, and HTTP POSTs chunks to `POST /arduino/readings` when the buffer is full.
