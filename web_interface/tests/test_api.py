import app as app_module
from app import app


class FakeBridge:
    error = None

    def publish(self, request_dict):
        return True


def test_home_page_returns_200():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_valid_orientation_request(monkeypatch):
    monkeypatch.setattr(app_module, "bridge", FakeBridge())
    client = app.test_client()
    response = client.post(
        "/api/request",
        json={"category": "ORIENTATION", "item": "PHARMACY"},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.get_json()["request"] == {
        "category": "ORIENTATION",
        "destination": "PHARMACY",
    }


def test_information_response_has_title_and_disclaimer(monkeypatch):
    monkeypatch.setattr(app_module, "bridge", FakeBridge())
    client = app.test_client()
    response = client.post(
        "/api/request",
        json={"category": "INFORMATION", "item": "HIV"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "VIH / SIDA"
    assert "non diagnostique" in data["message"]


def test_unknown_item_returns_400():
    client = app.test_client()
    response = client.post(
        "/api/request",
        json={"category": "ORIENTATION", "item": "UNKNOWN_DESTINATION"},
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_empty_body_returns_400():
    client = app.test_client()
    response = client.post(
        "/api/request",
        data="",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_create_appointment_returns_pending(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "HIAR_APPOINTMENTS_DB",
        str(tmp_path / "appointments.sqlite3"),
    )
    client = app.test_client()
    response = client.post(
        "/api/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason": "Consultation générale",
            "requested_date": "2099-01-15",
            "requested_time": "09:00",
        },
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["ok"] is True
    assert data["status"] == "PENDING"
    assert data["appointment_id"] > 0


def test_create_appointment_rejects_invalid_date(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "HIAR_APPOINTMENTS_DB",
        str(tmp_path / "appointments.sqlite3"),
    )
    client = app.test_client()
    response = client.post(
        "/api/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason": "Consultation générale",
            "requested_date": "2099-99-45",
            "requested_time": "09:00",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_create_appointment_rejects_missing_fields():
    client = app.test_client()
    response = client.post(
        "/api/appointments",
        json={"patient_name": "Patient Test"},
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_create_appointment_rejects_overlong_name(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "HIAR_APPOINTMENTS_DB",
        str(tmp_path / "appointments.sqlite3"),
    )
    client = app.test_client()
    response = client.post(
        "/api/appointments",
        json={
            "patient_name": "A" * 121,
            "contact": "0340000000",
            "reason": "Consultation générale",
            "requested_date": "2099-01-15",
            "requested_time": "09:00",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_create_appointment_rejects_whitespace_only_name():
    client = app.test_client()
    response = client.post(
        "/api/appointments",
        json={
            "patient_name": "   ",
            "contact": "0340000000",
            "reason": "Consultation générale",
            "requested_date": "2099-01-15",
            "requested_time": "09:00",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False

def _create_test_appointment(client):
    return client.post(
        "/api/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason": "Consultation générale",
            "requested_date": "2099-01-15",
            "requested_time": "09:00",
        },
    )


def test_staff_appointments_requires_authentication(monkeypatch):
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "secret-test-token")
    response = app.test_client().get("/api/appointments")

    assert response.status_code == 401
    assert response.get_json()["ok"] is False


def test_staff_appointments_returns_503_when_token_is_not_configured(
    monkeypatch,
):
    monkeypatch.delenv("HIAR_STAFF_API_TOKEN", raising=False)
    response = app.test_client().get(
        "/api/appointments",
        headers={"X-Staff-Token": "any-token"},
    )

    assert response.status_code == 503


def test_staff_can_list_and_filter_appointments(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "HIAR_APPOINTMENTS_DB",
        str(tmp_path / "appointments.sqlite3"),
    )
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "secret-test-token")
    client = app.test_client()
    created = _create_test_appointment(client)
    assert created.status_code == 201

    headers = {"X-Staff-Token": "secret-test-token"}
    response = client.get("/api/appointments", headers=headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert len(data["appointments"]) == 1
    assert data["appointments"][0]["patient_name"] == "Patient Test"

    filtered = client.get(
        "/api/appointments?status=appel%C3%A9",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert filtered.get_json()["appointments"] == []

    invalid_filter = client.get(
        "/api/appointments?status=inconnu",
        headers=headers,
    )
    assert invalid_filter.status_code == 400


def test_staff_can_update_appointment_status(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "HIAR_APPOINTMENTS_DB",
        str(tmp_path / "appointments.sqlite3"),
    )
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "secret-test-token")
    client = app.test_client()
    created = _create_test_appointment(client)
    appointment_id = created.get_json()["appointment_id"]

    response = client.patch(
        f"/api/appointments/{appointment_id}",
        json={"status": "appelé"},
        headers={"X-Staff-Token": "secret-test-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "appelé"

    listed = client.get(
        "/api/appointments?status=appel%C3%A9",
        headers={"X-Staff-Token": "secret-test-token"},
    )
    assert listed.status_code == 200
    assert len(listed.get_json()["appointments"]) == 1


def test_staff_update_rejects_invalid_status_and_unknown_id(
    monkeypatch, tmp_path,
):
    monkeypatch.setenv(
        "HIAR_APPOINTMENTS_DB",
        str(tmp_path / "appointments.sqlite3"),
    )
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "secret-test-token")
    client = app.test_client()
    headers = {"X-Staff-Token": "secret-test-token"}

    invalid = client.patch(
        "/api/appointments/1",
        json={"status": "statut-inconnu"},
        headers=headers,
    )
    assert invalid.status_code == 400

    missing = client.patch(
        "/api/appointments/9999",
        json={"status": "appelé"},
        headers=headers,
    )
    assert missing.status_code == 404
