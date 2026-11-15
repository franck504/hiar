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

```bash
# 1. Démarrer le pont central WebSocket ROS 2
PYTHONPATH=src/hospital_robot python3 src/hospital_robot/hospital_robot/hmi_websocket_bridge_node.py

# 2. Rediriger le port 5000 vers le smartphone connecté en USB
adb reverse tcp:5000 tcp:5000

# 3. Lancer l'application Flutter
cd hiar_mobile && flutter run
```

---

## Technologies Utilisées

- **ROS 2 Humble** & Python (asyncio, websockets)
- **Flutter 3.x / Dart** (Application Kiosk Android, STT, TTS)
- **ESP32 & Arduino C++** (Capteurs vitaux, capteurs IR, ultrason, pont en H L298N)
- **Raspberry Pi 4** (Calcul embarqué)

---

## Auteur

**Cecilia RAZAKAHARISOA** — Projet de Master 2

---

## Checkpoint technique — Adaptation matérielle du firmware ESP32

### État au 04 novembre 2026

**Référence stable**
- `HIAR_ESP32_V08_stable.ino` : dernier firmware testé et vérifié.
- V0.8 est conservé sans modification.
- Son brochage et ses entrées IR numériques ne correspondent pas au nouveau câblage.

**Nouvelle version de développement**
- Fichier : `firmware/esp32/HIAR_ESP32_adaptation_materielle_dev/HIAR_ESP32_adaptation_materielle_dev.ino`
- Créé à partir d'une copie de V0.8.
- Aucun téléversement ni test physique de cette adaptation effectué à ce stade.

### Nouveau brochage matériel

| Fonction | GPIO ESP32 |
|---|---:|
| L298N ENA | 25 |
| L298N IN1 | 26 |
| L298N IN2 | 27 |
| L298N IN3 | 14 |
| L298N IN4 | 18 |
| L298N ENB | 19 |
| IR gauche analogique AO | 32 |
| IR droit analogique AO | 33 |
| HC-SR04 TRIG | 13 |
| HC-SR04 ECHO | 34 |
| DS18B20 DATA | 4 |
| MAX30102 SDA | 21 |
| MAX30102 SCL | 22 |

### Intégration ROS 2

Le nœud `esp32_interface` utilise :
- Liaison série à 115200 bauds.
- Commandes moteurs : `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`.
- Distance : `DIST,<cm>`.
- Infrarouges : `IR,LEFT,0/1` et `IR,RIGHT,0/1`.
- États IR attendus par la navigation : `1 = CLEAR`, `0 = OBSTACLE`.

Les capteurs IR analogiques devront être calibrés sur le matériel, puis convertis en états binaires compatibles avec ROS 2.

### Travaux restant à réaliser

- Adapter le firmware au nouveau brochage.
- Développer la lecture analogique et la calibration des deux IR.
- Vérifier la mesure ultrasonique et les sécurités moteurs.
- Intégrer les signes vitaux DS18B20 et MAX30102 dans le protocole série commun.
- Vérifier la compatibilité du protocole avec `esp32_interface`.
- Compiler avec Arduino IDE.
- Effectuer les essais matériels progressifs, puis l'intégration ROS 2.

### Points de vigilance

- Ne pas téléverser V0.8 avec le nouveau câblage.
- Vérifier la résistance pull-up du DS18B20 sur GPIO4.
- Conserver une protection contre les obstacles et une commande STOP prioritaire.
- Ne pas considérer la compilation ou les tests logiciels comme une preuve de fonctionnement physique.
- L'alimentation 12 V des moteurs reste déconnectée pendant la préparation.

**Statut :** adaptation matérielle en développement, dérivée de V0.8. La version officielle V0.9 reste à identifier.
