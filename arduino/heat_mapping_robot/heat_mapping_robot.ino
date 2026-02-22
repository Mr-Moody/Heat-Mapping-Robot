/*
 * Heat Mapping Robot — Arduino Sketch
 * Sends ultrasonic sweep readings to Python backend.
 *
 * USE_SERIAL=1: USB serial (Arduino Uno, any board with Serial)
 * USE_SERIAL=0: WiFi HTTP POST (ESP32)
 *
 * Hardware:
 *   - HC-SR04 ultrasonic: TRIG_PIN, ECHO_PIN
 *   - 180° micro servo: SERVO_PIN (positional)
 *   - DHT11 temp/humidity: DHT_PIN (data)
 */

#define USE_SERIAL 1   // 1 = USB serial, 0 = WiFi

#if !USE_SERIAL
#include <WiFi.h>
#include <HTTPClient.h>
#endif
#include <ArduinoJson.h>
#include <DHT.h>
#include <Servo.h>

// ── CONFIG ────────────────────────────────────────────────────────────────
#if !USE_SERIAL
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"
#define BACKEND_URL     "http://192.168.1.100:8000"  // Python backend IP
#endif
#define CHUNK_SIZE      8                            // Readings per HTTP POST
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
#define MAX_DISTANCE_CM 400
#define MIN_DISTANCE_CM 2
// Distance calibration: run distance_calibrate.ino to tune. 58.2 = standard HC-SR04.
#define MICROSEC_PER_CM  58.2
#define DISTANCE_OFFSET_CM 1.7   // raw 28.3 @ 30cm true → add 1.7

// ── GLOBALS ────────────────────────────────────────────────────────────────
struct Reading {
  float angle;
  float distance;
};
Reading buffer[CHUNK_SIZE];
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

// ── ULTRASONIC ────────────────────────────────────────────────────────────
float readDistanceCm()
{
  // 1. Clean pulse logic from your test script
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // 2. Read the signal
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0)
    return 0.0;

  float cm = (float)duration / (float)MICROSEC_PER_CM + DISTANCE_OFFSET_CM;
  return cm;
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
  StaticJsonDocument<768> doc;  // readings + thermal
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
    r["distance"] = round(readings[i].distance * 10) / 10.0;
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

void loop() {
  // Take one reading at current angle
  float dist = readDistanceCm();
  
  if (dist >= MIN_DISTANCE_CM && dist <= MAX_DISTANCE_CM) {
    buffer[bufferIdx].angle = currentAngle + ANGLE_OFFSET;
    buffer[bufferIdx].distance = dist;
    bufferIdx++;

    if (bufferIdx >= CHUNK_SIZE) {
      if (sendReadings(buffer, CHUNK_SIZE)) {
#if !USE_SERIAL
        Serial.print("Sent ");
        Serial.print(CHUNK_SIZE);
        Serial.println(" readings");
#endif
      } else {
#if !USE_SERIAL
        Serial.println("POST failed");
#endif
      }
      bufferIdx = 0;
    }
  }

  stepServo();
  delay(100);  // Let positional servo reach target before ultrasonic read
}
