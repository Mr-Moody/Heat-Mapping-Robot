/*
 * Heat Mapping Robot — Arduino Sketch
 * Sends ultrasonic sweep readings to Python backend over WiFi.
 *
 * Target: ESP32 (WiFi built-in)
 * For Arduino Uno WiFi Rev2: use WiFiNINA and adjust HTTP client.
 *
 * Hardware:
 *   - HC-SR04 ultrasonic: TRIG_PIN, ECHO_PIN
 *   - Continuous servo: SERVO_PIN (PWM)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Servo.h>

// ── CONFIG ────────────────────────────────────────────────────────────────
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"
#define BACKEND_URL     "http://192.168.1.100:8000"  // Python backend IP
#define CHUNK_SIZE      8                            // Readings per HTTP POST
#define SWEEP_STEP_DEG  30.0                         // Angle step per reading
#define SERVO_SPEED     90                            // 90 = stop, <90 CCW, >90 CW
#define TRIG_PIN        5
#define ECHO_PIN        7
#define SERVO_PIN      13
#define MAX_DISTANCE_CM 400
#define MIN_DISTANCE_CM 2

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
Servo sweepServo;

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

  // 3. Convert to CM using your script's formula: (duration/2) / 29.1
  return (duration / 2.0) / 29.1;
}

// ── SERVO ─────────────────────────────────────────────────────────────────
void stepServo() {
  // Continuous servo: 90=stop, <90 one dir, >90 other
  sweepServo.write(SERVO_SPEED);
  delay(50);  // Allow servo to move

  currentAngle += sweepDirection ? SWEEP_STEP_DEG : -SWEEP_STEP_DEG;

  if (currentAngle >= 360.0) {
    currentAngle = 360.0 - SWEEP_STEP_DEG;
    sweepDirection = false;
  } else if (currentAngle < 0.0) {
    currentAngle = SWEEP_STEP_DEG;
    sweepDirection = true;
  }
}

// ── HTTP POST ─────────────────────────────────────────────────────────────
bool sendReadings(Reading* readings, int count) {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  String url = String(BACKEND_URL) + "/arduino/readings";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<512> doc;
  doc["timestamp_ms"] = (long)(millis() - startTimeMs);

  JsonArray arr = doc.createNestedArray("readings");

  for (int i = 0; i < count; i++) {
    JsonObject r = arr.add<JsonObject>();
    r["angle"] = round(readings[i].angle * 10) / 10.0;
    r["distance"] = round(readings[i].distance * 10) / 10.0;
  }

  String body;
  serializeJson(doc, body);

  int code = http.POST(body);
  http.end();

  return (code == 200);
}

// ── SETUP & LOOP ───────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  sweepServo.attach(SERVO_PIN);

  Serial.println("Connecting to WiFi...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  startTimeMs = millis();
}

void loop() {
  // Take one reading at current angle
  float dist = readDistanceCm();
  
  if (dist >= MIN_DISTANCE_CM && dist <= MAX_DISTANCE_CM) {
    buffer[bufferIdx].angle = currentAngle;
    buffer[bufferIdx].distance = dist;
    bufferIdx++;

    if (bufferIdx >= CHUNK_SIZE) {
      if (sendReadings(buffer, CHUNK_SIZE)) {
        Serial.print("Sent ");
        Serial.print(CHUNK_SIZE);
        Serial.println(" readings");
      } else {
        Serial.println("POST failed");
      }
      bufferIdx = 0;
    }
  }

  stepServo();
  delay(80);  // Debounce + servo settle
}
