import os
import sys
import time
from datetime import datetime
from pathlib import Path
import pytest

from app import app
from appointments_store import get_connection, init_db, init_sessions_db
from consultation_sessions_store import (
    create_session_appointment,
    ensure_daily_sessions,
    set_doctor_session,
    TZ,
)
from hospital_robot.hmi_websocket_bridge_node import HMIWebSocketBridgeNode
from hospital_robot.vitals_data_parser import validate_vitals


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_appointments.sqlite3"
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(test_db))
    monkeypatch.setenv("HIAR_WEB_PIN", "123456")
    init_sessions_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_favicon_route(client):
    """Vérifie que la route /favicon.ico répond 200 OK avec le bon mimetype."""
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.mimetype in ("image/x-icon", "image/png", "image/vnd.microsoft.icon")
    assert len(resp.data) > 0


def test_validate_vitals_cleaning():
    """Vérifie que validate_vitals gère correctement les chaînes avec unités et virgules."""
    temp, hr, spo2, err = validate_vitals("37,5 °C", "72 bpm", "98 %")
    assert err is None or len(err) == 0
    assert temp == 37.5
    assert hr == 72
    assert spo2 == 98


def test_mobile_consultation_vitals_appear_in_dashboard(client, monkeypatch):
    """Vérifie qu'un RDV soumis depuis l'app mobile après prise de constantes apparaît dans le dashboard admin."""
    today_iso = datetime.now(TZ).date().isoformat()
    ensure_daily_sessions()
    set_doctor_session(today_iso, "B", "MAT", True)

    bridge = HMIWebSocketBridgeNode()
    bridge.get_logger().info = lambda *args, **kwargs: None
    bridge.get_logger().warn = lambda *args, **kwargs: None
    bridge.get_logger().error = lambda *args, **kwargs: None

    unique_phone = f"032{int(time.time() * 1000) % 10000000:07d}"
    mobile_payload = {
        "patient_name": "Jean Dupont",
        "contact": unique_phone,
        "patient_phone": unique_phone,
        "reason_code": "consultation_generale",
        "selected_reason": "consultation_generale",
        "doctor_code": "B",
        "selected_doctor": "B",
        "period": "MAT",
        "selected_period": "MAT",
        "temperature_c": "38.5 °C",  # fièvre -> déclenche alerte dashboard
        "heart_rate_bpm": "82 bpm",
        "spo2_percent": "97 %",
    }

    res = bridge._book_appointment(mobile_payload)
    assert res.get("ok") is True
    assert res.get("ticket_label") == f"B-MAT-{res.get('ticket_number')}"
    appt_id = res.get("appointment_id")
    assert appt_id is not None

    # Requête sur le dashboard admin
    headers = {"X-Web-PIN": "123456"}
    dash_resp = client.get("/api/admin/dashboard", headers=headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.get_json()
    assert dash_data.get("ok") is True

    appts = dash_data.get("appointments", [])
    matching = [a for a in appts if a.get("id") == appt_id]
    assert len(matching) == 1
    target = matching[0]

    assert target["patient_name"] == "Jean Dupont"
    assert target["temperature_c"] == 38.5
    assert target["heart_rate_bpm"] == 82
    assert target["spo2_percent"] == 97
    assert target["ticket_label"] == f"B-MAT-{res.get('ticket_number')}"

    # Vérification que l'alerte température est bien comptée
    stats = dash_data.get("stats", {})
    assert stats.get("alerts", 0) >= 1
    assert stats.get("total", 0) >= 1
