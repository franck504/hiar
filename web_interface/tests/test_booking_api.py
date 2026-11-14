import pytest

from app import app

DAY = "2099-01-15"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(tmp_path / "t.sqlite3"))
    return app.test_client()


def _payload(**overrides):
    data = {
        "patient_name": "Patient Test",
        "contact": "034 12 345 67",
        "reason": "Consultation générale",
        "requested_date": DAY,
        "requested_time": "09:00",
    }
    data.update(overrides)
    return data


def test_booking_returns_queue_number_and_doctor(client):
    response = client.post("/api/appointments", json=_payload(slot_id=2))
    assert response.status_code == 201
    body = response.get_json()
    assert body["ok"] is True
    assert body["queue_number"] == 1
    assert body["doctor"] == "Médecin B"
    assert "appointment_id" in body


def test_booking_persists_valid_vital_signs(client):
    response = client.post(
        "/api/appointments",
        json=_payload(
            temperature_c=36.7,
            heart_rate_bpm=72,
            spo2_percent=None,
        ),
    )

    assert response.status_code == 201

    from appointments_store import list_appointments

    appointments = list_appointments()
    assert len(appointments) == 1
    assert appointments[0]["temperature_c"] == pytest.approx(36.7)
    assert appointments[0]["heart_rate_bpm"] == 72
    assert appointments[0]["spo2_percent"] is None


@pytest.mark.parametrize("temperature", [float("nan"), float("inf"), float("-inf")])
def test_booking_rejects_non_finite_temperature(client, temperature):
    response = client.post(
        "/api/appointments",
        json=_payload(temperature_c=temperature),
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_booking_rejects_temperature_out_of_range(client):
    response = client.post(
        "/api/appointments",
        json=_payload(temperature_c=99.0),
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_duplicate_phone_same_day_is_409_without_queue_number(client):
    assert client.post("/api/appointments", json=_payload()).status_code == 201
    response = client.post(
        "/api/appointments",
        json=_payload(contact="+261 34 12 345 67", requested_time="10:00"),
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["ok"] is False
    assert body["code"] == "duplicate_phone"
    assert "queue_number" not in body


def test_slot_taken_is_409(client):
    assert client.post("/api/appointments", json=_payload()).status_code == 201
    response = client.post(
        "/api/appointments", json=_payload(contact="033 11 111 11")
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "slot_taken"


def test_invalid_slot_is_400(client):
    response = client.post(
        "/api/appointments", json=_payload(requested_time="12:00")
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_slot"


def test_slot_id_inconsistent_with_time_is_400(client):
    response = client.post("/api/appointments", json=_payload(slot_id=1))
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_slot"


def test_invalid_phone_is_400(client):
    response = client.post(
        "/api/appointments", json=_payload(contact="abc")
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_phone"


def test_slots_endpoint_shows_availability_without_patient_data(client):
    client.post("/api/appointments", json=_payload())
    response = client.get("/api/slots?date=" + DAY)
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["slots"]) == 4
    taken = [s for s in body["slots"] if not s["available"]]
    assert [s["id"] for s in taken] == [2]
    assert "patient_name" not in response.get_data(as_text=True)


def test_slots_endpoint_rejects_bad_date(client):
    assert client.get("/api/slots?date=demain").status_code == 400
    assert client.get("/api/slots").status_code == 400

def _create_staff_test_appointment(client):
    response = client.post("/api/appointments", json=_payload())
    assert response.status_code == 201
    return response.get_json()["appointment_id"]


def test_staff_appointments_api_requires_authentication(client, monkeypatch):
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "test-staff-token")

    response = client.get("/api/appointments")
    assert response.status_code == 401

    response = client.patch(
        "/api/appointments/1",
        json={"status": "appelé"},
    )
    assert response.status_code == 401


def test_staff_api_updates_only_through_normal_transitions(client, monkeypatch):
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "test-staff-token")
    appointment_id = _create_staff_test_appointment(client)
    headers = {"X-Staff-Token": "test-staff-token"}

    response = client.patch(
        f"/api/appointments/{appointment_id}",
        json={"status": "terminé"},
        headers=headers,
    )
    assert response.status_code == 400

    response = client.patch(
        f"/api/appointments/{appointment_id}",
        json={"status": "appelé"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "appelé"

    response = client.patch(
        f"/api/appointments/{appointment_id}",
        json={"status": "terminé"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "terminé"


def test_staff_api_requires_explicit_boolean_for_exceptional_correction(
    client, monkeypatch
):
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "test-staff-token")
    appointment_id = _create_staff_test_appointment(client)
    headers = {"X-Staff-Token": "test-staff-token"}

    invalid = client.patch(
        f"/api/appointments/{appointment_id}",
        json={"status": "appelé", "exceptional_correction": "true"},
        headers=headers,
    )
    assert invalid.status_code == 400

    normal = client.patch(
        f"/api/appointments/{appointment_id}",
        json={"status": "appelé"},
        headers=headers,
    )
    assert normal.status_code == 200

    correction = client.patch(
        f"/api/appointments/{appointment_id}",
        json={
            "status": "en attente",
            "exceptional_correction": True,
        },
        headers=headers,
    )
    assert correction.status_code == 200
    assert correction.get_json()["status"] == "en attente"
