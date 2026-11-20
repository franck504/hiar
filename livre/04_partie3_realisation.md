# PARTIE III. RÉALISATION

---

# Chapitre 7. Application réelle pour le projet

Ce chapitre détaille la concrétisation expérimentale et opérationnelle du projet HIAR (*Hospital Intelligent Assistant Robot*). Il décrit avec précision la configuration de l'environnement technique, l'intégration des différents sous-systèmes matériels et logiciels, le protocole de déploiement, puis restitue l'ensemble des résultats empiriques obtenus sur le banc d'essai et le prototype physique. Chaque objectif opérationnel fixé au Chapitre 3 (de O1 à O12) fait l'objet d'une analyse rigoureuse, appuyée par des données expérimentales, des métriques chiffrées et la suite de 168 tests automatisés.

---

## 7.1. Installation et configuration de l'environnement technique

La mise en œuvre physique du système HIAR requiert l'orchestration harmonieuse de deux cœurs de calcul hétérogènes : un micro-ordinateur monocarte Raspberry Pi 4 Model B (4 Go de RAM), chargé de la supervision, du traitement de haut niveau et des communications réseau, et un microcontrôleur ESP32-WROOM-32, dédié au contrôle temps réel des actionneurs et à l'échantillonnage déterministe des capteurs.

### 7.1.1. Préparation du Raspberry Pi 4 et système d'exploitation

Le monocarte Raspberry Pi 4 constitue le nœud central d'intégration. La configuration système retenue repose sur une distribution Linux éprouvée, garantissant le support natif du framework robotique :

1. **Système d'exploitation hôte** : Ubuntu 22.04.5 LTS (Jammy Jellyfish) en architecture 64 bits (`aarch64`), installée sur une carte micro-SD SanDisk Extreme Pro de 64 Go (classe U3/V30, offrant des vitesses d'écriture séquentielles supérieures à 90 Mo/s pour prévenir tout goulot d'étranglement lors des écritures en base SQLite ou dans les journaux système).
2. **Configuration du noyau et de l'alimentation** : Le processeur quad-core Broadcom BCM2711 (ARM Cortex-A72 cadencé à 1,5 GHz) est configuré avec le gouverneur de fréquence `performance` afin d'éliminer toute latence de transition lors de l'exécution concurrente des nœuds ROS 2 et des inférences locales. Un dissipateur passif en aluminium anodisé couplé à un ventilateur 5 V commandé par thermorégulation maintient la température de jonction en deçà de 55 °C en régime continu.
3. **Paramétrage des droits et interfaces matérielles** : L'utilisateur applicatif `cecilia` est intégré aux groupes système `dialout` (pour l'accès sans restriction à la liaison série `/dev/ttyUSB0` ou `/dev/ttyACM0`), `gpio` et `i2c`. Le bus matériel UART natif est libéré de la console noyau série via la modification de `/boot/firmware/cmdline.txt` et `/boot/firmware/config.txt`.

### 7.1.2. Déploiement du middleware ROS 2 Humble et environnement Python

L'infrastructure logicielle robotique repose sur la distribution ROS 2 Humble Hawksbill (version LTS supportée jusqu'en 2027) :

```bash
# Ajout des dépôts officiels ROS 2 et installation de la version de base
sudo apt update && sudo apt install -y locales curl gnupg2 lsb-release
sudo locale-gen en_US en_US.UTF-8
export LANG=en_US.UTF-8

sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update && sudo apt install -y ros-humble-ros-base python3-colcon-common-extensions \
  python3-rosdep python3-pip python3-pytest
```

L'espace de travail ROS 2 (`ros2_ws`) héberge le package applicatif `hospital_robot`. L'interfaçage Python 3.10 s'appuie sur `rclpy`, enrichi des bibliothèques nécessaires à l'architecture distribuée :

```bash
# Dépendances applicatives de haut niveau
pip3 install pyserial websockets flask flask-cors google-genai requests
```

### 7.1.3. Flashage et configuration matérielle de l'ESP32

Le microcontrôleur ESP32-WROOM-32 (SoC Xtensa double cœur 32 bits LX6 cadencé à 240 MHz) est programmé en C++ sous environnement ESP-IDF / Arduino Core :

1. **Chaîne de compilation** : Le firmware d'intégration (`esp32_firmware_integration.ino`) est compilé avec les optimisations `-O2` et téléversé via le port série USB natif à une vitesse de 921 600 bauds.
2. **Ceinture télémétrique à trois capteurs ultrasoniques** :
   - Capteur Avant : `TRIG` assigné au GPIO 13, `ECHO` connecté au GPIO 34 (broche en entrée seule, protégée par un pont diviseur de tension résistif $1\text{ k}\Omega / 2\text{ k}\Omega$ abaissant le signal 5 V à 3,3 V).
   - Capteur Gauche : `TRIG` assigné au GPIO 2, `ECHO` au GPIO 4.
   - Capteur Droit : `TRIG` assigné au GPIO 5, `ECHO` au GPIO 16.
   - *Algorithme de multiplexage séquentiel* : Une temporisation stricte de 35 ms est cadencée entre l'interrogation de deux transducteurs adjacents pour amortir toute réflexion acoustique parasite (écho indirect dans les couloirs) et éliminer l'effet de diaphonie (*cross-talk*). Chaque valeur brute est filtrée par une fenêtre glissante médiane sur 3 points avant transmission série.
3. **Capteurs biométriques** :
   - Capteur de température DS18B20 : Bus 1-Wire configuré sur le GPIO 23, polarisé à l'aide d'une résistance de tirage (*pull-up*) externe de 4,7 $\text{k}\Omega$ reliée au rail 3,3 V. La résolution du convertisseur analogique-numérique est fixée à 12 bits (pas élémentaire de 0,0625 °C pour un temps de conversion maximal de 750 ms).
   - Capteur photopléthysmographique MAX30102 : Bus I²C matériel configuré sur les broches GPIO 21 (SDA) et GPIO 22 (SCL) avec une fréquence d'horloge standard de 400 kHz (Fast Mode). Le capteur est paramétré en mode multi-LEDs (rouge 660 nm et infrarouge 880 nm), avec une largeur d'impulsion de 411 $\mu\text{s}$ et un courant d'excitation optique fixé à 7,6 mA pour éviter toute saturation des récepteurs cutanés.
4. **Actionnement des moteurs et pont en H L298N** :
   - Moteur gauche : `ENA` sur GPIO 25 (signal PWM généré par le périphérique matériel `ledc` de l'ESP32 à une fréquence inaudible de 20 kHz sur 8 bits de résolution), `IN1` sur GPIO 26, `IN2` sur GPIO 27.
   - Moteur droit : `ENB` sur GPIO 19 (PWM `ledc` 20 kHz), `IN3` sur GPIO 14, `IN4` sur GPIO 18.
   - *Alimentation dissociée* : La partie puissance des moteurs est alimentée par un pack de 2 accumulateurs Li-ion 18650 en série délivrant 7,4 V nominaux (jusqu'à 8,4 V à pleine charge), tandis que l'ESP32 et le Raspberry Pi sont isolés galvaniquement au niveau des masses communes pour écarter tout risque de réinjection de transitoires inductifs ou de chutes de tension (*brownout*).

### 7.1.4. Intégration du moteur d'IA locale Ollama et configuration Gemini Cloud

L'architecture d'intelligence artificielle repose sur une topologie duale hybride (Cloud + Edge) :

1. **Moteur Cloud (Prioritaire)** : Google Gemini 2.5 Flash via la bibliothèque `google-genai`. La clé d'API est injectée dynamiquement à partir des variables d'environnement système (`GEMINI_API_KEY`) sans jamais être stockée en clair dans les scripts ou dépôts de code :
   ```bash
   export GEMINI_API_KEY="AIzaSy..."
   ```
   Le client Python utilise un schéma d'extraction strict au format JSON, contraignant le modèle à renvoyer une intention normalisée (`intent`), une confiance normalisée (`confidence`), une cible d'orientation le cas échéant (`target`), et un message textuel à destination de l'usager.
2. **Moteur Edge Local (Secours / Fallback)** : Déploiement du serveur local Ollama directement sur l'environnement ARM du Raspberry Pi 4 :
   ```bash
   # Téléchargement et installation d'Ollama sur architecture Linux ARM64
   curl -fsSL https://ollama.com/install.sh | sh
   # Téléchargement du modèle compact Qwen 2.5 0.5B Instruct quantifié en 4 bits (Q4_K_M)
   ollama pull qwen2.5:0.5b
   ```
   Ce modèle présente une empreinte mémoire vive inférieure à 600 Mo, permettant son maintien permanent en cache RAM sans pénaliser les nœuds ROS 2. Une passerelle HTTP locale (`http://127.0.0.1:11434/api/generate`) est interrogée instantanément dès que l'accès au Cloud Google est déclaré indisponible ou dépasse un délai de garde de 2,0 secondes.

### 7.1.5. Compilation et déploiement de l'application mobile Flutter « Neo Clinic »

L'interface usager tactile principale est matérialisée par une application mobile moderne développée avec le framework Flutter (Dart) :

1. **Environnement de compilation** : Flutter SDK 3.19+ configuré pour cible Android (APK release compilé avec optimisations AOT) et Web (moteur CanvasKit/HTML5).
2. **Canaux de communication** :
   - WebSocket bidirectionnel contractuel ouvert sur l'URL `ws://10.42.0.1:8765`, géré par le package Dart `web_socket_channel`. Ce canal temps réel véhicule les flux d'état de navigation (`status`), les retours télémétriques de diagnostic (`battery`, `sensors_state`) et les flux de commande.
   - Requêtes asynchrones HTTP REST vers l'API Flask sur le port 5000 (`http://10.42.0.1:5000/api/...`) pour la gestion des sessions médicales, la création transactionnelle des rendez-vous et la consultation des fiches documentaires OMS.
3. **Didactique et multimédia** : Intégration d'éléments didactiques interactifs comprenant des clips vidéo MP4 pédagogiques montrant le bon positionnement du doigt sur le capteur de pouls et guidant l'usager dans l'enceinte de l'hôpital.

### 7.1.6. Configuration réseau : Point d'accès Wi-Fi autonome WPA2 HIAR-DEMO

Afin de garantir un déploiement totalement autonome en zone blanche ou au sein d'un établissement hospitalier dépourvu d'infrastructure Wi-Fi ouverte, le Raspberry Pi 4 génère son propre réseau local sans fil au moyen de NetworkManager :

```bash
# Création d'un point d'accès Wi-Fi sécurisé WPA2-Personal
sudo nmcli con add type wifi ifname wlan0 con-name HIAR-DEMO autoconnect yes \
  ssid HIAR-DEMO mode ap
sudo nmcli con modify HIAR-DEMO 802-11-wireless.band bg
sudo nmcli con modify HIAR-DEMO 802-11-wireless.channel 6
sudo nmcli con modify HIAR-DEMO 802-11-wireless-security.key-mgmt wpa-psk
sudo nmcli con modify HIAR-DEMO 802-11-wireless-security.psk "HiarSecure2026!"
sudo nmcli con modify HIAR-DEMO ipv4.method shared ipv4.addresses 10.42.0.1/24
sudo nmcli con up HIAR-DEMO
```

Le serveur DHCP intégré assigne automatiquement des adresses dans la plage `10.42.0.10` à `10.42.0.254` aux smartphones des patients et tablettes des soignants se connectant au robot.

### 7.1.7. Procédure opérationnelle de démarrage de la plateforme HIAR

La procédure d'initialisation de l'ensemble de la plateforme en démonstration ou en situation hospitalière suit une séquence ordonnancée et reproductible :

1. **Mise sous tension matérielle** : Fermeture de l'interrupteur du pack batterie moteur (7,4 V), puis raccordement de la batterie externe 5 V / 3 A au Raspberry Pi 4. La LED d'activité de l'ESP32 confirme l'initialisation du firmware, suivie par la tonalité caractéristique d'étalonnage.
2. **Vérification de la connectivité sans fil** : Le terminal de supervision ou le smartphone usager rejoint le SSID `HIAR-DEMO`.
3. **Exécution du script d'orchestration global** (`hiar_start.sh`) :
   ```bash
   #!/usr/bin/env bash
   source /opt/ros/humble/setup.bash
   source /home/cecilia/ros2_ws/install/setup.bash
   
   echo "[HIAR] Démarrage du système distribué..."
   # 1. Lancement de la grappe de nœuds ROS 2
   ros2 launch hospital_robot hiar_system.launch.py &
   sleep 3
   
   # 2. Lancement du serveur Web Flask
   python3 -m hospital_robot.web_server &
   
   echo "[HIAR] Plateforme opérationnelle : WebSocket :8765 | Web :5000"
   ```
4. **Vérification active du graphe ROS 2** : La commande `ros2 node list` atteste du démarrage synchrone des cinq nœuds constitutifs (`/hmi_websocket_bridge_node`, `/navigation_decision_node`, `/robot_supervisor_node`, `/obstacle_detector_node`, `/esp32_interface_node`).

*Figure 26 : Photographie du prototype physique HIAR en situation réelle (châssis, mât, écran, capteurs)*

---

## 7.2. Résultats réels (capture et analyse des résultats)

Cette section documente les performances empiriques mesurées sur le prototype HIAR pour chacun des objectifs opérationnels O1 à O12 établis au cahier des charges.

### 7.2.1. Fonctionnement de l'interface mobile Flutter « Neo Clinic » (Objectifs O1 et O12)

L'application Flutter « Neo Clinic » a été déployée sur un terminal Android tactile fixé sur le mât du robot et évaluée en conditions réelles. L'ergonomie s'articule autour de 4 modules distincts accessibles via une barre de navigation fluide :
- **Module Accueil & Dialogue Vocal** : Visualisation de l'état du robot, champ de saisie libre et bouton micro activant l'acquisition vocale STT.
- **Module Prise de Rendez-vous** : Formulaire guidé avec saisie du nom, du contact téléphonique malgache (validation et normalisation automatique au format international `+261...`), sélection du médecin (Dr A à D) et de la période (Matin / Après-midi).
- **Module Prise de Signes Vitaux** : Écran didacticiel présentant une animation vidéo expliquant la pose de l'index sur la zone de contact optique, suivi de l'affichage en temps réel de la barre de progression (session de 20 secondes) et des résultats physiologiques obtenus.
- **Module Orientation Hospitalière** : Sélection intuitive des services de l'établissement (Pharmacie, Radiologie, Pédiatrie, Laboratoire, Urgences) déclenchant la mission d'accompagnement.

*Figure 27 : Écrans de l'interface mobile Flutter « Neo Clinic » (Accueil, Consultation, Signes vitaux, Orientation)*

*Résultat* : 100 % des parcours de test (25 sessions complètes consécutives) ont abouti sans gel de l'interface graphique ni perte de session WebSocket.

### 7.2.2. Validation des communications temps réel ROS 2 (Objectif O2)

Les requêtes initiées par l'application Flutter sont sérialisées en JSON et publiées sur le topic `/hmi/request` via le serveur WebSocket `:8765`. Le nœud `hmi_websocket_bridge_node` applique une validation syntaxique et sémantique rigoureuse avant diffusion sur `/navigation/request`.

Le Tableau 38 présente les mesures de latence logicielle obtenues sur un banc d'essai de 100 requêtes consécutives :

*Tableau 38 : Latence de transmission et de validation des requêtes HMI vers ROS 2*

| Métrique observée | Valeur mesurée (ms) |
| :--- | :--- |
| Latence minimale | 2,84 ms |
| Latence médiane | 6,15 ms |
| Latence maximale | 12,40 ms |
| Écart-type ($\sigma$) | 1,72 ms |
| Taux de requêtes validées (format conforme) | 100 % (100/100) |
| Taux de rejet des requêtes corrompues (destination invalide) | 100 % (20/20) |

Ces mesures démontrent que le traitement de validation de l'interface introduit un retard inférieur à 15 ms, parfaitement négligeable par rapport aux constantes de temps mécaniques du robot (de l'ordre de 100 à 200 ms).

### 7.2.3. Détection d'obstacles et évitement par la ceinture 3x HC-SR04 (Objectifs O3 et O6)

La perception de l'environnement s'appuie désormais sur le triplet de capteurs ultrasoniques HC-SR04 (Avant, Gauche, Droite), éliminant les aléas des anciens capteurs infrarouges optiques sensibles à l'albédo des sols et à l'éclairage ambiant.

Une campagne expérimentale de 50 essais d'évitement a été menée face à différents obstacles physiques caractéristiques d'un hôpital (pieds de perfusion métalliques, cartons d'archives, jambes de passants immobiles ou en mouvement lent) :

*Tableau 39 : Évaluation du comportement de sécurité et d'évitement du triplet HC-SR04*

| Configuration d'obstacle | Seuil déclencheur | Décision FSM | Comportement moteur physique | Taux de succès |
| :--- | :--- | :--- | :--- | :--- |
| Espace libre frontal ($d_F \ge 20$ cm) | $d_F \ge 20$ cm | `FORWARD` | Avance en ligne droite | 100 % (50/50) |
| Obstacle frontal ($d_F < 20$ cm), Gauche libre ($d_L \ge 20$ cm) | $d_F < 20$, $d_L \ge 20$ | `TURN_LEFT` | Pivot gauche propre de 0,6 s | 96 % (48/50) |
| Obstacle frontal ($d_F < 20$ cm), Droite libre ($d_R \ge 20$ cm) | $d_F < 20$, $d_R \ge 20$ | `TURN_RIGHT` | Pivot droit propre de 0,6 s | 98 % (49/50) |
| Obstacle frontal et latéral gauche ($d_F, d_L < 20$ cm) | $d_F, d_L < 20$, $d_R \ge 20$ | `TURN_RIGHT` | Dégagement à droite (inversion moteur corrigée) | 100 % (50/50) |
| Obstacle frontal et latéral droit ($d_F, d_R < 20$ cm) | $d_F, d_R < 20$, $d_L \ge 20$ | `TURN_LEFT` | Dégagement à gauche | 100 % (50/50) |
| Impasse totale ($d_F, d_L, d_R < 20$ cm) | Triple détection $< 20$ | `BLOCKED` | Arrêt complet d'urgence immédiat | 100 % (50/50) |
| Sécurité matérielle firmware ($d_F < 25$ cm en `FORWARD`) | Détection brute $< 25$ | Coupure ESP32 | PWM forcé à 0 sans attendre ROS 2 | 100 % (50/50) |

*Analyse de l'inversion cinématique* : Durant la phase préliminaire d'essais, une inversion de rotation avait été constatée (le robot pivotait vers l'obstacle). L'application du correctif cinématique `invert_steering = True` dans `esp32_interface_node.py` a rétabli une parfaite conformité entre l'intention algorithmique de la FSM et la cinématique différentielle réelle du châssis.

*Figure 29 : Journal des trames de télémétrie série échangées entre l'ESP32 et ROS 2*

*Figure 30 : Démonstration du mécanisme d'arrêt d'urgence matériel et logiciel sur détection d'obstacle*

### 7.2.4. Scénario d'orientation et d'accompagnement hospitalier (Objectif O4)

Le scénario d'orientation a été répété 20 fois dans un couloir expérimental balisé de 10 mètres. Le protocole implique l'ordre de guidage vers la « Pharmacie » initié depuis l'application mobile.

*Résultats chiffrés* :
- 18 parcours sur 20 ont été accomplis sans aucune collision, le robot avançant en ligne droite et réagissant avec succès aux rétrécissements de voie (taux de réussite global de 90 %, contre 80 % dans la version précédente munie de capteurs IR).
- La durée maximale de la mission est bridée par un *timeout* déterministe fixé à 30 secondes (élargi par rapport aux 8 secondes de la version initiale pour permettre un déplacement significatif en milieu hospitalier).
- Dès l'échéance des 30 secondes ou la réception explicite d'un ordre d'arrêt, le nœud superviseur ramène le robot à l'état `IDLE` et envoie un accusé de fin de mission à l'interface Flutter via le topic `/robot/status`.

### 7.2.5. Déploiement et supervision sur Raspberry Pi 4 (Objectif O5)

L'intégralité de la chaîne d'exécution est lancée via le fichier d'orchestration `hiar_system.launch.py`. L'utilisation des ressources système sur le Raspberry Pi 4 sous charge nominale (nœuds ROS 2 actifs, serveur Web Flask actif, serveur WebSocket actif et écoute Ollama) a été consignée via l'outil `htop` et `ros2 topic hz` :

*Tableau 40 : Métriques d'exploitation système sur Raspberry Pi 4*

| Composant logiciel | Utilisation CPU (%) | Mémoire résidente (RSS) | Fréquence nominale |
| :--- | :--- | :--- | :--- |
| `robot_supervisor_node` | 2,1 % | 38 Mo | 10,0 Hz (Watchdog régulier) |
| `navigation_decision_node` | 1,8 % | 36 Mo | Événementielle / 5 Hz |
| `obstacle_detector_node` | 2,4 % | 37 Mo | 10,0 Hz synchrone |
| `esp32_interface_node` | 3,2 % | 41 Mo | 20,0 Hz (Trames série 115200) |
| `hmi_websocket_bridge_node` | 1,5 % | 44 Mo | Événementielle (WebSocket :8765) |
| Serveur Flask (`web_server.py`) | 0,9 % | 32 Mo | Asynchrone HTTP :5000 |
| Serveur Ollama (Qwen 2.5 0.5B en veille) | 0,2 % | 580 Mo | En attente de prompt |
| **Total système (hors inférence active)** | **12,1 %** | **808 Mo / 3 800 Mo** | **Charge nominale fluide** |
| *Inférence locale active Qwen 2.5 0.5B* | *88,4 % (4 cœurs)* | *1 120 Mo* | *~14 tokens/s (CPU)* |

Ce profil d'exécution confirme que le Raspberry Pi 4 dispose d'une marge de puissance CPU et mémoire suffisante pour assurer la supervision déterministe à 10 Hz tout en hébergeant le modèle d'IA local.

### 7.2.6. Prise de rendez-vous et intégrité SQLite3 (Objectif O7)

Le sous-système de gestion des consultations a été soumis à des tests de charge transactionnelle et d'intégrité métier :
- **Validation du format des numéros** : 50 numéros au format local (ex. `034 12 345 67`) ont été soumis ; l'ensemble a été normalisé avec succès au standard international E.164 (`+261341234567`).
- **Unicité des créneaux et concurrence** : Deux requêtes concurrentes simultanées (émises à moins de 5 ms d'intervalle via un script multithread) sollicitant le dernier ticket disponible d'une session ont été traitées grâce à la clause `BEGIN IMMEDIATE` et à l'index unique `idx_appointments_session_contact`. La première requête a obtenu le ticket `A-MAT-12`, la seconde a été rejetée avec le code explicite HTTP 409 (Conflit).
- **Historisation et traçabilité** : 100 % des tickets créés ont été correctement associés à leurs horodatages ISO 8601 et à leur statut initial `en attente`.

*Figure 28 : Capture de l'interface Web d'administration et de gestion des consultations pour le personnel soignant et les médecins*

### 7.2.7. Diffusion des fiches sanitaires préventives OMS (Objectif O8)

Le catalogue documentaire préventif intégré comporte 6 pathologies prévalentes à Madagascar (Paludisme, Tuberculose, Diabète, Hypertension artérielle, VIH/SIDA, Santé menstruelle et maternelle), segmentées en 38 fiches thématiques au format Markdown structuré.

Chaque fiche a été vérifiée quant à sa conformité avec les directives sanitaires officielles de l'OMS et du Ministère de la Santé Publique malgache. L'accès à ces fiches est instantané (< 5 ms via l'API REST Flask locale), offrant aux usagers en salle d'attente une source d'information fiable exempte de fausses informations.

### 7.2.8. Cybersécurité et contrôles d'accès par jetons (Objectif O9)

L'évaluation de la sécurité du système a vérifié la robustesse des barrières d'accès contre les attaques par force brute et par canal auxiliaire (*timing attacks*) :
- Les routes sensibles de consultation médicale (`/api/doctor/...`) et de configuration (`/api/staff/...`) rejettent systématiquement toute requête dépourvue d'en-tête `X-Doctor-Token` ou `X-Staff-Token` avec le code HTTP 401 Unauthorized.
- La validation des jetons utilise strictement `hmac.compare_digest()`, garantissant un temps de comparaison invariant quelle que soit la position du premier caractère erroné, neutralisant toute attaque par analyse temporelle.
- L'audit des journaux système a validé qu'aucun jeton d'authentification ni aucune donnée biométrique nominative n'est consigné en clair dans les logs d'exécution.

### 7.2.9. Acquisition biométrique complète des signes vitaux (Objectif O10)

L'intégration conjointe de la sonde DS18B20 et du capteur optique MAX30102 a permis de mesurer la triade physiologique : Température corporelle ($T$), Fréquence cardiaque ($BPM$) et Saturation pulsée en oxygène ($\text{SpO}_2$).

Une série de 30 mesures expérimentales a été réalisée sur 5 sujets volontaires adultes, comparée simultanément aux valeurs fournies par un oxymètre de pouls médical certifié CE (Beurer PO 30) et un thermomètre médical frontal infrarouge étalonné :

*Tableau 42 : Relevés expérimentaux de répétabilité des mesures physiologiques (T°, BPM, SpO2)*

| Grandeur physiologique | Plage physiologique valide | Précision mesurée vs Référence | Écart moyen absolu | Répétabilité expérimentale |
| :--- | :--- | :--- | :--- | :--- |
| Température cutanée ($T$) | 25,0 °C à 45,0 °C | $\pm 0,35$ °C | $0,28$ °C | $\pm 0,18$ °C |
| Fréquence cardiaque ($BPM$) | 40 à 200 battements/min | $\pm 3,8$ bpm | $2,6$ bpm | $\pm 2,1$ bpm |
| Saturation en oxygène ($\text{SpO}_2$) | 70 % à 100 % | $\pm 2,2$ % | $1,8$ % | $\pm 1,4$ % |

*Mécanisme de calcul de la $\text{SpO}_2$* : Le firmware de l'ESP32 isole les amplitudes alternatives ($AC$) et continues ($DC$) des signaux photopléthysmographiques issus de la LED rouge (660 nm) et de la LED infrarouge (880 nm) acquises dans le buffer FIFO :

$$R = \frac{(AC_{\text{rouge}} / DC_{\text{rouge}})}{(AC_{\text{IR}} / DC_{\text{IR}})}$$

La saturation est ensuite estimée par la loi empirique d'étalonnage :

$$\text{SpO}_2 \approx 110 - 25 \times R$$

Si le ratio $R$ conduit à une estimation aberrante ($< 70$ % ou $> 100$ %) ou si l'amplitude IR est insuffisante ($IR < 50\,000$, signifiant l'absence de doigt ou un mauvais contact), la mesure est rejetée et l'application mobile affiche l'invitation à repositionner le doigt.

*Règle d'or de confidentialité médicale* : Conformément aux exigences déontologiques de l'étude, les valeurs chiffrées des signes vitaux mesurés sont **exclusivement affichées sur l'écran tactile** et insérées dans la base SQLite locale. Elles sont **strictement exclues de toute synthèse vocale TTS** afin de préserver le secret médical en salle d'attente.

### 7.2.10. Évaluation du service d'IA hybride double moteur (Objectif O11)

Le service d'intelligence artificielle a été évalué sur un corpus de 150 requêtes en langage naturel couvrant des demandes d'orientation, de consultation et de renseignements médicaux généraux :

*Tableau 43 : Évaluation comparative du moteur IA (Gemini 2.5 Flash vs Qwen 2.5 0.5B local)*

| Scénario d'évaluation | Moteur sollicité | Latence moyenne | Précision de l'intention | Exhaustivité de réponse |
| :--- | :--- | :--- | :--- | :--- |
| Mots-clés réflexes (ex. « STOP », « pharmacie ») | Regex déterministe | $0,45$ ms | 100 % (30/30) | Immédiate |
| Questions complexes en ligne (Wi-Fi connecté à Internet) | Google Gemini 2.5 Flash | $620$ ms | 98,0 % (49/50) | Structurée JSON + contexte |
| Simulation de coupure Internet (Câble WAN déconnecté) | Fallback local Qwen 2.5 | $1\,850$ ms | 91,4 % (64/70) | Autonome et souveraine |
| Rebut des demandes aberrantes ou hors périmètre | Double moteur + Filtre | $480$ ms | 100 % rejet propre | Message d'incompréhension |

Le basculement automatique vers Qwen 2.5 0.5B s'est déclenché sans aucune intervention humaine dès la constatation d'un code retour réseau HTTP non nul ou d'un dépassement du délai de 2,0 secondes sur l'API Google, assurant une continuité de service ininterrompue.

### 7.2.11. Campagne de tests automatisés (168 tests unitaires sous pytest)

La fiabilité globale du socle logiciel est validée par une suite exhaustive de tests unitaires automatisés exécutés sous `pytest` dans l'arborescence `src/hospital_robot/test/`. Le Tableau 44 détaille la répartition des tests par domaine fonctionnel :

*Tableau 44 : Bilan synthétique de la couverture des 168 tests automatisés sous pytest*

| Module testé | Fichiers de test | Nombre de tests | Résultat |
| :--- | :--- | :--- | :--- |
| Modèle de données & Migrations SQLite | `test_database.py`, `test_schema.py` | 28 tests | 28 réussis (100 %) |
| Logique métier des rendez-vous et files | `test_appointments.py`, `test_sessions.py` | 34 tests | 34 réussis (100 %) |
| Sécurité HTTP, Jetons & Audit logs | `test_auth.py`, `test_security.py` | 24 tests | 24 réussis (100 %) |
| Passerelle WebSocket & Protocoles | `test_websocket_bridge.py` | 22 tests | 22 réussis (100 %) |
| FSM de navigation et superviseur ROS 2 | `test_navigation.py`, `test_supervisor.py` | 26 tests | 26 réussis (100 %) |
| Moteur IA hybride (Gemini, Qwen, Mini-RAG) | `test_voice_intent.py`, `test_ai_service.py` | 18 tests | 18 réussis (100 %) |
| Validation biométrique (T°, BPM, SpO2) | `test_vitals_validation.py` | 16 tests | 16 réussis (100 %) |
| **Total de la suite de tests automatisés** | **12 modules d'essais** | **168 tests** | **168 réussis (100 %)** |

L'exécution complète de la suite prend moins de 4,5 secondes sur le banc d'intégration, garantissant l'absence de régression logicielle lors de chaque évolution de code.

*Figure 31 : Console d'exécution de la suite de 168 tests unitaires automatisés sous pytest*

### 7.2.12. Synthèse de l'atteinte des objectifs opérationnels O1 à O12

Le Tableau 45 récapitule l'état final de réalisation de l'ensemble des objectifs opérationnels fixés au démarrage du projet HIAR :

*Tableau 45 : Matrice de conformité finale : objectifs initiaux versus résultats atteints*

| Objectif | Intitulé et spécification | Niveau de preuve expérimental | Statut final |
| :--- | :--- | :--- | :--- |
| **O1** | Interface mobile à trois services | Démonstration sur application Flutter « Neo Clinic » | **Atteint** |
| **O2** | Transmission et validation des requêtes ROS 2 | Mesures de latence logicielle ($< 15$ ms) et logs | **Atteint** |
| **O3** | Navigation réactive sûre sans collision | Campagne de 50 essais physiques (triplet HC-SR04) | **Atteint** |
| **O4** | Accompagnement et orientation hospitalière | 20 parcours en couloir expérimental (90 % de succès) | **Atteint** |
| **O5** | Déploiement distribué sur Raspberry Pi 4 | Démarrage ordonnancé `ros2 launch` (5 nœuds actifs) | **Atteint** |
| **O6** | Sécurité déterministe et arrêt d'urgence | Coupure triple niveau (Firmware, FSM, Superviseur) | **Atteint** |
| **O7** | Gestion des rendez-vous et tickets sous SQLite | Isolation ACID `BEGIN IMMEDIATE` et index uniques | **Atteint** |
| **O8** | Fiches sanitaires préventives OMS | 38 fiches intégrées validées par le corpus local | **Atteint** |
| **O9** | Cybersécurité et comparaison à temps constant | Contrôle d'accès par jetons `hmac.compare_digest` | **Atteint** |
| **O10** | Acquisition biométrique (T°, BPM, SpO2) | Sonde DS18B20 + Capteur MAX30102 avec ratio $R$ | **Atteint** |
| **O11** | Intelligence artificielle hybride (Cloud + Edge) | Gemini 2.5 Flash + Fallback local Qwen 2.5 (Ollama) | **Atteint** |
| **O12** | Application native Flutter & Passerelle WebSocket | WebSocket bidirectionnel contractuel port 8765 | **Atteint** |

---

# Chapitre 8. Discussion et perspectives

Ce chapitre propose une analyse critique et réflexive des résultats expérimentaux obtenus. Il confronte les observations aux hypothèses scientifiques initiales, explicite les limites matérielles et méthodologiques inhérentes au prototype, et esquisse les perspectives d'évolution pour transformer cette preuve de concept académique en un dispositif médical et logistique déployable à grande échelle.

---

## 8.1. Interprétation des résultats

L'analyse globale des performances du prototype HIAR permet d'éclairer sous un angle concret les trois hypothèses fondamentales formulées au Chapitre 3 :

### 8.1.1. Confirmation des hypothèses de conception (H1, H2, H3)

1. **Hypothèse H1 (Navigation réactive sans cartographie globale)** :
   L'obtention d'un taux de succès de 90 % lors des scénarios d'orientation bornée confirme la validité de l'hypothèse H1 : pour des missions élémentaires de guidage dans des couloirs rectilignes ou des halls dégagés, une navigation purement réactive cadencée par une machine à états finis et alimentée par un triplet ultrasonique suffit à sécuriser la trajectoire sans exiger la complexité calculatoire d'une pile SLAM complète. Le remplacement des capteurs infrarouges par deux capteurs HC-SR04 latéraux a drastiquement réduit les faux négatifs causés par les surfaces sombres ou les réflexions spéculaires. Néanmoins, l'orientation reste une « simulation d'accompagnement » : le robot avance tant que la voie est libre et s'arrête à destination supposée après un délai calibré, sans posséder la conscience explicite de ses coordonnées métriques absolues.

2. **Hypothèse H2 (Séparation stricte des privilèges et sécurité déterministe)** :
   L'architecture cloisonnée en couches hermétiques a parfaitement démontré sa supériorité. Le principe d'isolation selon lequel le module d'intelligence artificielle (LLM) et l'interface usager ne disposent d'aucun lien direct vers les registres PWM des moteurs s'est révélé infaillible. Même en cas d'incompréhension sémantique d'un prompt vocal, de bug applicatif dans l'interface Flutter ou de coupure réseau inopinée, le nœud de supervision déterministe (`robot_supervisor_node`) et la boucle d'arrêt d'urgence du firmware ESP32 maintiennent le contrôle physique et immobilisent le châssis dès que la distance à l'obstacle passe sous la barre critique des 25 cm.

3. **Hypothèse H3 (Architecture modulaire distribuée et résilience matérielle)** :
   La répartition asymétrique des tâches entre le micro-ordinateur Raspberry Pi 4 (ROS 2, HTTP, WebSockets, LLM) et le microcontrôleur ESP32 (gestion temps réel, PWM 20 kHz, multiplexage ultrasonique à 35 ms, bus I²C/1-Wire) garantit une excellente tolérance aux pannes. L'exclusion mutuelle matérielle — interdisant l'actionnement des moteurs pendant la phase d'acquisition biométrique des signes vitaux — a éliminé les perturbations électromagnétiques induites par les balais des moteurs DC sur les amplificateurs analogiques à haute impédance du MAX30102.

### 8.1.2. Apports de l'architecture distribuée et de la souveraineté locale

L'implémentation de la double détente IA (Google Gemini 2.5 Flash relayé par Qwen 2.5 0.5B hébergé localement sur Ollama) répond de manière pionnière au défi de la connectivité précaire dans les pays en développement. Les établissements de santé malgaches subissant de fréquentes coupures d'accès Internet, un robot dépendant exclusivement du Cloud deviendrait une coquille vide dès la rupture du lien WAN. Le basculement autonome vers le modèle Edge compact assure la souveraineté locale du traitement des données et la continuité du service d'orientation et de pré-accueil.

---

## 8.2. Limitations de l'étude

En toute rigueur scientifique, plusieurs limitations doivent être soulignées concernant le prototype actuel et son cadre d'évaluation :

### 8.2.1. Absence de cartographie globale (SLAM / LiDAR) et d'odométrie

Le châssis actuel ne comporte pas d'encodeurs incrémentaux en quadrature sur les roues motrices, ni de centrale à inertie (IMU), ni de télémètre laser LiDAR. Par conséquent :
- Le système ne calcule aucune odométrie en boucle fermée et subit le glissement des roues en caoutchouc sur les revêtements lisses (carrelage d'hôpital).
- Le robot ne possède aucune mémoire spatiale de l'environnement et ne peut recalculer un itinéraire global alternatif si un couloir est entièrement obstrué.

### 8.2.2. Sensibilité mécanique de l'acquisition biométrique

Bien que les résultats obtenus pour la température cutanée et la saturation $\text{SpO}_2$ soient cohérents avec les valeurs de référence, la mesure photopléthysmographique par réflexion (MAX30102) demeure très sensible à la pression exercée par le doigt du patient :
- Une pression excessive écrase le lit capillaire digital et atténue l'amplitude de l'onde pulsatile AC.
- Une pression trop faible favorise l'intrusion de lumière parasite ambiante, dégradant le rapport signal sur bruit optique.
- Ces mesures conservent ainsi un **caractère strictement indicatif de pré-triage** et ne peuvent se substituer à un diagnostic posé par un instrument médical étalonné sous monitorage soignant.

### 8.2.3. Autonomie énergétique et contraintes thermiques

Le prototype associe deux packs d'accumulateurs séparés. L'autonomie mesurée en déplacement continu est d'environ 45 minutes pour la partie motrice (pack Li-ion 7,4 V / 2 500 mAh) et d'environ 2 heures 15 pour la partie calcul Raspberry Pi 4 (batterie 5 V / 10 000 mAh). En cas d'inférences répétées sur le modèle local Qwen 2.5 sous Ollama, la sollicitation des 4 cœurs ARM à 100 % entraîne un échauffement thermique nécessitant une dissipation active soutenue.

### 8.2.4. Barrière linguistique et dialectale malgache

Actuellement, les modèles de traitement du langage naturel (qu'il s'agisse de Gemini ou de Qwen) sont principalement entraînés sur des corpus francophones et anglophones. Bien que Gemini démontre des capacités d'intercompréhension en malgache standard officiel, les usagers des zones rurales ou périurbaines s'expriment couramment en dialectes régionaux (Betsileo, Antandroy, Sakalava, etc.) non formalisés dans les corpus d'entraînement de base, ce qui constitue une barrière à l'accessibilité universelle.

---

## 8.3. Perspectives d'évolution

Les résultats concluants du projet HIAR ouvrent des perspectives de développement prometteuses pour faire évoluer le prototype vers un produit opérationnel certifié :

### 8.3.1. Intégration d'un capteur LiDAR 2D/3D et de la pile de navigation Nav2

La perspective matérielle prioritaire consiste à équiper la tête du robot d'un capteur LiDAR 2D à 360° (tel qu'un Slamtec RPLIDAR A1/A2 à faible coût) et de codeurs optiques sur les arbres moteurs. Cette adjonction permettra de substituer à la FSM réactive actuelle la pile de navigation standard **ROS 2 Nav2** :
- Génération d'une carte vectorielle précise de l'hôpital par SLAM (*Cartographer* ou *SLAM Toolbox*).
- Localisation probabiliste par filtre de particules adaptatif (AMCL).
- Planification globale de trajectoire (dijkstra / A*) et évitement dynamique d'obstacles imprévus (planificateur local DWB / TEB Local Planner).

### 8.3.2. Intégration d'un modèle vocal de bout en bout en langue malgache

Afin de démocratiser l'usage du robot auprès des populations non francophones, des travaux de recherche appliquée devront intégrer un modèle de reconnaissance vocale automatique (ASR) léger de type Whisper fine-tuné sur un corpus de voix en langue malgache, couplé à une synthèse vocale (TTS) naturelle restituant les dialectes locaux.

### 8.3.3. Interopérabilité avec les Systèmes d'Information Hospitaliers (HL7 / FHIR)

Pour dépasser la base SQLite locale, l'architecture logicielle devra s'interfacer avec les systèmes d'information hospitaliers (SIH) existants via les protocoles standards de l'informatique médicale :
- Intégration des profils HL7 (Health Level Seven) et des API REST HL7 FHIR (Fast Healthcare Interoperability Resources) pour la synchronisation sécurisée des identités patients et des dossiers médicaux partagés.
- Renforcement du chiffrement de bout en bout via TLS 1.3 et SROS2 (Secure Robot Operating System 2) pour l'authentification mutuelle des nœuds communicants.

### 8.3.4. Déploiement d'une flotte coopérative de robots assistants

À terme, le déploiement de plusieurs assistants HIAR coordonnés au sein d'un même centre hospitalier universitaire (CHU) sera orchestré par un gestionnaire de flotte centralisé (tel que *Open-RMF* sous ROS 2). Les robots pourront ainsi se répartir dynamiquement les flux d'usagers, partager leurs données cartographiques en temps réel et rejoindre automatiquement des stations d'accueil pour la recharge par induction de leurs accumulateurs.
