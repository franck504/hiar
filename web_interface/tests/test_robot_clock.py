"""La date des rendez-vous vient du robot ; un script recale ceux datés pendant une horloge fausse."""

import importlib.util
from datetime import datetime
from pathlib import Path
import sqlite3

import pytest

from app import app
from appointments_store import get_db_path, init_sessions_db
from consultation_sessions_store import TZ, create_session_appointment, set_doctor_session

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("hiar_fix_dates", ROOT / "scripts" / "hiar_fix_dates.py")
fix_dates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix_dates)


def test_server_time_is_the_robot_clock():
    app.config["TESTING"] = True
    body = app.test_client().get("/api/server/time").get_json()
    now = datetime.now(TZ)
    assert body["ok"] is True
    assert body["date"] == now.date().isoformat()
    assert body["timezone"] == "Indian/Antananarivo"
    assert abs(body["epoch_ms"] / 1000 - now.timestamp()) < 5


def test_web_pages_ask_the_robot_for_today_not_the_browser():
    for js in ("doctor.js", "staff.js", "consultation.js"):
        src = (ROOT / "web_interface" / "static" / js).read_text(encoding="utf-8")
        assert "/api/server/time" in src, js
        assert "serverDay ||" in src, js


def _book_on(day, doctor, period, phone, name="Patient Test"):
    clock = datetime(*map(int, day.split("-")), 9, 0, tzinfo=TZ)
    set_doctor_session(day, doctor, period, True, now=clock)
    return create_session_appointment(
        patient_name=name, contact=phone, reason_code="suivi_medical", requested_date=day,
        doctor_code=doctor, period=period, now=clock, bypass_cutoff=True,
    )


def _rows():
    con = sqlite3.connect(str(get_db_path()))
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT id, requested_date, created_at, ticket_number FROM appointments ORDER BY id")]
    finally:
        con.close()


def test_fix_dates_dry_run_changes_nothing_then_apply_shifts_and_backs_up(tmp_path, capsys):
    init_sessions_db()
    _book_on("2026-11-18", "A", "MAT", "0341111111")
    _book_on("2026-11-18", "B", "AM", "0342222222")
    args = ["--db", str(get_db_path()), "--from-date", "2026-11-18", "--to-date", "2026-11-18", "--shift-days", "6"]

    assert fix_dates.main(args) == 0
    assert {r["requested_date"] for r in _rows()} == {"2026-11-18"}   # simulation : rien d'écrit
    out = capsys.readouterr().out
    assert "Patient Test" not in out and "034" not in out              # aucune donnée personnelle affichée

    assert fix_dates.main(args + ["--apply"]) == 0
    rows = _rows()
    assert {r["requested_date"] for r in rows} == {"2026-11-24"}
    assert all(r["created_at"].startswith("2026-11-24") for r in rows)
    assert list(Path(get_db_path()).parent.glob("*.avant-recalage-*"))  # sauvegarde faite


def test_fix_dates_refuses_ticket_collisions_unless_renumber():
    init_sessions_db()
    _book_on("2026-11-24", "A", "MAT", "0341111111")                    # vrai ticket du jour A-MAT-1
    _book_on("2026-11-18", "A", "MAT", "0343333333")                    # mal daté, aussi A-MAT-1
    args = ["--db", str(get_db_path()), "--from-date", "2026-11-18", "--to-date", "2026-11-18",
            "--shift-days", "6", "--apply"]

    assert fix_dates.main(args) == 1                                     # conflit : rien n'est écrit
    assert sorted(r["requested_date"] for r in _rows()) == ["2026-11-18", "2026-11-24"]

    assert fix_dates.main(args + ["--renumber"]) == 0
    moved = [r for r in _rows() if r["id"] == 2][0]
    assert moved["requested_date"] == "2026-11-24" and moved["ticket_number"] == 2


def test_fix_dates_refuses_same_phone_same_day():
    init_sessions_db()
    _book_on("2026-11-24", "A", "MAT", "0341111111")
    _book_on("2026-11-18", "B", "AM", "0341111111")
    rc = fix_dates.main(["--db", str(get_db_path()), "--from-date", "2026-11-18", "--to-date", "2026-11-18",
                         "--shift-days", "6", "--apply", "--renumber"])
    assert rc == 1
