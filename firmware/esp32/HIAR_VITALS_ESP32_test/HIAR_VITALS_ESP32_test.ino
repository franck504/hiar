// HIAR - Acquisition des signes vitaux (ESP32) - sketch dédié, test.
// DS18B20 : DATA sur GPIO23 (+ 4,7 kOhm vers 3V3).
// MAX30102 : SDA sur GPIO21, SCL sur GPIO22.
// SpO2 : NON implémenté, toujours NA. Mesures indicatives, non diagnostiques.
//
// Protocole série (115200 bauds, lignes terminées par \n) :
//   commandes : MEASURE, STOP, STATUS, PING
//   réponses  : READY,temp=0|1,pulse=0|1
//               STATE,RUNNING
//               RESULT,temperature_c=<x|NA>,heart_rate_bpm=<x|NA>,spo2_percent=NA
//               STATE,DONE | STATE,IDLE | ERROR,<raison> | PONG

#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "MAX30105.h"
#include "heartRate.h"

const int ONE_WIRE_PIN = 23;

const unsigned long SESSION_MAX_MS = 20000;
const long FINGER_MIN_IR = 50000;
const int BEATS_TARGET = 8;
const int BEATS_MIN = 5;
const float BPM_MIN = 40.0f;
const float BPM_MAX = 200.0f;
const float TEMP_MIN_C = 25.0f;   // plausibilité capteur, pas une plage clinique
const float TEMP_MAX_C = 45.0f;
const int RECENT_SIZE = 4;

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature tempSensor(&oneWire);
MAX30105 pulseSensor;

bool tempReady = false;
bool pulseReady = false;

bool running = false;
unsigned long sessionStart = 0;
unsigned long lastBeatMs = 0;
bool haveLastBeat = false;
int beatCount = 0;
float recent[RECENT_SIZE];
int recentIdx = 0;
int recentCount = 0;

String line = "";

void printReady() {
  Serial.print("READY,temp=");
  Serial.print(tempReady ? 1 : 0);
  Serial.print(",pulse=");
  Serial.println(pulseReady ? 1 : 0);
}

void resetSession() {
  haveLastBeat = false;
  lastBeatMs = 0;
  beatCount = 0;
  recentIdx = 0;
  recentCount = 0;
}

void startSession() {
  if (!tempReady && !pulseReady) {
    Serial.println("ERROR,NO_SENSOR");
    return;
  }
  resetSession();
  running = true;
  sessionStart = millis();
  Serial.println("STATE,RUNNING");
}

void finishSession() {
  running = false;

  bool tempOk = false;
  float t = 0.0f;
  if (tempReady) {
    tempSensor.requestTemperatures();
    t = tempSensor.getTempCByIndex(0);
    tempOk = (t != DEVICE_DISCONNECTED_C) && t >= TEMP_MIN_C && t <= TEMP_MAX_C;
  }

  bool bpmOk = false;
  float bpm = 0.0f;
  if (pulseReady && beatCount >= BEATS_MIN && recentCount > 0) {
    float sum = 0.0f;
    for (int i = 0; i < recentCount; i++) sum += recent[i];
    bpm = sum / recentCount;
    bpmOk = bpm >= BPM_MIN && bpm <= BPM_MAX;
  }

  Serial.print("RESULT,temperature_c=");
  if (tempOk) Serial.print(t, 1); else Serial.print("NA");
  Serial.print(",heart_rate_bpm=");
  if (bpmOk) Serial.print((int)(bpm + 0.5f)); else Serial.print("NA");
  Serial.println(",spo2_percent=NA");
  Serial.println("STATE,DONE");
}

void handleCommand(const String &cmd) {
  if (cmd == "MEASURE") {
    if (running) Serial.println("ERROR,BUSY"); else startSession();
  } else if (cmd == "STOP") {
    running = false;
    Serial.println("STATE,IDLE");
  } else if (cmd == "STATUS") {
    printReady();
  } else if (cmd == "PING") {
    Serial.println("PONG");
  } else if (cmd.length() > 0) {
    Serial.println("ERROR,UNKNOWN_COMMAND");
  }
}

void readSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      line.trim();
      handleCommand(line);
      line = "";
    } else if (line.length() < 24) {
      line += c;
    } else {
      line = "";
      Serial.println("ERROR,OVERFLOW");
    }
  }
}

void updateMeasure() {
  if (!running) return;

  if (millis() - sessionStart >= SESSION_MAX_MS) {
    finishSession();
    return;
  }

  if (pulseReady) {
    long ir = pulseSensor.getIR();
    if (ir < FINGER_MIN_IR) {
      // Pas de doigt : on repart de zéro pour ne jamais moyenner du bruit.
      resetSession();
      return;
    }
    if (checkForBeat(ir)) {
      unsigned long now = millis();
      if (haveLastBeat) {
        float bpm = 60000.0f / (float)(now - lastBeatMs);
        if (bpm >= BPM_MIN && bpm <= BPM_MAX) {
          recent[recentIdx] = bpm;
          recentIdx = (recentIdx + 1) % RECENT_SIZE;
          if (recentCount < RECENT_SIZE) recentCount++;
          beatCount++;
        }
      }
      lastBeatMs = now;
      haveLastBeat = true;
      if (beatCount >= BEATS_TARGET) finishSession();
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);

  tempSensor.begin();
  tempReady = tempSensor.getDeviceCount() > 0;

  Wire.begin();  // SDA 21, SCL 22 par défaut
  pulseReady = pulseSensor.begin(Wire, I2C_SPEED_FAST);
  if (pulseReady) {
    pulseSensor.setup();
    pulseSensor.setPulseAmplitudeRed(0x0A);
    pulseSensor.setPulseAmplitudeGreen(0);
  }

  Serial.println("HIAR VITALS test (SpO2 non implemente)");
  printReady();
}

void loop() {
  readSerial();
  updateMeasure();
}
