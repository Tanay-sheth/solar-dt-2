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

// Angle limits: -90° to +90° (0° is center -> 90° on servo)
const float PAN_MIN  = -90, PAN_MAX  = 90;
const float TILT_MIN = -90, TILT_MAX = 90;

// Pulse width (µs) for standard servos (0° to 180°)
const int SERVO_US_MIN = 544, SERVO_US_MAX = 2400;

// Settle delay (ms) after servo movement before power reading
const unsigned long SETTLE_MS = 60;
// ==============================================

Servo panServo;
Servo tiltServo;
Adafruit_INA219 ina219;
WiFiClient client;

bool inaOk = false;
float curPan = 0, curTilt = 0;

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

// INA219 reading, returned in watts.
float readPowerWatts() {
  if (!inaOk) return 0.0;
  float mW = ina219.getBusVoltage_V() * ina219.getCurrent_mA();  // V * mA = mW
  if (mW < 0) mW = 0;
  return mW / 1000.0;
}

void handleCommand(float pan, float tilt) {
  pan  = constrain(pan,  PAN_MIN,  PAN_MAX);
  tilt = constrain(tilt, TILT_MIN, TILT_MAX);

  // The gateway repeats the setpoint periodically. Only move servos if the target changed.
  bool moved = (fabs(pan - curPan) > 0.1) || (fabs(tilt - curTilt) > 0.1);
  if (moved) {
    // Map pan and tilt (-90..+90) to standard servo angles (0..180)
    int servoPan  = (int)round(pan + 90.0);
    int servoTilt = (int)round(tilt + 90.0);

    panServo.write(servoPan);
    tiltServo.write(servoTilt);

    curPan = pan;
    curTilt = tilt;
    Serial.printf("Move -> pan %.1f (servo %d), tilt %.1f (servo %d)\n", pan, servoPan, tilt, servoTilt);
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

  panServo.attach(PAN_PIN, SERVO_US_MIN, SERVO_US_MAX);
  tiltServo.attach(TILT_PIN, SERVO_US_MIN, SERVO_US_MAX);
  panServo.write((int)round(curPan + 90.0));
  tiltServo.write((int)round(curTilt + 90.0));

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

  // Drain any queued frames to only process the freshest setpoint
  String latestLine = "";
  while (client.available()) {
    String line = client.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      latestLine = line;
    }
  }

  if (latestLine.length() > 0) {
    float pan, tilt;
    if (parseCommand(latestLine, pan, tilt)) {
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
