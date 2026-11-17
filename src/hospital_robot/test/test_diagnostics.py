"""Tests unitaires et d'intégration pour les diagnostics ESP32/capteurs (Option B)."""

import asyncio
import json
import socket
import pytest
import websockets

from hospital_robot.hmi_websocket_bridge_node import HMIWebSocketBridgeNode


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _FakeMsg:
    def __init__(self, data: str):
        self.data = data


def test_bridge_diagnostics_offline_then_online():
    port = _free_port()
    node = HMIWebSocketBridgeNode(host="127.0.0.1", port=port)

    # Avant réception de /esp32/diagnostics -> ESP32 offline
    diag_off = node.build_system_diagnostics()
    assert diag_off["esp32"]["status"] == "offline"
    assert diag_off["sensors"]["ds18b20"]["status"] == "offline"
    assert diag_off["sensors"]["max30102"]["status"] == "offline"

    # Simulation de réception d'une trame /esp32/diagnostics (Option B)
    sample = {
        "ts": 123456.0,
        "firmware_diagnostics": "option_b",
        "esp32": {"status": "ok", "port": "/dev/ttyUSB0", "detail": "Connecté (/dev/ttyUSB0)"},
        "sensors": {
            "ultrasonic": {"status": "ok", "distance_cm": 42.5, "detail": "42.5 cm"},
            "ir_left": {"status": "ok", "state": 1, "raw": 3100, "detail": "Libre (ADC 3100)"},
            "ir_right": {"status": "ok", "state": 0, "raw": 800, "detail": "Obstacle (ADC 800)"},
            "ds18b20": {"status": "ok", "detail": "1-Wire OK (GPIO 23)"},
            "max30102": {"status": "absent", "detail": "Non détecté (I²C 0x57)"},
            "motors": {"status": "ok", "mode": "IDLE", "detail": "Prêt (IDLE)"},
        },
    }
    node._on_esp32_diagnostics(_FakeMsg(json.dumps(sample)))

    diag_on = node.build_system_diagnostics()
    assert diag_on["firmware_diagnostics"] == "option_b"
    assert diag_on["esp32"]["status"] == "ok"
    assert diag_on["sensors"]["ultrasonic"]["distance_cm"] == 42.5
    assert diag_on["sensors"]["ds18b20"]["status"] == "ok"
    assert diag_on["sensors"]["max30102"]["status"] == "absent"
    node.destroy_node()


def test_websocket_diagnostics_subscription_and_refresh():
    port = _free_port()
    node = HMIWebSocketBridgeNode(host="127.0.0.1", port=port)

    class _Rec:
        def __init__(self):
            self.published = []
        def publish(self, msg):
            self.published.append(msg)

    node.diagnostics_request_pub = _Rec()
    node.start_websocket_server()

    async def _run():
        uri = f"ws://127.0.0.1:{port}/ws"
        async with websockets.connect(uri) as ws:
            welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            assert welcome["type"] == "welcome"

            # S'abonner à robot/diagnostics -> doit recevoir un snapshot immédiat
            await ws.send(json.dumps({"v": 1, "type": "sub", "id": "s1", "topic": "robot/diagnostics"}))
            diag_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            assert diag_msg["topic"] == "robot/diagnostics"
            assert "esp32" in diag_msg["payload"]
            assert "sensors" in diag_msg["payload"]
            assert "ros_nodes" in diag_msg["payload"]

            # Envoyer l'action tactile diagnostics.refresh -> doit publier sur /esp32/diagnostics/request et renvoyer un snapshot
            await ws.send(json.dumps({
                "v": 1,
                "type": "pub",
                "topic": "ui/action/request",
                "payload": {"action_id": "diagnostics.refresh", "args": {}},
            }))
            refreshed = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            assert refreshed["topic"] == "robot/diagnostics"
            assert len(node.diagnostics_request_pub.published) == 1
            assert node.diagnostics_request_pub.published[0].data == "REFRESH"

    try:
        asyncio.run(_run())
    finally:
        node.stop_websocket_server()
        node.destroy_node()
