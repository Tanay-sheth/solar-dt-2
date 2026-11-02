/*
  Solar tracker firmware for NodeMCU (ESP8266)

  What it does:
    1. Joins your Wi-Fi (phone hotspot, 2.4 GHz).
    2. Connects to the gateway on your laptop (TCP port 4001).
    3. Receives lines like   <pan,tilt>\n   and moves the two servos.
    4. Reads the INA219 and replies with   >P:<watts>\n

  Wiring (NodeMCU pin labels):
    Pan servo signal  -> D5
    Tilt servo signal -> D6
    INA219 SDA        -> D2
    INA219 SCL        -> D1
    INA219 VCC        -> 3V3
    Servo power       -> battery rail (NOT the NodeMCU 3V3 pin)
    All grounds       -> common ground

  Libraries needed (Sketch > Include Library > Manage Libraries):
    "Adafruit INA219"  (say yes to installing Adafruit BusIO too)
    Servo is already included with the ESP8266 board package.
*/

#include <ESP8266WiFi.h>
#include <Wire.h>
#include <Servo.h>
#include <Adafruit_INA219.h>

// ================= EDIT THESE =================
   const char* WIFI_SSID     = "Redmi Note 12 5G";
   const char* WIFI_PASSWORD = "Murthy@246";
   const char* GATEWAY_HOST  = "10.45.91.101";
const uint16_t GATEWAY_PORT = 4001;

const uint8_t PAN_PIN  = D5;
const uint8_t TILT_PIN = D6;

// Angle limits (same ranges the repo's mock panel uses)
const float PAN_MIN  = 0,  PAN_MAX  = 180;
const float TILT_MIN = 0,  TILT_MAX = 90;

// How long to wait after the servos move before reading power
const unsigned long SETTLE_MS = 800;
// ==============================================

Servo panServo;
Servo tiltServo;
Adafruit_INA219 ina219;
WiFiClient client;

bool inaOk = false;
float curPan = 90, curTilt = 45;

void connectWiFi() {
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Wi-Fi connected. ESP IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.print("Wi-Fi FAILED. Status code: ");
    Serial.println(WiFi.status());
  }
}

// Parses "<90,45>" into pan and tilt. Returns false if the line is malformed.
bool parseCommand(String line, float &pan, float &tilt) {
  line.trim();
  int n = line.length();
  if (n < 5 || line[0] != '<' || line[n - 1] != '>') return false;
  String body = line.substring(1, n - 1);
  int comma = body.indexOf(',');
  if (comma < 0) return false;
  pan  = body.substring(0, comma).toFloat();
  tilt = body.substring(comma + 1).toFloat();
  return true;
}

// Average of a few INA219 readings, returned in watts.
float readPowerWatts() {
  if (!inaOk) return 0.0;
  const int N = 5;
  float sum_mW = 0;
  for (int i = 0; i < N; i++) {
    sum_mW += ina219.getBusVoltage_V() * ina219.getCurrent_mA();  // V * mA = mW
    delay(10);
  }
  float mW = sum_mW / N;
  if (mW < 0) mW = 0;
  return mW / 1000.0;
}

// Moves both servos 1 degree at a time so the battery doesn't see a big current spike.
void moveSmooth(float pan, float tilt) {
  while (fabs(pan - curPan) > 0.5 || fabs(tilt - curTilt) > 0.5) {
    if (fabs(pan - curPan) > 0.5)   curPan  += (pan  > curPan)  ? 1 : -1;
    if (fabs(tilt - curTilt) > 0.5) curTilt += (tilt > curTilt) ? 1 : -1;
    panServo.write((int)round(curPan));
    tiltServo.write((int)round(curTilt));
    delay(15);
  }
}

void handleCommand(float pan, float tilt) {
  pan  = constrain(pan,  PAN_MIN,  PAN_MAX);
  tilt = constrain(tilt, TILT_MIN, TILT_MAX);

  // The gateway repeats the same setpoint every second, so only wait
  // for the servos if the angles actually changed.
  bool moved = (fabs(pan - curPan) > 0.5) || (fabs(tilt - curTilt) > 0.5);
  if (moved) {
    moveSmooth(pan, tilt);
    Serial.printf("Move -> pan %.1f, tilt %.1f\n", pan, tilt);
    delay(SETTLE_MS);
  }

  float watts = readPowerWatts();
  client.print(">P:");
  client.print(watts, 4);
  client.print("\n");
}

void setup() {
  Serial.begin(9600);
  delay(1000);
  Serial.println();
  Serial.println("Solar tracker firmware starting");

  Wire.begin(D2, D1);  // SDA = D2, SCL = D1
  inaOk = ina219.begin();
  Serial.println(inaOk ? "INA219 found" : "INA219 NOT found - will report 0 W");

  panServo.attach(PAN_PIN);
  tiltServo.attach(TILT_PIN);
  panServo.write((int)curPan);
  tiltServo.write((int)curTilt);

  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    return;
  }

  if (!client.connected()) {
    Serial.print("Connecting to gateway ");
    Serial.print(GATEWAY_HOST);
    Serial.print(":");
    Serial.println(GATEWAY_PORT);
    if (!client.connect(GATEWAY_HOST, GATEWAY_PORT)) {
      Serial.println("Gateway connect failed, retrying in 3 s");
      delay(3000);
      return;
    }
    client.setNoDelay(true);
    Serial.println("Gateway connected");
  }

  while (client.available()) {
    String line = client.readStringUntil('\n');
    float pan, tilt;
    if (parseCommand(line, pan, tilt)) {
      handleCommand(pan, tilt);
    }
  }
     static unsigned long lastDbg = 0;
   if (millis() - lastDbg > 2000) {
     lastDbg = millis();
     Serial.printf("INA ok: %d | bus %.3f V | shunt %.3f mV | current %.3f mA\n",
       inaOk, ina219.getBusVoltage_V(), ina219.getShuntVoltage_mV(), ina219.getCurrent_mA());
   }
  delay(10);
}
