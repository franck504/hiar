# Hospital Assistant Robot (HIAR)

## Projet de Master 2

Robot assistant hospitalier autonome destiné à améliorer l'accueil, l'orientation et l'accompagnement des patients et visiteurs au sein d'un établissement de santé.

📖 **Consultez le [Guide d'Utilisation Complet (docs/GUIDE_UTILISATION.md)](docs/GUIDE_UTILISATION.md)** pour le démarrage, la configuration IP dynamique et les scénarios d'interaction.  
📡 **Consultez la [Spécification du Protocole WebSocket (docs/WEBSOCKET_PROTOCOL.md)](docs/WEBSOCKET_PROTOCOL.md)** pour l'architecture des échanges temps réel.

---

## Fonctionnalités Principales

- **Accueil bimodal (Voix + Tactile)** : Interaction vocale naturelle continue en français avec déduplication et filtre anti-écho acoustique.
- **Orientation & Accompagnement direct** : Guidage physique vers les services hospitaliers (Pharmacie, Laboratoire, Réception, Radiologie) sans popup bloquante.
- **Sécurité active hospitalière** : Bouton d'arrêt d'urgence tactile et vocal permanent (« *Stop* »), avec reprise sécurisée (« *Reprendre* ») ou clôture (« *Terminer* »).
- **Renseignements de santé publique** : Fiches de prévention interactives et conseils sonores conformes aux directives de l'OMS (Paludisme, Hygiène des mains, Vaccination, Nutrition, Santé mentale).
- **Consultation & Constantes vitales** : Acquisition des constantes médicales (température corporelle, fréquence cardiaque, saturation SpO2) et délivrance de ticket patient.
- **Configuration IP dynamique** : Réglage en un clic de l'adresse IP du serveur depuis l'écran d'accueil sans aucune recompilation.

---

## Architecture Logicielle

* **Application Mobile Kiosk** (`hiar_mobile/`) : Application Flutter optimisée pour écran tactile paysage (tablette / smartphone monté sur le robot).
* **Cerveau Central ROS 2** (`src/hospital_robot/`) :
  * Pont WebSocket bidirectionnel temps réel (`hmi_websocket_bridge_node.py` sur port 5000).
  * Analyseur d'intentions vocales NLP (`voice_intent_parser.py`).
  * Nœuds ROS 2 pour la navigation, la supervision et la gestion des requêtes IHM.
* **Interface Web Administrative** (`web_interface/`) : Tableau de bord de supervision, prise de rendez-vous et gestion des consultations.
* **Firmware Bas Niveau** (`firmware/esp32/`) : Gestion temps réel des capteurs biométriques (DS18B20, MAX30102), télémétrie ultrasonique et contrôle des moteurs.

---

## Démarrage Rapide

### Sur le Raspberry Pi 4 (Cerveau du robot) :
```bash
cd ~/hospital_assistant_robot

# Charger l'environnement ROS 2 Humble
source /opt/ros/humble/setup.bash

# Démarrer le pont WebSocket IHM & Serveur Vocal (Port 5000)
PYTHONPATH=src/hospital_robot python3 src/hospital_robot/hospital_robot/hmi_websocket_bridge_node.py

# Ou lancer l'ensemble des nœuds ROS 2 (Navigation, Superviseur, Série ESP32)
# ros2 launch hospital_robot hospital_robot_launch.py
```

### Sur le poste de développement (avec smartphone USB) :
```bash
# 1. Rediriger le port 5000 vers le smartphone connecté en USB
adb reverse tcp:5000 tcp:5000

# 2. Lancer l'application Flutter
cd hiar_mobile && flutter run
```

---

## Technologies Utilisées

- **ROS 2 Humble** & Python 3 (asyncio, websockets, rclpy)
- **Flutter 3.x / Dart** (Application Kiosk Android paysage, STT, TTS)
- **ESP32 & Arduino C++** (Capteurs vitaux, capteurs IR, ultrason, pont en H L298N)
- **Raspberry Pi 4** (Calcul embarqué et nœuds ROS 2)

---

## Firmware ESP32 — Intégration Matérielle Complète

Le firmware unifié pour le microcontrôleur ESP32 se trouve dans :  
📂 `firmware/esp32/HIAR_ESP32_integration_vitals/HIAR_ESP32_integration_vitals.ino`

Il rassemble l'ensemble des fonctionnalités matérielles du robot :
1. **Contrôle de motricité (Pont en H L298N)** : `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`.
2. **Détection d'obstacles (HC-SR04)** : télémétrie ultrasonique temps réel (`DIST,<cm>`).
3. **Suivi de ligne / détection de sol (Capteurs IR analogiques)** : entrées analogiques calibrées (`IR,LEFT,<0/1>`, `IR,RIGHT,<0/1>`).
4. **Acquisition biomédicale (Signes vitaux)** :
   * **Température corporelle** : sonde Dallas 1-Wire DS18B20 (`temperature_c`).
   * **Fréquence cardiaque & Saturation en oxygène** : capteur optique I2C MAX30102 (`heart_rate_bpm`, `spo2_percent`).
   * **Déclenchement par commande série** : `MEASURE\n` ➔ renvoie la trame `RESULT,temperature_c=...,heart_rate_bpm=...,spo2_percent=...` (ou `NA` si aucun doigt n'est posé).

### Brochage Matériel ESP32

| Composant | Fonction / Broche | GPIO ESP32 | Notes |
|---|---|---:|---|
| **L298N** | ENA (Vitesse Moteur G) | **25** | PWM |
| **L298N** | IN1 (Sens Moteur G) | **26** | Digital OUT |
| **L298N** | IN2 (Sens Moteur G) | **27** | Digital OUT |
| **L298N** | IN3 (Sens Moteur D) | **14** | Digital OUT |
| **L298N** | IN4 (Sens Moteur D) | **18** | Digital OUT |
| **L298N** | ENB (Vitesse Moteur D) | **19** | PWM |
| **IR Gauche** | Sortie analogique AO | **32** | ADC1 |
| **IR Droit** | Sortie analogique AO | **33** | ADC1 |
| **HC-SR04** | TRIG (Émission) | **13** | Digital OUT |
| **HC-SR04** | ECHO (Réception) | **34** | Entrée pure (Input-only) |
| **DS18B20** | DATA (Bus 1-Wire) | **23** *(ou 4)* | Avec résistance pull-up 4.7 kΩ |
| **MAX30102** | SDA (Données I2C) | **21** | Bus I2C standard |
| **MAX30102** | SCL (Horloge I2C) | **22** | Bus I2C standard |

---

## Chaîne de Données des Signes Vitaux (Zéro Valeur Fictive)

Pour garantir une intégrité médicale rigoureuse, aucune donnée fictive n'est affichée ni annoncée :
1. **Application Mobile** : Les constantes sont initialisées à `null`. L'écran affiche des tirets **`"—"`** par défaut, et le récapitulatif indique *« Constantes : Non mesurées »*.
2. **Déclenchement** : Par bouton tactile ou par commande vocale (🎤 « *Mesurer mes constantes* »).
3. **Transmission ROS 2** : Requête sur `/vitals/request` ➔ Ordre série `MEASURE` vers l'ESP32.
4. **Traitement (`vitals_data_parser.py`)** :
   * Si les capteurs détectent le doigt : les valeurs réelles sont validées, transmises au mobile et annoncées par la voix du robot.
   * Si aucun doigt n'est posé ou en cas d'erreur (`NA` ou timeout) : aucune valeur fictive n'est transmise, le mobile conserve `"—"`, et le robot annonce : *« La mesure des constantes n'a pas pu aboutir. Veuillez repositionner votre doigt sur le capteur. »*.

---

## Auteur

**Cecilia RAZAKAHARISOA** — Projet de Master 2
