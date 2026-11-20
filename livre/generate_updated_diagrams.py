#!/usr/bin/env python3
"""
Script de génération des diagrammes mis à jour pour le mémoire de fin d'études HIAR.
Auteur : RAZAKAHARISOA Barovaosolo Cecilia
École Nationale d'Informatique (ENI) / Orange Digital Center Madagascar (2026)
"""

import os
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

OUTPUT_DIR = "/home/franck/Documents/Cecilia/hospital_assistant_robot/livre/HIAR_diagrammes_png"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def render_dot(dot_source, output_png_path, dpi=250):
    cmd = ["dot", "-Tpng", f"-Gdpi={dpi}"]
    p = subprocess.run(cmd, input=dot_source.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        print(f"Error rendering {output_png_path}: {p.stderr.decode()}")
    else:
        with open(output_png_path, "wb") as f:
            f.write(p.stdout)
        print(f"Generated: {output_png_path}")

# ============================================================
# 1. ARCH_MATERIELLE.PNG (Figure 11)
# ============================================================
def generate_arch_materielle():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.5;
        ranksep=0.6;
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=11, penwidth=1.5];
        edge [color="#1b365d", penwidth=1.3, fontname="DejaVu Sans", fontsize=9];

        phone [label="Smartphone / Tablette Usager\\n(Application Flutter « Neo Clinic » & Portail Web)", fillcolor="#ffffff", color="#1b365d"];

        subgraph cluster_rpi {
            label="";
            style="rounded,filled";
            fillcolor="#eef7ee";
            color="#2d7d32";
            penwidth=1.5;
            
            rpi_label [label="Raspberry Pi 4 Model B (4 Go)", shape=none, fillcolor="transparent", fontcolor="#1b5e20", fontsize=12];
            wifi [label="Point d'accès Wi-Fi autonome\\nHIAR-DEMO (WPA2, 10.42.0.1)", fillcolor="#ffffff", color="#1b365d"];
            rpi_sw [label="ROS 2 Humble · Serveur WebSocket :8765\\nServeur Flask :5000 · SQLite3 (appointments.sqlite3)\\nDual IA : Gemini 2.5 Flash / Qwen 2.5 0.5B (Ollama)", fillcolor="#ffffff", color="#1b365d"];
            
            wifi -> rpi_sw [color="#1b365d", dir=both];
        }

        phone -> wifi [color="#1b365d", dir=both, label="Wi-Fi 2,4 GHz\\n(WebSocket JSON & HTTP REST)"];

        subgraph cluster_esp {
            label="";
            style="rounded,filled";
            fillcolor="#fdf2f2";
            color="#b71c1c";
            penwidth=1.5;
            
            esp [label="ESP32-WROOM-32 (240 MHz)\\nGPIO / PWM 20 kHz / I²C 400 kHz / OneWire\\nUART Matériel natif 115200 bauds", fillcolor="#ffffff", color="#b71c1c", fontcolor="#b71c1c", fontsize=12];
        }

        rpi_sw -> esp [label="Liaison série USB (/dev/ttyUSB0)\\n115200 bauds (Trames texte)", dir=both, color="#1b365d"];

        // Capteurs et actionneurs
        us_f [label="HC-SR04 Avant\\nTRIG GPIO 13\\nECHO GPIO 34 (pont diviseur)", fillcolor="#ffffff", color="#1b365d"];
        us_l [label="HC-SR04 Gauche\\nTRIG GPIO 2\\nECHO GPIO 4", fillcolor="#ffffff", color="#1b365d"];
        us_r [label="HC-SR04 Droit\\nTRIG GPIO 5\\nECHO GPIO 16", fillcolor="#ffffff", color="#1b365d"];
        ds18 [label="DS18B20 (Température cutanée)\\nGPIO 23 + pull-up 4,7 kΩ", fillcolor="#ffffff", color="#1b365d"];
        max30 [label="MAX30102 (BPM & SpO2 %)\\nSDA 21, SCL 22 (I²C 0x57)", fillcolor="#ffffff", color="#1b365d"];
        l298n [label="Pilote Pont en H L298N\\nENA 25, IN1 26, IN2 27\\nENB 19, IN3 14, IN4 18", fillcolor="#ffffff", color="#1b365d"];
        motors [label="2 Moteurs DC à réducteur\\n(Entraînement différentiel)", fillcolor="#ffffff", color="#1b365d"];

        us_f -> esp [dir=both, color="#1b365d"];
        us_l -> esp [dir=both, color="#1b365d"];
        us_r -> esp [dir=both, color="#1b365d"];
        ds18 -> esp [dir=both, label="1-Wire", color="#1b365d"];
        max30 -> esp [dir=both, label="I²C", color="#1b365d"];
        esp -> l298n [color="#1b365d"];
        l298n -> motors [color="#1b365d"];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "arch_materielle.png"), dpi=250)

# ============================================================
# 2. ARCH_GLOBALE.PNG (Figure 12)
# ============================================================
def generate_arch_globale():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.4;
        ranksep=0.45;
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=10, penwidth=1.5];
        edge [color="#1b365d", penwidth=1.2, fontname="DejaVu Sans", fontsize=8];

        // 1. Couche IHM
        subgraph cluster_ihm {
            label="Couche IHM et interaction (Terminal mobile tactile & Web)";
            style="rounded,filled";
            fillcolor="#eaf2f8";
            color="#2980b9";
            penwidth=1.5;
            
            ihm_desc [label="Application Mobile Native Flutter « Neo Clinic »\\n(WebSocket contractuel :8765, animations didactiques MP4, TTS/STT)\\n& Interface Web Flask :5000 (Portail Soignants et Médecins)", fillcolor="#ffffff", color="#2980b9"];
        }

        // 2. Couche Applicative
        subgraph cluster_app {
            label="Couche applicative (Raspberry Pi 4, Ubuntu 22.04 LTS)";
            style="rounded,filled";
            fillcolor="#eef7ee";
            color="#27ae60";
            penwidth=1.5;
            
            srv_ai [label="Service IA Hybride Résilient\\n1. Regex réflexe (< 1 ms)\\n2. Google Gemini 2.5 Flash (Cloud)\\n3. Qwen 2.5 0.5B local (Edge / Ollama)\\n+ Mini-RAG 6 fiches OMS", fillcolor="#ffffff", color="#27ae60"];
            srv_flask [label="Serveur Web Flask :5000\\nAPI REST, validation requêtes,\\ncontrôle d'accès par jetons HMAC", fillcolor="#ffffff", color="#27ae60"];
            db_sql [label="SQLite 3\\n(appointments.sqlite3)\\nSessions, Tickets, Vitaux", shape=cylinder, fillcolor="#ffffff", color="#27ae60"];
            ws_bridge [label="hmi_websocket_bridge_node\\n(Serveur WebSocket :8765\\n& nœud ROS 2 rclpy)", fillcolor="#ffffff", color="#27ae60"];

            srv_flask -> db_sql [label="SQL"];
            srv_flask -> ws_bridge [dir=both, style=dashed];
            ws_bridge -> srv_ai [dir=both, label="requêtes NLU"];
        }

        ihm_desc -> ws_bridge [dir=both, label="Wi-Fi (WPA2) / WebSockets JSON", color="#1b365d"];
        ihm_desc -> srv_flask [dir=both, label="HTTP / JSON", color="#1b365d"];

        // 3. Couche Décision et Supervision (ROS 2)
        subgraph cluster_ros {
            label="Couche décision et supervision (ROS 2 Humble)";
            style="rounded,filled";
            fillcolor="#fef9e7";
            color="#d4ac0d";
            penwidth=1.5;

            obs_det [label="obstacle_detector_node\\nQualification seuils 20 cm\\n(Ceinture 3x HC-SR04)", fillcolor="#ffffff", color="#b7950b"];
            nav_dec [label="navigation_decision_node\\nMachine à états finis (FSM)\\nIDLE / DECIDE / FORWARD / TURN / BLOCKED", fillcolor="#ffffff", color="#b7950b"];
            supervisor [label="robot_supervisor_node\\nWatchdog 10 Hz & validation déterministe\\n(Arrêt d'urgence si obstacle)", fillcolor="#ffffff", color="#b7950b"];
            esp_node [label="esp32_interface_node\\nPasserelle série USB & Inversion cinématique\\n(invert_steering = True)", fillcolor="#ffffff", color="#b7950b"];

            ws_bridge -> nav_dec [label="/navigation/request"];
            ws_bridge -> esp_node [label="/vitals/request"];
            esp_node -> ws_bridge [label="/vitals/result & /esp32/diagnostics"];

            esp_node -> obs_det [label="/sensors/ultrasonic*"];
            esp_node -> nav_dec [label="/sensors/ultrasonic*"];
            obs_det -> supervisor [label="/sensors/obstacle"];
            obs_det -> nav_dec [label="/sensors/obstacle_left & right"];
            
            nav_dec -> supervisor [label="/robot/command"];
            supervisor -> esp_node [label="/robot/motor_command"];
        }

        // 4. Couche Contrôle Embarqué
        subgraph cluster_esp32 {
            label="Couche contrôle embarqué temps réel (ESP32-WROOM-32)";
            style="rounded,filled";
            fillcolor="#fdf2f2";
            color="#c0392b";
            penwidth=1.5;

            firmware [label="Firmware C++ : Gestion temps réel, interruptions matérielles\\nMultiplexage 35 ms 3x HC-SR04 · Filtre médian 3 points\\nChaîne biométrique T° (1-Wire) + BPM / SpO2 % (I2C)\\nArrêt d'urgence matériel (< 25 cm, timeout 2 s)", fillcolor="#ffffff", color="#c0392b"];
        }

        esp_node -> firmware [dir=both, label="Liaison série USB (115200 bauds)", color="#1b365d"];

        // 5. Couche Matérielle
        subgraph cluster_hw {
            label="Couche matérielle physique";
            style="rounded,filled";
            fillcolor="#f4f6f7";
            color="#7f8c8d";
            penwidth=1.5;

            hw_motors [label="L298N + 2 Moteurs DC\\n(Châssis différentiel)", fillcolor="#ffffff", color="#7f8c8d"];
            hw_us [label="Ceinture 3x HC-SR04\\n(Avant, Gauche, Droite)", fillcolor="#ffffff", color="#7f8c8d"];
            hw_ds [label="Sonde DS18B20\\n(Température cutanée)", fillcolor="#ffffff", color="#7f8c8d"];
            hw_max [label="Capteur MAX30102\\n(Pouls BPM & SpO2 %)", fillcolor="#ffffff", color="#7f8c8d"];
        }

        firmware -> hw_motors;
        firmware -> hw_us [dir=both];
        firmware -> hw_ds [dir=both];
        firmware -> hw_max [dir=both];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "arch_globale.png"), dpi=250)

# ============================================================
# 3. ARCH_IA.PNG (Figure 24)
# ============================================================
def generate_arch_ia():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.45;
        ranksep=0.5;
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=10, penwidth=1.5];
        edge [color="#1b365d", penwidth=1.2, fontname="DejaVu Sans", fontsize=8.5];

        ui [label="Interface Utilisateur\\n(App Mobile Flutter & Dialogue Vocal STT/TTS)", fillcolor="#ffffff", color="#1b365d"];
        bridge [label="hmi_websocket_bridge_node\\n(Gestionnaire de session & routeur NLU)", fillcolor="#eaf2f8", color="#2980b9"];

        ui -> bridge [label="Texte libre ou\\nTranscription vocale (STT)", color="#1b365d"];
        bridge -> ui [label="Réponse structurée,\\nGuidage vocal (TTS)", style=dashed, color="#1b365d"];

        subgraph cluster_dual_ai {
            label="Moteur d'Intelligence Artificielle Hybride Résilient (voice_intent_parser.py)";
            style="rounded,filled";
            fillcolor="#fcf3cf";
            color="#d4ac0d";
            penwidth=1.5;

            stage1 [label="Étape 1 : Moteur Déterministe (Regex réflexe)\\nMots-clés navigation immédiate (STOP, Pharmacie, Labo)\\nLatence < 1 ms", fillcolor="#ffffff", color="#b7950b"];
            cache [label="Cache LRU Mémoire\\nRequêtes récurrentes (< 1 ms)", shape=note, fillcolor="#ffffff", color="#b7950b"];
            
            subgraph cluster_llms {
                label="Compréhension Sémantique & Traitement du Langage Naturel (LLM)";
                style="rounded,filled";
                fillcolor="#ffffff";
                color="#b7950b";

                gemini [label="MOTEUR PRINCIPAL CLOUD\\nGoogle Gemini 2.5 Flash API\\nPrompt enrichi : cartographie hospitalière,\\nrègles d'orientation et formatage JSON\\n(Latence ~400-800 ms)", fillcolor="#e8f8f5", color="#1abc9c", fontcolor="#117864"];
                qwen [label="MOTEUR DE SECOURS SOUVERAIN (EDGE)\\nQwen 2.5 0.5B Instruct (Ollama Local)\\nExécution 100% hors-ligne sur CPU Raspberry Pi 4\\n(Garantie de continuité sans Internet)", fillcolor="#fbeee6", color="#e67e22", fontcolor="#a04000"];
            }

            rag [label="Module Documentaire Mini-RAG\\n6 Fiches sanitaires officielles OMS\\n(VIH, Paludisme, Diabète, HTA, TB, Santé menstruelle)", fillcolor="#ffffff", color="#b7950b"];

            stage1 -> cache [label="Si non réflexe"];
            cache -> gemini [label="Miss cache (Internet actif)"];
            gemini -> qwen [label="Fallback automatique\\n(si coupure réseau / timeout 2 s)", color="#c0392b", style=dashed, penwidth=1.8];
            gemini -> rag [label="Si demande d'information"];
            qwen -> rag [label="Si demande d'information"];
        }

        bridge -> stage1 [label="Requête usager"];
        gemini -> bridge [label="JSON Intention", style=dashed];
        qwen -> bridge [label="JSON Intention", style=dashed];
        stage1 -> bridge [label="Action immédiate", style=dashed];

        notice [label="Sécurité Déontologique :\\nAucun accès direct aux moteurs\\nAucun diagnostic médical\\nNon-vocalisation des constantes vitales (secret médical)", shape=note, fillcolor="#fadbd8", color="#c0392b", fontcolor="#922b21", fontsize=9.5];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "arch_ia.png"), dpi=250)

# ============================================================
# 4. DEPLOIEMENT.PNG (Figure 22)
# ============================================================
def generate_deploiement():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.5;
        ranksep=0.6;
        node [shape=box3d, style="filled", fontname="DejaVu Sans", fontsize=10, fillcolor="#ffffff", color="#1b365d", penwidth=1.5];
        edge [color="#1b365d", penwidth=1.3, fontname="DejaVu Sans", fontsize=9];

        device_phone [label="<< device >>\\nTerminal Tactile Usager\\n(Smartphone / Tablette)\\nApplication Flutter Neo Clinic\\n& Navigateur Chrome"];

        device_rpi [label="<< device >>\\nRaspberry Pi 4 Model B (4 Go, Ubuntu 22.04 LTS)\\n<< execution environment >> ROS 2 Humble\\n• hmi_websocket_bridge_node (:8765)\\n• navigation_decision_node\\n• robot_supervisor_node (Watchdog 10 Hz)\\n• obstacle_detector_node\\n• esp32_interface_node\\n<< service >> Serveur Web Flask (:5000)\\n<< service >> Moteur Ollama local (Qwen 2.5 0.5B)\\n<< artifact >> Base SQLite3 (appointments.sqlite3)", fillcolor="#eef7ee", color="#27ae60"];

        device_esp [label="<< device >>\\nESP32-WROOM-32 (240 MHz)\\n<< artifact >> Firmware d'intégration C++\\n• Multiplexage séquentiel 35 ms (3x HC-SR04)\\n• Filtre médian 3 points\\n• Chaîne photopléthysmographique BPM & SpO2 %\\n• Boucle de sécurité matérielle (Arrêt < 25 cm)", fillcolor="#fdf2f2", color="#c0392b"];

        device_hw [label="<< device >>\\nChâssis & Électronique de Puissance\\n• Pilote double pont en H L298N\\n• 2 Motoréducteurs DC (Entraînement différentiel)\\n• Ceinture 3x HC-SR04 (Avant, Gauche, Droite)\\n• Sonde 1-Wire DS18B20 & Capteur I²C MAX30102\\n• Alimentation autonome Li-ion 18650", fillcolor="#f4f6f7", color="#7f8c8d"];

        device_phone -> device_rpi [dir=both, label="Wi-Fi WPA2 (HIAR-DEMO)\\nWebSocket JSON :8765 / HTTP :5000"];
        device_rpi -> device_esp [dir=both, label="Liaison série USB\\n115200 bauds (/dev/ttyUSB0)"];
        device_esp -> device_hw [label="Signaux GPIO, PWM (20 kHz),\\nBus I²C & Bus 1-Wire"];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "deploiement.png"), dpi=250)

# ============================================================
# 5. ROS_GRAPHE.PNG (Figure 14)
# ============================================================
def generate_ros_graphe():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.45;
        ranksep=0.5;
        fontname="DejaVu Sans";
        node [fontname="DejaVu Sans", fontsize=10];
        edge [color="#1b365d", penwidth=1.3, fontname="DejaVu Sans", fontsize=8];

        // Nœuds
        node [shape=ellipse, style="filled", fillcolor="#fef9e7", color="#b7950b", penwidth=1.5];
        n_bridge [label="hmi_websocket_bridge\\n(Passerelle WebSockets & UI)"];
        n_dec [label="navigation_decision\\n(Machine à états FSM)"];
        n_sup [label="robot_supervisor\\n(Garde-fou déterministe 10 Hz)"];
        n_obs [label="obstacle_detector\\n(Qualification seuils 20 cm)"];
        n_esp [label="esp32_interface\\n(Liaison série & Invert steering)"];

        // Topics
        node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="#1b365d", penwidth=1.3];
        t_req [label="/navigation/request\\nstd_msgs/String (JSON)"];
        t_cmd [label="/navigation/command\\nstd_msgs/String"];
        t_stat [label="/navigation/status\\nstd_msgs/String"];
        t_rcmd [label="/robot/command\\nstd_msgs/String"];
        t_mcmd [label="/robot/motor_command\\nstd_msgs/String"];
        t_rstat [label="/robot/status\\nstd_msgs/String"];
        t_obs [label="/sensors/obstacle\\nstd_msgs/String (FRONT)"];
        t_obs_l [label="/sensors/obstacle_left\\nstd_msgs/String"];
        t_obs_r [label="/sensors/obstacle_right\\nstd_msgs/String"];
        t_us [label="/sensors/ultrasonic\\nstd_msgs/Float32 (Avant)"];
        t_us_l [label="/sensors/ultrasonic_left\\nstd_msgs/Float32 (Gauche)"];
        t_us_r [label="/sensors/ultrasonic_right\\nstd_msgs/Float32 (Droite)"];
        t_vreq [label="/vitals/request\\nstd_msgs/String (JSON)"];
        t_vres [label="/vitals/result\\nstd_msgs/String (JSON)"];
        t_diag [label="/esp32/diagnostics\\nstd_msgs/String (JSON)"];

        // Raccordements
        n_bridge -> t_req;
        t_req -> n_dec;

        n_bridge -> t_cmd;
        t_cmd -> n_dec;

        n_dec -> t_stat;
        t_stat -> n_bridge;

        n_dec -> t_rcmd;
        t_rcmd -> n_sup;

        n_sup -> t_mcmd;
        t_mcmd -> n_esp;

        n_sup -> t_rstat;
        t_rstat -> n_bridge;

        n_esp -> t_us;
        t_us -> n_obs;
        t_us -> n_dec;

        n_esp -> t_us_l;
        t_us_l -> n_obs;
        t_us_l -> n_dec;

        n_esp -> t_us_r;
        t_us_r -> n_obs;
        t_us_r -> n_dec;

        n_obs -> t_obs;
        t_obs -> n_sup;

        n_obs -> t_obs_l;
        t_obs_l -> n_dec;

        n_obs -> t_obs_r;
        t_obs_r -> n_dec;

        n_bridge -> t_vreq;
        t_vreq -> n_esp;

        n_esp -> t_vres;
        t_vres -> n_bridge;

        n_esp -> t_diag;
        t_diag -> n_bridge;
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "ros_graphe.png"), dpi=250)

# ============================================================
# 6. ERD.PNG (Figure 19)
# ============================================================
def generate_erd():
    dot = """
    digraph G {
        rankdir=LR;
        bgcolor="white";
        nodesep=0.6;
        ranksep=0.8;
        node [shape=none, fontname="DejaVu Sans", fontsize=10];
        edge [color="#1b365d", penwidth=1.3, fontname="DejaVu Sans", fontsize=9];

        migrations [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff">
            <tr><td bgcolor="#eaf2f8"><b>hiar_schema_migrations</b></td></tr>
            <hr/>
            <tr><td align="left">version : INTEGER (PK)</td></tr>
            <tr><td align="left">applied_at : TEXT NOT NULL</td></tr>
        </table>>];

        sessions [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff">
            <tr><td bgcolor="#eaf2f8"><b>doctor_sessions</b></td></tr>
            <hr/>
            <tr><td align="left">requested_date : TEXT (PK)</td></tr>
            <tr><td align="left">doctor_code : TEXT (PK, CHECK A-D)</td></tr>
            <tr><td align="left">period : TEXT (PK, CHECK MAT/AM)</td></tr>
            <tr><td align="left">is_open : INTEGER (0/1)</td></tr>
            <tr><td align="left">opened_at : TEXT</td></tr>
            <tr><td align="left">closed_at : TEXT</td></tr>
            <tr><td align="left">manual_open : INTEGER (0/1)</td></tr>
        </table>>];

        appointments [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#ffffff">
            <tr><td bgcolor="#eaf2f8"><b>appointments</b></td></tr>
            <hr/>
            <tr><td align="left">id : INTEGER (PK, AUTOINCREMENT)</td></tr>
            <tr><td align="left">patient_name : TEXT NOT NULL (&lt;= 120)</td></tr>
            <tr><td align="left">contact : TEXT NOT NULL</td></tr>
            <tr><td align="left">contact_normalized : TEXT (+261...)</td></tr>
            <tr><td align="left">requested_date : TEXT NOT NULL (AAAA-MM-JJ)</td></tr>
            <tr><td align="left">doctor : TEXT NOT NULL (A-D)</td></tr>
            <tr><td align="left">period : TEXT NOT NULL (MAT/AM)</td></tr>
            <tr><td align="left">ticket_number : INTEGER (&gt; 0)</td></tr>
            <tr><td align="left">reason_code : TEXT (C_GEN/C_SPE/URG)</td></tr>
            <tr><td align="left">reason : TEXT NOT NULL</td></tr>
            <tr><td align="left">status : TEXT (en attente/appelé/terminé/annulé)</td></tr>
            <tr><td align="left">temperature_c : REAL (25 - 45 °C)</td></tr>
            <tr><td align="left">heart_rate_bpm : INTEGER (40 - 200 BPM)</td></tr>
            <tr><td align="left"><b>spo2_percent : REAL (70 - 100 % ACTIF)</b></td></tr>
            <tr><td align="left">created_at : TEXT NOT NULL (ISO 8601)</td></tr>
        </table>>];

        sessions -> appointments [label="Lien logique métier\\n(Date, Médecin, Période)\\nIndex unique (contact, date)", style=dashed, arrowhead=crow];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "erd.png"), dpi=250)

# ============================================================
# 7. ETATS_NAVIGATION.PNG (Figure 17)
# ============================================================
def generate_etats_navigation():
    dot = """
    digraph G {
        rankdir=LR;
        bgcolor="white";
        nodesep=0.5;
        ranksep=0.7;
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=10, penwidth=1.5, fillcolor="#fef9e7", color="#b7950b"];
        edge [color="#1b365d", penwidth=1.2, fontname="DejaVu Sans", fontsize=8.5];

        idle [label="IDLE\\n(En attente de mission)", fillcolor="#ffffff"];
        decide [label="DECIDE\\n(Évaluation triplet HC-SR04)", fillcolor="#fef9e7"];
        fwd [label="FORWARD\\n(Avance tout droit)", fillcolor="#eef7ee", color="#27ae60"];
        turn_l [label="TURN_LEFT\\n(Pivot gauche 0,6 s)", fillcolor="#eaf2f8", color="#2980b9"];
        turn_r [label="TURN_RIGHT\\n(Pivot droite 0,6 s)", fillcolor="#eaf2f8", color="#2980b9"];
        recheck [label="RECHECK\\n(Stabilisation 0,2 s)", fillcolor="#ffffff"];
        blocked [label="BLOCKED\\n(Arrêt sécurité impasse)", fillcolor="#fdf2f2", color="#c0392b"];

        idle -> decide [label="Demande valide &\\nCapteurs frais (Start)"];
        
        decide -> fwd [label="Devant >= 20 cm"];
        decide -> turn_l [label="Devant < 20 cm &\\nGauche libre & Droite obst."];
        decide -> turn_r [label="Devant < 20 cm &\\nDroite libre & Gauche obst."];
        decide -> turn_l [label="Devant < 20 cm &\\n2 côtés libres (Gauche max)"];
        decide -> turn_r [label="Devant < 20 cm &\\n2 côtés libres (Droite max +5)"];
        decide -> blocked [label="Tous côtés < 20 cm"];

        fwd -> decide [label="Obstacle < 20 cm OU\\nCapteurs périmés (> 0,6 s)"];
        fwd -> idle [label="Timeout mission (30 s)\\nOU Ordre STOP", style=dashed];

        turn_l -> recheck [label="Après 0,6 s"];
        turn_r -> recheck [label="Après 0,6 s"];
        recheck -> decide [label="Après 0,2 s"];

        blocked -> decide [label="Dès qu'une direction\\nredevient libre (> 20 cm)"];
        blocked -> idle [label="Ordre STOP", style=dashed];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "etats_navigation.png"), dpi=250)

# ============================================================
# 8. VITALS.PNG (Figure 8)
# ============================================================
def generate_vitals():
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), dpi=250)
    plt.subplots_adjust(hspace=0.45)

    box_blue = dict(boxstyle="round,pad=0.5", fc="#eaf2f8", ec="#1b365d", lw=1.5)
    box_red = dict(boxstyle="round,pad=0.5", fc="#fdf2f2", ec="#c0392b", lw=1.5)

    # 1. Température
    ax0 = axes[0]
    ax0.axis('off')
    ax0.set_title("1. Température corporelle cutanée (DS18B20 - Bus 1-Wire)", fontsize=11, fontweight='bold', color="#922b21", loc='left')
    
    t_boxes = [
        "Homéothermie corporelle\\n(Hypothalamus ~37,0 °C)",
        "Température cutanée\\nau point de contact",
        "Sonde Dallas DS18B20\\nMot 12 bits (GPIO 23 1-Wire)\\nRésolution 0,0625 °C",
        "Firmware ESP32 & ROS 2\\nValidation [25 - 45 °C]\\nAffichage indicatif (sans TTS)"
    ]
    for i, t in enumerate(t_boxes):
        ax0.text(0.12 + i*0.25, 0.45, t, ha='center', va='center', bbox=box_red, fontsize=8.5)
        if i < 3:
            ax0.annotate('', xy=(0.23 + i*0.25, 0.45), xytext=(0.17 + i*0.25, 0.45),
                         arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.5))

    # 2. Rythme cardiaque & SpO2
    ax1 = axes[1]
    ax1.axis('off')
    ax1.set_title("2. Fréquence cardiaque & Saturation en oxygène SpO2 (MAX30102 - Bus I²C)", fontsize=11, fontweight='bold', color="#1b365d", loc='left')
    
    c_boxes = [
        "Systole cardiaque & onde\\nde pouls capillaire pulsatile",
        "MAX30102 (Doigt posé)\\nLED Rouge 660 nm\\nLED Infrarouge 880 nm",
        "Photodiode & ADC 18 bits\\nFIFO rouge + IR\\nSéparation composantes AC/DC",
        "Firmware : BPM = 60/T\\nRatio R = (AC/DC)_R / (AC/DC)_IR\\nSpO2 ≈ 110 - 25*R"
    ]
    for i, t in enumerate(c_boxes):
        ax1.text(0.12 + i*0.25, 0.45, t, ha='center', va='center', bbox=box_blue, fontsize=8.5)
        if i < 3:
            ax1.annotate('', xy=(0.23 + i*0.25, 0.45), xytext=(0.17 + i*0.25, 0.45),
                         arrowprops=dict(arrowstyle="->", color="#1b365d", lw=1.5))

    # 3. Onde PPG illustrative
    ax2 = axes[2]
    t = np.linspace(0, 4, 1000)
    ppg = 1.0 + 0.25 * np.maximum(0, np.sin(2 * np.pi * 1.25 * t))**2 + 0.08 * np.maximum(0, np.sin(2 * np.pi * 1.25 * t - 0.7))**3
    ax2.plot(t, ppg, color="#1b365d", lw=1.8, label="Signal photopléthysmographique (PPG) pulsatile")
    ax2.axhline(1.0, color="#7f8c8d", linestyle="--", lw=1, label="Composante continue (DC) : tissus fixes & sang veineux")
    
    ax2.annotate('Composante pulsatile (AC)\nsynchrone du cœur', xy=(0.4, 1.25), xytext=(0.55, 1.32),
                 arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2), fontsize=8.5, color="#c0392b")
    ax2.annotate('Intervalle R-R (T)\nBPM = 60 / T', xy=(0.8, 1.25), xytext=(1.05, 1.32),
                 arrowprops=dict(arrowstyle="<->", color="#27ae60", lw=1.2), fontsize=8.5, color="#27ae60")

    ax2.set_xlabel("Temps (secondes)", fontsize=9)
    ax2.set_ylabel("Amplitude optique (u.a.)", fontsize=9)
    ax2.set_ylim(0.95, 1.45)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right", fontsize=8)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "vitals.png"))
    plt.close()
    print("Generated: vitals.png")

# ============================================================
# 9. SEQ_OBSTACLE.PNG (Figure 18)
# ============================================================
def generate_seq_obstacle():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.4;
        ranksep=0.4;
        fontname="DejaVu Sans";
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=9.5, penwidth=1.5];
        edge [color="#1b365d", penwidth=1.2, fontname="DejaVu Sans", fontsize=8];

        // Lignes de vie
        hw [label="Environnement /\\nObstacle physique", fillcolor="#f4f6f7", color="#7f8c8d"];
        esp [label="ESP32\\n(3x HC-SR04)", fillcolor="#fdf2f2", color="#c0392b"];
        obs [label="obstacle_detector_node\\n(Seuils 20 cm)", fillcolor="#fef9e7", color="#b7950b"];
        nav [label="navigation_decision_node\\n(Machine à états FSM)", fillcolor="#fef9e7", color="#b7950b"];
        sup [label="robot_supervisor_node\\n(Watchdog 10 Hz)", fillcolor="#fef9e7", color="#b7950b"];
        mot [label="Pilote L298N &\\nMoteurs DC", fillcolor="#f4f6f7", color="#7f8c8d"];

        // Flux séquentiel
        hw -> esp [label="1. Obstacle à 18 cm (< 20 cm)", color="#c0392b"];
        esp -> obs [label="2. Trame série : SENSOR,FRONT,18.0\\n/sensors/ultrasonic"];
        obs -> sup [label="3. /sensors/obstacle (FRONT=OBSTACLE)", color="#c0392b"];
        sup -> mot [label="4. /robot/motor_command (STOP immédiat)", color="#c0392b", penwidth=1.5];
        
        esp -> obs [label="5. Multiplexage 35 ms : SENSOR,LEFT,45.0 & SENSOR,RIGHT,12.0"];
        obs -> nav [label="6. /sensors/obstacle_left (FREE) & right (OBSTACLE)"];
        nav -> sup [label="7. FSM transition DECIDE -> TURN_LEFT\\n/robot/command (TURN_LEFT)"];
        sup -> mot [label="8. Commande validée : TURN_LEFT (inversion corrigée)", color="#27ae60"];
        mot -> hw [label="9. Pivot physique à gauche pendant 0,6 s", color="#27ae60"];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "seq_obstacle.png"), dpi=250)

# ============================================================
# 10. SEQ_IA.PNG (Figure 25)
# ============================================================
def generate_seq_ia():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.4;
        ranksep=0.4;
        fontname="DejaVu Sans";
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=9.5, penwidth=1.5];
        edge [color="#1b365d", penwidth=1.2, fontname="DejaVu Sans", fontsize=8];

        usr [label="Usager hospitalier\\n(Voix / Texte)", fillcolor="#ffffff", color="#1b365d"];
        app [label="App Flutter Neo Clinic\\n(STT / WebSocket)", fillcolor="#eaf2f8", color="#2980b9"];
        bridge [label="hmi_websocket_bridge\\n(Routeur NLU)", fillcolor="#fef9e7", color="#b7950b"];
        parser [label="voice_intent_parser\\n(Double moteur)", fillcolor="#fef9e7", color="#b7950b"];
        gemini [label="Google Gemini 2.5 Flash\\n(Cloud)", fillcolor="#e8f8f5", color="#1abc9c"];
        ollama [label="Qwen 2.5 0.5B (Ollama)\\n(Edge local Raspberry Pi)", fillcolor="#fbeee6", color="#e67e22"];

        usr -> app [label="1. Prompt vocal : « Où se trouve la pharmacie ? »"];
        app -> bridge [label="2. WebSocket :8765 JSON (texte transcrit)"];
        bridge -> parser [label="3. Appel parse_intent(text)"];
        parser -> gemini [label="4. Tentative prioritaire API Cloud (Timeout 2 s)", color="#1abc9c"];
        gemini -> parser [label="5. Défaillance réseau simulée (Erreur HTTP / Timeout)", color="#c0392b", style=dashed];
        parser -> ollama [label="6. BASCULEMENT SOUVERAIN EDGE\\nPOST http://127.0.0.1:11434/api/generate", color="#e67e22", penwidth=1.6];
        ollama -> parser [label="7. Réponse JSON : {intent: ORIENTATION, target: PHARMACY}", color="#e67e22"];
        parser -> bridge [label="8. Intention normalisée structurée"];
        bridge -> app [label="9. WebSocket : Confirmation visuelle & guidage vocal TTS"];
        app -> usr [label="10. Vocalisation : « Suivez-moi, guidage vers la pharmacie »", color="#27ae60"];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "seq_ia.png"), dpi=250)

# ============================================================
# 11. SEQ_ORIENTATION.PNG (Figure 16)
# ============================================================
def generate_seq_orientation():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.4;
        ranksep=0.4;
        fontname="DejaVu Sans";
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=9.5, penwidth=1.5];
        edge [color="#1b365d", penwidth=1.2, fontname="DejaVu Sans", fontsize=8];

        usr [label="Usager / Patient", fillcolor="#ffffff", color="#1b365d"];
        app [label="App Flutter Neo Clinic\\n(Écran d'orientation)", fillcolor="#eaf2f8", color="#2980b9"];
        bridge [label="hmi_websocket_bridge\\n(:8765)", fillcolor="#fef9e7", color="#b7950b"];
        nav [label="navigation_decision\\n(FSM)", fillcolor="#fef9e7", color="#b7950b"];
        sup [label="robot_supervisor\\n(Watchdog 10 Hz)", fillcolor="#fef9e7", color="#b7950b"];
        esp [label="esp32_interface &\\nMoteurs DC", fillcolor="#fdf2f2", color="#c0392b"];

        usr -> app [label="1. Sélectionne 'Pharmacie'"];
        app -> bridge [label="2. WebSocket : {action: 'navigate', destination: 'PHARMACY'}"];
        bridge -> nav [label="3. /navigation/request (Vérification validité)"];
        nav -> bridge [label="4. /navigation/status (STARTING)"];
        bridge -> app [label="5. WebSocket broadcast : Début d'accompagnement"];
        
        nav -> sup [label="6. FSM état FORWARD : /robot/command (FORWARD)"];
        sup -> esp [label="7. Commande autorisée : /robot/motor_command (FORWARD)"];
        esp -> esp [label="8. Avance différentielle cadencée (Ceinture HC-SR04 active)"];
        
        nav -> nav [label="9. Échéance du timeout de mission (30 s)"];
        nav -> sup [label="10. Transition IDLE : /robot/command (STOP)"];
        sup -> esp [label="11. /robot/motor_command (STOP)"];
        esp -> esp [label="12. Arrêt complet des moteurs (PWM = 0)"];
        nav -> bridge [label="13. /navigation/status (COMPLETED:PHARMACY)"];
        bridge -> app [label="14. Notification d'arrivée à destination"];
        app -> usr [label="15. Écran et voix TTS : « Vous êtes arrivé à destination »", color="#27ae60"];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "seq_orientation.png"), dpi=250)

# ============================================================
# 12. SEQ_CONSULTATION.PNG (Figure 21)
# ============================================================
def generate_seq_consultation():
    dot = """
    digraph G {
        rankdir=TB;
        bgcolor="white";
        nodesep=0.4;
        ranksep=0.4;
        fontname="DejaVu Sans";
        node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=9.5, penwidth=1.5];
        edge [color="#1b365d", penwidth=1.2, fontname="DejaVu Sans", fontsize=8];

        usr [label="Usager / Patient", fillcolor="#ffffff", color="#1b365d"];
        app [label="App Flutter Neo Clinic\\n(Formulaire & Vitaux)", fillcolor="#eaf2f8", color="#2980b9"];
        flask [label="Serveur Flask :5000\\n(API REST)", fillcolor="#eef7ee", color="#27ae60"];
        db [label="Base SQLite 3\\n(appointments.sqlite3)", shape=cylinder, fillcolor="#ffffff", color="#27ae60"];
        bridge [label="hmi_websocket_bridge\\n(:8765)", fillcolor="#fef9e7", color="#b7950b"];
        esp [label="ESP32 (DS18B20 &\\nMAX30102)", fillcolor="#fdf2f2", color="#c0392b"];

        usr -> app [label="1. Saisie : Nom, Tél (034...), Médecin A, Période MAT"];
        usr -> app [label="2. Lance l'acquisition des signes vitaux"];
        app -> bridge [label="3. WebSocket : {action: 'vitals_start'}"];
        bridge -> esp [label="4. /vitals/request (Session 20 s)"];
        
        esp -> esp [label="5. Mesure T° (1-Wire) + BPM et SpO2 % par ratio R"];
        esp -> bridge [label="6. /vitals/result : {T: 36.8, BPM: 72, SpO2: 98.0}"];
        bridge -> app [label="7. WebSocket : Transmission des constantes"];
        app -> usr [label="8. Affichage visuel confidentiel (AUCUN TTS prononcé !)", color="#27ae60"];

        app -> flask [label="9. POST /api/appointments (Données patient + vitaux)"];
        flask -> db [label="10. Transaction BEGIN IMMEDIATE\\nAttribution ticket séquentiel A-MAT-1"];
        db -> flask [label="11. Succès commit"];
        flask -> app [label="12. Réponse 201 Created : Ticket A-MAT-1"];
        app -> usr [label="13. Écran du ticket de consultation généré", color="#27ae60"];
    }
    """
    render_dot(dot, os.path.join(OUTPUT_DIR, "seq_consultation.png"), dpi=250)

# ============================================================
# EXÉCUTION PRINCIPALE
# ============================================================
if __name__ == "__main__":
    print("Démarrage de la génération des diagrammes structuraux et méthodologiques...")
    generate_arch_materielle()
    generate_arch_globale()
    generate_arch_ia()
    generate_deploiement()
    generate_ros_graphe()
    generate_erd()
    generate_etats_navigation()
    generate_vitals()
    generate_seq_obstacle()
    generate_seq_ia()
    generate_seq_orientation()
    generate_seq_consultation()
    print("-> Tous les 12 diagrammes clés ont été régénérés avec succès dans :", OUTPUT_DIR)
