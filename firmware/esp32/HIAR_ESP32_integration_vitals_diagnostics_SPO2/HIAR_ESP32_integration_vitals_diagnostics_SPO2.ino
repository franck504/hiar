// ============================================
// HIAR - ESP32 INTEGRATION NAVIGATION + VITAUX + DIAGNOSTICS + SpO2
// Fichier : HIAR_ESP32_integration_vitals_diagnostics_SPO2.ino
// Carte   : ESP32 Dev Module / ESP32-WROOM-32
// Core    : Arduino ESP32 3.x
// Baud    : 115200
//
// Navigation  : L298N + HC-SR04 + IR analogiques
// Vitaux      : DS18B20 + MAX30102
// Diagnostics : Detection dynamique a chaud 1-Wire (DS18B20) + I2C ACK 0x57 (MAX30102)
//               + Etat HC-SR04 + IR + Moteurs via commandes STATUS et HEALTH
// SpO2        : ESTIMATION par ratio R = (AC/DC rouge) / (AC/DC IR),
//               formule empirique, NON calibree cliniquement.
//               Lecture FIFO rouge+IR, LED 0x24, 100 Hz.
// ============================================

#include <Arduino.h>
#include <string.h>
#include <math.h>
#include "driver/gpio.h"
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "MAX30105.h"
#include "heartRate.h"

// ============================================
// ENUMS
// ============================================

enum UsState {
  US_IDLE,
  US_WAITING_ECHO
};

enum MotionMode {
  MODE_IDLE,
  MODE_FORWARD,
  MODE_BACKWARD,
  MODE_LEFT,
  MODE_RIGHT
};

enum VitalsState {
  VITALS_IDLE,
  VITALS_ACQUIRING,
  VITALS_TEMP_WAIT,
  VITALS_DONE
};

// ============================================
// BROCHAGE MOTEURS - L298N
// ============================================

const int MOTOR_A_EN  = 25;
const int MOTOR_A_IN1 = 26;
const int MOTOR_A_IN2 = 27;

const int MOTOR_B_EN  = 19;
const int MOTOR_B_IN1 = 14;
const int MOTOR_B_IN2 = 18;

// ============================================
// HC-SR04
// ============================================

const int ULTRASONIC_TRIG = 13;
const int ULTRASONIC_ECHO = 34;

const unsigned long ULTRASONIC_TIMEOUT_US = 25000;
const unsigned long ULTRASONIC_MIN_INTERVAL_US = 60000;

// ============================================
// CAPTEURS IR ANALOGIQUES
// ============================================

const int IR_LEFT_PIN  = 32;
const int IR_RIGHT_PIN = 33;

const int IR_LEFT_THRESHOLD  = 1200;
const int IR_RIGHT_THRESHOLD = 1200;

// 1 = CLEAR ; 0 = OBSTACLE

int lastIrLeftState  = -1;
int lastIrRightState = -1;

unsigned long lastIrPublish = 0;
const unsigned long IR_PUBLISH_INTERVAL = 100;

unsigned long lastIrRawPublish = 0;
const unsigned long IR_RAW_PUBLISH_INTERVAL = 250;

// ============================================
// PWM ET VITESSE
// ============================================

const int PWM_FREQ = 20000;
const int PWM_RESOLUTION = 8;

const int MOTOR_SPEED_PERCENT = 65;
const int MOTOR_SPEED =
  (255 * MOTOR_SPEED_PERCENT) / 100;

// ============================================
// SECURITE NAVIGATION
// ============================================

const unsigned long MAX_MOVE_DURATION = 2000;

const float OBSTACLE_STOP_CM = 25.0f;

const unsigned long MAX_DISTANCE_AGE_MS = 200;

const int MAX_INVALID_READS = 3;

const unsigned long GUARD_INTERVAL = 60;

const unsigned long REVERSE_PAUSE_MS = 150;

// ============================================
// MODE AUTONOME
// ============================================

bool autoMode = false;

// ============================================
// RECEPTION SERIE
// ============================================

const size_t RX_MAX = 32;

char rxBuffer[RX_MAX + 1];

size_t rxLen = 0;

bool rxDiscard = false;

// ============================================
// ULTRASON - VARIABLES ISR
// ============================================

volatile UsState usState = US_IDLE;

volatile unsigned long usEchoStartUs = 0;
volatile unsigned long usEchoDurationUs = 0;

volatile bool usResultReady = false;
volatile bool usResultValid = false;
volatile bool usEchoStarted = false;

unsigned long usTriggerTimeUs = 0;
unsigned long lastUsTriggerUs = 0;

// ============================================
// ETAT MOTEURS
// ============================================

MotionMode motionMode = MODE_IDLE;

unsigned long movementStartTime = 0;

bool motionPending = false;

MotionMode pendingMotion = MODE_IDLE;

unsigned long pendingSince = 0;

// ============================================
// GARDE HC-SR04
// ============================================

float guardBuffer[3] = {
  -1, -1, -1
};

int guardBufIdx = 0;

int invalidCount = 0;

unsigned long lastGuardTrigger = 0;

float lastFilteredDistance = -1.0f;
float lastRawDistance = -1.0f;

unsigned long lastValidDistanceMs = 0;

bool hasValidDistance = false;

// ============================================
// SIGNES VITAUX - CONSTANTES
// ============================================

const int ONE_WIRE_PIN = 23;

const unsigned long SESSION_MAX_MS = 20000;

const long FINGER_MIN_IR = 15000;   // valeur mesuree : doigt pose ~28000 (a confirmer doigt retire)

const int BEATS_TARGET = 8;
const int BEATS_MIN = 5;

const float BPM_MIN = 40.0f;
const float BPM_MAX = 200.0f;

const float TEMP_MIN_C = 25.0f;
const float TEMP_MAX_C = 45.0f;

const int RECENT_SIZE = 4;

const unsigned long TEMP_CONVERSION_MS = 750;

// ============================================
// SpO2 - CONSTANTES ET ETAT
// ============================================

#define SPO2_DEBUG 1   // 1 = ligne DEBUG,spo2_R=... ; 0 = silence

const uint8_t  PPG_LED_AMPLITUDE   = 0x24;    // rouge + IR (baisser a 0x1F si saturation)
const uint32_t PPG_SATURATION      = 260000;  // ADC 18 bits ~262143
const float    SPO2_DC_ALPHA       = 0.02f;   // filtre passe-bas IIR (estimation DC)
const int      SPO2_SETTLE_SAMPLES = 100;     // ~1 s a 100 Hz, stabilisation du DC
const uint32_t SPO2_MIN_SAMPLES    = 300;     // ~3 s d'echantillons utiles
const float    SPO2_R_MIN          = 0.3f;
const float    SPO2_R_MAX          = 1.6f;
const float    SPO2_MIN_VALID      = 80.0f;

float    spo2DcRed = 0.0f;
float    spo2DcIr  = 0.0f;
bool     spo2DcInit = false;
int      spo2Settle = 0;
uint32_t spo2N = 0;
uint32_t spo2Saturated = 0;
double   spo2SumAcRed2 = 0.0;
double   spo2SumAcIr2  = 0.0;
double   spo2SumDcRed  = 0.0;
double   spo2SumDcIr   = 0.0;

// ============================================
// SIGNES VITAUX - OBJETS ET ETAT
// ============================================

OneWire oneWire(ONE_WIRE_PIN);

DallasTemperature tempSensor(&oneWire);

MAX30105 pulseSensor;

bool vitalsTempReady = false;
bool vitalsPulseReady = false;
bool pwmAReady = false;
bool pwmBReady = false;
const uint8_t MAX30102_I2C_ADDR = 0x57;

VitalsState vitalsState = VITALS_IDLE;

unsigned long vitalsSessionStart = 0;

unsigned long vitalsTempRequestMs = 0;

unsigned long vitalsLastBeatMs = 0;

bool vitalsHaveLastBeat = false;

int vitalsBeatCount = 0;

float vitalsRecent[RECENT_SIZE];

int vitalsRecentIdx = 0;
int vitalsRecentCount = 0;

// ============================================
// DECLARATIONS
// ============================================

void requestMotion(MotionMode mode);
void applyMotion(MotionMode mode);
void setMotion(MotionMode mode);

void vitalsPrintReady();
void vitalsProbeSensors();
void printHealthStatus(bool probe = true);
void vitalsResetBeatData();
void vitalsStart();
void vitalsFinishAcquisition();
void vitalsPublishResult();
void vitalsCancel();
void vitalsUpdate();

bool vitalsIsBusy();

// ============================================
// ISR ULTRASON
// ============================================

void IRAM_ATTR ultrasonicISR() {

  unsigned long now = micros();

  if (usState != US_WAITING_ECHO) {
    return;
  }

  if (gpio_get_level(
        (gpio_num_t)ULTRASONIC_ECHO) == 1) {

    usEchoStartUs = now;
    usEchoStarted = true;

  } else if (usEchoStarted) {

    usEchoDurationUs = now - usEchoStartUs;

    usResultValid = true;
    usResultReady = true;

    usEchoStarted = false;

    usState = US_IDLE;
  }
}

// ============================================
// DEMANDE ULTRASON
// ============================================

bool requestUltrasonic() {

  if (usState != US_IDLE) {
    return false;
  }

  unsigned long now = micros();

  if (now - lastUsTriggerUs <
      ULTRASONIC_MIN_INTERVAL_US) {
    return false;
  }

  lastUsTriggerUs = now;

  noInterrupts();

  usResultReady = false;
  usResultValid = false;
  usEchoStarted = false;

  usTriggerTimeUs = micros();

  usState = US_WAITING_ECHO;

  interrupts();

  digitalWrite(ULTRASONIC_TRIG, HIGH);

  delayMicroseconds(10);

  digitalWrite(ULTRASONIC_TRIG, LOW);

  return true;
}

// ============================================
// MISE A JOUR ULTRASON
// ============================================

void updateUltrasonic() {

  if (usState == US_WAITING_ECHO &&
      micros() - usTriggerTimeUs >
      ULTRASONIC_TIMEOUT_US) {

    noInterrupts();

    if (usState == US_WAITING_ECHO) {

      usState = US_IDLE;

      usEchoStarted = false;

      usResultValid = false;
      usResultReady = true;
    }

    interrupts();
  }
}

// ============================================
// RECUPERATION DISTANCE
// ============================================

bool getUltrasonicDistance(float &dist) {

  if (!usResultReady) {
    return false;
  }

  noInterrupts();

  usResultReady = false;

  bool valid = usResultValid;

  unsigned long dur = usEchoDurationUs;

  interrupts();

  if (!valid || dur == 0) {

    dist = -1.0f;

  } else {

    dist = (dur * 0.0343f) / 2.0f;
  }

  return true;
}

// ============================================
// COMMANDE MOTEURS
// CORRECTION : TIMEOUT NON REINITIALISE
// PAR UNE COMMANDE REPETEE IDENTIQUE
// ============================================

void setMotion(MotionMode mode) {

  // Mémoriser le mode précédent avant modification.
  MotionMode previousMode = motionMode;

  motionPending = false;

  motionMode = mode;

  switch (mode) {

    case MODE_IDLE:

      ledcWrite(MOTOR_A_EN, 0);
      ledcWrite(MOTOR_B_EN, 0);

      digitalWrite(MOTOR_A_IN1, LOW);
      digitalWrite(MOTOR_A_IN2, LOW);

      digitalWrite(MOTOR_B_IN1, LOW);
      digitalWrite(MOTOR_B_IN2, LOW);

      break;

    case MODE_FORWARD:

      digitalWrite(MOTOR_A_IN1, HIGH);
      digitalWrite(MOTOR_A_IN2, LOW);

      digitalWrite(MOTOR_B_IN1, HIGH);
      digitalWrite(MOTOR_B_IN2, LOW);

      ledcWrite(MOTOR_A_EN, MOTOR_SPEED);
      ledcWrite(MOTOR_B_EN, MOTOR_SPEED);

      break;

    case MODE_BACKWARD:

      digitalWrite(MOTOR_A_IN1, LOW);
      digitalWrite(MOTOR_A_IN2, HIGH);

      digitalWrite(MOTOR_B_IN1, LOW);
      digitalWrite(MOTOR_B_IN2, HIGH);

      ledcWrite(MOTOR_A_EN, MOTOR_SPEED);
      ledcWrite(MOTOR_B_EN, MOTOR_SPEED);

      break;

    case MODE_LEFT:

      digitalWrite(MOTOR_A_IN1, LOW);
      digitalWrite(MOTOR_A_IN2, HIGH);

      digitalWrite(MOTOR_B_IN1, HIGH);
      digitalWrite(MOTOR_B_IN2, LOW);

      ledcWrite(MOTOR_A_EN, MOTOR_SPEED);
      ledcWrite(MOTOR_B_EN, MOTOR_SPEED);

      break;

    case MODE_RIGHT:

      digitalWrite(MOTOR_A_IN1, HIGH);
      digitalWrite(MOTOR_A_IN2, LOW);

      digitalWrite(MOTOR_B_IN1, LOW);
      digitalWrite(MOTOR_B_IN2, HIGH);

      ledcWrite(MOTOR_A_EN, MOTOR_SPEED);
      ledcWrite(MOTOR_B_EN, MOTOR_SPEED);

      break;
  }

  // Réinitialiser le chronomètre uniquement au démarrage
  // d'un mouvement ou lors d'un changement de direction.
  // Une commande répétée du même mouvement ne le réinitialise pas.
  if (mode != MODE_IDLE && mode != previousMode) {
    movementStartTime = millis();
  }
}

// ============================================
// DISTANCE FILTREE
// ============================================

float computeGuardDistance() {

  float tmp[3];

  int n = 0;

  for (int i = 0; i < 3; i++) {

    if (guardBuffer[i] >= 0) {
      tmp[n++] = guardBuffer[i];
    }
  }

  if (n == 0) return -1.0f;

  if (n == 1) return tmp[0];

  if (n == 2) {
    return (tmp[0] + tmp[1]) * 0.5f;
  }

  float a = tmp[0];
  float b = tmp[1];
  float c = tmp[2];

  if (a > b) {
    float t = a;
    a = b;
    b = t;
  }

  if (b > c) {
    float t = b;
    b = c;
    c = t;
  }

  if (a > b) {
    float t = a;
    a = b;
    b = t;
  }

  return b;
}

// ============================================
// GARDE AVANT HC-SR04
// ============================================

void updateForwardGuard() {

  float d;

  unsigned long now = millis();

  if (getUltrasonicDistance(d)) {

    if (d < 0.0f) {

      invalidCount++;

      hasValidDistance = false;

      lastRawDistance = -1.0f;
      lastFilteredDistance = -1.0f;

      guardBuffer[0] = -1.0f;
      guardBuffer[1] = -1.0f;
      guardBuffer[2] = -1.0f;

      guardBufIdx = 0;

      if (motionMode == MODE_FORWARD) {

        setMotion(MODE_IDLE);

        Serial.println("SAFETY,SENSOR_INVALID");

      } else if (invalidCount == MAX_INVALID_READS) {

        Serial.println("SAFETY,SENSOR_INVALID");
      }

    } else {

      invalidCount = 0;

      lastRawDistance = d;

      lastValidDistanceMs = now;

      hasValidDistance = true;

      guardBuffer[guardBufIdx] = d;

      guardBufIdx = (guardBufIdx + 1) % 3;

      lastFilteredDistance = computeGuardDistance();

      Serial.printf(
        "DIST,%.1f\n",
        lastFilteredDistance
      );

      if (motionMode == MODE_FORWARD &&
          (d < OBSTACLE_STOP_CM ||
           lastFilteredDistance < OBSTACLE_STOP_CM)) {

        setMotion(MODE_IDLE);

        Serial.printf(
          "SAFETY,OBSTACLE,%.1f\n",
          d
        );
      }
    }
  }

  now = millis();

  if (hasValidDistance &&
      now - lastValidDistanceMs >
      MAX_DISTANCE_AGE_MS) {

    hasValidDistance = false;

    lastRawDistance = -1.0f;
    lastFilteredDistance = -1.0f;

    guardBuffer[0] = -1.0f;
    guardBuffer[1] = -1.0f;
    guardBuffer[2] = -1.0f;

    guardBufIdx = 0;

    if (motionMode == MODE_FORWARD) {

      setMotion(MODE_IDLE);

      Serial.println("SAFETY,SENSOR_STALE");
    }
  }

  if (now - lastGuardTrigger < GUARD_INTERVAL) {
    return;
  }

  if (requestUltrasonic()) {
    lastGuardTrigger = now;
  }
}

// ============================================
// LECTURE IR
// ============================================

int readIrState(int pin) {

  int rawValue = analogRead(pin);

  int threshold =
    (pin == IR_LEFT_PIN)
      ? IR_LEFT_THRESHOLD
      : IR_RIGHT_THRESHOLD;

  return rawValue > threshold ? 1 : 0;
}

// ============================================
// PUBLICATION IR
// ============================================

void publishIrStates() {

  unsigned long now = millis();

  int leftRaw = analogRead(IR_LEFT_PIN);
  int rightRaw = analogRead(IR_RIGHT_PIN);

  int leftState =
    leftRaw > IR_LEFT_THRESHOLD ? 1 : 0;

  int rightState =
    rightRaw > IR_RIGHT_THRESHOLD ? 1 : 0;

  if (now - lastIrRawPublish >=
      IR_RAW_PUBLISH_INTERVAL) {

    Serial.print("IR_RAW,LEFT,");
    Serial.println(leftRaw);

    Serial.print("IR_RAW,RIGHT,");
    Serial.println(rightRaw);

    lastIrRawPublish = now;
  }

  bool publishPeriodic =
    (now - lastIrPublish >= IR_PUBLISH_INTERVAL);

  if (leftState != lastIrLeftState ||
      publishPeriodic) {

    Serial.printf("IR,LEFT,%d\n", leftState);

    lastIrLeftState = leftState;
  }

  if (rightState != lastIrRightState ||
      publishPeriodic) {

    Serial.printf("IR,RIGHT,%d\n", rightState);

    lastIrRightState = rightState;
  }

  if (publishPeriodic) {
    lastIrPublish = now;
  }
}

// ============================================
// ETAT ACQUISITION VITAUX
// ============================================

bool vitalsIsBusy() {

  return (
    vitalsState == VITALS_ACQUIRING ||
    vitalsState == VITALS_TEMP_WAIT
  );
}

// ============================================
// SECURITE AVANT
// ============================================

bool forwardSafetyClear() {

  return hasValidDistance &&
         millis() - lastValidDistanceMs <=
         MAX_DISTANCE_AGE_MS &&
         lastRawDistance >= OBSTACLE_STOP_CM &&
         lastFilteredDistance >= OBSTACLE_STOP_CM;
}

// ============================================
// APPLICATION MOUVEMENT
// ============================================

void applyMotion(MotionMode mode) {

  if (vitalsIsBusy()) {

    setMotion(MODE_IDLE);

    Serial.println("REJECTED,MEASURING");

    return;
  }

  if (mode == MODE_FORWARD &&
      !forwardSafetyClear()) {

    setMotion(MODE_IDLE);

    Serial.println("REJECTED,FORWARD_UNSAFE");

    return;
  }

  setMotion(mode);
}

// ============================================
// DEMANDE MOUVEMENT
// ============================================

void requestMotion(MotionMode mode) {

  if (vitalsIsBusy()) {

    Serial.println("REJECTED,MEASURING");

    return;
  }

  bool reversing =
    mode != MODE_IDLE &&
    motionMode != MODE_IDLE &&
    mode != motionMode;

  if (reversing) {

    setMotion(MODE_IDLE);

    pendingMotion = mode;

    pendingSince = millis();

    motionPending = true;

  } else {

    applyMotion(mode);
  }
}

// ============================================
// MOUVEMENT EN ATTENTE
// ============================================

void updatePendingMotion() {

  if (vitalsIsBusy()) {

    if (motionPending) {
      motionPending = false;
    }

    return;
  }

  if (motionPending &&
      millis() - pendingSince >=
      REVERSE_PAUSE_MS) {

    MotionMode m = pendingMotion;

    motionPending = false;

    applyMotion(m);
  }
}

// ============================================
// DECISION AUTONOME
// ============================================

void decideAutonomousMotion() {

  if (!autoMode) return;

  if (vitalsIsBusy()) return;

  if (!hasValidDistance ||
      millis() - lastValidDistanceMs >
      MAX_DISTANCE_AGE_MS) {

    if (motionMode == MODE_FORWARD) {

      setMotion(MODE_IDLE);

      Serial.println("SAFETY,SENSOR_STALE");
    }

    return;
  }

  bool frontClear =
    lastRawDistance >= OBSTACLE_STOP_CM &&
    lastFilteredDistance >= OBSTACLE_STOP_CM;

  int irLeft = readIrState(IR_LEFT_PIN);
  int irRight = readIrState(IR_RIGHT_PIN);

  if (frontClear) {

    if (motionMode != MODE_FORWARD) {

      requestMotion(MODE_FORWARD);

      Serial.println("AUTO,FORWARD");
    }

  } else {

    if (irLeft == 1 && irRight == 0) {

      if (motionMode != MODE_LEFT) {

        requestMotion(MODE_LEFT);

        Serial.println("AUTO,LEFT");
      }

    } else if (irRight == 1 && irLeft == 0) {

      if (motionMode != MODE_RIGHT) {

        requestMotion(MODE_RIGHT);

        Serial.println("AUTO,RIGHT");
      }

    } else if (irLeft == 1 && irRight == 1) {

      if (motionMode != MODE_LEFT) {

        requestMotion(MODE_LEFT);

        Serial.println("AUTO,LEFT_PREF");
      }

    } else {

      if (motionMode != MODE_IDLE) {

        setMotion(MODE_IDLE);

        Serial.println("AUTO,STOP_BOTH_BLOCKED");
      }
    }
  }
}

// ============================================
// SpO2 - INIT CAPTEUR + CALCUL
// ============================================

// Initialisation MAX30102 : mode rouge + IR, 100 Hz effectifs
// (400 sps / moyenne 4), LED a PPG_LED_AMPLITUDE.
bool vitalsBeginPulse() {

  if (!pulseSensor.begin(Wire, I2C_SPEED_FAST)) {
    return false;
  }

  // powerLevel, sampleAverage, ledMode (2 = rouge+IR),
  // sampleRate, pulseWidth, adcRange
  pulseSensor.setup(PPG_LED_AMPLITUDE, 4, 2, 400, 411, 16384);

  pulseSensor.setPulseAmplitudeRed(PPG_LED_AMPLITUDE);
  pulseSensor.setPulseAmplitudeIR(PPG_LED_AMPLITUDE);
  pulseSensor.setPulseAmplitudeGreen(0);

  return true;
}

void spo2Reset() {

  spo2DcInit = false;
  spo2Settle = 0;
  spo2N = 0;
  spo2Saturated = 0;

  spo2SumAcRed2 = 0.0;
  spo2SumAcIr2  = 0.0;
  spo2SumDcRed  = 0.0;
  spo2SumDcIr   = 0.0;
}

void spo2AddSample(uint32_t red, uint32_t ir) {

  if (red >= PPG_SATURATION || ir >= PPG_SATURATION) {
    spo2Saturated++;
  }

  // Premier echantillon : initialiser le DC
  if (!spo2DcInit) {

    spo2DcRed = (float)red;
    spo2DcIr  = (float)ir;
    spo2DcInit = true;

    return;
  }

  // DC = moyenne lissee ; AC = echantillon - DC
  spo2DcRed += SPO2_DC_ALPHA * ((float)red - spo2DcRed);
  spo2DcIr  += SPO2_DC_ALPHA * ((float)ir  - spo2DcIr);

  // Laisser le DC se stabiliser avant d'accumuler
  if (spo2Settle < SPO2_SETTLE_SAMPLES) {

    spo2Settle++;

    return;
  }

  float acRed = (float)red - spo2DcRed;
  float acIr  = (float)ir  - spo2DcIr;

  spo2SumAcRed2 += (double)acRed * (double)acRed;
  spo2SumAcIr2  += (double)acIr  * (double)acIr;

  spo2SumDcRed += spo2DcRed;
  spo2SumDcIr  += spo2DcIr;

  spo2N++;
}

bool spo2Compute(float &spo2) {

  if (spo2N < SPO2_MIN_SAMPLES) return false;

  // Signal sature : mesure rejetee
  if (spo2Saturated > 0) return false;

  float acRed = (float)sqrt(spo2SumAcRed2 / (double)spo2N);
  float acIr  = (float)sqrt(spo2SumAcIr2  / (double)spo2N);

  float dcRed = (float)(spo2SumDcRed / (double)spo2N);
  float dcIr  = (float)(spo2SumDcIr  / (double)spo2N);

  if (dcRed <= 0.0f || dcIr <= 0.0f || acIr <= 0.0f) return false;

  float R = (acRed / dcRed) / (acIr / dcIr);

#if SPO2_DEBUG
  Serial.printf(
    "DEBUG,spo2_R=%.3f,n=%lu,acR=%.1f,acIR=%.1f,dcR=%.0f,dcIR=%.0f\n",
    R, (unsigned long)spo2N, acRed, acIr, dcRed, dcIr
  );
#endif

  if (R < SPO2_R_MIN || R > SPO2_R_MAX) return false;

  // Formule empirique (type Maxim) - NON calibree cliniquement
  float s = -45.060f * R * R + 30.354f * R + 94.845f;

  if (s > 100.0f) s = 100.0f;

  if (s < SPO2_MIN_VALID) return false;

  spo2 = s;

  return true;
}

// ============================================
// VITAUX - ETAT CAPTEURS
// ============================================

void vitalsPrintReady() {

  Serial.print("READY,temp=");

  Serial.print(vitalsTempReady ? 1 : 0);

  Serial.print(",pulse=");

  Serial.println(vitalsPulseReady ? 1 : 0);
}

// ============================================
// DIAGNOSTICS - SONDE DYNAMIQUE A CHAUD (OPTION B)
// ============================================

void vitalsProbeSensors() {
  // Ne jamais interrompre une acquisition de constantes en cours
  if (vitalsIsBusy()) {
    return;
  }

  // 1. Sonde 1-Wire DS18B20
  tempSensor.begin();
  tempSensor.setWaitForConversion(false);
  vitalsTempReady = (tempSensor.getDeviceCount() > 0);

  // 2. Sonde ACK I2C MAX30102 (adresse 0x57)
  Wire.beginTransmission(MAX30102_I2C_ADDR);
  bool pulseAck = (Wire.endTransmission() == 0);

  if (pulseAck) {
    if (!vitalsPulseReady) {
      vitalsPulseReady = vitalsBeginPulse();
    }
  } else {
    vitalsPulseReady = false;
  }
}

const char* motionModeLabel(MotionMode mode) {
  switch (mode) {
    case MODE_FORWARD:  return "FWD";
    case MODE_BACKWARD: return "BWD";
    case MODE_LEFT:     return "LEFT";
    case MODE_RIGHT:    return "RIGHT";
    default:            return "IDLE";
  }
}

void printHealthStatus(bool probe) {
  if (probe) {
    vitalsProbeSensors();
  }

  unsigned long now = millis();
  bool usHealthy = hasValidDistance &&
                   (now - lastValidDistanceMs <= 2000) &&
                   (invalidCount < MAX_INVALID_READS);

  int irLeftRaw = analogRead(IR_LEFT_PIN);
  int irRightRaw = analogRead(IR_RIGHT_PIN);
  int irLeftState = (irLeftRaw > IR_LEFT_THRESHOLD) ? 1 : 0;
  int irRightState = (irRightRaw > IR_RIGHT_THRESHOLD) ? 1 : 0;

  Serial.printf(
    "HEALTH,temp=%d,pulse=%d,us=%d,dist=%.1f,ir_l=%d,ir_r=%d,ir_l_raw=%d,ir_r_raw=%d,motors=%d,mode=%s\n",
    vitalsTempReady ? 1 : 0,
    vitalsPulseReady ? 1 : 0,
    usHealthy ? 1 : 0,
    usHealthy ? lastFilteredDistance : -1.0f,
    irLeftState,
    irRightState,
    irLeftRaw,
    irRightRaw,
    (pwmAReady && pwmBReady) ? 1 : 0,
    motionModeLabel(motionMode)
  );
}

// ============================================
// VITAUX - RESET BATTEMENTS (+ SpO2)
// ============================================

void vitalsResetBeatData() {

  vitalsHaveLastBeat = false;

  vitalsLastBeatMs = 0;

  vitalsBeatCount = 0;

  vitalsRecentIdx = 0;

  vitalsRecentCount = 0;

  // La SpO2 repart de zero avec les battements
  spo2Reset();
}

// ============================================
// VITAUX - DEMARRAGE
// ============================================

void vitalsStart() {

  if (!vitalsTempReady && !vitalsPulseReady) {

    Serial.println("ERROR,NO_SENSOR");

    return;
  }

  // Vider le FIFO pour ne pas traiter d'echantillons perimes
  if (vitalsPulseReady) {
    pulseSensor.clearFIFO();
  }

  vitalsResetBeatData();

  vitalsState = VITALS_ACQUIRING;

  vitalsSessionStart = millis();

  Serial.println("STATE,RUNNING");
}

// ============================================
// VITAUX - PUBLICATION RESULTAT
// ============================================

void vitalsPublishResult() {

  bool tempOk = false;

  float t = 0.0f;

  if (vitalsTempReady) {

    t = tempSensor.getTempCByIndex(0);

    tempOk =
      (t != DEVICE_DISCONNECTED_C) &&
      t >= TEMP_MIN_C &&
      t <= TEMP_MAX_C;
  }

  bool bpmOk = false;

  float bpm = 0.0f;

  if (vitalsPulseReady &&
      vitalsBeatCount >= BEATS_MIN &&
      vitalsRecentCount > 0) {

    float sum = 0.0f;

    for (int i = 0; i < vitalsRecentCount; i++) {
      sum += vitalsRecent[i];
    }

    bpm = sum / vitalsRecentCount;

    bpmOk =
      bpm >= BPM_MIN &&
      bpm <= BPM_MAX;
  }

  float spo2 = 0.0f;

  bool spo2Ok = vitalsPulseReady && spo2Compute(spo2);

  Serial.print("RESULT,temperature_c=");

  if (tempOk) {
    Serial.print(t, 1);
  } else {
    Serial.print("NA");
  }

  Serial.print(",heart_rate_bpm=");

  if (bpmOk) {
    Serial.print((int)(bpm + 0.5f));
  } else {
    Serial.print("NA");
  }

  Serial.print(",spo2_percent=");

  if (spo2Ok) {
    Serial.println((int)(spo2 + 0.5f));
  } else {
    Serial.println("NA");
  }

  Serial.println("STATE,DONE");

  // L'état DONE sera remis à IDLE
  // au prochain cycle de vitalsUpdate().
  vitalsState = VITALS_DONE;
}

// ============================================
// VITAUX - FIN ACQUISITION CARDIAQUE
// ============================================

void vitalsFinishAcquisition() {

  if (vitalsState != VITALS_ACQUIRING) {
    return;
  }

  if (vitalsTempReady) {

    // Conversion DS18B20 non bloquante
    tempSensor.setWaitForConversion(false);

    tempSensor.requestTemperatures();

    vitalsTempRequestMs = millis();

    vitalsState = VITALS_TEMP_WAIT;

  } else {

    // Pas de température disponible.
    // Publier BPM/SpO2 si exploitables, sinon NA.
    vitalsPublishResult();
  }
}

// ============================================
// VITAUX - ANNULATION
// ============================================

void vitalsCancel() {

  if (vitalsIsBusy()) {

    vitalsState = VITALS_IDLE;

    Serial.println("STATE,IDLE");

  } else {

    vitalsState = VITALS_IDLE;
  }
}

// ============================================
// VITAUX - MISE A JOUR NON BLOQUANTE
// ============================================

void vitalsUpdate() {

  // Fin de cycle : DONE -> IDLE
  if (vitalsState == VITALS_DONE) {

    vitalsState = VITALS_IDLE;

    return;
  }

  if (vitalsState == VITALS_IDLE) {
    return;
  }

  unsigned long now = millis();

  // ----------------------------------------
  // PHASE 1 : ACQUISITION CARDIAQUE + SpO2
  // ----------------------------------------

  if (vitalsState == VITALS_ACQUIRING) {

    // Timeout de la phase cardiaque uniquement
    if (now - vitalsSessionStart >=
        SESSION_MAX_MS) {

      vitalsFinishAcquisition();

      return;
    }

    if (vitalsPulseReady) {

      // Lecture FIFO : rouge + IR synchronises
      pulseSensor.check();

      while (pulseSensor.available()) {

        uint32_t red = pulseSensor.getFIFORed();
        uint32_t ir  = pulseSensor.getFIFOIR();

        pulseSensor.nextSample();

        if ((long)ir < FINGER_MIN_IR) {

          // Aucun doigt : éliminer battements et SpO2
          // sans remettre à zéro le chronomètre.
          vitalsResetBeatData();

          continue;
        }

        spo2AddSample(red, ir);

        if (checkForBeat((int32_t)ir)) {

          if (vitalsHaveLastBeat) {

            float bpm =
              60000.0f /
              (float)(now - vitalsLastBeatMs);

            if (bpm >= BPM_MIN && bpm <= BPM_MAX) {

              vitalsRecent[vitalsRecentIdx] = bpm;

              vitalsRecentIdx =
                (vitalsRecentIdx + 1) % RECENT_SIZE;

              if (vitalsRecentCount < RECENT_SIZE) {
                vitalsRecentCount++;
              }

              vitalsBeatCount++;
            }
          }

          vitalsLastBeatMs = now;

          vitalsHaveLastBeat = true;

          if (vitalsBeatCount >= BEATS_TARGET) {

            vitalsFinishAcquisition();

            return;
          }
        }
      }
    }

    // Si MAX30102 absent :
    // attente jusqu'au timeout global.
    return;
  }

  // ----------------------------------------
  // PHASE 2 : ATTENTE CONVERSION TEMPERATURE
  // ----------------------------------------

  if (vitalsState == VITALS_TEMP_WAIT) {

    // Le timeout global de 20 secondes ne doit
    // plus interrompre cette conversion.
    if (now - vitalsTempRequestMs >=
        TEMP_CONVERSION_MS) {

      vitalsPublishResult();

      return;
    }
  }
}

// ============================================
// COMMANDES SERIE
// ============================================

void processCommand(const char* raw) {

  char buf[RX_MAX + 1];

  size_t n = strlen(raw);

  if (n > RX_MAX) {
    n = RX_MAX;
  }

  size_t j = 0;

  for (size_t i = 0; i < n; i++) {

    char c = raw[i];

    if (c >= 'a' && c <= 'z') {
      c -= 32;
    }

    buf[j++] = c;
  }

  buf[j] = '\0';

  size_t start = 0;

  size_t end = j;

  while (start < end &&
         (buf[start] == ' ' ||
          buf[start] == '\t')) {
    start++;
  }

  while (end > start &&
         (buf[end - 1] == ' ' ||
          buf[end - 1] == '\t')) {
    end--;
  }

  buf[end] = '\0';

  const char* cmd = buf + start;

  // ----------------------------------------
  // STOP
  // ----------------------------------------

  if (strcmp(cmd, "STOP") == 0) {

    autoMode = false;

    setMotion(MODE_IDLE);

    motionPending = false;

    vitalsCancel();

    Serial.println("ACK,STOP");

    return;
  }

  // ----------------------------------------
  // MEASURE
  // ----------------------------------------

  if (strcmp(cmd, "MEASURE") == 0) {

    if (motionMode != MODE_IDLE ||
        motionPending ||
        autoMode) {

      Serial.println("ERROR,ROBOT_BUSY");

      return;
    }

    if (vitalsIsBusy() ||
        vitalsState == VITALS_DONE) {

      Serial.println("ERROR,BUSY");

      return;
    }

    vitalsStart();

    return;
  }

  // ----------------------------------------
  // STATUS (re-sonde a chaud + READY + HEALTH)
  // ----------------------------------------

  if (strcmp(cmd, "STATUS") == 0) {

    vitalsProbeSensors();

    vitalsPrintReady();

    printHealthStatus(false);

    return;
  }

  // ----------------------------------------
  // HEALTH (diagnostic capteurs complet)
  // ----------------------------------------

  if (strcmp(cmd, "HEALTH") == 0) {

    printHealthStatus();

    return;
  }

  // ----------------------------------------
  // PING
  // ----------------------------------------

  if (strcmp(cmd, "PING") == 0) {

    Serial.println("PONG");

    return;
  }

  // ----------------------------------------
  // COMMANDES INTERDITES PENDANT MESURE
  // ----------------------------------------

  if (vitalsIsBusy()) {

    if (strcmp(cmd, "FORWARD") == 0 ||
        strcmp(cmd, "BACKWARD") == 0 ||
        strcmp(cmd, "LEFT") == 0 ||
        strcmp(cmd, "RIGHT") == 0 ||
        strcmp(cmd, "AUTO_ON") == 0) {

      Serial.println("REJECTED,MEASURING");

      return;
    }
  }

  // ----------------------------------------
  // FORWARD
  // ----------------------------------------

  if (strcmp(cmd, "FORWARD") == 0) {

    if (!forwardSafetyClear()) {

      setMotion(MODE_IDLE);

      Serial.println("REJECTED,FORWARD_UNSAFE");

      return;
    }

    requestMotion(MODE_FORWARD);

    Serial.printf(
      "ACK,FORWARD,%d\n",
      MOTOR_SPEED_PERCENT
    );
  }

  // ----------------------------------------
  // BACKWARD
  // ----------------------------------------

  else if (strcmp(cmd, "BACKWARD") == 0) {

    requestMotion(MODE_BACKWARD);

    Serial.printf(
      "ACK,BACKWARD,%d\n",
      MOTOR_SPEED_PERCENT
    );
  }

  // ----------------------------------------
  // LEFT
  // ----------------------------------------

  else if (strcmp(cmd, "LEFT") == 0) {

    requestMotion(MODE_LEFT);

    Serial.printf(
      "ACK,LEFT,%d\n",
      MOTOR_SPEED_PERCENT
    );
  }

  // ----------------------------------------
  // RIGHT
  // ----------------------------------------

  else if (strcmp(cmd, "RIGHT") == 0) {

    requestMotion(MODE_RIGHT);

    Serial.printf(
      "ACK,RIGHT,%d\n",
      MOTOR_SPEED_PERCENT
    );
  }

  // ----------------------------------------
  // AUTO ON
  // ----------------------------------------

  else if (strcmp(cmd, "AUTO_ON") == 0) {

    autoMode = true;

    Serial.println("ACK,AUTO_ON");
  }

  // ----------------------------------------
  // AUTO OFF
  // ----------------------------------------

  else if (strcmp(cmd, "AUTO_OFF") == 0) {

    autoMode = false;

    setMotion(MODE_IDLE);

    Serial.println("ACK,AUTO_OFF");
  }

  // ----------------------------------------
  // COMMANDE INCONNUE
  // ----------------------------------------

  else {

    setMotion(MODE_IDLE);

    Serial.printf("REJECTED,%s\n", cmd);
  }
}

// ============================================
// RECEPTION SERIE - PARSER UNIQUE
// ============================================

void handleSerial() {

  while (Serial.available() > 0) {

    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {

      if (rxDiscard) {

        rxDiscard = false;

        rxLen = 0;

      } else if (rxLen > 0) {

        rxBuffer[rxLen] = '\0';

        processCommand(rxBuffer);

        rxLen = 0;
      }

    } else if (!rxDiscard) {

      if (rxLen < RX_MAX) {

        rxBuffer[rxLen++] = c;

      } else {

        rxLen = 0;

        rxDiscard = true;

        setMotion(MODE_IDLE);

        Serial.println("REJECTED,OVERFLOW");
      }
    }
  }
}

// ============================================
// SETUP
// ============================================

void setup() {

  Serial.begin(115200);

  delay(300);

  // ----------------------------------------
  // MOTEURS
  // ----------------------------------------

  pinMode(MOTOR_A_IN1, OUTPUT);
  pinMode(MOTOR_A_IN2, OUTPUT);

  pinMode(MOTOR_B_IN1, OUTPUT);
  pinMode(MOTOR_B_IN2, OUTPUT);

  pwmAReady =
    ledcAttach(
      MOTOR_A_EN,
      PWM_FREQ,
      PWM_RESOLUTION
    );

  pwmBReady =
    ledcAttach(
      MOTOR_B_EN,
      PWM_FREQ,
      PWM_RESOLUTION
    );

  // ----------------------------------------
  // HC-SR04
  // ----------------------------------------

  pinMode(ULTRASONIC_TRIG, OUTPUT);

  pinMode(ULTRASONIC_ECHO, INPUT);

  digitalWrite(ULTRASONIC_TRIG, LOW);

  attachInterrupt(
    digitalPinToInterrupt(ULTRASONIC_ECHO),
    ultrasonicISR,
    CHANGE
  );

  // ----------------------------------------
  // CAPTEURS IR
  // ----------------------------------------

  pinMode(IR_LEFT_PIN, INPUT);

  pinMode(IR_RIGHT_PIN, INPUT);

  // ----------------------------------------
  // DS18B20
  // ----------------------------------------

  tempSensor.begin();

  tempSensor.setWaitForConversion(false);

  vitalsTempReady =
    tempSensor.getDeviceCount() > 0;

  // ----------------------------------------
  // MAX30102 (+ SpO2 : mode rouge + IR)
  // ----------------------------------------

  Wire.begin();

  vitalsPulseReady = vitalsBeginPulse();

  // ----------------------------------------
  // INITIALISATION ETAT
  // ----------------------------------------

  setMotion(MODE_IDLE);

  vitalsState = VITALS_IDLE;

  // ----------------------------------------
  // INFORMATIONS DEMARRAGE
  // ----------------------------------------

  Serial.println();

  Serial.println("================================");

  Serial.println("HIAR INTEGRATION NAV + VITAUX + SpO2");

  Serial.println("================================");

  Serial.printf(
    "PWM A ready: %d | PWM B ready: %d\n",
    pwmAReady,
    pwmBReady
  );

  Serial.printf(
    "Motor speed: %d%% (PWM %d/255 @ %d Hz)\n",
    MOTOR_SPEED_PERCENT,
    MOTOR_SPEED,
    PWM_FREQ
  );

  Serial.printf(
    "Max move duration: %lu ms\n",
    MAX_MOVE_DURATION
  );

  Serial.printf(
    "Obstacle stop: %.0f cm\n",
    OBSTACLE_STOP_CM
  );

  Serial.printf(
    "HC-SR04 TRIG: GPIO%d, ECHO: GPIO%d\n",
    ULTRASONIC_TRIG,
    ULTRASONIC_ECHO
  );

  Serial.printf(
    "IR LEFT: GPIO%d thr=%d | RIGHT: GPIO%d thr=%d\n",
    IR_LEFT_PIN,
    IR_LEFT_THRESHOLD,
    IR_RIGHT_PIN,
    IR_RIGHT_THRESHOLD
  );

  Serial.println("IR logic: 1=CLEAR, 0=OBSTACLE");

  Serial.printf(
    "DS18B20: GPIO%d ready=%d | MAX30102 ready=%d\n",
    ONE_WIRE_PIN,
    vitalsTempReady,
    vitalsPulseReady
  );

  Serial.printf(
    "SpO2: estimation R/IR, LED=0x%02X, debug=%d\n",
    PPG_LED_AMPLITUDE,
    SPO2_DEBUG
  );

  Serial.println("Mode: MANUEL (AUTO_ON pour activer)");

  Serial.println(
    "Commandes: FORWARD BACKWARD LEFT RIGHT STOP AUTO_ON AUTO_OFF MEASURE STATUS HEALTH PING"
  );

  vitalsPrintReady();
  printHealthStatus(false);
}

// ============================================
// LOOP
// ============================================

void loop() {

  handleSerial();

  updatePendingMotion();

  updateUltrasonic();

  // ----------------------------------------
  // TIMEOUT MOUVEMENT
  // ----------------------------------------

  if (motionMode != MODE_IDLE &&
      millis() - movementStartTime >=
      MAX_MOVE_DURATION) {

    setMotion(MODE_IDLE);

    autoMode = false;

    Serial.println("SAFETY,TIMEOUT");

    // Une nouvelle commande AUTO_ON
    // est nécessaire pour réactiver l'autonomie.
  }

  // ----------------------------------------
  // CAPTEURS ET SECURITE
  // ----------------------------------------

  publishIrStates();

  updateForwardGuard();

  decideAutonomousMotion();

  // ----------------------------------------
  // ACQUISITION VITAUX
  // ----------------------------------------

  vitalsUpdate();
}
