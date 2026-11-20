import json
import pytest
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(tmp_path / "appts.sqlite3"))
    monkeypatch.setenv("HIAR_SESSIONS_DB", str(tmp_path / "sessions.sqlite3"))
    monkeypatch.setenv("HIAR_WEB_PIN", "4321")
    return app.test_client()


def test_patients_route_has_correct_title_and_no_diagnostics_panel(client):
    """Vérifie la route [ /patients : Rendez-vous ]"""
    res = client.get("/patients")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "<title>Rendez-vous — HIAR</title>" in html
    assert "queue-panel" in html
    assert "login-panel" in html
    assert "pin-inputs" in html
    # La gestion des capteurs NE DOIT PAS être dans /patients
    assert "diagnostics-panel" not in html
    assert "diag-grid" not in html


def test_admin_route_has_correct_title_and_no_queue_panel(client):
    """Vérifie la route [ /admin : Gestion de HIAR ]"""
    res = client.get("/admin")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "<title>Gestion de HIAR — HIAR</title>" in html
    assert "diagnostics-panel" in html
    assert "diag-grid" in html
    assert "dashboard-panel" in html
    assert "admin-tab-nav" in html
    assert "tab-btn-hardware" in html
    assert "tab-btn-dashboard" in html
    assert "admin-emergency-stop-btn" in html
    assert "login-panel" in html
    # La file de consultation NE DOIT PAS être dans /admin
    assert "queue-panel" not in html
    assert "queue-body" not in html


def test_admin_dashboard_api(client):
    """Vérifie l'API du tableau de bord d'administration et l'historique."""
    # 1. Non authentifié -> 401
    unauth = client.get("/api/admin/dashboard")
    assert unauth.status_code == 401

    # 2. Authentifié via X-Web-PIN -> 200
    res = client.get("/api/admin/dashboard", headers={"X-Web-PIN": "4321"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "stats" in data
    assert "appointments" in data
    assert "total" in data["stats"]
    assert "confirmed" in data["stats"]


def test_robot_stop_api(client, monkeypatch):
    """Vérifie l'endpoint /api/robot/stop d'arrêt d'urgence."""
    class FakeBridge:
        error = None
        def cancel_navigation(self):
            return True

    import app as app_module
    monkeypatch.setattr(app_module, "bridge", FakeBridge())
    res = client.post("/api/robot/stop")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True


def test_both_pages_share_navigation_links(client):
    """Vérifie que les deux pages contiennent la navigation croisée [/patients] et [/admin]"""
    for route in ["/patients", "/admin"]:
        res = client.get(route)
        html = res.get_data(as_text=True)
        assert 'href="/patients"' in html
        assert 'href="/admin"' in html


def test_pin_authentication_success_and_failure(client):
    """Vérifie la validation du code PIN à 4 chiffres configuré dans .env"""
    # 1. Échec avec un mauvais PIN
    fail_res = client.post("/api/auth/pin", json={"pin": "9999"})
    assert fail_res.status_code == 401
    assert fail_res.get_json()["ok"] is False
    assert "incorrect" in fail_res.get_json()["error"]

    # 2. Échec avec une longueur invalide
    len_res = client.post("/api/auth/pin", json={"pin": "12"})
    assert len_res.status_code == 401

    # 3. Succès avec le bon PIN (4321)
    ok_res = client.post("/api/auth/pin", json={"pin": "4321"})
    assert ok_res.status_code == 200
    data = ok_res.get_json()
    assert data["ok"] is True
    assert data["pin"] == "4321"

    # 4. Requête API authentifiée par le PIN via X-Web-PIN
    api_res = client.get(
        "/api/doctor/appointments?date=2026-11-20",
        headers={"X-Web-PIN": "4321"},
    )
    assert api_res.status_code == 200
    assert api_res.get_json()["ok"] is True


def test_pin_logout_clears_session(client):
    """Vérifie la déconnexion"""
    # Connexion
    client.post("/api/auth/pin", json={"pin": "4321"})
    # Déconnexion
    logout_res = client.post("/api/auth/logout", json={})
    assert logout_res.status_code == 200
    assert logout_res.get_json()["ok"] is True
