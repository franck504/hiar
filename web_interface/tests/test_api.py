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


def test_flask_secret_key_security(monkeypatch, tmp_path):
    """Vérifie le remplacement et la génération d'un secret Flask cryptographique."""
    from app import _resolve_flask_secret_key

    # 1. Rejet du fallback statique faible
    monkeypatch.setenv("FLASK_SECRET_KEY", "hiar_hospital_robot_secret_key_session_2026")
    key = _resolve_flask_secret_key()
    assert key != "hiar_hospital_robot_secret_key_session_2026"
    assert len(key) >= 32

    # 2. Clé valide personnalisée acceptée
    valid_key = "my_custom_secure_secret_key_abcdef_123456"
    monkeypatch.setenv("FLASK_SECRET_KEY", valid_key)
    assert _resolve_flask_secret_key() == valid_key


def test_web_ssl_context_resolution(monkeypatch, tmp_path):
    """Vérifie la détection et configuration HTTPS pour Flask."""
    from app import _get_web_ssl_context

    # 1. Sans variables -> None
    monkeypatch.delenv("HIAR_WEB_SSL_CERT", raising=False)
    monkeypatch.delenv("HIAR_WEB_SSL_KEY", raising=False)
    monkeypatch.delenv("HIAR_WEB_ENABLE_ADHOC_SSL", raising=False)
    assert _get_web_ssl_context() is None

    # 2. Avec fichiers valides -> (cert, key)
    c_file = tmp_path / "server.crt"
    k_file = tmp_path / "server.key"
    c_file.write_text("cert", encoding="utf-8")
    k_file.write_text("key", encoding="utf-8")
    monkeypatch.setenv("HIAR_WEB_SSL_CERT", str(c_file))
    monkeypatch.setenv("HIAR_WEB_SSL_KEY", str(k_file))
    assert _get_web_ssl_context() == (str(c_file), str(k_file))

    # 3. Mode adhoc
    monkeypatch.delenv("HIAR_WEB_SSL_CERT", raising=False)
    monkeypatch.setenv("HIAR_WEB_ENABLE_ADHOC_SSL", "1")
    assert _get_web_ssl_context() == "adhoc"


def test_http_security_headers_present():
    """Vérifie la présence systématique des en-têtes HTTP de sécurité."""
    client = app.test_client()
    resp = client.get("/patients")
    assert resp.status_code == 200
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")

    # Avec HTTPS simulé
    https_resp = client.get("/patients", base_url="https://localhost")
    assert "Strict-Transport-Security" in https_resp.headers


def test_cors_origin_restriction(monkeypatch):
    """Vérifie la restriction CORS aux réseaux locaux ou liste blanche."""
    client = app.test_client()

    # 1. Origine locale/privée autorisée
    local_resp = client.get("/patients", headers={"Origin": "http://192.168.43.52:5001"})
    assert local_resp.headers.get("Access-Control-Allow-Origin") == "http://192.168.43.52:5001"

    loopback_resp = client.get("/patients", headers={"Origin": "http://localhost:3000"})
    assert loopback_resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

    # 2. Origine publique non autorisée rejetée
    evil_resp = client.get("/patients", headers={"Origin": "http://malicious-site.com"})
    assert "Access-Control-Allow-Origin" not in evil_resp.headers

    # 3. Liste blanche explicite dans HIAR_ALLOWED_ORIGINS
    monkeypatch.setenv("HIAR_ALLOWED_ORIGINS", "https://hospital.chu,http://custom-lan:8080")
    custom_resp = client.get("/patients", headers={"Origin": "https://hospital.chu"})
    assert custom_resp.headers.get("Access-Control-Allow-Origin") == "https://hospital.chu"

    blocked_resp = client.get("/patients", headers={"Origin": "http://other-site.com"})
    assert "Access-Control-Allow-Origin" not in blocked_resp.headers



