#!/usr/bin/env python3
"""
Hub Interactif Vocal HIAR (Raspberry Pi 4 / ROS 2)
Mode : PILOTAGE MANUEL EN LIGNE DE COMMANDE (CLI) - Wizard of Oz

Fonctionnement :
1. Le smartphone écoute en continu et envoie tout ce qu'il entend par WebSocket (voice/stt/final).
2. Le terminal affiche clairement les paroles entendues :
   ┌──────────────────────────────────────────────────────────┐
   │ 🎤 [ENTENDU AU MICROPHONE DU SMARTPHONE]                 │
   │ « ... »                                                  │
   └──────────────────────────────────────────────────────────┘
3. AUCUNE RÉPONSE N'EST SIMULÉE AUTOMATIQUEMENT.
4. C'est VOUS, dans le terminal, qui écrivez la réponse à lire à haute voix ou les commandes.
"""

import asyncio
import json
import os
import subprocess
import sys
import time

try:
    import websockets
except ImportError:
    print("\n❌ Le module 'websockets' n'est pas installé.")
    print("👉 Exécutez : pip install websockets\n")
    sys.exit(1)

# Codes couleurs ANSI
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

CLIENTS = set()

def get_local_ips():
    ips = []
    try:
        output = subprocess.check_output(["hostname", "-I"], text=True)
        ips = [ip.strip() for ip in output.split() if ip.strip()]
    except Exception:
        pass
    return ips or ["127.0.0.1"]

def try_adb_reverse():
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = [l for l in res.stdout.strip().splitlines()[1:] if "device" in l and not "offline" in l]
        if lines:
            subprocess.run(["adb", "reverse", "tcp:5000", "tcp:5000"], capture_output=True)
            return True
    except Exception:
        pass
    return False

def make_envelope(msg_type, topic=None, payload=None, qos=1):
    return json.dumps({
        "v": 1,
        "type": msg_type,
        "ts": int(time.time()),
        "topic": topic,
        "payload": payload or {},
        "qos": qos,
    })

async def broadcast_instruction(instruction: dict):
    """Envoie un paquet unifié ServerInstruction au smartphone connecté."""
    if not CLIENTS:
        print(f"\n{YELLOW}⚠️ Aucun smartphone connecté pour le moment.{RESET}")
        return

    msg = make_envelope("pub", topic="server/instruction", payload=instruction, qos=1)
    for ws in list(CLIENTS):
        try:
            await ws.send(msg)
        except Exception:
            pass

async def broadcast_tts_only(text: str):
    """Fait prononcer une phrase au smartphone sans modifier l'écran."""
    await broadcast_instruction({
        "origin": "server",
        "text_to_speak": text,
        "instruction_ui": None,
        "value_to_show": None,
        "robot_status": {
            "face_expression": "speaking",
            "status_label": text[:35]
        }
    })
    print(f"\n{GREEN}🔊 [VOCALISÉ SUR LE SMARTPHONE]{RESET} : « {BOLD}{text}{RESET} »\n")

async def handle_client(websocket):
    remote = websocket.remote_address
    CLIENTS.add(websocket)
    print(f"\n{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{GREEN}🟢 SMARTPHONE CONNECTÉ depuis {remote}{RESET}")
    print(f"{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{DIM}👉 Tapez directement votre texte ci-dessous pour le faire prononcer au smartphone.{RESET}\n")
    print(f"{BOLD}💬 Votre texte à prononcer (ou /help) : {RESET}", end="", flush=True)

    try:
        # Message d'accueil silencieux (aucune parole automatique sans accord de l'opérateur)
        welcome = {
            "origin": "server",
            "text_to_speak": None,
            "instruction_ui": {"screen": "home", "action": "navigate"},
            "value_to_show": {"field_id": "status", "value": "IDLE"},
            "robot_status": {"face_expression": "happy", "status_label": "Prêt (Contrôle CLI)"}
        }
        await websocket.send(make_envelope("pub", topic="server/instruction", payload=welcome))

        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                topic = data.get("topic")
                payload = data.get("payload", {})

                # Répondre aux pings de heartbeat
                if msg_type == "ping":
                    await websocket.send(json.dumps({"v": 1, "type": "pong", "ts": int(time.time())}))
                    continue

                # 1. PAROLE DÉTECTÉE PAR LE MICROPHONE DU SMARTPHONE
                if topic == "voice/stt/final":
                    heard = payload.get("text", "").strip()
                    print(f"\n\n{YELLOW}╔═══════════════════════════════════════════════════════════════════════╗{RESET}")
                    print(f"{YELLOW}║ 🎤 [ENTENDU AU MICROPHONE DU SMARTPHONE]                              ║{RESET}")
                    print(f"{YELLOW}╚═══════════════════════════════════════════════════════════════════════╝{RESET}")
                    print(f"« {BOLD}{heard}{RESET} »\n")
                    print(f"{DIM}👉 Écrivez votre réponse ci-dessous pour la faire lire à voix haute au robot :{RESET}")
                    print(f"{BOLD}💬 Votre texte à prononcer (ou /help) : {RESET}", end="", flush=True)

                # 2. ACTION TACTILE SUR L'ÉCRAN
                elif topic == "ui/action/request":
                    action_id = payload.get("action_id")
                    args = payload.get("args", {})
                    print(f"\n{CYAN}👆 [TACTILE SMARTPHONE] Action appuyée : {BOLD}{action_id}{RESET} {args}")
                    print(f"{BOLD}💬 Votre texte à prononcer (ou /help) : {RESET}", end="", flush=True)

                # 3. CHANGEMENT D'ÉCRAN
                elif topic == "ui/state":
                    screen = payload.get("screen")
                    actions = payload.get("actions", [])
                    print(f"\n{DIM}📱 [ÉCRAN DU SMARTPHONE] Écran actif : '{screen}'{RESET}")
                    print(f"{BOLD}💬 Votre texte à prononcer (ou /help) : {RESET}", end="", flush=True)

            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"{RED}Erreur : {e}{RESET}")

    except websockets.exceptions.ConnectionClosed:
        print(f"\n{RED}🔴 Smartphone déconnecté ({remote}){RESET}\n")
    finally:
        CLIENTS.discard(websocket)

async def run_vitals_demo():
    """Démonstration de mise à jour des capteurs (température, pouls, SpO2)."""
    print(f"\n{CYAN}🩺 [DÉMARRAGE MESURE SIGNES VITAUX]{RESET}")
    await broadcast_instruction({
        "origin": "server",
        "text_to_speak": "Début de la mesure. Veuillez poser votre doigt sur le capteur.",
        "instruction_ui": {"screen": "consultation", "step": 4, "action": "measure_vitals"},
        "value_to_show": {"field_id": "vitals_state", "value": "measuring"},
        "fields": {"vitals_state": "measuring", "consultation_step": 4},
        "robot_status": {"face_expression": "thinking", "status_label": "Prise de température et pouls…"}
    })
    await asyncio.sleep(2.5)

    print(f"{CYAN}   👉 [Mise à jour silencieuse de l'écran] Température = 36.8 °C{RESET}")
    await broadcast_instruction({
        "origin": "server",
        "text_to_speak": None,
        "value_to_show": {"field_id": "temperature", "value": 36.8, "unit": "°C"},
        "fields": {"temperature": 36.8}
    })
    await asyncio.sleep(2.0)

    print(f"{CYAN}   👉 [Mise à jour silencieuse de l'écran] Pouls = 72 BPM{RESET}")
    await broadcast_instruction({
        "origin": "server",
        "text_to_speak": None,
        "value_to_show": {"field_id": "heart_rate", "value": 72, "unit": "BPM"},
        "fields": {"heart_rate": 72}
    })
    await asyncio.sleep(1.8)

    print(f"{CYAN}   👉 [Mise à jour silencieuse de l'écran] SpO2 = 98 %{RESET}")
    await broadcast_instruction({
        "origin": "server",
        "text_to_speak": None,
        "value_to_show": {"field_id": "spo2", "value": 98, "unit": "%"},
        "fields": {"spo2": 98, "vitals_state": "done"}
    })
    await asyncio.sleep(1.2)

    print(f"{GREEN}   👉 [Synthèse vocale finale]{RESET}")
    await broadcast_instruction({
        "origin": "server",
        "text_to_speak": "Mesure terminée. Température 36 degrés 8, rythme cardiaque 72 battements par minute, oxygénation 98 pour cent.",
        "value_to_show": {"field_id": "vitals_state", "value": "done"},
        "robot_status": {"face_expression": "happy", "status_label": "Constantes validées"}
    })

async def terminal_input_loop():
    """Boucle interactive pour taper les phrases à prononcer ou les commandes."""
    loop = asyncio.get_running_loop()
    await asyncio.sleep(0.5)

    while True:
        try:
            prompt = f"{BOLD}💬 Votre texte à prononcer (ou /help) : {RESET}"
            print(prompt, end="", flush=True)
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            raw_text = line.strip()
            if not raw_text:
                continue

            # Commandes spéciales commençant par "/"
            if raw_text.startswith("/"):
                parts = raw_text.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""

                if cmd in ["/quit", "/exit", "/q"]:
                    print(f"\n{YELLOW}Fermeture du hub...{RESET}")
                    os._exit(0)

                elif cmd in ["/help", "/?"]:
                    print(f"\n{BOLD}GUIDE DES COMMANDES CLI :{RESET}")
                    print(f"  • {BOLD}Tapez directement n'importe quelle phrase{RESET}")
                    print(f"    👉 Le smartphone la lit immédiatement à voix haute via son TTS !")
                    print(f"       Exemple : {GREEN}Bonjour ! Que puis-je faire pour vous ?{RESET}\n")
                    print(f"  • {CYAN}/pharma [phrase]{RESET} -> Ouvre l'écran Pharmacie (sans pop-up) et lit la phrase si fournie")
                    print(f"       Exemple : {GREEN}/pharma Suivez-moi jusqu'à la pharmacie.{RESET}")
                    print(f"  • {CYAN}/labo [phrase]{RESET}   -> Ouvre l'écran Laboratoire (sans pop-up)")
                    print(f"  • {CYAN}/radio [phrase]{RESET}  -> Ouvre l'écran Radiologie (sans pop-up)")
                    print(f"  • {CYAN}/consult [phrase]{RESET}-> Ouvre la consultation médicale")
                    print(f"  • {CYAN}/info <HIV|MALARIA|DIABETES|HYPERTENSION|TUBERCULOSIS>{RESET} -> Ouvre une fiche OMS")
                    print(f"  • {CYAN}/step <1..6> [phrase]{RESET} -> Saute à une étape de consultation (4 = Signes vitaux)")
                    print(f"       Exemple : {GREEN}/step 4 Veuillez poser votre doigt sur le capteur.{RESET}")
                    print(f"  • {CYAN}/ticket [numéro] [phrase]{RESET} -> Affiche le ticket de passage confirmé")
                    print(f"       Exemple : {GREEN}/ticket A-MAT-3 Votre numéro est le A-MAT-3.{RESET}")
                    print(f"  • {CYAN}/val <champ> <valeur> [phrase]{RESET} -> Met à jour un champ à l'écran silencieusement")
                    print(f"       Exemple : {GREEN}/val temperature 37.1{RESET} (met à jour sans parler)")
                    print(f"       Exemple : {GREEN}/val heart_rate 75 Pouls mesuré à 75.{RESET} (met à jour et parle)")
                    print(f"  • {CYAN}/vitals{RESET}          -> Déroule la séquence complète de mesure de température/pouls")
                    print(f"  • {CYAN}/home [phrase]{RESET}   -> Retourne à l'écran d'accueil")
                    print(f"  • {CYAN}/splash{RESET}         -> Met le smartphone en veille (écran initial pour tester le réveil)")
                    print(f"  • {RED}/stop [phrase]{RESET}   -> Arrêt d'urgence du robot (interrompt la voix et fige le robot)\n")
                    continue

                # 1. NAVIGATION PHARMACIE (origin: "voice" -> sans pop-up)
                elif cmd == "/pharma":
                    speech = arg or "Je vous accompagne à la pharmacie. Suivez-moi."
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": speech,
                        "instruction_ui": {"screen": "mission", "destination": "Pharmacie", "require_confirmation": False},
                        "value_to_show": {"field_id": "destination", "value": "Pharmacie"},
                        "fields": {"destination": "Pharmacie", "distance": "15 m", "eta": "20 s"},
                        "voice_hints": ["Stop", "Terminer"],
                        "robot_status": {"status_label": "En route vers la Pharmacie"}
                    })
                    print(f"\n{GREEN}👉 Écran Mission Pharmacie activé (sans pop-up) | Voix : « {speech} »{RESET}\n")
                    continue

                # 2. NAVIGATION LABORATOIRE
                elif cmd == "/labo":
                    speech = arg or "Direction le laboratoire d'analyses médicales. Suivez-moi."
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": speech,
                        "instruction_ui": {"screen": "mission", "destination": "Laboratoire", "require_confirmation": False},
                        "value_to_show": {"field_id": "destination", "value": "Laboratoire"},
                        "fields": {"destination": "Laboratoire", "distance": "22 m", "eta": "30 s"},
                        "voice_hints": ["Stop", "Terminer"],
                        "robot_status": {"status_label": "En route vers le Laboratoire"}
                    })
                    print(f"\n{GREEN}👉 Écran Mission Laboratoire activé (sans pop-up) | Voix : « {speech} »{RESET}\n")
                    continue

                # 3. NAVIGATION RADIOLOGIE
                elif cmd == "/radio":
                    speech = arg or "Je vous guide vers la radiologie. Suivez-moi."
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": speech,
                        "instruction_ui": {"screen": "mission", "destination": "Radiologie", "require_confirmation": False},
                        "value_to_show": {"field_id": "destination", "value": "Radiologie"},
                        "fields": {"destination": "Radiologie", "distance": "30 m", "eta": "40 s"},
                        "voice_hints": ["Stop", "Terminer"],
                        "robot_status": {"status_label": "En route vers la Radiologie"}
                    })
                    print(f"\n{GREEN}👉 Écran Mission Radiologie activé (sans pop-up) | Voix : « {speech} »{RESET}\n")
                    continue

                # 4. CONSULTATION / ÉTAPE
                elif cmd == "/consult":
                    speech = arg or "Prise de rendez-vous de consultation médicale."
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": speech,
                        "instruction_ui": {"screen": "consultation", "step": 1, "require_confirmation": False},
                        "fields": {"consultation_step": 1},
                        "voice_hints": ["Générale", "Suivi", "Annuler"],
                        "robot_status": {"status_label": "Consultation"}
                    })
                    print(f"\n{GREEN}👉 Écran Consultation ouvert (Étape 1) | Voix : « {speech} »{RESET}\n")
                    continue

                # 4 bis. FICHE DE SANTÉ OMS (Information)
                elif cmd == "/info":
                    topic = arg.upper() or "MALARIA"
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": f"Voici les repères de santé publique concernant {topic}.",
                        "instruction_ui": {"screen": "information", "topic": topic, "require_confirmation": False},
                        "fields": {"topic": topic},
                        "robot_status": {"status_label": f"Fiche {topic}"}
                    })
                    print(f"\n{GREEN}👉 Fiche santé OMS '{topic}' affichée à l'écran.{RESET}\n")
                    continue

                elif cmd == "/step":
                    subparts = arg.split(maxsplit=1)
                    step_num = int(subparts[0]) if subparts and subparts[0].isdigit() else 4
                    speech = subparts[1] if len(subparts) > 1 else None
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": speech,
                        "instruction_ui": {"screen": "consultation", "step": step_num, "require_confirmation": False},
                        "fields": {"consultation_step": step_num},
                        "robot_status": {"status_label": f"Consultation (Étape {step_num})"}
                    })
                    print(f"\n{GREEN}👉 Consultation avancée à l'Étape {step_num} | Voix : {speech or '(silence)'}{RESET}\n")
                    continue

                # 5. TICKET FINAL
                elif cmd == "/ticket":
                    subparts = arg.split(maxsplit=1)
                    t_num = subparts[0] if subparts else "A-MAT-3"
                    speech = subparts[1] if len(subparts) > 1 else f"Votre rendez-vous est confirmé, voici votre ticket numéro {t_num}."
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": speech,
                        "instruction_ui": {"screen": "consultation", "step": 6, "require_confirmation": False},
                        "value_to_show": {"field_id": "ticket_label", "value": t_num},
                        "fields": {"ticket_label": t_num, "consultation_step": 6},
                        "voice_hints": ["Terminer", "Accueil"],
                        "robot_status": {"status_label": f"Ticket {t_num} émis"}
                    })
                    print(f"\n{GREEN}👉 Écran Ticket {t_num} affiché | Voix : « {speech} »{RESET}\n")
                    continue

                # 6. MISE À JOUR CIBLÉE D'UNE VALEUR À L'ÉCRAN (/val field_id valeur [phrase])
                elif cmd == "/val":
                    subparts = arg.split(maxsplit=2)
                    if len(subparts) < 2:
                        print(f"{YELLOW}Usage : /val <field_id> <valeur> [phrase facultative]{RESET}")
                        print(f"Ex : /val temperature 36.8")
                        print(f"Ex : /val heart_rate 72 Votre pouls est mesuré à 72.")
                        continue
                    fid = subparts[0]
                    fval = subparts[1]
                    speech = subparts[2] if len(subparts) > 2 else None

                    # Détection d'unité automatique
                    unit = "°C" if "temp" in fid else ("BPM" if "heart" in fid or "pulse" in fid else ("%" if "spo2" in fid else ""))
                    await broadcast_instruction({
                        "origin": "server",
                        "text_to_speak": speech,
                        "value_to_show": {"field_id": fid, "value": fval, "unit": unit},
                        "fields": {fid: fval}
                    })
                    print(f"\n{GREEN}👉 Champ mis à jour à l'écran : {fid} = {fval} {unit} | Voix : {speech or '(silence)'}{RESET}\n")
                    continue

                # 7. SCÉNARIO VITALS AUTOMATISÉ (Optionnel)
                elif cmd == "/vitals":
                    await run_vitals_demo()
                    continue

                # 8. RETOUR À L'ACCUEIL
                elif cmd == "/home":
                    speech = arg or "Retour à l'écran d'accueil."
                    await broadcast_instruction({
                        "origin": "server",
                        "text_to_speak": speech,
                        "instruction_ui": {"screen": "home", "action": "navigate"},
                        "voice_hints": ["Orientation", "Renseignements", "Consultation"],
                        "robot_status": {"status_label": "Prêt"}
                    })
                    print(f"\n{GREEN}👉 Retour Accueil | Voix : « {speech} »{RESET}\n")
                    continue

                # 9. ÉCRAN DE VEILLE (SPLASH)
                elif cmd == "/splash":
                    await broadcast_instruction({
                        "origin": "server",
                        "text_to_speak": None,
                        "instruction_ui": {"screen": "splash", "action": "navigate"},
                        "robot_status": {"status_label": "En veille"}
                    })
                    print(f"\n{GREEN}👉 Téléphone mis sur l'écran initial (Splash / Veille). Touchez l'écran ou parlez pour tester le réveil !{RESET}\n")
                    continue

                # 10. ARRÊT D'URGENCE
                elif cmd == "/stop":
                    speech = arg or "Arrêt d'urgence du robot."
                    await broadcast_instruction({
                        "origin": "voice",
                        "text_to_speak": speech,
                        "speech_priority": "interrupt",
                        "instruction_ui": {"screen": "mission", "action": "stop", "require_confirmation": False},
                        "value_to_show": {"field_id": "mission_state", "value": "STOPPED"},
                        "fields": {"mission_state": "STOPPED"},
                        "robot_status": {"face_expression": "emergency", "status_label": "ROBOT ARRÊTÉ"}
                    })
                    print(f"\n{RED}🛑 ARRÊT D'URGENCE DÉCLENCHÉ | Voix : « {speech} »{RESET}\n")
                    continue

                else:
                    print(f"{YELLOW}Commande inconnue : {cmd}. Tapez /help pour la liste des commandes.{RESET}\n")
                    continue

            # TEXTE NORMAL TAPE SANS SLASH -> Lu à haute voix par le smartphone
            await broadcast_tts_only(raw_text)

        except Exception as e:
            print(f"Erreur : {e}")

async def main():
    host = "0.0.0.0"
    port = 5000

    adb_ok = try_adb_reverse()
    local_ips = get_local_ips()

    print(f"\n{CYAN}╔═══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}║{BOLD}        HUB VOCAL HIAR - CONTRÔLE OPÉRATEUR MANUEL (Raspberry Pi 4)   {RESET}{CYAN}║{RESET}")
    print(f"{CYAN}╚═══════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"🚀 Serveur WebSocket actif sur {BOLD}ws://0.0.0.0:{port}/ws{RESET}")
    print(f"📡 Adresses disponibles : 127.0.0.1 (USB ADB reverse) | {local_ips[0]} (Wi-Fi)\n")
    print(f"{YELLOW}💡 MODE OPÉRATEUR MANUEL :{RESET}")
    print(f"   • Le smartphone affiche tout ce qu'il entend.")
    print(f"   • Aucune réponse n'est inventée ou simulée par le programme.")
    print(f"   • Tapez n'importe quelle phrase dans ce terminal pour la faire prononcer par le robot !")
    print(f"   • Tapez {CYAN}/help{RESET} pour voir toutes les commandes (navigation, constantes, etc.)\n")

    server = websockets.serve(handle_client, host, port)
    await asyncio.gather(
        server,
        terminal_input_loop(),
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Arrêt du hub.{RESET}")
