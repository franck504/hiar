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
            "ultrasonic_left": {"status": "ok", "distance_cm": 68.0, "detail": "68.0 cm"},
            "ultrasonic_right": {"status": "ok", "distance_cm": 19.2, "detail": "19.2 cm"},
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
    assert diag_on["sensors"]["ultrasonic_left"]["distance_cm"] == 68.0
    assert diag_on["sensors"]["ultrasonic_right"]["distance_cm"] == 19.2
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


def test_esp32_interface_parses_three_ultrasonic_frames_and_health(monkeypatch):
    import sys
    from unittest.mock import MagicMock

    fake_serial_mod = MagicMock()
    fake_serial_mod.SerialException = Exception
    fake_serial_mod.Serial.side_effect = Exception("no usb in test")
    monkeypatch.setitem(sys.modules, "serial", fake_serial_mod)

    from hospital_robot.esp32_interface_node import ESP32Interface

    node = ESP32Interface()

    class _FakeSerial:
        def __init__(self, lines):
            self._lines = list(lines)
            self.is_open = True

        @property
        def in_waiting(self):
            return len(self._lines)

        def readline(self):
            return self._lines.pop(0) if self._lines else b""

        def close(self):
            self.is_open = False

    node.serial_connection = _FakeSerial([
        b"DIST,45.2\n",
        b"DIST_L,72.3\n",
        b"DIST_R,18.6\n",
        b"HEALTH,temp=1,pulse=1,us=1,dist=45.2,us_l=1,dist_l=72.3,us_r=1,dist_r=18.6,motors=1,mode=IDLE\n",
    ])
    node.read_serial()

    assert [m.data for m in node.ultrasonic_publisher.published] == [45.2]
    assert [m.data for m in node.ultrasonic_left_publisher.published] == [72.3]
    assert [m.data for m in node.ultrasonic_right_publisher.published] == [18.6]

    diag = node.build_diagnostics_dict()
    assert diag["sensors"]["ultrasonic"]["distance_cm"] == 45.2
    assert diag["sensors"]["ultrasonic_left"]["distance_cm"] == 72.3
    assert diag["sensors"]["ultrasonic_right"]["distance_cm"] == 18.6
    assert "ir_left" not in diag["sensors"]
    assert "ir_right" not in diag["sensors"]
    node.destroy_node()


def test_esp32_interface_survives_oserror_errno5_and_reconnects(monkeypatch):
    import sys
    from unittest.mock import MagicMock

    class _MockSerialException(Exception):
        pass

    class _ReconnectedSerial:
        is_open = True

        def write(self, data):
            pass

        def close(self):
            self.is_open = False

    fake_serial_mod = MagicMock()
    fake_serial_mod.SerialException = _MockSerialException
    fake_serial_mod.Serial.side_effect = _MockSerialException("initial offline")
    monkeypatch.setitem(sys.modules, "serial", fake_serial_mod)

    from hospital_robot import esp32_interface_node as mod

    monkeypatch.setattr(mod, "serial", fake_serial_mod)
    node = mod.ESP32Interface()

    class _BrokenSerial:
        is_open = True

        @property
        def in_waiting(self):
            raise OSError(5, "Input/output error")

        def close(self):
            raise OSError(5, "Input/output error")

    node.serial_connection = _BrokenSerial()
    # Ne doit PAS lever d'exception
    node.read_serial()
    assert node.serial_connection is None

    # Simule une ré-énumération USB sur /dev/ttyUSB1
    monkeypatch.setattr(mod.glob, "glob", lambda pattern: ["/dev/ttyUSB1"] if "ttyUSB" in pattern else [])

    def _open_port(port, baudrate, timeout):
        if port == "/dev/ttyUSB1":
            return _ReconnectedSerial()
        raise _MockSerialException("port missing")

    fake_serial_mod.Serial.side_effect = _open_port
    node.diagnostics_tick()

    assert node.serial_connection is not None
    assert node.port == "/dev/ttyUSB1"
    node.destroy_node()
