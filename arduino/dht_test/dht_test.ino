/*
 * DHT11 Test Sketch (3-pin PCB module)
 * Pinout: VCC→5V, DATA→pin below, GND→GND (no external pull-up needed)
 * Open Serial Monitor at 115200. If NaN: swap DATA/GND or try another pin.
 */
#include <DHT.h>

#define DHT_PIN 4
DHT dht(DHT_PIN, DHT11);

void setup() {
  Serial.begin(115200);
  dht.begin();
  delay(2000);
  Serial.println("DHT11 test on pin 8");
}

void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  Serial.print("Temp: ");
  Serial.print(isnan(t) ? "NaN" : String(t, 1));
  Serial.print(" C  Hum: ");
  Serial.print(isnan(h) ? "NaN" : String(h, 1));
  Serial.println("%");
  delay(2000);
}
