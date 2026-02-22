/*
 * Heat Mapping Robot — Arduino Sketch
 * Sends ultrasonic sweep readings to Python backend.
 *
 * USE_SERIAL=1: USB serial (Arduino Uno, any board with Serial)
 * USE_SERIAL=0: WiFi HTTP POST (ESP32)
 * USE_IMU=1: Include Modulino Movement (LSM6DSOXTR) gyro/accel via I2C
 * USE_MOTORS=1: Enable DC motor drive (L298N style, same as motor_test)
 *
 * Hardware:
 *   - HC-SR04 ultrasonic: TRIG_PIN, ECHO_PIN
 *   - 180° micro servo: SERVO_PIN (positional)
 *   - DHT11 temp/humidity: DHT_PIN (data)
 *   - Motors: in1/in2 (Motor A), in3/in4 (Motor B) — L298N style
 *   - Modulino Movement: I2C (Qwiic) for gyro_z, accel
 */

#define USE_SERIAL 1   // 1 = USB serial, 0 = WiFi
#define USE_IMU   0    // 1 = Modulino (UNO R4 only), 0 = skip (required for AVR/Arduino Uno)
#define USE_MOTORS 1   // 1 = DC motors (L298N), 0 = servo/sensors only
#define COMMAND_MODE 1 // 1 = backend sends F/B/L/R/S via serial, 0 = autonomous move-stop-sweep

#if !USE_SERIAL
#include <WiFi.h>
#include <HTTPClient.h>
#endif
#include <ArduinoJson.h>
#include <DHT.h>
#include <Servo.h>
#include <Wire.h>

#if USE_IMU
#include <Modulino.h>
ModulinoMovement imu;
#endif

// ── CONFIG ────────────────────────────────────────────────────────────────
#if !USE_SERIAL
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"
#define BACKEND_URL     "http://192.168.1.100:8000"  // Python backend IP
#endif
#define CHUNK_SIZE      8                            // Readings per HTTP POST
#define SWEEP_BATCH_SIZE 19                          // Full 180°: -90..+90 step 10°
#define SWEEP_STEP_DEG  10.0                         // Angle step per reading
#define SWEEP_MIN_DEG   -90.0                        // Left limit
#define SWEEP_MAX_DEG   90.0                         // Right limit, 0 = forwards
#define ANGLE_OFFSET    0.0                          // fine-tune reported angle
// Servo: 0°=right, 180°=left. Map our -90°(left) and +90°(right) accordingly.
#define SERVO_AT_MIN    180                          // servo 180 = our -90° (left)
#define SERVO_AT_MAX    0                            // servo 0 = our +90° (right)
#define TRIG_PIN        5
#define ECHO_PIN        7
#define SERVO_PIN      9
#define DHT_PIN         8
// Motor pins (same as motor_test — L298N dual H-bridge)
#define MOTOR_A_IN1     13
#define MOTOR_A_IN2     12
#define MOTOR_B_IN3     10
#define MOTOR_B_IN4     11
#define MOVE_DURATION_MS   2000   // Forward per segment (≈20 cm)
#define STOP_BEFORE_SWEEP_MS 2000 // DHT11 stabilization
#define MAX_DISTANCE_CM 400
#define MIN_DISTANCE_CM 2
// Distance calibration: run distance_calibrate.ino to tune. 58.2 = standard HC-SR04.
#define MICROSEC_PER_CM  58.2
#define DISTANCE_OFFSET_CM 1.7   // raw 28.3 @ 30cm true → add 1.7

// ── GLOBALS ────────────────────────────────────────────────────────────────
struct Reading {
  float angle;    // Servo angle at pulse time (servo-sync)
  float distance;
  float temp_c;   // air_temp at read time
  float gyro_z;   // yaw rate deg/s from IMU
};
#define SEND_CHUNK 8
Reading buffer[SEND_CHUNK];
int bufferIdx = 0;
float currentAngle = 0.0;
bool sweepDirection = true;  // true = CW
unsigned long startTimeMs = 0;
unsigned long lastDhtReadMs = 0;
float lastTempC = NAN;
float lastHumPct = NAN;
Servo sweepServo;
DHT dht(DHT_PIN, DHT11);
#define DHT_READ_INTERVAL_MS 2000

#if USE_MOTORS && !COMMAND_MODE
enum RobotState { STATE_MOVE, STATE_STOP, STATE_SWEEP };
RobotState robotState = STATE_MOVE;
unsigned long stateStartMs = 0;
#endif
char currentMotorCmd = 'F';  // F=forward, B=back, L=left, R=right, S=stop

// ── MOTORS ─────────────────────────────────────────────────────────────────
#if USE_MOTORS
void motorSetup() {
  pinMode(MOTOR_A_IN1, OUTPUT);
  pinMode(MOTOR_A_IN2, OUTPUT);
  pinMode(MOTOR_B_IN3, OUTPUT);
  pinMode(MOTOR_B_IN4, OUTPUT);
  stopMotors();
}

void moveForward() {
  digitalWrite(MOTOR_A_IN1, LOW);
  digitalWrite(MOTOR_A_IN2, HIGH);
  digitalWrite(MOTOR_B_IN3, LOW);
  digitalWrite(MOTOR_B_IN4, HIGH);
}

void moveBackward() {
  digitalWrite(MOTOR_A_IN1, HIGH);
  digitalWrite(MOTOR_A_IN2, LOW);
  digitalWrite(MOTOR_B_IN3, HIGH);
  digitalWrite(MOTOR_B_IN4, LOW);
}

void turnLeft() {
  digitalWrite(MOTOR_A_IN1, LOW);
  digitalWrite(MOTOR_A_IN2, HIGH);
  digitalWrite(MOTOR_B_IN3, HIGH);
  digitalWrite(MOTOR_B_IN4, LOW);
}

void turnRight() {
  digitalWrite(MOTOR_A_IN1, HIGH);
  digitalWrite(MOTOR_A_IN2, LOW);
  digitalWrite(MOTOR_B_IN3, LOW);
  digitalWrite(MOTOR_B_IN4, HIGH);
}

void stopMotors() {
  digitalWrite(MOTOR_A_IN1, LOW);
  digitalWrite(MOTOR_A_IN2, LOW);
  digitalWrite(MOTOR_B_IN3, LOW);
  digitalWrite(MOTOR_B_IN4, LOW);
}
#endif

// ── ULTRASONIC ────────────────────────────────────────────────────────────
#define ULTRASONIC_SAMPLES 5   // 3-5 samples for median filter
#define MAX_VALID_CM 3000.0    // Reject duration-equivalent outliers

float readDistanceCm()
{
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return 0.0;

  float cm = (float)duration / (float)MICROSEC_PER_CM + DISTANCE_OFFSET_CM;
  return cm;
}

// Insertion sort helper for median (no dynamic allocation)
static void sortFloat(float* arr, int n) {
  for (int i = 1; i < n; i++) {
    float v = arr[i];
    int j = i;
    while (j > 0 && arr[j - 1] > v) {
      arr[j] = arr[j - 1];
      j--;
    }
    arr[j] = v;
  }
}

float readDistanceCmMedian(int samples = ULTRASONIC_SAMPLES) {
  float buf[8];  // Max 8 samples without malloc
  if (samples > 8) samples = 8;
  if (samples < 3) samples = 3;

  int valid = 0;
  for (int i = 0; i < samples; i++) {
    float cm = readDistanceCm();
    if (cm >= MIN_DISTANCE_CM && cm <= MAX_DISTANCE_CM && cm > 0.0f && cm < MAX_VALID_CM) {
      buf[valid++] = cm;
    }
    delay(5);
  }
  if (valid == 0) return 0.0;
  sortFloat(buf, valid);
  return buf[valid / 2];
}

// ── SERVO ─────────────────────────────────────────────────────────────────
// Maps logical angle (-90..+90) to servo PWM (SERVO_AT_MIN..SERVO_AT_MAX)
int angleToServo(float deg) {
  return (int)(SERVO_AT_MIN + (deg - SWEEP_MIN_DEG) * (SERVO_AT_MAX - SERVO_AT_MIN) / (SWEEP_MAX_DEG - SWEEP_MIN_DEG));
}

void stepServo() {
  currentAngle += sweepDirection ? SWEEP_STEP_DEG : -SWEEP_STEP_DEG;

  if (currentAngle >= SWEEP_MAX_DEG) {
    currentAngle = SWEEP_MAX_DEG;
    sweepDirection = false;
  } else if (currentAngle <= SWEEP_MIN_DEG) {
    currentAngle = SWEEP_MIN_DEG;
    sweepDirection = true;
  }

  sweepServo.write(angleToServo(currentAngle));
}

// ── SEND READINGS (Serial or WiFi) ────────────────────────────────────────
bool sendReadings(Reading* readings, int count) {
  StaticJsonDocument<1024> doc;  // readings + thermal + IMU
  doc["timestamp_ms"] = (long)(millis() - startTimeMs);

  unsigned long now = millis();
  if (now - lastDhtReadMs >= DHT_READ_INTERVAL_MS) {
    lastDhtReadMs = now;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) lastTempC = t;
    if (!isnan(h)) lastHumPct = h;
  }
  if (!isnan(lastTempC)) doc["air_temp_c"] = round(lastTempC * 10) / 10.0;
  if (!isnan(lastHumPct)) doc["humidity_pct"] = round(lastHumPct * 10) / 10.0;

  JsonArray arr = doc.createNestedArray("readings");
  for (int i = 0; i < count; i++) {
    JsonObject r = arr.add<JsonObject>();
    r["angle"] = round(readings[i].angle * 10) / 10.0;
    r["dist"] = round(readings[i].distance * 10) / 10.0;
    r["distance"] = round(readings[i].distance * 10) / 10.0;  // Backend accepts both
    r["temp"] = round(readings[i].temp_c * 10) / 10.0;
    r["gyro_z"] = round(readings[i].gyro_z * 1000) / 1000.0;
  }

  String body;
  serializeJson(doc, body);

#if USE_SERIAL
  Serial.println(body);
  return true;
#else
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  String url = String(BACKEND_URL) + "/arduino/readings";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  int code = http.POST(body);
  http.end();

  return (code == 200);
#endif
}

// ── SETUP & LOOP ───────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  dht.begin();
  delay(2000);  // DHT11 needs 1–2 s to stabilize
  sweepServo.attach(SERVO_PIN);
  currentAngle = 0.0;
  sweepDirection = true;
  sweepServo.write(angleToServo(0));
  delay(500);  // let servo reach centre

#if USE_MOTORS
  motorSetup();
  #if !COMMAND_MODE
  robotState = STATE_MOVE;
  stateStartMs = millis();
  #endif
#endif

#if USE_IMU
  Modulino.begin();
  if (imu.begin()) {
    Serial.println(F("Modulino Movement IMU OK"));
  } else {
    Serial.println(F("Modulino Movement IMU not found - set USE_IMU 0 if no IMU"));
  }
#endif

#if USE_SERIAL
  Serial.println("USB Serial mode - connect to Python backend");
#else
  Serial.println("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
#endif

  startTimeMs = millis();
}

#if USE_MOTORS && COMMAND_MODE
void applyMotorCmd(char cmd) {
  if (cmd == 'F') moveForward();
  else if (cmd == 'B') moveBackward();
  else if (cmd == 'L') turnLeft();
  else if (cmd == 'R') turnRight();
  else stopMotors();
}
#endif

void loop() {
#if USE_MOTORS && COMMAND_MODE
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S')
      currentMotorCmd = c;
  }
#endif

#if USE_MOTORS && !COMMAND_MODE
  unsigned long elapsed = millis() - stateStartMs;
  switch (robotState) {
    case STATE_MOVE:
      moveForward();
      if (elapsed >= MOVE_DURATION_MS) {
        stopMotors();
        robotState = STATE_STOP;
        stateStartMs = millis();
      }
      delay(50);
      return;
    case STATE_STOP:
      stopMotors();
      if (elapsed >= STOP_BEFORE_SWEEP_MS) {
        robotState = STATE_SWEEP;
        stateStartMs = millis();
      }
      delay(50);
      return;
    case STATE_SWEEP:
      break;
  }
#endif

  float distRaw = readDistanceCmMedian(ULTRASONIC_SAMPLES);
  float dist = distRaw;
  if (dist < MIN_DISTANCE_CM || dist > MAX_DISTANCE_CM || dist <= 0 || dist >= MAX_VALID_CM)
    dist = 400.0;

  float gyroZ = 0.0f;
  float tempC = lastTempC;
  if (isnan(tempC)) tempC = 20.0f;
#if USE_IMU
  if (imu.update()) gyroZ = imu.getYaw();
#endif

  buffer[bufferIdx].angle = currentAngle + ANGLE_OFFSET;
  buffer[bufferIdx].distance = dist;
  buffer[bufferIdx].temp_c = tempC;
  buffer[bufferIdx].gyro_z = gyroZ;
  bufferIdx++;

  if (bufferIdx >= SEND_CHUNK) {
    sendReadings(buffer, SEND_CHUNK);
    bufferIdx = 0;
  }

#if USE_MOTORS && COMMAND_MODE
  float fwd = (abs(currentAngle) < 15) ? distRaw : 400.0;
  if (fwd >= MIN_DISTANCE_CM && fwd <= MAX_DISTANCE_CM && fwd < 15)
    stopMotors();
  else
    applyMotorCmd(currentMotorCmd);
#endif

  stepServo();
  delay(80);
}
