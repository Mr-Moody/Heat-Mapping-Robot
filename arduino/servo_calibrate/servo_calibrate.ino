/*
 * 180° Micro Servo Calibration
 *
 * Use this sketch to find SERVO_AT_MIN and SERVO_AT_MAX for heat_mapping_robot.ino.
 * Open Serial Monitor at 115200.
 *
 * Commands:
 *   a / d     : move left / right by 1°
 *   A / D     : move left / right by 10°
 *   1         : save current position as -90° (left limit)
 *   2         : save current position as +90° (right limit)
 *   c         : move to centre (90°)
 *   p         : print current value (copy into main sketch)
 */
#include <Servo.h>

#define SERVO_PIN 9

Servo s;
int pos = 90;        // 0–180
int savedMin = 0;    // value for -90°
int savedMax = 180;  // value for +90°
bool calibrated = false;

void setup() {
  Serial.begin(115200);
  s.attach(SERVO_PIN);
  s.write(pos);

  Serial.println(F("Servo calibration — 180° micro servo"));
  Serial.println(F("a/d: -1/+1 deg   A/D: -10/+10 deg"));
  Serial.println(F("1: save as -90° (left)   2: save as +90° (right)"));
  Serial.println(F("c: centre   p: print values"));
  Serial.println();
  printStatus();
}

void printStatus() {
  Serial.print(F("pos="));
  Serial.print(pos);
  if (calibrated) {
    Serial.print(F("   SERVO_AT_MIN="));
    Serial.print(savedMin);
    Serial.print(F("   SERVO_AT_MAX="));
    Serial.println(savedMax);
  } else {
    Serial.println();
  }
}

void loop() {
  if (!Serial.available()) return;

  char c = Serial.read();
  if (c == 'a') { pos = max(0, pos - 1); }
  else if (c == 'd') { pos = min(180, pos + 1); }
  else if (c == 'A') { pos = max(0, pos - 10); }
  else if (c == 'D') { pos = min(180, pos + 10); }
  else if (c == '1') {
    savedMin = pos;
    calibrated = true;
    Serial.println(F("Saved as -90° (left)"));
  }
  else if (c == '2') {
    savedMax = pos;
    calibrated = true;
    Serial.println(F("Saved as +90° (right)"));
  }
  else if (c == 'c') {
    pos = 90;
    Serial.println(F("Centre (90)"));
  }
  else if (c == 'p') {
    Serial.println(F("--- Copy into heat_mapping_robot.ino ---"));
    Serial.print(F("#define SERVO_AT_MIN    "));
    Serial.println(savedMin);
    Serial.print(F("#define SERVO_AT_MAX    "));
    Serial.println(savedMax);
    Serial.println(F("----------------------------------------"));
    return;
  }
  else return;

  s.write(pos);
  printStatus();
}
