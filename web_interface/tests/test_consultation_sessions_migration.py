import sqlite3

import pytest

from migrations.consultation_sessions import migrate


@pytest.fixture
def legacy_db(tmp_path):
    path = tmp_path / "legacy_sessions.sqlite3"
    con = sqlite3.connect(path)

    con.execute("""
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            reason TEXT NOT NULL,
            requested_date TEXT NOT NULL,
            requested_time TEXT NOT NULL,
            status TEXT,
            created_at TEXT NOT NULL,
            pass_number INTEGER,
            doctor TEXT,
            contact_normalized TEXT,
            temperature_c REAL,
            heart_rate_bpm INTEGER,
            spo2_percent REAL
        )
    """)

    con.execute("""
        INSERT INTO appointments (
            id, patient_name, contact, reason,
            requested_date, requested_time, status,
            created_at, pass_number, doctor,
            contact_normalized, temperature_c,
            heart_rate_bpm, spo2_percent
        )
        VALUES (
            7, 'Patient synthétique', '0340000000',
            'Consultation', '2027-01-15', '09:30',
            'PENDING', '2026-10-01T08:00:00+03:00',
            42, 'Médecin A', '0340000000',
            36.7, 75, 98
        )
    """)

    con.commit()
    con.close()
    return path


def test_migration_preserves_legacy_data_and_measures(legacy_db):
    con = sqlite3.connect(legacy_db)
    try:
        assert migrate(con) is True

        row = con.execute("""
            SELECT id, patient_name, status, legacy_status,
                   pass_number, doctor, period, ticket_number,
                   temperature_c, heart_rate_bpm, spo2_percent
            FROM appointments WHERE id = 7
        """).fetchone()

        assert row == (
            7, "Patient synthétique", "en attente", "PENDING",
            42, "A", "MAT", None, 36.7, 75, 98
        )
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        con.close()


def test_migration_is_idempotent(legacy_db):
    con = sqlite3.connect(legacy_db)
    try:
        assert migrate(con) is True
        assert migrate(con) is False
        assert con.execute(
            "SELECT COUNT(*) FROM appointments"
        ).fetchone()[0] == 1
    finally:
        con.close()


def test_session_defaults_to_closed_and_ticket_is_unique(legacy_db):
    con = sqlite3.connect(legacy_db)
    try:
        migrate(con)

        con.execute("""
            INSERT INTO doctor_sessions (
                requested_date, doctor_code, period
            ) VALUES ('2099-12-31', 'A', 'MAT')
        """)
        assert con.execute("""
            SELECT is_open FROM doctor_sessions
            WHERE requested_date='2099-12-31'
              AND doctor_code='A' AND period='MAT'
        """).fetchone()[0] == 0

        values = (
            "Patient synthétique", "0340000001", "Consultation",
            "2099-12-31", "08:00", "en attente",
            "2099-12-01T08:00:00+03:00", 1, "A", "MAT", 1
        )
        sql = """
            INSERT INTO appointments (
                patient_name, contact, reason, requested_date,
                requested_time, status, created_at, pass_number,
                doctor, period, ticket_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        con.execute(sql, values)

        # Même ticket, même session : l'index unique doit refuser.
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(sql, values)

        # Les anciens pass_number ne sont plus globalement uniques.
        second = list(values)
        second[1] = "0340000002"
        second[7] = 1
        second[10] = 2
        con.execute(sql, tuple(second))

        con.rollback()
    finally:
        con.close()


def test_migration_rolls_back_on_duplicate_phone_day(legacy_db):
    con = sqlite3.connect(legacy_db)
    try:
        con.execute("""
            INSERT INTO appointments (
                patient_name, contact, reason, requested_date,
                requested_time, status, created_at,
                contact_normalized
            )
            VALUES (
                'Autre patient synthétique', '0340000000',
                'Consultation', '2027-01-15', '10:00',
                'PENDING', '2026-10-01T09:00:00+03:00',
                '0340000000'
            )
        """)
        con.commit()

        with pytest.raises(sqlite3.IntegrityError):
            migrate(con)

        # La table d'origine doit être intacte après le rollback.
        assert con.execute(
            "SELECT COUNT(*) FROM appointments"
        ).fetchone()[0] == 2
        assert con.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='appointments_new'
        """).fetchone() is None
        assert con.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='hiar_schema_migrations'
        """).fetchone() is None
    finally:
        con.close()


def test_store_integration_does_not_restore_legacy_slot_index(
    legacy_db, monkeypatch
):
    import appointments_store as store

    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(legacy_db))

    assert store.init_sessions_db() is True

    # Les appels habituels de l'application ne doivent pas annuler
    # la migration en recréant l'ancien index de créneaux.
    store.init_db()

    with store.get_connection() as con:
        indexes = {
            row["name"]
            for row in con.execute("PRAGMA index_list(appointments)")
        }

    assert "ux_appointments_slot_day" not in indexes
    assert "ux_appointments_session_ticket" in indexes
    assert "ux_appointments_phone_day" in indexes
