/*
 * Accelerometer & Gyroscope Test
 *
 * Uses Arduino LSM6DSOX library (Library Manager: Arduino_LSM6DSOX).
 * Compatible with LSM6DSOX on Modulino Movement or I2C breakout.
 *
 * Wiring (I2C): SDA→A4, SCL→A5 (Uno). Open Serial Monitor at 115200.
 *
 * Expected:
 *   - Accel: ~0, 0, 1 g when flat (z up)
 *   - Gyro: ~0, 0, 0 deg/s when still
 */
#include <Wire.h>
#include <Arduino_LSM6DSOX.h>

#define LSM6DSOX_ADDR 0x6A

LSM6DSOXClass imu(Wire, LSM6DSOX_ADDR);

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  pinMode(A4, INPUT_PULLUP);  // SDA
  pinMode(A5, INPUT_PULLUP);  // SCL
  Wire.begin();

  Serial.println(F("LSM6DSOX Accel/Gyro Test"));
  Serial.println(F("------------------------"));

  if (!imu.begin()) {
    Serial.println(F("ERROR: LSM6DSOX not found. Check wiring (SDA=A4, SCL=A5)."));
    while (1) delay(1000);
  }

  Serial.println(F("LSM6DSOX OK"));
  Serial.println();
}

void loop() {
  float ax, ay, az, gx, gy, gz;

  if (imu.accelerationAvailable() && imu.readAcceleration(ax, ay, az) &&
      imu.gyroscopeAvailable() && imu.readGyroscope(gx, gy, gz)) {

    Serial.print(F("Accel X:"));
    Serial.print(ax, 3);
    Serial.print(F("  Y:"));
    Serial.print(ay, 3);
    Serial.print(F("  Z:"));
    Serial.print(az, 3);
    Serial.print(F(" g   |   Gyro X:"));
    Serial.print(gx, 3);
    Serial.print(F("  Y:"));
    Serial.print(gy, 3);
    Serial.print(F("  Z:"));
    Serial.print(gz, 3);
    Serial.println(F(" deg/s"));
  }

  delay(100);
}
