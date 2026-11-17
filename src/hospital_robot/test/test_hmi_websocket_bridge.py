"""Tests d'intégration pour le pont WebSocket HMI (HMIWebSocketBridgeNode)."""

import asyncio
import json
import socket
import time
import pytest
import websockets

try:
    import rclpy
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False

from hospital_robot.hmi_websocket_bridge_node import HMIWebSocketBridgeNode, String


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeMsg:
    def __init__(self, data: str):
        self.data = data


@pytest.fixture
def bridge_node():
    initialized_here = False
    if ROS_AVAILABLE and not rclpy.ok():
        rclpy.init()
        initialized_here = True

    port = get_free_port()
    node = HMIWebSocketBridgeNode(host="127.0.0.1", port=port)

    # Enregistreur de messages publiés sur les publishers ROS 2
    class _PubRecorder:
        def __init__(self, orig_pub):
            self.published = []
            self._orig = orig_pub
        def publish(self, msg):
            self.published.append(msg)

    node.hmi_request_pub = _PubRecorder(node.hmi_request_pub)
    node.navigation_command_pub = _PubRecorder(node.navigation_command_pub)
    node.vitals_request_pub = _PubRecorder(node.vitals_request_pub)

    node.start_websocket_server()
    yield node, port
    node.stop_websocket_server()
    node.destroy_node()

    if ROS_AVAILABLE and initialized_here and rclpy.ok():
        rclpy.shutdown()


def test_bridge_lifecycle_and_messages(bridge_node):
    node, port = bridge_node

    async def _run_test():
        uri = f"ws://127.0.0.1:{port}/ws"
        async with websockets.connect(uri) as ws:
            # 1. Vérification du message de bienvenue automatique
            welcome_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            welcome_data = json.loads(welcome_raw)
            assert welcome_data["type"] == "welcome"
            assert welcome_data["payload"]["server"] == "HIAR Central ROS2 Bridge"

            # 2. Test du Ping / Pong
            await ws.send(json.dumps({"v": 1, "type": "ping", "ts": 12345}))
            pong_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            pong_data = json.loads(pong_raw)
            assert pong_data["type"] == "pong"

            # 3. Test de la réception vocale : orientation pharmacie
            stt_envelope = {
                "v": 1,
                "type": "pub",
                "topic": "voice/stt/final",
                "ts": 12345,
                "payload": {"text": "Emmène-moi à la pharmacie", "confidence": 0.96},
            }
            await ws.send(json.dumps(stt_envelope))

            # Attente de server/instruction et voice/tts/request
            instruction_received = None
            tts_received = None

            for _ in range(2):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg_data = json.loads(msg_raw)
                if msg_data["topic"] == "server/instruction":
                    instruction_received = msg_data["payload"]
                elif msg_data["topic"] == "voice/tts/request":
                    tts_received = msg_data["payload"]

            assert instruction_received is not None
            assert instruction_received["instruction_ui"]["screen"] == "orientation"
            assert instruction_received["instruction_ui"]["destination"] == "Pharmacie"
            assert instruction_received["instruction_ui"]["require_confirmation"] is True
            assert "Pharmacie" in instruction_received["text_to_speak"]

            assert tts_received is not None
            assert "Pharmacie" in tts_received["text"]

            # Pas de publication ROS 2 avant confirmation vocale !
            assert len(node.hmi_request_pub.published) == 0

            # 3b. Test de la confirmation vocale : "Oui"
            confirm_envelope = {
                "v": 1,
                "type": "pub",
                "topic": "voice/stt/final",
                "ts": 12345,
                "payload": {"text": "Oui s'il vous plaît", "confidence": 0.98},
            }
            await ws.send(json.dumps(confirm_envelope))

            confirm_instruction = None
            for _ in range(2):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg_data = json.loads(msg_raw)
                if msg_data["topic"] == "server/instruction":
                    confirm_instruction = msg_data["payload"]

            assert confirm_instruction is not None
            assert confirm_instruction["instruction_ui"]["screen"] == "mission"
            assert confirm_instruction["instruction_ui"]["destination"] == "Pharmacie"

            # Vérification de la publication ROS 2 correspondante après confirmation
            assert len(node.hmi_request_pub.published) > 0
            last_hmi_msg = node.hmi_request_pub.published[-1]
            assert json.loads(last_hmi_msg.data) == {
                "category": "ORIENTATION",
                "destination": "PHARMACY",
            }

            # 4. Test de la commande vocale d'arrêt d'urgence
            stop_stt_envelope = {
                "v": 1,
                "type": "pub",
                "topic": "voice/stt/final",
                "ts": 12346,
                "payload": {"text": "Stop arrête-toi !", "confidence": 0.99},
            }
            await ws.send(json.dumps(stop_stt_envelope))

            # Lecture de l'instruction et du TTS d'arrêt
            stop_inst = None
            for _ in range(2):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg_data = json.loads(msg_raw)
                if msg_data["topic"] == "server/instruction":
                    stop_inst = msg_data["payload"]

            assert stop_inst is not None
            assert stop_inst["speech_priority"] == "interrupt"
            assert stop_inst["instruction_ui"]["action"] == "stop"
            assert stop_inst["value_to_show"]["value"] == "STOPPED"

            # Vérification de la commande STOP sur /navigation/command
            assert len(node.navigation_command_pub.published) > 0
            assert node.navigation_command_pub.published[-1].data == "STOP"

            # 5. Test d'action tactile sur l'écran : orientation laboratoire
            touch_envelope = {
                "v": 1,
                "type": "pub",
                "topic": "ui/action/request",
                "ts": 12347,
                "payload": {
                    "action_id": "orientation.select",
                    "args": {"destination": "LABORATORY"},
                },
            }
            await ws.send(json.dumps(touch_envelope))
            await asyncio.sleep(0.1)

            last_hmi_msg = node.hmi_request_pub.published[-1]
            assert json.loads(last_hmi_msg.data) == {
                "category": "ORIENTATION",
                "destination": "LABORATORY",
            }

            # 6. Test de retour ROS 2 ➔ WebSocket : signes vitaux
            vitals_line = "RESULT,temperature_c=36.8,heart_rate_bpm=72,spo2_percent=98"
            node._on_vitals_result(
                FakeMsg(json.dumps({"request_id": "req-1", "line": vitals_line}))
            )

            # Le smartphone doit recevoir l'instruction mise à jour
            vitals_inst = None
            for _ in range(2):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg_data = json.loads(msg_raw)
                if msg_data["topic"] == "server/instruction":
                    vitals_inst = msg_data["payload"]

            assert vitals_inst is not None

            # 7. Test d'enregistrement de rendez-vous consultation en base de données
            import sys
            from pathlib import Path
            for cand in [
                Path(__file__).resolve().parents[3] / "web_interface",
                Path.home() / "hiar-main" / "web_interface",
                Path("/home/cecilia/hiar-main/web_interface"),
            ]:
                if cand.exists() and str(cand) not in sys.path:
                    sys.path.insert(0, str(cand))

            from consultation_sessions_store import set_doctor_session, TZ
            from datetime import datetime
            today_iso = datetime.now(TZ).date().isoformat()
            set_doctor_session(today_iso, "B", "MAT", True)

            unique_phone = f"032{int(time.time() * 1000) % 10000000:07d}"
            book_envelope = {
                "v": 1,
                "type": "pub",
                "topic": "ui/action/request",
                "ts": 12348,
                "payload": {
                    "action_id": "consult.confirm",
                    "args": {
                        "patient_name": "Alice Dupont",
                        "contact": unique_phone,
                        "reason_code": "consultation_generale",
                        "doctor_code": "B",
                        "period": "MAT",
                        "temperature_c": 36.6,
                        "heart_rate_bpm": 70,
                        "spo2_percent": 99,
                    },
                },
            }
            await ws.send(json.dumps(book_envelope))
            await asyncio.sleep(0.15)

            last_hmi = node.hmi_request_pub.published[-1]
            last_hmi_payload = json.loads(last_hmi.data)
            assert last_hmi_payload["category"] == "CONSULTATION"
            assert last_hmi_payload["action"] == "APPOINTMENT"
            assert "ticket_label" in last_hmi_payload

            # Consommer l'instruction et le TTS émis lors de la confirmation
            booking_inst = None
            for _ in range(2):
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg_data = json.loads(msg_raw)
                if msg_data["topic"] == "server/instruction":
                    booking_inst = msg_data["payload"]

            assert booking_inst is not None
            assert booking_inst["instruction_ui"]["screen"] == "consultation"
            assert booking_inst["instruction_ui"]["step"] == 6
            assert "ticket_label" in booking_inst["fields"]
            assert vitals_inst["instruction_ui"]["screen"] == "consultation"
            assert vitals_inst["value_to_show"]["value"] == "done"
            assert vitals_inst["fields"]["temperature"] == 36.8
            assert vitals_inst["fields"]["heart_rate"] == 72
            assert vitals_inst["fields"]["spo2"] == 98

            # 7. Test de retour ROS 2 ➔ WebSocket : statut d'arrêt d'urgence
            node._on_robot_status(FakeMsg("EMERGENCY_STOP"))
            robot_status_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            status_data = json.loads(robot_status_msg)
            assert status_data["topic"] == "robot/mission/status"
            assert status_data["payload"]["status"] == "EMERGENCY_STOP"

    asyncio.run(_run_test())
