import pytest

from app import app


DAY = "2099-01-05"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "HIAR_APPOINTMENTS_DB",
        str(tmp_path / "consultation_api.sqlite3"),
    )
    monkeypatch.setenv("HIAR_DOCTOR_TOKEN_A", "token-medecin-A")
    monkeypatch.setenv("HIAR_DOCTOR_TOKEN_B", "token-medecin-B")
    monkeypatch.setenv("HIAR_STAFF_API_TOKEN", "token-personnel-test")
    monkeypatch.delenv("HIAR_DOCTOR_TOKEN_C", raising=False)
    monkeypatch.delenv("HIAR_DOCTOR_TOKEN_D", raising=False)
    return app.test_client()


def doctor_headers(token):
    return {"X-Doctor-Token": token}


def open_session(client, token, period="MAT", doctor="A"):
    return client.post(
        "/api/doctor/sessions",
        headers=doctor_headers(token),
        json={
            "requested_date": DAY,
            "period": period,
            "is_open": True,
            "doctor_code": doctor,
        },
    )


def test_doctor_sessions_requires_authentication(client):
    response = client.get(f"/api/doctor/sessions?date={DAY}")
    assert response.status_code == 401


def test_doctor_sessions_rejects_invalid_token(client):
    response = client.get(
        f"/api/doctor/sessions?date={DAY}",
        headers=doctor_headers("mauvais-token"),
    )
    assert response.status_code == 401


def test_doctor_sessions_returns_only_own_sessions(client):
    assert open_session(client, "token-medecin-A").status_code == 200
    assert open_session(
        client, "token-medecin-B", period="AM", doctor="B"
    ).status_code == 200

    response = client.get(
        f"/api/doctor/sessions?date={DAY}",
        headers=doctor_headers("token-medecin-A"),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["doctor"] == "A"
    assert [item["doctor_code"] for item in body["sessions"]] == ["A"]


def test_doctor_cannot_open_session_for_another_doctor(client):
    response = open_session(
        client, "token-medecin-A", period="MAT", doctor="B"
    )

    assert response.status_code == 200
    assert response.get_json()["doctor"] == "A"

    own_sessions = client.get(
        f"/api/doctor/sessions?date={DAY}",
        headers=doctor_headers("token-medecin-A"),
    )
    assert [
        item["doctor_code"] for item in own_sessions.get_json()["sessions"]
    ] == ["A"]


def test_doctor_can_close_own_session(client):
    assert open_session(client, "token-medecin-A").status_code == 200

    response = client.post(
        "/api/doctor/sessions",
        headers=doctor_headers("token-medecin-A"),
        json={
            "requested_date": DAY,
            "period": "MAT",
            "is_open": False,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["is_open"] is False


def test_invalid_session_data_returns_400(client):
    response = client.post(
        "/api/doctor/sessions",
        headers=doctor_headers("token-medecin-A"),
        json={
            "requested_date": DAY,
            "period": "SOIR",
            "is_open": True,
        },
    )
    assert response.status_code == 400


def test_missing_doctor_configuration_returns_503(client, monkeypatch):
    for code in ("A", "B", "C", "D"):
        monkeypatch.delenv(f"HIAR_DOCTOR_TOKEN_{code}", raising=False)

    response = client.get(
        f"/api/doctor/sessions?date={DAY}"
    )
    assert response.status_code == 503


def test_duplicate_doctor_tokens_are_rejected(client, monkeypatch):
    monkeypatch.setenv("HIAR_DOCTOR_TOKEN_B", "token-medecin-A")

    response = client.get(
        f"/api/doctor/sessions?date={DAY}",
        headers=doctor_headers("token-medecin-A"),
    )
    assert response.status_code == 503


def prepare_consultation_clock(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import consultation_sessions_store

    fixed_now = datetime(
        2099, 1, 5, 9, 0,
        tzinfo=ZoneInfo("Indian/Antananarivo"),
    )
    monkeypatch.setattr(
        consultation_sessions_store,
        "_now",
        lambda value=None: fixed_now,
    )


def test_patient_can_register_and_receive_ticket(client, monkeypatch):
    prepare_consultation_clock(monkeypatch)
    assert open_session(client, "token-medecin-A").status_code == 200

    response = client.post(
        "/api/consultation/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason_code": "consultation_generale",
            "requested_date": DAY,
            "doctor_code": "A",
            "period": "MAT",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["ticket_label"] == "A-MAT-1"
    assert body["status"] == "en attente"

    from consultation_sessions_store import list_session_appointments
    appointments = list_session_appointments(DAY, "A", "MAT")
    assert len(appointments) == 1
    assert appointments[0]["temperature_c"] is None
    assert appointments[0]["heart_rate_bpm"] is None
    assert appointments[0]["spo2_percent"] is None


def test_patient_cannot_register_in_closed_session(client, monkeypatch):
    prepare_consultation_clock(monkeypatch)

    response = client.post(
        "/api/consultation/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason_code": "consultation_generale",
            "requested_date": DAY,
            "doctor_code": "A",
            "period": "MAT",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "session_closed"


def test_patient_registration_rejects_invalid_reason(client, monkeypatch):
    prepare_consultation_clock(monkeypatch)
    assert open_session(client, "token-medecin-A").status_code == 200

    response = client.post(
        "/api/consultation/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason_code": "diagnostic",
            "requested_date": DAY,
            "doctor_code": "A",
            "period": "MAT",
        },
    )

    assert response.status_code == 400


def test_doctor_appointments_requires_authentication(client):
    response = client.get(
        f"/api/doctor/appointments?date={DAY}"
    )
    assert response.status_code == 401


def test_doctor_appointments_returns_only_own_patients(client, monkeypatch):
    prepare_consultation_clock(monkeypatch)

    assert open_session(client, "token-medecin-A").status_code == 200
    assert open_session(
        client, "token-medecin-B", period="AM", doctor="B"
    ).status_code == 200

    for token, doctor, period, phone in (
        ("token-medecin-A", "A", "MAT", "0340000000"),
        ("token-medecin-B", "B", "AM", "0340000001"),
    ):
        response = client.post(
            "/api/consultation/appointments",
            json={
                "patient_name": "Patient Test",
                "contact": phone,
                "reason_code": "consultation_generale",
                "requested_date": DAY,
                "doctor_code": doctor,
                "period": period,
            },
        )
        assert response.status_code == 201

    response = client.get(
        f"/api/doctor/appointments?date={DAY}",
        headers=doctor_headers("token-medecin-A"),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["doctor"] == "A"
    assert len(body["appointments"]) == 1
    assert body["appointments"][0]["doctor"] == "A"


def test_doctor_appointments_filters_by_period_and_status(client, monkeypatch):
    prepare_consultation_clock(monkeypatch)
    assert open_session(client, "token-medecin-A").status_code == 200

    response = client.post(
        "/api/consultation/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason_code": "consultation_generale",
            "requested_date": DAY,
            "doctor_code": "A",
            "period": "MAT",
        },
    )
    assert response.status_code == 201

    response = client.get(
        f"/api/doctor/appointments?date={DAY}&period=MAT&status=en%20attente",
        headers=doctor_headers("token-medecin-A"),
    )

    assert response.status_code == 200
    assert len(response.get_json()["appointments"]) == 1

    response = client.get(
        f"/api/doctor/appointments?date={DAY}&period=AM",
        headers=doctor_headers("token-medecin-A"),
    )
    assert response.status_code == 200
    assert response.get_json()["appointments"] == []


def create_test_ticket(client, monkeypatch, phone="0340000000"):
    prepare_consultation_clock(monkeypatch)
    assert open_session(client, "token-medecin-A").status_code == 200

    response = client.post(
        "/api/consultation/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": phone,
            "reason_code": "consultation_generale",
            "requested_date": DAY,
            "doctor_code": "A",
            "period": "MAT",
        },
    )
    assert response.status_code == 201
    return response.get_json()["appointment_id"]


def test_doctor_can_call_own_patient(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        headers=doctor_headers("token-medecin-A"),
        json={"status": "appelé"},
    )

    assert response.status_code == 200

    from consultation_sessions_store import list_session_appointments
    appointments = list_session_appointments(DAY, "A", "MAT")
    assert appointments[0]["status"] == "appelé"


def test_doctor_cannot_modify_another_doctors_ticket(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        headers=doctor_headers("token-medecin-B"),
        json={"status": "appelé"},
    )

    assert response.status_code == 404


def test_doctor_cannot_modify_ticket_without_authentication(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        json={"status": "appelé"},
    )

    assert response.status_code == 401


def test_doctor_cannot_reopen_final_ticket(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    headers = doctor_headers("token-medecin-A")
    first = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        headers=headers,
        json={"status": "annulé"},
    )
    assert first.status_code == 200

    second = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        headers=headers,
        json={"status": "en attente"},
    )
    assert second.status_code == 400


def test_doctor_cannot_use_exceptional_correction(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        headers=doctor_headers("token-medecin-A"),
        json={
            "status": "annulé",
            "exceptional_correction": True,
        },
    )

    assert response.status_code == 403


def test_doctor_patch_rejects_invalid_status(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        headers=doctor_headers("token-medecin-A"),
        json={"status": "inconnu"},
    )

    assert response.status_code == 400


def test_doctor_cannot_skip_called_step(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/doctor/appointments/{appointment_id}",
        headers=doctor_headers("token-medecin-A"),
        json={"status": "terminé"},
    )

    assert response.status_code == 400


def test_doctor_page_is_served(client):
    response = client.get("/doctor")
    assert response.status_code == 200
    assert "Espace médecin".encode() in response.data


def staff_headers():
    return {"X-Staff-Token": "token-personnel-test"}


def test_staff_consultations_requires_authentication(client):
    response = client.get(f"/api/staff/consultations?date={DAY}")
    assert response.status_code == 401


def test_staff_can_view_all_doctors_appointments(client, monkeypatch):
    prepare_consultation_clock(monkeypatch)

    for token, doctor, period, phone in (
        ("token-medecin-A", "A", "MAT", "0340000000"),
        ("token-medecin-B", "B", "AM", "0340000001"),
    ):
        assert open_session(
            client, token, period=period, doctor=doctor
        ).status_code == 200

        response = client.post(
            "/api/consultation/appointments",
            json={
                "patient_name": "Patient Test",
                "contact": phone,
                "reason_code": "consultation_generale",
                "requested_date": DAY,
                "doctor_code": doctor,
                "period": period,
            },
        )
        assert response.status_code == 201

    response = client.get(
        f"/api/staff/consultations?date={DAY}",
        headers=staff_headers(),
    )

    assert response.status_code == 200
    appointments = response.get_json()["appointments"]
    assert len(appointments) == 2
    assert {item["doctor"] for item in appointments} == {"A", "B"}


def test_staff_can_filter_consultations(client, monkeypatch):
    prepare_consultation_clock(monkeypatch)
    assert open_session(client, "token-medecin-A").status_code == 200

    response = client.post(
        "/api/consultation/appointments",
        json={
            "patient_name": "Patient Test",
            "contact": "0340000000",
            "reason_code": "consultation_generale",
            "requested_date": DAY,
            "doctor_code": "A",
            "period": "MAT",
        },
    )
    assert response.status_code == 201

    response = client.get(
        f"/api/staff/consultations?date={DAY}&doctor=A&period=MAT&status=en%20attente",
        headers=staff_headers(),
    )

    assert response.status_code == 200
    assert len(response.get_json()["appointments"]) == 1


def test_staff_can_use_exceptional_correction(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/staff/consultations/{appointment_id}",
        headers=staff_headers(),
        json={"status": "terminé", "exceptional_correction": True},
    )

    assert response.status_code == 200

    from consultation_sessions_store import list_session_appointments
    appointments = list_session_appointments(DAY, "A", "MAT")
    assert appointments[0]["status"] == "terminé"


def test_staff_patch_requires_authentication(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/staff/consultations/{appointment_id}",
        json={"status": "appelé"},
    )

    assert response.status_code == 401


def test_staff_patch_rejects_invalid_correction_flag(client, monkeypatch):
    appointment_id = create_test_ticket(client, monkeypatch)

    response = client.patch(
        f"/api/staff/consultations/{appointment_id}",
        headers=staff_headers(),
        json={"status": "appelé", "exceptional_correction": "yes"},
    )

    assert response.status_code == 400


def test_public_consultation_sessions_returns_open_sessions(client):
    assert open_session(client, "token-medecin-A").status_code == 200
    assert open_session(
        client, "token-medecin-B", period="AM", doctor="B"
    ).status_code == 200

    response = client.get(
        f"/api/consultation/sessions?date={DAY}"
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert {
        (item["doctor_code"], item["period"])
        for item in body["sessions"]
    } == {("A", "MAT"), ("B", "AM")}
    assert all("patient_name" not in item for item in body["sessions"])
    assert all("contact" not in item for item in body["sessions"])


def test_public_consultation_sessions_excludes_closed_sessions(client):
    assert open_session(client, "token-medecin-A").status_code == 200

    response = client.get(
        f"/api/consultation/sessions?date={DAY}"
    )

    assert response.status_code == 200
    sessions = response.get_json()["sessions"]
    assert [(item["doctor_code"], item["period"]) for item in sessions] == [
        ("A", "MAT")
    ]


def test_public_consultation_sessions_rejects_invalid_date(client):
    response = client.get(
        "/api/consultation/sessions?date=05-01-2099"
    )

    assert response.status_code == 400
