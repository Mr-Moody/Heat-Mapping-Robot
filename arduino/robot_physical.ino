/*
 * Heat Mapping Robot — Physical / Standalone
 * ───────────────────────────────────────────────────────────────────────────
 * Target boards:
 *   - Arduino Uno R3 (AVR): Tools → Board → Arduino Uno. Uses standard Servo library.
 *   - Arduino Uno Q (Zephyr): Uses built-in Zephyr servo path (no Servo library).
 *
 * Runs the same path-planning logic as the simulated robot (backend PathPlanner)
 * directly on the Arduino. No Python backend required.
 *
 * Logic (from backend/src/path_planning.py):
 *   1. Obstacle avoidance — stop and turn if forward < 25 cm
 *   2. Wall following — maintain ~30 cm from left wall (left/right from sweep)
 *   3. Stuck recovery — if forward < 15 cm for 3 steps, full sweep and turn to best direction
 *
 * Hardware (same as heat_mapping_robot.ino):
 *   - HC-SR04: TRIG 5, ECHO 7
 *   - 180° micro servo: pin 9 (-90° = left, 0° = forward, +90° = right)
 *   - DHT11: pin 8
 *   - L298N motors: A=13,12  B=10,11
 */

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

// ── Pins (match heat_mapping_robot) ─────────────────────────────────────────
#define TRIG_PIN        5
#define ECHO_PIN        7
#define SERVO_PIN       9
#define DHT_PIN         8
#define MOTOR_A_IN1     13
#define MOTOR_A_IN2     12
#define MOTOR_B_IN3     10
#define MOTOR_B_IN4     11

// Servo mapping: logical -90..+90 → PWM (run servo_calibrate to get values)
#define SERVO_AT_MIN    180   // our -90° (left)
#define SERVO_AT_MAX    0     // our +90° (right)
#define SWEEP_MIN_DEG   -90.0
#define SWEEP_MAX_DEG    90.0
#define SWEEP_STEP_DEG   10.0

// Path planner constants (from path_planning.py)
#define OBSTACLE_THRESHOLD_CM  25.0f
#define STUCK_THRESHOLD_CM     15.0f
#define WALL_TARGET_CM         30.0f
#define WALL_TOLERANCE_CM      8.0f
#define CONSECUTIVE_STUCK_FOR_SWEEP 3

// Sweep: 12 bins for planner. Index 0=forward, 3=left(90°), 6=rear(no sensor), 9=right(90°)
#define SWEEP_BINS       12
#define DEFAULT_FAR_CM   150.0f
#define MAX_DISTANCE_CM  400.0f
#define MIN_DISTANCE_CM  2.0f
#define MICROSEC_PER_CM  58.2f
#define DISTANCE_OFFSET_CM 1.7f

// Move durations (tune for your robot; ~0.05 m per step in sim → scale to time)
#define MOVE_FORWARD_MS    500
#define TURN_15_MS         150
#define TURN_45_MS         400
#define TURN_90_MS         800
#define STOP_SAMPLE_MS     2000   // DHT pause (optional)
#define STOP_SAMPLE_EVERY  10     // pause every N moves (0 = disable)

// Ultrasonic median filter
#define ULTRASONIC_SAMPLES  5
#define MAX_VALID_CM        3000.0f

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
#define DHT_READ_INTERVAL_MS 2000

int consecutiveObstacles = 0;

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
// Maps logical angle -90..+90 to servo position 0..180 (or reversed per SERVO_AT_*).
int angleToServo(float deg) {
  return (int)(SERVO_AT_MIN + (deg - SWEEP_MIN_DEG) * (SERVO_AT_MAX - SERVO_AT_MIN) / (SWEEP_MAX_DEG - SWEEP_MIN_DEG));
}

void setServoAngle(float deg) {
#if USE_ZEPHYR_SERVO
  // Zephyr: no Servo library. Generate 50 Hz pulse: 1 ms (0°) to 2 ms (180°).
  int pos = angleToServo(deg);
  if (pos < 0) pos = 0;
  if (pos > 180) pos = 180;
  int pulseUs = 1000 + (pos * 1000 / 180);
  digitalWrite(SERVO_PIN, HIGH);
  delayMicroseconds(pulseUs);
  digitalWrite(SERVO_PIN, LOW);
  delay(20);  // ~20 ms period (blocking)
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

// ── Motors (same as heat_mapping_robot.ino) ──────────────────────────────────
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

// ── Sweep collection ────────────────────────────────────────────────────────
// Build 12-bin sweep: bin 0 = forward (0°), 3 = left (-90°), 6 = rear (no sensor), 9 = right (+90°)
void initSweep() {
  for (int i = 0; i < SWEEP_BINS; i++)
    sweep_cm[i] = DEFAULT_FAR_CM;
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

  // Map 180° sweep (-90..+90) to planner bins: 0=forward, 3=left, 9=right (rear 6 has no sensor).
  int bin = -1;
  if (currentAngle >= -15.0f && currentAngle <= 15.0f) bin = 0;   // forward
  else if (currentAngle <= -75.0f)                     bin = 3;   // left
  else if (currentAngle >= 75.0f)                     bin = 9;   // right
  if (bin < 0) return;
  if (sweep_cm[bin] >= DEFAULT_FAR_CM - 1.0f)
    sweep_cm[bin] = dist;
  else
    sweep_cm[bin] = 0.6f * sweep_cm[bin] + 0.4f * dist;
}

bool sweepComplete() {
  // One full pass: -90° -> +90° (19 steps). Then we're ready to decide.
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

// Call this repeatedly to fill sweep; returns true when one full sweep is done.
bool collectSweepStep() {
  stepServoAndCollect();
  return sweepComplete();
}

// ── Path planner (mirrors path_planning.py PathPlanner.decide) ──────────────
// Returns: action (for logging), motor char F/B/L/R/S, turn_deg (for duration)
void plannerDecide(float* out_turn_deg, char* out_cmd) {
  float forward_cm = sweep_cm[0];
  float left_cm    = sweep_cm[3];
  float right_cm   = sweep_cm[9];
  if (forward_cm <= 0.0f || forward_cm > MAX_DISTANCE_CM) forward_cm = DEFAULT_FAR_CM;
  if (left_cm    <= 0.0f || left_cm    > MAX_DISTANCE_CM) left_cm    = DEFAULT_FAR_CM;
  if (right_cm   <= 0.0f || right_cm   > MAX_DISTANCE_CM) right_cm   = DEFAULT_FAR_CM;

  *out_turn_deg = 0.0f;
  *out_cmd = 'F';

  // Layer 1: Very stuck -> full sweep and turn to best direction
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
      // bestIdx 0=forward, 3=left, 9=right. Turn angle: 0°->0, 3->-90, 9->+90, etc.
      float bestAngle = bestIdx * 30.0f;
      if (bestAngle > 180.0f) bestAngle -= 360.0f;
      *out_turn_deg = bestAngle;
      *out_cmd = (bestAngle < 0) ? 'L' : 'R';
      return;
    }
  } else {
    consecutiveObstacles = 0;
  }

  // Layer 2: Obstacle avoidance
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

  // Layer 3: Wall following (left wall)
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

// ── Execute move for a duration ──────────────────────────────────────────────
unsigned long turnDegToMs(float deg) {
  float a = (deg < 0) ? -deg : deg;
  if (a <= 20.0f) return TURN_15_MS;
  if (a <= 50.0f) return TURN_45_MS;
  return TURN_90_MS;
}

void applyMotorCmd(char cmd) {
  if (cmd == 'F') moveForward();
  else if (cmd == 'B') moveBackward();
  else if (cmd == 'L') turnLeft();
  else if (cmd == 'R') turnRight();
  else stopMotors();
}

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
  currentAngle = SWEEP_MIN_DEG;  // start at left (-90°), sweep toward right (+90°)
  sweepDirection = true;
  setServoAngle(currentAngle);
  delay(500);
  motorSetup();
  initSweep();
  phase = PHASE_COLLECT_SWEEP;
  phaseStartMs = millis();
  Serial.println(F("Robot physical — path planner onboard (no backend)"));
}

// ── Main loop ───────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // DHT read (non-blocking)
  if (now - lastDhtReadMs >= DHT_READ_INTERVAL_MS) {
    lastDhtReadMs = now;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) lastTempC = t;
    if (!isnan(h)) lastHumPct = h;
  }

  switch (phase) {
    case PHASE_COLLECT_SWEEP: {
      if (collectSweepStep()) {
        phase = PHASE_DECIDE;
        phaseStartMs = now;
      }
      return;
    }

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
        if (cmd == 'F')
          phaseStartMs = now;  // MOVE_FORWARD_MS
        else
          phaseStartMs = now;  // turnDegToMs
      }
      moveCount++;
      break;
    }

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
      unsigned long durationMs = (pendingMotorCmd == 'F') ? MOVE_FORWARD_MS : turnDegToMs(pendingTurnDeg);
      if (now - phaseStartMs >= durationMs) {
        stopMotors();
        phase = PHASE_COLLECT_SWEEP;
        initSweep();
        // Debug: Serial.print("Fwd="); Serial.print(sweep_cm[0]); Serial.print(" L="); Serial.print(sweep_cm[3]); Serial.print(" R="); Serial.println(sweep_cm[9]);
      }
      return;
    }
  }
}
