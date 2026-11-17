"""Tests unitaires pour le moniteur de logs unifié HIAR (scripts/hiar_log_monitor.py)."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import hiar_log_monitor as lm  # noqa: E402


def test_parse_esp32_node_log():
    raw = "[esp32_interface-1] [ERROR] [1794940939.946829467] [esp32_interface]: Unable to connect to ESP32"
    entry = lm.parse_log_line(raw, source_hint="ros2")
    assert entry is not None
    assert entry.tag == "ESP32"
    assert entry.level == "ERROR"
    assert "Unable to connect to ESP32" in entry.message


def test_parse_mobile_explicit_tag_from_bridge():
    raw = '[hmi_websocket_bridge-6] [INFO] [1794940962.144] [hmi_websocket_bridge]: [MOBILE] 🎤 Voix STT: "Pharmacie" (conf=0.95)'
    entry = lm.parse_log_line(raw, source_hint="ros2")
    assert entry is not None
    assert entry.tag == "MOBILE"
    assert entry.level == "INFO"
    assert entry.message.startswith("🎤 Voix STT")
    assert "[MOBILE]" not in entry.message


def test_parse_mobile_inferred_tag_from_bridge():
    raw = "[hmi_websocket_bridge-6] [INFO] [1794940962.144] [hmi_websocket_bridge]: Client connected: ('192.168.43.1', 54321)"
    entry = lm.parse_log_line(raw, source_hint="ros2")
    assert entry is not None
    assert entry.tag == "MOBILE"
    assert entry.level == "INFO"


def test_parse_llm_tag_from_pylog():
    raw = "[hmi_websocket_bridge-6] 2026-11-17 21:42:35,973 [WARNING] LLM inference error: timed out"
    entry = lm.parse_log_line(raw, source_hint="ros2")
    assert entry is not None
    assert entry.tag == "LLM"
    assert entry.level == "WARN"
    assert entry.timestamp == "21:42:35"


def test_parse_navigation_and_obstacle_nodes():
    nav = lm.parse_log_line(
        "[navigation_decision-4] [INFO] [1794940940.059] [navigation_decision]: Sensors: FRONT ultrasonic + LEFT/RIGHT IR.",
        source_hint="ros2",
    )
    obs = lm.parse_log_line(
        "[obstacle_detector-2] [WARN] [1794940940.060] [obstacle_detector]: Obstacle detected at 15.0 cm",
        source_hint="ros2",
    )
    assert nav is not None and nav.tag == "NAVIGATION"
    assert obs is not None and obs.tag == "OBSTACLE" and obs.level == "WARN"


def test_parse_web_access_log():
    raw = '192.168.43.1 - - [17/Nov/2026 21:42:42] "GET /api/doctor/appointments HTTP/1.1" 200 -'
    entry = lm.parse_log_line(raw, source_hint="web")
    assert entry is not None
    assert entry.tag == "WEB"
    assert entry.level == "INFO"
    assert entry.timestamp == "21:42:42"
    assert "GET /api/doctor/appointments" in entry.message
    assert "-> 200" in entry.message


def test_format_and_filtering():
    entry = lm.LogEntry(timestamp="22:10:00", level="INFO", tag="MOBILE", message="Connecté")
    plain = lm.format_entry(entry, use_color=False)
    assert plain == "22:10:00 [INFO ] [MOBILE]     Connecté"
    assert lm.should_emit(entry, {"MOBILE", "ESP32"}, lm.LEVEL_ORDER["INFO"]) is True
    assert lm.should_emit(entry, {"ESP32"}, lm.LEVEL_ORDER["INFO"]) is False
    assert lm.should_emit(entry, None, lm.LEVEL_ORDER["WARN"]) is False
