/*
 * HC-SR04 Distance Calibration
 *
 * Use this sketch to verify and calibrate the ultrasonic sensor.
 * Open Serial Monitor at 115200.
 *
 * PROCEDURE:
 * 1. Place a flat object at a KNOWN distance (e.g. 50 cm) in front of the sensor
 * 2. Measure with a ruler — sensor measures from transducer face to object
 * 3. Note: duration_us, raw_cm, and adjusted_cm. Adjust MICROSEC_PER_CM
 *    and DISTANCE_OFFSET_CM until adjusted_cm matches your measured distance
 * 4. Copy the working values into heat_mapping_robot.ino
 *
 * HC-SR04 formula: distance_cm = (duration_us / 2) / (microsec_per_cm)
 * Speed of sound ~343 m/s at 20°C → 29.15 µs/cm (one-way) → 58.3 µs/cm round-trip
 * Default 58.2 matches common formula (duration/2)/29.1
 */
#define TRIG_PIN 5
#define ECHO_PIN 7

// Tune these until output matches measured distance
#define MICROSEC_PER_CM  58.2   // 58.2 = standard; increase if sensor reads too high
#define DISTANCE_OFFSET_CM 0.0  // Additive correction (e.g. -1.5 if consistently 1.5cm high)

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Serial.println(F("HC-SR04 Distance Calibration"));
  Serial.println(F("Place object at known distance, compare raw vs measured."));
  Serial.println(F("Adjust MICROSEC_PER_CM and DISTANCE_OFFSET_CM as needed."));
  Serial.println();
}

void loop() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) {
    Serial.println("No echo (timeout or out of range)");
  } else {
    // Standard: distance = (duration/2)/29.1 = duration/58.2 (round-trip µs per cm)
    float raw_cm = (float)duration / (float)MICROSEC_PER_CM;
    float adjusted_cm = raw_cm + DISTANCE_OFFSET_CM;

    Serial.print("duration_us=");
    Serial.print(duration);
    Serial.print("  raw_cm=");
    Serial.print(raw_cm, 1);
    Serial.print("  adjusted_cm=");
    Serial.print(adjusted_cm, 1);
    Serial.println();
  }

  delay(200);
}
