// ============================================
// HIAR - ESP32 NAVIGATION COULOIRS + VITAUX
// Fichier : HIAR_ESP32_integration_vitals.ino
// Carte   : ESP32 Dev Module / ESP32-WROOM-32
// Core    : Arduino ESP32 3.x
// Baud    : 115200
//
// Navigation : L298N + HC-SR04 + IR analogiques
// Vitaux     : DS18B20 + MAX30102
// SpO2       : NON implémenté (toujours NA)
//
// Lieux : ACCUEIL (fond du couloir principal)
//         1er couloir à gauche = TOILETTES
//         2e  couloir à gauche = PHARMACIE
//         3e  couloir à gauche = DOCTEUR
// ============================================

#include <Arduino.h>
#include <string.h>
#include <ctype.h>
#include "driver/gpio.h"
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "MAX30105.h"
#include "heartRate.h"
#include "mbedtls/md.h"

// Clé secrète partagée pour authentification UART (Item 16)
const char* HIAR_AUTH_KEY = "hiar_esp32_secret_key_2026";

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

enum Place {
  PLACE_ACCUEIL = 0,
  PLACE_TOILETTES,
  PLACE_PHARMACIE,
  PLACE_DOCTEUR,
  PLACE_COUNT
};

const char* PLACE_NAMES[PLACE_COUNT] = {
  "ACCUEIL", "TOILETTES", "PHARMACIE", "DOCTEUR"
};

enum NavState {
  NAV_IDLE,
  NAV_TURNING,
  NAV_DRIVING,
  NAV_ALIGN,
  NAV_ENTER_DRIVE,
  NAV_EXIT_DRIVE
};

enum OpenState {
  OS_WALL,
  OS_MAYBE_OPEN,
  OS_OPEN,
  OS_MAYBE_WALL
};

enum TurnNext {
  TN_MAIN_180,
  TN_ENTER,
  TN_EXIT_180,
  TN_EXIT_90
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

// 1 = LIBRE (ouverture) ; 0 = MUR / OBSTACLE

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

const int MOTOR_SPEED_PERCENT = 5;
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
// NAVIGATION ENTRE LIEUX - CONSTANTES
// ============================================

const unsigned long OPENING_CONFIRM_MS = 300;   // vide pendant 300 ms = couloir
const unsigned long WALL_CONFIRM_MS    = 300;   // mur revenu pendant 300 ms
const unsigned long TURN_180_MS        = 1800;  // A CALIBRER
const unsigned long TURN_90_MS         = 900;   // A CALIBRER (= TURN_180_MS / 2)
const unsigned long ALIGN_MS           = 100;   // avance pour se centrer devant le couloir
const unsigned long NAV_MAX_MS         = 90000;
const unsigned long NAV_RETRY_MS       = 200;

// Pendant la sortie d'un couloir, l'ultrason regarde le mur d'en face :
// la garde est réduite. EXIT_DONE_CM = (largeur couloir principal / 2)
// - (distance centre robot -> ultrason). Ex : 60/2 - 14 = 16 -> 17.
const float EXIT_STOP_CM = 12.0f;
const float EXIT_DONE_CM = 17.0f;

// ============================================
// NAVIGATION ENTRE LIEUX - ETAT
// ============================================

NavState  navState  = NAV_IDLE;
OpenState openState = OS_WALL;
TurnNext  turnNext  = TN_MAIN_180;

int currentPlace = PLACE_ACCUEIL;
int targetPlace  = PLACE_ACCUEIL;

int  facing = 1;              // +1 = vers le fond, -1 = vers l'accueil
int  exitDir = 1;
bool insideCorridor = false;

unsigned long openT0 = 0;
unsigned long navStartMs = 0;
unsigned long navTurnStart = 0;
unsigned long navLastTry = 0;
unsigned long turnDuration = 0;
unsigned long alignStart = 0;
unsigned long exitStartMs = 0;

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

const long FINGER_MIN_IR = 50000;

const int BEATS_TARGET = 8;
const int BEATS_MIN = 5;

const float BPM_MIN = 40.0f;
const float BPM_MAX = 200.0f;

const float TEMP_MIN_C = 25.0f;
const float TEMP_MAX_C = 45.0f;

const int RECENT_SIZE = 4;

const unsigned long TEMP_CONVERSION_MS = 750;

// ============================================
// SIGNES VITAUX - OBJETS ET ETAT
// ============================================

OneWire oneWire(ONE_WIRE_PIN);

DallasTemperature tempSensor(&oneWire);

MAX30105 pulseSensor;

bool vitalsTempReady = false;
bool vitalsPulseReady = false;

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
void vitalsResetBeatData();
void vitalsStart();
void vitalsFinishAcquisition();
void vitalsPublishResult();
void vitalsCancel();
void vitalsUpdate();

bool vitalsIsBusy();

void navStop(const char* reason);
void navArrived();
void goTo(int target);
void handleNavCommand(const char* cmd);

// Seuil d'arrêt avant : réduit pendant la sortie d'un couloir
float currentStopCm() {
  return (navState == NAV_EXIT_DRIVE) ? EXIT_STOP_CM : OBSTACLE_STOP_CM;
}

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
// Le chrono n'est pas réinitialisé par une
// commande répétée identique.
// ============================================

void setMotion(MotionMode mode) {

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
          (d < currentStopCm() ||
           lastFilteredDistance < currentStopCm())) {

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
         lastRawDistance >= currentStopCm() &&
         lastFilteredDistance >= currentStopCm();
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
// DECISION AUTONOME (evitement simple)
// ============================================

void decideAutonomousMotion() {

  if (!autoMode) return;

  if (navState != NAV_IDLE) return;

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
// NAVIGATION - DETECTION D'OUVERTURE
// Un vide continu de OPENING_CONFIRM_MS = couloir.
// ============================================

bool openingEvent(bool clear) {

  unsigned long now = millis();

  switch (openState) {

    case OS_WALL:
      if (clear) {
        openState = OS_MAYBE_OPEN;
        openT0 = now;
      }
      break;

    case OS_MAYBE_OPEN:
      if (!clear) {
        openState = OS_WALL;
      } else if (now - openT0 >= OPENING_CONFIRM_MS) {
        openState = OS_OPEN;
        return true;
      }
      break;

    case OS_OPEN:
      if (!clear) {
        openState = OS_MAYBE_WALL;
        openT0 = now;
      }
      break;

    case OS_MAYBE_WALL:
      if (clear) {
        openState = OS_OPEN;
      } else if (now - openT0 >= WALL_CONFIRM_MS) {
        openState = OS_WALL;
      }
      break;
  }

  return false;
}

// ============================================
// NAVIGATION - ARRET / ARRIVEE / VIRAGE
// ============================================

void navStop(const char* reason) {

  setMotion(MODE_IDLE);

  navState = NAV_IDLE;

  Serial.printf("NAV,%s\n", reason);
}

void navArrived() {

  setMotion(MODE_IDLE);

  navState = NAV_IDLE;

  Serial.printf("ARRIVED,%s\n", PLACE_NAMES[currentPlace]);
}

void startTurn(MotionMode m, unsigned long ms, TurnNext next) {

  setMotion(m);

  turnDuration = ms;

  turnNext = next;

  navTurnStart = millis();

  navState = NAV_TURNING;
}

// ============================================
// NAVIGATION - DEMANDE DE DESTINATION
// ============================================

void goTo(int target) {

  if (target < 0 || target >= PLACE_COUNT) return;

  if (vitalsIsBusy()) {
    Serial.println("REJECTED,MEASURING");
    return;
  }

  if (navState == NAV_TURNING) {
    Serial.println("REJECTED,TURNING");
    return;
  }

  if (target == currentPlace) {
    navArrived();
    return;
  }

  autoMode = false;

  targetPlace = target;

  navStartMs = millis();

  int needed = (target > currentPlace) ? 1 : -1;

  if (insideCorridor) {

    // Dans un couloir : demi-tour, sortie, puis virage vers la cible
    exitDir = needed;

    startTurn(MODE_LEFT, TURN_180_MS, TN_EXIT_180);

  } else if (needed != facing) {

    startTurn(MODE_LEFT, TURN_180_MS, TN_MAIN_180);

  } else {

    navState = NAV_DRIVING;
  }

  Serial.printf("NAV,GO,%s\n", PLACE_NAMES[target]);
}

// ============================================
// NAVIGATION - MACHINE A ETATS
// ============================================

void updateNavigation() {

  if (navState == NAV_IDLE) return;

  unsigned long now = millis();

  if (vitalsIsBusy())                { navStop("ABORT_MEASURING"); return; }
  if (now - navStartMs > NAV_MAX_MS) { navStop("TIMEOUT");         return; }

  // --- VIRAGE EN COURS ---
  if (navState == NAV_TURNING) {

    if (now - navTurnStart < turnDuration) return;

    setMotion(MODE_IDLE);

    switch (turnNext) {

      case TN_MAIN_180:
        facing = -facing;
        openState = (currentPlace == PLACE_ACCUEIL) ? OS_WALL : OS_OPEN;
        navState = NAV_DRIVING;
        break;

      case TN_ENTER:
        insideCorridor = true;
        navState = NAV_ENTER_DRIVE;
        break;

      case TN_EXIT_180:
        exitStartMs = 0;
        navState = NAV_EXIT_DRIVE;
        break;

      case TN_EXIT_90:
        insideCorridor = false;
        facing = exitDir;
        openState = OS_OPEN;
        navState = NAV_DRIVING;
        break;
    }

    return;
  }

  // --- CENTRAGE DEVANT LE COULOIR PUIS VIRAGE A 90 ---
  if (navState == NAV_ALIGN) {

    if (now - alignStart >= ALIGN_MS) {

      setMotion(MODE_IDLE);

      // couloirs a gauche a l'aller, a droite au retour
      startTurn(facing == 1 ? MODE_LEFT : MODE_RIGHT,
                TURN_90_MS, TN_ENTER);
    }

    return;
  }

  // --- ENTREE DANS LE COULOIR : jusqu'au fond ---
  if (navState == NAV_ENTER_DRIVE) {

    bool endWall = hasValidDistance &&
                   lastFilteredDistance >= 0 &&
                   lastFilteredDistance < OBSTACLE_STOP_CM;

    if (endWall) {
      navArrived();
      return;
    }

    if (motionMode != MODE_FORWARD && !motionPending &&
        now - navLastTry >= NAV_RETRY_MS) {

      navLastTry = now;
      requestMotion(MODE_FORWARD);
    }

    return;
  }

  // --- SORTIE DU COULOIR : jusqu'au mur d'en face ---
  if (navState == NAV_EXIT_DRIVE) {

    if (exitStartMs && hasValidDistance &&
        lastFilteredDistance >= 0 &&
        lastFilteredDistance < EXIT_DONE_CM) {

      setMotion(MODE_IDLE);

      startTurn(exitDir == 1 ? MODE_LEFT : MODE_RIGHT,
                TURN_90_MS, TN_EXIT_90);

      return;
    }

    if (!exitStartMs) {

      if (motionMode != MODE_FORWARD && !motionPending &&
          now - navLastTry >= NAV_RETRY_MS) {

        navLastTry = now;
        requestMotion(MODE_FORWARD);
      }

      if (motionMode == MODE_FORWARD) exitStartMs = now;

    } else if (motionMode != MODE_FORWARD) {

      navStop("EXIT_BLOCKED");
    }

    return;
  }

  // --- NAV_DRIVING : couloir principal ---

  // Retour a l'accueil = mur du fond vu par l'ultrason
  bool endWall = hasValidDistance &&
                 lastFilteredDistance >= 0 &&
                 lastFilteredDistance < OBSTACLE_STOP_CM;

  if (targetPlace == PLACE_ACCUEIL && facing == -1 && endWall) {
    currentPlace = PLACE_ACCUEIL;
    navArrived();
    return;
  }

  // Avancer (relance si la garde ultrason a coupe)
  if (motionMode != MODE_FORWARD && !motionPending &&
      now - navLastTry >= NAV_RETRY_MS) {

    navLastTry = now;
    requestMotion(MODE_FORWARD);
  }

  // Compter les couloirs : IR gauche a l'aller, IR droit au retour
  bool clear =
    (readIrState(facing == 1 ? IR_LEFT_PIN : IR_RIGHT_PIN) == 1);

  if (motionMode == MODE_FORWARD && openingEvent(clear)) {

    int np = currentPlace + facing;

    if (np >= PLACE_TOILETTES && np < PLACE_COUNT) {

      currentPlace = np;

      Serial.printf("PLACE,%s\n", PLACE_NAMES[currentPlace]);

      if (currentPlace == targetPlace) {
        alignStart = now;
        navState = NAV_ALIGN;
      }
    }
  }
}

// ============================================
// NAVIGATION - COMMANDES SERIE
// ============================================

void handleNavCommand(const char* cmd) {

  if      (strcmp(cmd, "GOTO,ACCUEIL")   == 0) goTo(PLACE_ACCUEIL);
  else if (strcmp(cmd, "GOTO,TOILETTES") == 0) goTo(PLACE_TOILETTES);
  else if (strcmp(cmd, "GOTO,PHARMACIE") == 0) goTo(PLACE_PHARMACIE);
  else if (strcmp(cmd, "GOTO,DOCTEUR")   == 0) goTo(PLACE_DOCTEUR);
  else if (strcmp(cmd, "WHERE")          == 0) Serial.printf("PLACE,%s\n", PLACE_NAMES[currentPlace]);
  else if (strcmp(cmd, "NAVSTOP")        == 0) navStop("CANCELLED");
  else Serial.println("ERROR,UNKNOWN_GOTO");
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
// VITAUX - RESET BATTEMENTS
// ============================================

void vitalsResetBeatData() {

  vitalsHaveLastBeat = false;

  vitalsLastBeatMs = 0;

  vitalsBeatCount = 0;

  vitalsRecentIdx = 0;

  vitalsRecentCount = 0;
}

// ============================================
// VITAUX - DEMARRAGE
// ============================================

void vitalsStart() {

  if (!vitalsTempReady && !vitalsPulseReady) {

    Serial.println("ERROR,NO_SENSOR");

    return;
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

  Serial.println(",spo2_percent=NA");

  Serial.println("STATE,DONE");

  // DONE repasse a IDLE au prochain vitalsUpdate()
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

    vitalsPublishResult();
  }
}

// ============================================
// VITAUX - ANNULATION
// ============================================

void vitalsCancel() {

  if (vitalsIsBusy()) {

    vitalsState = VITALS_IDLE;

    vitalsResetBeatData();

    Serial.println("STATE,CANCELLED");
  }
}

// ============================================
// VITAUX - MISE A JOUR (appelee dans loop)
// ============================================

void vitalsUpdate() {

  unsigned long now = millis();

  if (vitalsState == VITALS_DONE) {

    vitalsState = VITALS_IDLE;

    return;
  }

  if (vitalsState == VITALS_ACQUIRING) {

    if (vitalsPulseReady) {

      pulseSensor.check();

      while (pulseSensor.available()) {

        long ir = pulseSensor.getFIFOIR();

        pulseSensor.nextSample();

        // Pas de doigt : on repart de zero
        if (ir < FINGER_MIN_IR) {
          vitalsResetBeatData();
          continue;
        }

        if (checkForBeat(ir)) {

          if (vitalsHaveLastBeat) {

            float bpm = 60000.0f / (float)(now - vitalsLastBeatMs);

            if (bpm >= BPM_MIN && bpm <= BPM_MAX) {

              vitalsRecent[vitalsRecentIdx] = bpm;

              vitalsRecentIdx = (vitalsRecentIdx + 1) % RECENT_SIZE;

              if (vitalsRecentCount < RECENT_SIZE) {
                vitalsRecentCount++;
              }

              vitalsBeatCount++;
            }
          }

          vitalsLastBeatMs = now;

          vitalsHaveLastBeat = true;
        }
      }
    }

    bool enough = !vitalsPulseReady ||
                  vitalsBeatCount >= BEATS_TARGET;

    bool timeout = now - vitalsSessionStart >= SESSION_MAX_MS;

    if (enough || timeout) {
      vitalsFinishAcquisition();
    }

    return;
  }

  if (vitalsState == VITALS_TEMP_WAIT &&
      now - vitalsTempRequestMs >= TEMP_CONVERSION_MS) {

    vitalsPublishResult();
  }
}

// ============================================
// SECURITE : DUREE MAX D'UN MOUVEMENT MANUEL
// (desactivee pendant une navigation)
// ============================================

void checkMoveTimeout() {

  if (motionMode == MODE_IDLE) return;

  if (navState != NAV_IDLE) return;

  if (millis() - movementStartTime > MAX_MOVE_DURATION) {

    setMotion(MODE_IDLE);

    Serial.println("SAFETY,MOVE_TIMEOUT");
  }
}

// ============================================
// COMMANDES SERIE
// Mouvement : FORWARD/F, BACKWARD/B, LEFT/L, RIGHT/R, STOP/S
// Mode auto : AUTO,ON  AUTO,OFF
// Vitaux    : VITALS,START  VITALS,CANCEL
// Lieux     : GOTO,ACCUEIL|TOILETTES|PHARMACIE|DOCTEUR
//             WHERE  NAVSTOP
// Autres    : STATUS  PING
// ============================================

void manualMotion(MotionMode m) {

  autoMode = false;

  if (navState != NAV_IDLE) {
    navStop("MANUAL_OVERRIDE");
  }

  requestMotion(m);
}

void handleAuthChallenge(const char* nonce) {
  char cleanNonce[16];
  size_t len = 0;
  while (nonce[len] && nonce[len] != '\r' && nonce[len] != '\n' && nonce[len] != ' ' && len < 15) {
    cleanNonce[len] = nonce[len];
    len++;
  }
  cleanNonce[len] = '\0';

  byte hmacResult[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_type_t md_type = MBEDTLS_MD_SHA256;

  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(md_type), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*)HIAR_AUTH_KEY, strlen(HIAR_AUTH_KEY));
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)cleanNonce, strlen(cleanNonce));
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);

  Serial.print("AUTH,");
  for (int i = 0; i < 32; i++) {
    if (hmacResult[i] < 0x10) Serial.print("0");
    Serial.print(hmacResult[i], HEX);
  }
  Serial.println();
}

void handleCommand(char* cmd) {

  for (char* p = cmd; *p; p++) {
    *p = toupper((unsigned char)*p);
  }

  // ----------------------------------------
  // AUTH (Authentification UART HMAC-SHA256 - Item 16)
  // ----------------------------------------
  if (strncmp(cmd, "AUTH,", 5) == 0) {
    handleAuthChallenge(cmd + 5);
    return;
  }

  if (strncmp(cmd, "GOTO,", 5) == 0 ||
      strcmp(cmd, "WHERE") == 0 ||
      strcmp(cmd, "NAVSTOP") == 0) {

    handleNavCommand(cmd);

  } else if (strcmp(cmd, "FORWARD") == 0 || strcmp(cmd, "F") == 0) {

    manualMotion(MODE_FORWARD);

  } else if (strcmp(cmd, "BACKWARD") == 0 || strcmp(cmd, "B") == 0) {

    manualMotion(MODE_BACKWARD);

  } else if (strcmp(cmd, "LEFT") == 0 || strcmp(cmd, "L") == 0) {

    manualMotion(MODE_LEFT);

  } else if (strcmp(cmd, "RIGHT") == 0 || strcmp(cmd, "R") == 0) {

    manualMotion(MODE_RIGHT);

  } else if (strcmp(cmd, "STOP") == 0 || strcmp(cmd, "S") == 0) {

    autoMode = false;

    if (navState != NAV_IDLE) navStop("STOPPED");

    motionPending = false;

    setMotion(MODE_IDLE);

  } else if (strcmp(cmd, "AUTO,ON") == 0) {

    if (navState != NAV_IDLE) navStop("MANUAL_OVERRIDE");

    autoMode = true;

    Serial.println("AUTO,ENABLED");

  } else if (strcmp(cmd, "AUTO,OFF") == 0) {

    autoMode = false;

    setMotion(MODE_IDLE);

    Serial.println("AUTO,DISABLED");

  } else if (strcmp(cmd, "VITALS,START") == 0) {

    if (navState != NAV_IDLE) navStop("ABORT_MEASURING");

    autoMode = false;

    setMotion(MODE_IDLE);

    vitalsStart();

  } else if (strcmp(cmd, "VITALS,CANCEL") == 0) {

    vitalsCancel();

  } else if (strcmp(cmd, "STATUS") == 0) {

    Serial.printf("PLACE,%s\n", PLACE_NAMES[currentPlace]);

    vitalsPrintReady();

  } else if (strcmp(cmd, "PING") == 0) {

    Serial.println("PONG");

  } else {

    Serial.println("ERROR,UNKNOWN_COMMAND");
  }
}

void readSerial() {

  while (Serial.available()) {

    char c = (char)Serial.read();

    if (c == '\r') continue;

    if (c == '\n') {

      if (rxDiscard) {

        rxDiscard = false;

        Serial.println("ERROR,LINE_TOO_LONG");

      } else if (rxLen > 0) {

        rxBuffer[rxLen] = '\0';

        handleCommand(rxBuffer);
      }

      rxLen = 0;

      continue;
    }

    if (rxDiscard) continue;

    if (rxLen >= RX_MAX) {

      rxDiscard = true;

      rxLen = 0;

      continue;
    }

    rxBuffer[rxLen++] = c;
  }
}

// ============================================
// SETUP
// ============================================

void setup() {

  Serial.begin(115200);

  delay(300);

  // Moteurs
  pinMode(MOTOR_A_IN1, OUTPUT);
  pinMode(MOTOR_A_IN2, OUTPUT);
  pinMode(MOTOR_B_IN1, OUTPUT);
  pinMode(MOTOR_B_IN2, OUTPUT);

  ledcAttach(MOTOR_A_EN, PWM_FREQ, PWM_RESOLUTION);
  ledcAttach(MOTOR_B_EN, PWM_FREQ, PWM_RESOLUTION);

  setMotion(MODE_IDLE);

  // Ultrason
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  digitalWrite(ULTRASONIC_TRIG, LOW);

  pinMode(ULTRASONIC_ECHO, INPUT);

  attachInterrupt(
    digitalPinToInterrupt(ULTRASONIC_ECHO),
    ultrasonicISR,
    CHANGE
  );

  // IR analogiques
  analogReadResolution(12);

  analogSetPinAttenuation(IR_LEFT_PIN, ADC_11db);
  analogSetPinAttenuation(IR_RIGHT_PIN, ADC_11db);

  // Capteurs vitaux
  Wire.begin();

  tempSensor.begin();

  vitalsTempReady = (tempSensor.getDeviceCount() > 0);

  vitalsPulseReady = pulseSensor.begin(Wire, I2C_SPEED_FAST);

  if (vitalsPulseReady) {

    pulseSensor.setup();

    pulseSensor.setPulseAmplitudeRed(0x0A);

    pulseSensor.setPulseAmplitudeGreen(0);
  }

  vitalsResetBeatData();

  vitalsPrintReady();

  Serial.println("BOOT,OK");
}

// ============================================
// LOOP
// ============================================

void loop() {

  readSerial();

  updateUltrasonic();

  updateForwardGuard();

  updatePendingMotion();

  updateNavigation();

  decideAutonomousMotion();

  checkMoveTimeout();

  publishIrStates();

  vitalsUpdate();
}
