/*
 * Heat Mapping Robot — Physical
 * ───────────────────────────────────────────────────────────────────────────
 * Target: Arduino Uno R3 (AVR) or Arduino Uno Q (Zephyr)
 *
 * MODES:
 *   BACKEND_MODE=1 (default): Connects to Python backend via USB Serial.
 *     Backend runs: OccupancyGrid (SLAM), path planning, thermal exploration,
 *     hot/cold spot detection. Arduino sends sensor JSON, receives F/B/L/R/S.
 *
 *   BACKEND_MODE=0: Standalone onboard planner (no backend).
 *
 * Hardware:
 *   - HC-SR04: TRIG 5, ECHO 7
 *   - 180° servo: pin 9 (-90°=left, 0°=forward, +90°=right)
 *   - DHT11: pin 8 (temp/humidity for thermal mapping)
 *   - L298N motors: A=13,12  B=10,11
 *
 * Backend: Run with SERIAL_PORT=COMx (Windows) or /dev/ttyACM0 (Linux)
 *   cd backend && SERIAL_PORT=COM3 python main.py
 */

#define BACKEND_MODE 1   // 1 = Python backend (SLAM, occupancy grid, thermal), 0 = standalone
#define DEBUG_CMD 0      // 1 = print cmd to Serial (disable when backend connected - avoids polluting JSON stream)

#include <DHT.h>

#if defined(__AVR__)
  #include <Servo.h>
  #define USE_ZEPHYR_SERVO 0
#elif defined(__ZEPHYR__)
  #define USE_ZEPHYR_SERVO 1
#else
  #include <Servo.h>
  #define USE_ZEPHYR_SERVO 0
#endif

#if BACKEND_MODE
#include <ArduinoJson.h>  // Install via Library Manager if needed
#endif

// ── Pins ───────────────────────────────────────────────────────────────────
#define TRIG_PIN        5
#define ECHO_PIN        7
#define SERVO_PIN       9
#define DHT_PIN         8
#define MOTOR_A_IN1     13
#define MOTOR_A_IN2     12
#define MOTOR_B_IN3     10
#define MOTOR_B_IN4     11

// Servo: -90° (left) .. 0° (forward) .. +90° (right)
#define SERVO_AT_MIN    180
#define SERVO_AT_MAX    0
#define SWEEP_MIN_DEG   -90.0f
#define SWEEP_MAX_DEG    90.0f
#define SWEEP_STEP_DEG   10.0f
#define READINGS_MAX     20   // 19 steps -90..+90

// Path planner (standalone mode)
#define OBSTACLE_THRESHOLD_CM  25.0f
#define STUCK_THRESHOLD_CM     15.0f
#define WALL_TARGET_CM         30.0f
#define WALL_TOLERANCE_CM      8.0f
#define CONSECUTIVE_STUCK_FOR_SWEEP 3

#define SWEEP_BINS       12
#define DEFAULT_FAR_CM   150.0f
#define MAX_DISTANCE_CM  400.0f
#define MIN_DISTANCE_CM  2.0f
#define MICROSEC_PER_CM  58.2f
#define DISTANCE_OFFSET_CM 1.7f

#define MOVE_FORWARD_MS    500
#define TURN_15_MS         150
#define TURN_45_MS         400
#define TURN_90_MS         800
#define STOP_SAMPLE_MS     2000
#define STOP_SAMPLE_EVERY  10

#define ULTRASONIC_SAMPLES  5
#define MAX_VALID_CM        3000.0f
#define DHT_READ_INTERVAL_MS 2000
#define BACKEND_CMD_TIMEOUT_MS 3000

// ── Globals ─────────────────────────────────────────────────────────────────
#if !USE_ZEPHYR_SERVO
Servo sweepServo;
#endif
DHT dht(DHT_PIN, DHT11);

float sweep_cm[SWEEP_BINS];
float currentAngle = 0.0f;
bool sweepDirection = true;
float lastTempC = 20.0f;
float lastHumPct = 50.0f;
unsigned long lastDhtReadMs = 0;
unsigned long startTimeMs = 0;

#if BACKEND_MODE
struct PolarReading { float angle; float distance; };
PolarReading polarReadings[READINGS_MAX];
int polarCount = 0;
char backendCmd = 'F';  // Last command from backend (F=forward if no backend)
unsigned long lastBackendCmdMs = 0;
#else
int consecutiveObstacles = 0;
#endif

enum Phase {
  PHASE_COLLECT_SWEEP,
  PHASE_DECIDE,
  PHASE_MOVE,
  PHASE_STOP_SAMPLE
};
Phase phase = PHASE_COLLECT_SWEEP;
unsigned long phaseStartMs = 0;
char pendingMotorCmd = 'S';
float pendingTurnDeg = 0.0f;
int moveCount = 0;

// ── Servo ──────────────────────────────────────────────────────────────────
int angleToServo(float deg) {
  return (int)(SERVO_AT_MIN + (deg - SWEEP_MIN_DEG) * (SERVO_AT_MAX - SERVO_AT_MIN) / (SWEEP_MAX_DEG - SWEEP_MIN_DEG));
}

void setServoAngle(float deg) {
#if USE_ZEPHYR_SERVO
  int pos = angleToServo(deg);
  if (pos < 0) pos = 0;
  if (pos > 180) pos = 180;
  int pulseUs = 1000 + (pos * 1000 / 180);
  digitalWrite(SERVO_PIN, HIGH);
  delayMicroseconds(pulseUs);
  digitalWrite(SERVO_PIN, LOW);
  delay(20);
#else
  sweepServo.write(angleToServo(deg));
#endif
}

// ── Ultrasonic ──────────────────────────────────────────────────────────────
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

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return 0.0f;
  return (float)duration / MICROSEC_PER_CM + DISTANCE_OFFSET_CM;
}

float readDistanceCmMedian(int samples) {
  float buf[8];
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
  if (valid == 0) return 0.0f;
  sortFloat(buf, valid);
  return buf[valid / 2];
}

// ── Motors ──────────────────────────────────────────────────────────────────
void motorSetup() {
  pinMode(MOTOR_A_IN1, OUTPUT);
  pinMode(MOTOR_A_IN2, OUTPUT);
  pinMode(MOTOR_B_IN3, OUTPUT);
  pinMode(MOTOR_B_IN4, OUTPUT);
  digitalWrite(MOTOR_A_IN1, LOW);
  digitalWrite(MOTOR_A_IN2, LOW);
  digitalWrite(MOTOR_B_IN3, LOW);
  digitalWrite(MOTOR_B_IN4, LOW);
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

void applyMotorCmd(char cmd) {
  if (cmd == 'F') moveForward();
  else if (cmd == 'B') moveBackward();
  else if (cmd == 'L') turnLeft();
  else if (cmd == 'R') turnRight();
  else stopMotors();
}

// ── Sweep: collect polar readings + binned sweep ────────────────────────────
void initSweep() {
  for (int i = 0; i < SWEEP_BINS; i++)
    sweep_cm[i] = DEFAULT_FAR_CM;
#if BACKEND_MODE
  polarCount = 0;
#endif
}

void stepServoAndCollect() {
  currentAngle += sweepDirection ? SWEEP_STEP_DEG : -SWEEP_STEP_DEG;
  if (currentAngle >= SWEEP_MAX_DEG) {
    currentAngle = SWEEP_MAX_DEG;
    sweepDirection = false;
  } else if (currentAngle <= SWEEP_MIN_DEG) {
    currentAngle = SWEEP_MIN_DEG;
    sweepDirection = true;
  }
  setServoAngle(currentAngle);
  delay(30);

  float dist = readDistanceCmMedian(ULTRASONIC_SAMPLES);
  if (dist < MIN_DISTANCE_CM || dist > MAX_DISTANCE_CM || dist <= 0.0f) dist = DEFAULT_FAR_CM;

#if BACKEND_MODE
  if (polarCount < READINGS_MAX) {
    polarReadings[polarCount].angle = currentAngle;
    polarReadings[polarCount].distance = dist;
    polarCount++;
  }
#endif

  int bin = -1;
  if (currentAngle >= -15.0f && currentAngle <= 15.0f) bin = 0;
  else if (currentAngle <= -75.0f) bin = 3;
  else if (currentAngle >= 75.0f) bin = 9;
  if (bin >= 0) {
    if (sweep_cm[bin] >= DEFAULT_FAR_CM - 1.0f)
      sweep_cm[bin] = dist;
    else
      sweep_cm[bin] = 0.6f * sweep_cm[bin] + 0.4f * dist;
  }
}

bool sweepComplete() {
  static int stepCount = 0;
  static bool reachedMax = false;
  if (currentAngle >= SWEEP_MAX_DEG - 5.0f) reachedMax = true;
  stepCount++;
  int stepsOneWay = (int)((SWEEP_MAX_DEG - SWEEP_MIN_DEG) / SWEEP_STEP_DEG);
  bool done = reachedMax && (stepCount >= stepsOneWay);
  if (done) {
    stepCount = 0;
    reachedMax = false;
  }
  return done;
}

bool collectSweepStep() {
  stepServoAndCollect();
  return sweepComplete();
}

// ── Backend: send JSON, receive command ─────────────────────────────────────
#if BACKEND_MODE
// Arduino Uno has 2KB SRAM. StaticJsonDocument must fit in stack.
// 512 overflowed (corrupt at ~char 310). 384 + 8 readings keeps under capacity.
#define BACKEND_JSON_SIZE 384
#define BACKEND_READINGS_MAX 8

void sendBackendPayload() {
  StaticJsonDocument<BACKEND_JSON_SIZE> doc;
  doc["timestamp_ms"] = (long)(millis() - startTimeMs);
  if (!isnan(lastTempC)) doc["air_temp_c"] = round(lastTempC * 10) / 10.0;
  if (!isnan(lastHumPct)) doc["humidity_pct"] = round(lastHumPct * 10) / 10.0;

  JsonArray arr = doc.createNestedArray("readings");
  int n = min(polarCount, BACKEND_READINGS_MAX);
  for (int i = 0; i < n; i++) {
    float a = polarReadings[i].angle;
    float d = polarReadings[i].distance;
    if (!isnan(a) && !isinf(a) && !isnan(d) && !isinf(d)) {
      JsonObject r = arr.add<JsonObject>();
      r["angle"] = round(a * 10) / 10.0;
      r["distance"] = round(d * 10) / 10.0;
    }
  }

  if (doc.overflowed()) {
    doc.clear();
    doc["timestamp_ms"] = (long)(millis() - startTimeMs);
    doc.createNestedArray("readings");
  }

  String body;
  serializeJson(doc, body);
  Serial.println(body);
  Serial.flush();
}

char readBackendCommand() {
  unsigned long start = millis();
  while (millis() - start < BACKEND_CMD_TIMEOUT_MS) {
    if (Serial.available()) {
      char c = Serial.read();
      if (c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S') {
        lastBackendCmdMs = millis();
#if DEBUG_CMD
        Serial.print(F("<-cmd:"));
        Serial.println(c);
#endif
        return c;
      }
    }
    delay(10);
  }
#if DEBUG_CMD
  Serial.print(F("<-timeout, using:"));
  Serial.println(backendCmd);
#endif
  return backendCmd;  // Timeout: use last (or 'F' if never connected)
}
#endif

// ── Standalone path planner ──────────────────────────────────────────────────
#if !BACKEND_MODE
static int consecutiveObstacles = 0;

void plannerDecide(float* out_turn_deg, char* out_cmd) {
  float forward_cm = sweep_cm[0];
  float left_cm    = sweep_cm[3];
  float right_cm   = sweep_cm[9];
  if (forward_cm <= 0.0f || forward_cm > MAX_DISTANCE_CM) forward_cm = DEFAULT_FAR_CM;
  if (left_cm    <= 0.0f || left_cm    > MAX_DISTANCE_CM) left_cm    = DEFAULT_FAR_CM;
  if (right_cm   <= 0.0f || right_cm   > MAX_DISTANCE_CM) right_cm   = DEFAULT_FAR_CM;

  *out_turn_deg = 0.0f;
  *out_cmd = 'F';

  if (forward_cm < STUCK_THRESHOLD_CM) {
    consecutiveObstacles++;
    if (consecutiveObstacles >= CONSECUTIVE_STUCK_FOR_SWEEP) {
      consecutiveObstacles = 0;
      float best = sweep_cm[0];
      int bestIdx = 0;
      for (int i = 1; i < SWEEP_BINS; i++) {
        if (sweep_cm[i] > best) {
          best = sweep_cm[i];
          bestIdx = i;
        }
      }
      float bestAngle = bestIdx * 30.0f;
      if (bestAngle > 180.0f) bestAngle -= 360.0f;
      *out_turn_deg = bestAngle;
      *out_cmd = (bestAngle < 0) ? 'L' : 'R';
      return;
    }
  } else {
    consecutiveObstacles = 0;
  }

  if (forward_cm < OBSTACLE_THRESHOLD_CM) {
    if (left_cm > right_cm) {
      *out_turn_deg = -45.0f;
      *out_cmd = 'L';
    } else {
      *out_turn_deg = 45.0f;
      *out_cmd = 'R';
    }
    return;
  }

  float error = left_cm - WALL_TARGET_CM;
  if (error > WALL_TOLERANCE_CM) {
    *out_turn_deg = -15.0f;
    *out_cmd = 'L';
    return;
  }
  if (error < -WALL_TOLERANCE_CM) {
    *out_turn_deg = 15.0f;
    *out_cmd = 'R';
    return;
  }
  *out_cmd = 'F';
}

unsigned long turnDegToMs(float deg) {
  float a = (deg < 0) ? -deg : deg;
  if (a <= 20.0f) return TURN_15_MS;
  if (a <= 50.0f) return TURN_45_MS;
  return TURN_90_MS;
}
#endif

// ── Setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  dht.begin();
  delay(2000);

#if USE_ZEPHYR_SERVO
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);
#else
  sweepServo.attach(SERVO_PIN);
#endif

  currentAngle = SWEEP_MIN_DEG;
  sweepDirection = true;
  setServoAngle(currentAngle);
  delay(500);
  motorSetup();
  initSweep();
  phase = PHASE_COLLECT_SWEEP;
  phaseStartMs = millis();
  startTimeMs = millis();

#if BACKEND_MODE
  Serial.println(F("Robot physical — BACKEND MODE: SLAM, occupancy grid, thermal"));
#else
  Serial.println(F("Robot physical — STANDALONE mode"));
#endif
}

// ── Main loop ───────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  if (now - lastDhtReadMs >= DHT_READ_INTERVAL_MS) {
    lastDhtReadMs = now;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) lastTempC = t;
    if (!isnan(h)) lastHumPct = h;
  }

#if BACKEND_MODE
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'F' || c == 'B' || c == 'L' || c == 'R' || c == 'S')
      backendCmd = c;
  }
#endif

  switch (phase) {
    case PHASE_COLLECT_SWEEP: {
      if (collectSweepStep()) {
#if BACKEND_MODE
        sendBackendPayload();
        pendingMotorCmd = readBackendCommand();
        backendCmd = pendingMotorCmd;
        pendingTurnDeg = (pendingMotorCmd == 'L') ? -45.0f : (pendingMotorCmd == 'R') ? 45.0f : 0.0f;
        phase = PHASE_MOVE;
        phaseStartMs = now;
#else
        phase = PHASE_DECIDE;
        phaseStartMs = now;
#endif
      }
      return;
    }

#if !BACKEND_MODE
    case PHASE_DECIDE: {
      float turnDeg;
      char cmd;
      plannerDecide(&turnDeg, &cmd);
      pendingMotorCmd = cmd;
      pendingTurnDeg = turnDeg;

      if (STOP_SAMPLE_EVERY > 0 && (moveCount % STOP_SAMPLE_EVERY) == 0 && moveCount > 0) {
        phase = PHASE_STOP_SAMPLE;
        phaseStartMs = now;
        stopMotors();
        Serial.println(F("STOP_SAMPLE"));
      } else {
        phase = PHASE_MOVE;
        phaseStartMs = now;
      }
      moveCount++;
      break;
    }
#endif

    case PHASE_STOP_SAMPLE: {
      stopMotors();
      if (now - phaseStartMs >= STOP_SAMPLE_MS) {
        phase = PHASE_COLLECT_SWEEP;
        initSweep();
      }
      return;
    }

    case PHASE_MOVE: {
      applyMotorCmd(pendingMotorCmd);
#if BACKEND_MODE
      unsigned long durationMs = (pendingMotorCmd == 'F') ? MOVE_FORWARD_MS
        : (pendingMotorCmd == 'B') ? MOVE_FORWARD_MS
        : (abs(pendingTurnDeg) <= 20) ? TURN_15_MS
        : (abs(pendingTurnDeg) <= 50) ? TURN_45_MS
        : TURN_90_MS;
#else
      unsigned long durationMs = (pendingMotorCmd == 'F') ? MOVE_FORWARD_MS : turnDegToMs(pendingTurnDeg);
#endif
      if (now - phaseStartMs >= durationMs) {
        stopMotors();
        phase = PHASE_COLLECT_SWEEP;
        initSweep();
      }
      return;
    }
  }
}
