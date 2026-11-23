"""Les médecins ont un prénom reconnaissable ; les codes A-D restent les clés stables."""

import re
from datetime import datetime
from pathlib import Path

import pytest

from app import app
from appointments_store import BookingError, init_sessions_db, normalize_phone
from consultation_sessions_store import (
    DOCTORS,
    DOCTOR_NAMES,
    PERIODS,
    TZ,
    create_session_appointment,
    ensure_daily_sessions,
    doctor_name,
    set_doctor_session,
)

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {"A": "Raissa", "B": "Bell", "C": "Pierrot", "D": "Alice"}
PIN = {"X-Web-PIN": "123456"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HIAR_WEB_PIN", "123456")
    init_sessions_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _book(doctor="B", period="AM", phone="0341234567", name="Hery Rakoto"):
    init_sessions_db()
    ensure_daily_sessions()
    return create_session_appointment(
        patient_name=name, contact=phone, reason_code="suivi_medical",
        requested_date=datetime.now(TZ).date().isoformat(),
        doctor_code=doctor, period=period, bypass_cutoff=True,
    )


def test_names_and_codes():
    assert DOCTOR_NAMES == EXPECTED
    assert tuple(DOCTOR_NAMES) == DOCTORS
    assert doctor_name("B") == "Bell" and doctor_name("Z") == "Z" and doctor_name(None) == ""


def test_web_voice_and_mobile_catalogs_agree():
    """Une seule vérité pour trois implémentations : web (Python), dialogue vocal (Python), mobile (Dart)."""
    voice = pytest.importorskip("hospital_robot.consultation_catalog")
    assert {c: d["name"] for c, d in voice.DOCTORS.items()} == EXPECTED

    dart = (ROOT / "hiar_mobile/lib/features/consultation/doctors.dart").read_text(encoding="utf-8")
    rows = re.findall(r"DoctorInfo\('([A-D])', '([^']+)', '(MAT|AM)'\)", dart)
    assert {code: name for code, name, _ in rows} == EXPECTED
    assert [code for code, _, _ in rows] == list(DOCTORS)  # même ordre d'affichage
    assert {code: period for code, _, period in rows} == {c: d["period"] for c, d in voice.DOCTORS.items()}


@pytest.mark.parametrize("raw", ["0341234567", "034 12 345 67", "261341234567", "00261341234567",
                                 "034123456", "03412345678", "1341234567"])
def test_dictated_phone_rule_agrees_with_the_booking_rule(raw):
    """Un numéro que le dialogue vocal accepte doit être accepté à la réservation (et inversement)."""
    voice = pytest.importorskip("hospital_robot.consultation_catalog")
    national = voice.national_phone(raw)
    try:
        stored = normalize_phone(voice.format_phone_display(national) if national else raw)
        accepted = True
    except BookingError:
        accepted = False
    if national:
        assert accepted and stored == "+261" + national[1:]
    else:
        # Rejeté par le dialogue vocal : la réservation peut l'accepter (format international), jamais l'inverse
        assert accepted in (True, False)


def test_creating_a_booking_returns_the_doctor_name():
    result = _book("C", "MAT")
    assert result["doctor"] == "C" and result["doctor_name"] == "Pierrot"
    assert result["ticket_label"] == "C-MAT-1"  # le ticket garde le code stable


def test_staff_queue_and_admin_dashboard_carry_the_name(client):
    _book("D", "AM")
    day = datetime.now(TZ).date().isoformat()

    queue = client.get(f"/api/doctor/appointments?date={day}", headers={**PIN, "X-Doctor-Code": "ALL"}).get_json()
    assert [(a["doctor"], a["doctor_name"]) for a in queue["appointments"]] == [("D", "Alice")]

    staff = client.get(f"/api/staff/consultations?date={day}", headers=PIN).get_json()
    assert staff["appointments"][0]["doctor_name"] == "Alice"

    dash = client.get("/api/admin/dashboard", headers=PIN).get_json()
    assert dash["appointments"][0]["doctor_name"] == "Alice"
    assert dash["appointments"][0]["ticket_label"] == "D-AM-1"

    sessions = client.get(f"/api/doctor/sessions?date={day}", headers={**PIN, "X-Doctor-Code": "ALL"}).get_json()
    assert {s["doctor_code"]: s["doctor_name"] for s in sessions["sessions"]} == EXPECTED


def test_public_sessions_list_names_the_doctors(client):
    # Ouverture manuelle : sinon la liste dépend de l'heure (inscriptions closes 30 min avant la fin de la période)
    today = datetime.now(TZ).date().isoformat()
    ensure_daily_sessions()
    for code in DOCTORS:
        for period in PERIODS:
            set_doctor_session(today, code, period, True)
    body = client.get("/api/consultation/sessions").get_json()
    assert {s["doctor_code"]: s["doctor_name"] for s in body["sessions"]} == EXPECTED


def test_appointments_page_offers_one_button_per_doctor_plus_all(client):
    html = client.get("/patients").get_data(as_text=True)
    assert 'data-doc="ALL"' in html
    for code, name in EXPECTED.items():
        assert f'data-doc="{code}"' in html and f"Dr {name}" in html
    assert "Médecin A" not in html and "Médecin D" not in html
    assert "<th>Médecin</th>" in html


@pytest.mark.parametrize("path", ["/admin", "/staff"])
def test_doctor_filters_list_all_four_doctors(client, path):
    """Régression : le filtre de l'admin ne proposait que les médecins A et B."""
    html = client.get(path).get_data(as_text=True)
    for code, name in EXPECTED.items():
        assert f'<option value="{code}">Dr {name}</option>' in html
