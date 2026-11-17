from pathlib import Path

import pytest

from app import app

BASE = Path(__file__).resolve().parent.parent
TOKEN = "test-token-123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(tmp_path / "t.sqlite3"))
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", TOKEN)
    return app.test_client()


def _book(client):
    return client.post("/api/appointments", json={
        "patient_name": "Nom Secret",
        "contact": "034 12 345 67",
        "reason": "Motif secret",
        "requested_date": "2099-01-15",
        "requested_time": "09:00",
        "slot_id": 2,
    })


def test_staff_page_is_served_without_patient_data(client):
    assert _book(client).status_code == 201
    response = client.get("/staff")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Nom Secret" not in html
    assert "Motif secret" not in html


def test_staff_api_logs_unauthorized_access_without_token(caplog, client):
    secret = "do-not-log-this-token"

    response = client.get(
        "/api/appointments",
        headers={"X-Staff-Token": secret},
    )

    assert response.status_code == 401
    assert "Refus d'accès : GET /api/appointments — HTTP 401" in caplog.text
    assert secret not in caplog.text

def test_staff_api_requires_token(client):
    assert _book(client).status_code == 201
    assert client.get("/api/appointments").status_code == 401
    bad = client.get("/api/appointments", headers={"X-Staff-Token": "mauvais"})
    assert bad.status_code == 401
    good = client.get("/api/appointments", headers={"X-Staff-Token": TOKEN})
    assert good.status_code == 200
    assert len(good.get_json()["appointments"]) == 1


def test_staff_interface_exposes_controlled_status_actions():
    js = (BASE / "static" / "staff.js").read_text(encoding="utf-8")
    html = (BASE / "templates" / "staff.html").read_text(encoding="utf-8")

    assert "PATCH" in js
    assert "/api/staff/consultations/" in js
    assert "exceptional_correction" in js
    assert "Appeler" in js
    assert "Terminer" in js
    assert "Confirmer la correction" in html

def test_patient_page_has_no_staff_access(client):
    html = client.get("/").get_data(as_text=True)
    assert "Espace du personnel" not in html


def test_vitals_unavailable_without_sensors(client, monkeypatch):
    monkeypatch.delenv("HIAR_VITALS_PORT", raising=False)

    response = client.post("/api/vitals/acquire")
    assert response.status_code == 200
    body = response.get_json()
    assert body["state"] == "indisponible"
    assert body["values"] == {
        "temperature_c": None,
        "heart_rate_bpm": None,
        "spo2_percent": None,
    }
    assert body["measured_at"] is None
    assert body["measured_at"] is None
