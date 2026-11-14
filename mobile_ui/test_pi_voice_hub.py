#!/usr/bin/env python3
"""
Test Hub WebSocket pour HIAR (Raspberry Pi 4 Mock / Démonstrateur vocal)
Conforme au contrat mobile_ui/hiar_contract_v1.json

Rôle de ce script :
1. Écoute sur ws://0.0.0.0:5000/ws
2. Dès que l'application mobile se connecte, il envoie un message TTS de bienvenue
3. Dès que l'application mobile envoie le texte brut entendu par le micro (voice/stt/final),
   ce script (simulant le Pi 4 / ROS 2) analyse la phrase et renvoie :
   - Un ordre TTS (voice/tts/request) que le smartphone prononce à haute voix
   - Ou un ordre d'action (ui/action/request) pour changer l'écran du smartphone
4. Dès que l'utilisateur clique sur un bouton de l'écran, ce script reçoit l'action tactile.
"""

import asyncio
import json
import logging
import time

try:
    import websockets
except ImportError:
    print("Erreur: websockets n'est pas installé. Exécutez : pip install websockets")
    exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CLIENTS = set()

def create_envelope(msg_type, topic=None, payload=None, qos=0):
    env = {
        "v": 1,
        "type": msg_type,
        "ts": int(time.time()),
    }
    if topic:
        env["topic"] = topic
    if payload is not None:
        env["payload"] = payload
    if qos:
        env["qos"] = qos
    return json.dumps(env)

async def handle_client(websocket):
    remote = websocket.remote_address
    logging.info(f"🟢 Nouvelle connexion mobile depuis {remote}")
    CLIENTS.add(websocket)

    try:
        # 1. Message de bienvenue : TTS ordonné par le Pi 4
        welcome_tts = create_envelope(
            "pub",
            topic="voice/tts/request",
            payload={"text": "Bonjour ! Le Raspberry Pi 4 est connecté. Je vous écoute."},
            qos=1,
        )
        await websocket.send(welcome_tts)

        # 2. Envoi de l'état du robot
        robot_ready = create_envelope(
            "pub",
            topic="robot/status",
            payload={"state": "IDLE", "battery": 95, "docked": False},
        )
        await websocket.send(robot_ready)

        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                topic = data.get("topic")
                payload = data.get("payload", {})

                # Ping / Pong
                if msg_type == "ping":
                    pong = json.dumps({"v": 1, "type": "pong", "ts": int(time.time())})
                    await websocket.send(pong)
                    continue

                # A. Réception du texte entendu par le micro du téléphone (Écoute permanente)
                if topic == "voice/stt/final":
                    heard_text = payload.get("text", "").strip()
                    logging.info(f"🎤 [MICROPHONE MOBILE] Reçu texte brut : « {heard_text} »")

                    # Le Pi 4 effectue ici l'analyse sémantique (NLU / Intent / ROS 2) :
                    text_lower = heard_text.lower()

                    if any(w in text_lower for w in ["pharmacie", "médicament", "ordonnance"]):
                        logging.info("🧠 [ANALYSE PI 4] Intention détectée : ORIENTATION -> PHARMACIE")
                        # 1. Ordre de changement d'écran vers confirmation Pharmacie
                        action_msg = create_envelope(
                            "pub",
                            topic="ui/action/request",
                            payload={"action_id": "orientation.select", "args": {"destination": "PHARMACY"}},
                            qos=1,
                        )
                        await websocket.send(action_msg)
                        # 2. Ordre TTS : le téléphone parle à haute voix
                        tts_msg = create_envelope(
                            "pub",
                            topic="voice/tts/request",
                            payload={"text": "Très bien. Je vous oriente vers la pharmacie."},
                            qos=1,
                        )
                        await websocket.send(tts_msg)

                    elif any(w in text_lower for w in ["laboratoire", "analyse", "prise de sang"]):
                        logging.info("🧠 [ANALYSE PI 4] Intention détectée : ORIENTATION -> LABORATOIRE")
                        action_msg = create_envelope(
                            "pub",
                            topic="ui/action/request",
                            payload={"action_id": "orientation.select", "args": {"destination": "LABORATORY"}},
                            qos=1,
                        )
                        await websocket.send(action_msg)
                        tts_msg = create_envelope(
                            "pub",
                            topic="voice/tts/request",
                            payload={"text": "Entendu, affichage du laboratoire."},
                            qos=1,
                        )
                        await websocket.send(tts_msg)

                    elif any(w in text_lower for w in ["stop", "arrête", "arrêter", "annuler"]):
                        logging.info("🧠 [ANALYSE PI 4] Intention détectée : ARRÊT D'URGENCE ROBOT")
                        action_msg = create_envelope(
                            "pub",
                            topic="ui/action/request",
                            payload={"action_id": "robot.stop", "args": {}},
                            qos=1,
                        )
                        await websocket.send(action_msg)
                        tts_msg = create_envelope(
                            "pub",
                            topic="voice/tts/request",
                            payload={"text": "Arrêt du robot immédiat."},
                            qos=1,
                        )
                        await websocket.send(tts_msg)

                    elif any(w in text_lower for w in ["commencer", "démarrer", "accueil"]):
                        action_msg = create_envelope(
                            "pub",
                            topic="ui/action/request",
                            payload={"action_id": "app.home", "args": {}},
                            qos=1,
                        )
                        await websocket.send(action_msg)
                        tts_msg = create_envelope(
                            "pub",
                            topic="voice/tts/request",
                            payload={"text": "Bienvenue sur HIAR. Choisissez un service."},
                            qos=1,
                        )
                        await websocket.send(tts_msg)

                    else:
                        # Écho générique du Pi 4 qui confirme qu'il a reçu le texte brut
                        tts_msg = create_envelope(
                            "pub",
                            topic="voice/tts/request",
                            payload={"text": f"Le Raspberry Pi a bien reçu : {heard_text}"},
                            qos=1,
                        )
                        await websocket.send(tts_msg)

                # B. Réception d'une action tactile depuis l'écran du smartphone
                elif topic == "ui/action/request":
                    action_id = payload.get("action_id")
                    args = payload.get("args", {})
                    logging.info(f"👆 [TACTILE MOBILE] Action reçue : {action_id} avec args={args}")

                    # Le Pi 4 peut faire parler le téléphone pour confirmer l'action tactile
                    if action_id == "splash.start":
                        tts_msg = create_envelope(
                            "pub",
                            topic="voice/tts/request",
                            payload={"text": "Bienvenue sur HIAR."},
                            qos=1,
                        )
                        await websocket.send(tts_msg)

                # C. Réception du changement d'écran (ui/state)
                elif topic == "ui/state":
                    screen = payload.get("screen")
                    actions = payload.get("actions", [])
                    logging.info(f"📱 [ÉTAT ÉCRAN] Écran actif : '{screen}' | Actions actives : {actions}")

            except json.JSONDecodeError:
                logging.warning(f"Message JSON invalide reçu : {message}")
            except Exception as e:
                logging.error(f"Erreur traitement message : {e}")

    except websockets.exceptions.ConnectionClosed:
        logging.info(f"🔴 Déconnexion mobile {remote}")
    finally:
        CLIENTS.remove(websocket)

async def main():
    host = "0.0.0.0"
    port = 5000
    logging.info(f"🚀 Hub WebSocket HIAR démarré sur ws://{host}:{port}/ws")
    logging.info("En attente de connexion depuis le smartphone Android...")
    async with websockets.serve(handle_client, host, port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Arrêt du Hub.")
