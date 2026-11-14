import pytest

from appointments_store import (
    ALLOWED_STATUSES,
    create_appointment,
    init_db,
    list_appointments,
    update_appointment_status,
)


@pytest.fixture
def database(tmp_path, monkeypatch):
    db_path = tmp_path / "appointments.sqlite3"
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(db_path))
    init_db()
    return db_path


def test_create_appointment_starts_pending(database):
    appointment_id = create_appointment(
        "Patient Test",
        "0340000000",
        "Consultation générale",
        "2027-01-15",
        "09:00",
    )

    appointments = list_appointments()

    assert len(appointments) == 1
    assert appointments[0]["id"] == appointment_id
    assert appointments[0]["status"] == "en attente"
    assert appointments[0]["pass_number"] == 1
    assert appointments[0]["queue_position"] == 1


def test_create_appointment_persists_vital_signs(database):
    appointment_id = create_appointment(
        "Patient Mesures",
        "0340000000",
        "Consultation générale",
        "2027-01-15",
        "09:00",
        temperature_c=36.7,
        heart_rate_bpm=72,
        spo2_percent=None,
    )

    appointment = next(
        item for item in list_appointments()
        if item["id"] == appointment_id
    )

    assert appointment["temperature_c"] == pytest.approx(36.7)
    assert appointment["heart_rate_bpm"] == 72
    assert appointment["spo2_percent"] is None


def test_update_appointment_status(database):
    appointment_id = create_appointment(
        "Patient Test",
        "0340000000",
        "Consultation générale",
        "2027-01-15",
        "09:00",
    )

    assert update_appointment_status(appointment_id, "appelé")
    assert list_appointments("appelé")[0]["id"] == appointment_id
    assert list_appointments("en attente") == []

    assert update_appointment_status(appointment_id, "terminé")
    assert list_appointments("terminé")[0]["id"] == appointment_id


def test_invalid_status_is_rejected(database):
    with pytest.raises(ValueError):
        update_appointment_status(1, "INVALID")

    with pytest.raises(ValueError):
        update_appointment_status(1, "CONFIRMED")


def test_status_transition_cannot_skip_or_reverse_normal_flow(database):
    appointment_id = create_appointment(
        "Patient Test",
        "0340000000",
        "Consultation générale",
        "2027-01-15",
        "09:00",
    )

    with pytest.raises(ValueError, match="Transition de statut interdite"):
        update_appointment_status(appointment_id, "terminé")

    assert update_appointment_status(appointment_id, "appelé")

    with pytest.raises(ValueError, match="Transition de statut interdite"):
        update_appointment_status(appointment_id, "en attente")

    assert update_appointment_status(appointment_id, "terminé")

    with pytest.raises(ValueError, match="Transition de statut interdite"):
        update_appointment_status(appointment_id, "appelé")


def test_exceptional_correction_allows_status_reversal(database):
    appointment_id = create_appointment(
        "Patient Test",
        "0340000000",
        "Consultation générale",
        "2027-01-15",
        "09:00",
    )

    assert update_appointment_status(appointment_id, "appelé")
    assert update_appointment_status(appointment_id, "en attente",
                                     exceptional_correction=True)
    assert list_appointments("en attente")[0]["id"] == appointment_id


def test_same_status_and_invalid_correction_flag_are_rejected(database):
    appointment_id = create_appointment(
        "Patient Test",
        "0340000000",
        "Consultation générale",
        "2027-01-15",
        "09:00",
    )

    with pytest.raises(ValueError, match="déjà ce statut"):
        update_appointment_status(appointment_id, "en attente")

    with pytest.raises(ValueError, match="doit être booléen|Indicateur"):
        update_appointment_status(
            appointment_id, "appelé", exceptional_correction="true"
        )


def test_allowed_statuses_are_exactly_the_three_queue_states():
    assert ALLOWED_STATUSES == {"en attente", "appelé", "terminé"}


def test_required_fields_are_validated(database):
    with pytest.raises(ValueError):
        create_appointment(
            "",
            "0340000000",
            "Consultation générale",
            "2027-01-15",
            "09:00",
        )


def test_invalid_date_is_rejected(database):
    with pytest.raises(ValueError, match="Date ou heure invalide"):
        create_appointment(
            "Patient Test",
            "0340000000",
            "Consultation générale",
            "2027-99-45",
            "09:00",
        )


def test_invalid_time_is_rejected(database):
    with pytest.raises(ValueError, match="Date ou heure invalide"):
        create_appointment(
            "Patient Test",
            "0340000000",
            "Consultation générale",
            "2027-01-15",
            "25:90",
        )
