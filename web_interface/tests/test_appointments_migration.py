import sqlite3

import pytest

from appointments_store import init_db, list_appointments


@pytest.fixture
def legacy_database(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_appointments.sqlite3"
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                contact TEXT NOT NULL,
                reason TEXT NOT NULL,
                requested_date TEXT NOT NULL,
                requested_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'CONFIRMED', 'REJECTED')),
                created_at TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO appointments (
                id, patient_name, contact, reason,
                requested_date, requested_time, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    7, "Patient En Attente", "0340000001",
                    "Consultation", "2027-01-15", "09:30",
                    "PENDING", "2026-10-01T08:00:00+03:00",
                ),
                (
                    8, "Patient Historique Confirmé", "0340000002",
                    "Consultation", "2027-01-16", "10:00",
                    "CONFIRMED", "2026-10-01T08:05:00+03:00",
                ),
                (
                    9, "Patient Historique Refusé", "0340000003",
                    "Consultation", "2027-01-17", "11:00",
                    "REJECTED", "2026-10-01T08:10:00+03:00",
                ),
            ],
        )

    return db_path


def test_migration_preserves_records_and_converts_legacy_statuses(
    legacy_database,
):
    init_db()

    with sqlite3.connect(legacy_database) as connection:
        rows = connection.execute(
            """
            SELECT id, patient_name, contact, reason,
                   requested_date, requested_time, status,
                   legacy_status, created_at,
                   temperature_c, heart_rate_bpm, spo2_percent
            FROM appointments
            ORDER BY id
            """
        ).fetchall()

    assert [row[0] for row in rows] == [7, 8, 9]
    assert [row[1] for row in rows] == [
        "Patient En Attente",
        "Patient Historique Confirmé",
        "Patient Historique Refusé",
    ]
    assert [row[2] for row in rows] == [
        "0340000001", "0340000002", "0340000003"
    ]
    assert [row[6] for row in rows] == [
        "en attente", None, None
    ]
    assert [row[7] for row in rows] == [
        "PENDING", "CONFIRMED", "REJECTED"
    ]
    assert [row[8] for row in rows] == [
        "2026-10-01T08:00:00+03:00",
        "2026-10-01T08:05:00+03:00",
        "2026-10-01T08:10:00+03:00",
    ]

    # Les mesures n'existaient pas dans l'ancienne base.
    assert [row[9:12] for row in rows] == [
        (None, None, None),
        (None, None, None),
        (None, None, None),
    ]


def test_active_queue_excludes_historical_records(legacy_database):
    init_db()

    appointments = list_appointments()

    assert [appointment["id"] for appointment in appointments] == [7]
    assert appointments[0]["status"] == "en attente"
