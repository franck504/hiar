"""Migration SQLite vers les consultations par session médecin/période."""

import sqlite3


MIGRATION_VERSION = 1
MANUAL_OPEN_MIGRATION_VERSION = 2

NEW_STATUSES = (
    "en attente",
    "appelé",
    "terminé",
    "annulé",
    "non reçu",
)

REASON_CODES = (
    "consultation_generale",
    "suivi_medical",
    "autre_motif",
)

DOCTOR_MAP = {
    "Médecin A": "A",
    "Médecin B": "B",
    "Médecin C": "C",
    "Médecin D": "D",
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D",
}


def _table_exists(connection, name):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _create_sessions_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS doctor_sessions (
            requested_date TEXT NOT NULL,
            doctor_code TEXT NOT NULL CHECK (
                doctor_code IN ('A', 'B', 'C', 'D')
            ),
            period TEXT NOT NULL CHECK (period IN ('MAT', 'AM')),
            is_open INTEGER NOT NULL DEFAULT 0 CHECK (is_open IN (0, 1)),
            opened_at TEXT,
            closed_at TEXT,
            PRIMARY KEY (requested_date, doctor_code, period)
        )
    """)


def _create_new_appointments_table(connection):
    connection.execute("""
        CREATE TABLE appointments_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            reason TEXT NOT NULL,
            requested_date TEXT NOT NULL,
            requested_time TEXT NOT NULL,
            status TEXT DEFAULT 'en attente'
                CHECK (
                    status IN (
                        'en attente', 'appelé', 'terminé',
                        'annulé', 'non reçu'
                    )
                    OR status IS NULL
                ),
            legacy_status TEXT
                CHECK (
                    legacy_status IN (
                        'PENDING', 'CONFIRMED', 'REJECTED'
                    )
                    OR legacy_status IS NULL
                ),
            pass_number INTEGER,
            created_at TEXT NOT NULL,
            slot_id INTEGER,
            doctor TEXT,
            contact_normalized TEXT,
            temperature_c REAL,
            heart_rate_bpm INTEGER,
            spo2_percent REAL,
            period TEXT CHECK (
                period IN ('MAT', 'AM') OR period IS NULL
            ),
            ticket_number INTEGER CHECK (
                ticket_number IS NULL OR ticket_number > 0
            ),
            reason_code TEXT CHECK (
                reason_code IN (
                    'consultation_generale',
                    'suivi_medical',
                    'autre_motif'
                ) OR reason_code IS NULL
            )
        )
    """)


def _historical_period(row):
    """N'infère une période que pour les horaires connus du matin."""
    requested_time = row.get("requested_time")
    if requested_time and "08:00" <= requested_time < "12:00":
        return "MAT"
    return None


def _copy_appointments(connection):
    cursor = connection.execute(
        "SELECT * FROM appointments ORDER BY id"
    )
    columns = [description[0] for description in cursor.description]
    old_rows = cursor.fetchall()

    for sqlite_row in old_rows:
        old = dict(zip(columns, sqlite_row))

        old_status = old.get("status")
        legacy_status = old.get("legacy_status")

        if old_status in {"PENDING", "CONFIRMED", "REJECTED"}:
            legacy_status = old_status
            status = "en attente" if old_status == "PENDING" else None
        else:
            status = old_status

        doctor = old.get("doctor")
        doctor_code = DOCTOR_MAP.get(doctor)

        period = old.get("period")
        if period not in {"MAT", "AM"}:
            period = _historical_period(old)

        values = {
            "id": old["id"],
            "patient_name": old["patient_name"],
            "contact": old["contact"],
            "reason": old["reason"],
            "requested_date": old["requested_date"],
            "requested_time": old["requested_time"],
            "status": status,
            "legacy_status": legacy_status,
            "pass_number": old.get("pass_number"),
            "created_at": old["created_at"],
            "slot_id": old.get("slot_id"),
            "doctor": doctor_code,
            "contact_normalized": old.get("contact_normalized"),
            "temperature_c": old.get("temperature_c"),
            "heart_rate_bpm": old.get("heart_rate_bpm"),
            "spo2_percent": old.get("spo2_percent"),
            "period": period,
            # Les anciens numéros globaux ne sont pas des tickets de session.
            "ticket_number": old.get("ticket_number"),
            "reason_code": old.get("reason_code"),
        }

        connection.execute("""
            INSERT INTO appointments_new (
                id, patient_name, contact, reason,
                requested_date, requested_time, status,
                legacy_status, pass_number, created_at,
                slot_id, doctor, contact_normalized,
                temperature_c, heart_rate_bpm, spo2_percent,
                period, ticket_number, reason_code
            )
            VALUES (
                :id, :patient_name, :contact, :reason,
                :requested_date, :requested_time, :status,
                :legacy_status, :pass_number, :created_at,
                :slot_id, :doctor, :contact_normalized,
                :temperature_c, :heart_rate_bpm, :spo2_percent,
                :period, :ticket_number, :reason_code
            )
        """, values)


def migrate(connection):
    """Applique les migrations des sessions sans rejouer la migration historique."""
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("Une connexion SQLite est obligatoire.")

    connection.execute("BEGIN IMMEDIATE")

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS hiar_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        applied_v1 = connection.execute(
            "SELECT 1 FROM hiar_schema_migrations WHERE version = ?",
            (MIGRATION_VERSION,),
        ).fetchone()

        changed = False

        if not applied_v1:
            if not _table_exists(connection, "appointments"):
                raise RuntimeError(
                    "La table appointments doit exister avant la migration."
                )

            _create_new_appointments_table(connection)
            _copy_appointments(connection)

            connection.execute("DROP TABLE appointments")
            connection.execute(
                "ALTER TABLE appointments_new RENAME TO appointments"
            )

            _create_sessions_table(connection)

            connection.execute("""
                CREATE UNIQUE INDEX ux_appointments_phone_day
                ON appointments(contact_normalized, requested_date)
                WHERE contact_normalized IS NOT NULL
            """)

            connection.execute("""
                CREATE UNIQUE INDEX ux_appointments_session_ticket
                ON appointments(
                    requested_date, doctor, period, ticket_number
                )
                WHERE ticket_number IS NOT NULL
            """)

            connection.execute("""
                CREATE INDEX idx_appointments_status_date
                ON appointments(status, requested_date, requested_time)
            """)

            connection.execute("""
                INSERT INTO hiar_schema_migrations(version)
                VALUES (?)
            """, (MIGRATION_VERSION,))
            changed = True

        applied_v2 = connection.execute(
            "SELECT 1 FROM hiar_schema_migrations WHERE version = ?",
            (MANUAL_OPEN_MIGRATION_VERSION,),
        ).fetchone()

        if not applied_v2:
            if not _table_exists(connection, "doctor_sessions"):
                raise RuntimeError(
                    "La table doctor_sessions doit exister avant la migration v2."
                )

            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(doctor_sessions)"
                )
            }

            if "manual_open" not in columns:
                connection.execute("""
                    ALTER TABLE doctor_sessions
                    ADD COLUMN manual_open INTEGER NOT NULL DEFAULT 0
                    CHECK (manual_open IN (0, 1))
                """)

            connection.execute("""
                INSERT INTO hiar_schema_migrations(version)
                VALUES (?)
            """, (MANUAL_OPEN_MIGRATION_VERSION,))
            changed = True

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError(
                f"Échec du contrôle d'intégrité SQLite : {integrity}"
            )

        connection.commit()
        return changed

    except Exception:
        connection.rollback()
        raise
