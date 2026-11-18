import json
import sys
import time
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import app as web_app


def test_system_diagnostics_offline_when_snapshot_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HIAR_DIAGNOSTICS_FILE", str(tmp_path / "missing.json"))
    client = web_app.app.test_client()

    resp = client.get("/api/system/diagnostics")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bridge_online"] is False
    assert data["esp32"]["status"] == "offline"
    assert "ds18b20" in data["sensors"]
    assert "max30102" in data["sensors"]


def test_system_diagnostics_returns_live_snapshot(tmp_path, monkeypatch):
    snap = tmp_path / "hiar_diagnostics.json"
    payload = {
        "ts": time.time(),
        "firmware_diagnostics": "option_b",
        "esp32": {"status": "ok", "port": "/dev/ttyUSB0", "detail": "Connecté"},
        "sensors": {
            "ultrasonic": {"status": "ok", "distance_cm": 45.2, "detail": "OK"},
            "ir_left": {"status": "ok", "state": "CLEAR", "raw": 1, "detail": "Libre"},
            "ir_right": {"status": "ok", "state": "CLEAR", "raw": 1, "detail": "Libre"},
            "ds18b20": {"status": "ok", "detail": "Sonde détectée"},
            "max30102": {"status": "ok", "detail": "I2C 0x57 OK"},
            "motors": {"status": "ok", "mode": "IDLE", "detail": "PWM prêt"},
        },
        "ros_nodes": {"status": "ok", "active_count": 6, "total_count": 6, "detail": "6/6 actifs"},
        "llm": {"status": "ok", "detail": "Gemini actif (5 clé(s)) + Qwen secours prêt"},
        "network": {"hostname": "cecilia-desktop", "ip": "192.168.43.52", "ws_port": 5000, "web_port": 5001},
    }
    snap.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("HIAR_DIAGNOSTICS_FILE", str(snap))

    client = web_app.app.test_client()
    resp = client.get("/api/system/diagnostics")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bridge_online"] is True
    assert data["esp32"]["status"] == "ok"
    assert data["sensors"]["ds18b20"]["status"] == "ok"
    assert data["llm"]["detail"] == "Gemini actif (5 clé(s)) + Qwen secours prêt"
