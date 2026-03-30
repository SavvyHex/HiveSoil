#include <WiFi.h>

// -------- Wi-Fi and server settings --------
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char* SERVER_HOST = "192.168.1.100";
const uint16_t SERVER_PORT = 9000;

const char* DEVICE_ID = "esp32-01";
const char* FIRMWARE_VERSION = "1.0.0";

// -------- Sensor calibration --------
const int SENSOR_PIN = 34;
const int SENSOR_DRY = 3200;
const int SENSOR_WET = 1400;

// -------- Timing --------
const unsigned long SEND_INTERVAL_MS = 5000;

WiFiClient client;
unsigned long lastSendMs = 0;

float clampPercent(float value) {
  if (value < 0.0f) return 0.0f;
  if (value > 100.0f) return 100.0f;
  return value;
}

float rawToPercent(int raw) {
  float percent = ((float)(SENSOR_DRY - raw) / (float)(SENSOR_DRY - SENSOR_WET)) * 100.0f;
  return clampPercent(percent);
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("[wifi] connecting");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("[wifi] connected, IP: ");
  Serial.println(WiFi.localIP());
}

void ensureServerConnection() {
  if (client.connected()) return;

  Serial.print("[tcp] connecting to ");
  Serial.print(SERVER_HOST);
  Serial.print(":");
  Serial.println(SERVER_PORT);

  if (!client.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("[tcp] connect failed");
    return;
  }

  Serial.println("[tcp] connected");
}

void sendReading() {
  int raw = analogRead(SENSOR_PIN);
  float moisturePercent = rawToPercent(raw);

  // Build compact JSON line without external libraries.
  String payload = "{";
  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  payload += "\"moisture_raw\":" + String(raw) + ",";
  payload += "\"moisture_percent\":" + String(moisturePercent, 2) + ",";
  payload += "\"sensor_pin\":" + String(SENSOR_PIN) + ",";
  payload += "\"firmware_version\":\"" + String(FIRMWARE_VERSION) + "\"";
  payload += "}";

  client.println(payload);
  Serial.print("[send] ");
  Serial.println(payload);

  unsigned long start = millis();
  while (!client.available() && (millis() - start) < 1500) {
    delay(10);
  }

  if (client.available()) {
    String ack = client.readStringUntil('\n');
    Serial.print("[ack] ");
    Serial.println(ack);
  } else {
    Serial.println("[ack] timeout/no response");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  analogReadResolution(12);

  ensureWifi();
  ensureServerConnection();
}

void loop() {
  ensureWifi();
  ensureServerConnection();

  unsigned long now = millis();
  if (now - lastSendMs >= SEND_INTERVAL_MS) {
    lastSendMs = now;

    if (client.connected()) {
      sendReading();
    }
  }

  if (!client.connected()) {
    client.stop();
  }

  delay(50);
}
