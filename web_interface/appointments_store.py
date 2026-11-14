"""Stockage SQLite des demandes de consultation HIAR."""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = (
    Path(__file__).resolve().parent
    / "instance"
    / "appointments.sqlite3"
)

ALLOWED_STATUSES = {"en attente", "appelé", "terminé"}
LEGACY_STATUSES = {"PENDING", "CONFIRMED", "REJECTED"}

# Configuration provisoire : 4 créneaux par jour au total (pas par médecin).
SLOTS = {
    1: {"start": "08:00", "end": "08:30", "doctor": "Médecin A"},
    2: {"start": "09:00", "end": "09:30", "doctor": "Médecin B"},
    3: {"start": "10:00", "end": "10:30", "doctor": "Médecin A"},
    4: {"start": "11:00", "end": "11:30", "doctor": "Médecin B"},
}

BOOKING_COLUMNS = {
    "slot_id": "INTEGER",
    "doctor": "TEXT",
    "contact_normalized": "TEXT",
    "temperature_c": "REAL",
    "heart_rate_bpm": "INTEGER",
    "spo2_percent": "REAL",
}


class BookingError(ValueError):
    """Erreur métier de réservation (sous-classe de ValueError : les
    gestionnaires existants continuent de fonctionner)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def normalize_phone(raw):
    """Normalise un numéro de téléphone (format malgache ou international)."""
    cleaned = re.sub(r"[\s.\-()]", "", raw or "")
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("261") and len(cleaned) == 12:
        digits = cleaned
    elif cleaned.startswith("0") and len(cleaned) == 10:
        digits = "261" + cleaned[1:]
    else:
        raise BookingError("invalid_phone", "Numéro de téléphone invalide.")

    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise BookingError("invalid_phone", "Numéro de téléphone invalide.")
    return "+" + digits


def _resolve_slot(requested_time, slot_id):
    """Retourne l'identifiant de créneau cohérent avec l'heure demandée."""
    if slot_id is None:
        for sid, slot in SLOTS.items():
            if slot["start"] == requested_time:
                return sid
        raise BookingError("invalid_slot", "Créneau invalide.")
    if slot_id not in SLOTS or SLOTS[slot_id]["start"] != requested_time:
        raise BookingError("invalid_slot", "Créneau invalide.")
    return slot_id


def get_db_path():
    """Retourne le chemin SQLite configurable."""
    return Path(os.environ.get("HIAR_APPOINTMENTS_DB", str(DEFAULT_DB)))


def get_connection():
    """Ouvre une connexion SQLite."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _create_appointments_table(connection, table_name="appointments"):
    """Crée une table conforme au nouveau modèle."""
    if table_name not in {"appointments", "appointments_new"}:
        raise ValueError("Nom de table interne invalide.")

    connection.execute(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            reason TEXT NOT NULL,
            requested_date TEXT NOT NULL,
            requested_time TEXT NOT NULL,
            status TEXT DEFAULT 'en attente'
                CHECK (
                    status IN ('en attente', 'appelé', 'terminé')
                    OR status IS NULL
                ),
            legacy_status TEXT
                CHECK (
                    legacy_status IN ('PENDING', 'CONFIRMED', 'REJECTED')
                    OR legacy_status IS NULL
                ),
            pass_number INTEGER UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )


def _ensure_booking_columns(connection):
    """Ajoute les colonnes de réservation sans toucher aux données."""
    existing = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(appointments)")
    }
    for name, sql_type in BOOKING_COLUMNS.items():
        if name not in existing:
            connection.execute(
                f"ALTER TABLE appointments ADD COLUMN {name} {sql_type}"
            )
    # Filets de sécurité en plus de BEGIN IMMEDIATE. Les anciennes lignes
    # (colonnes NULL) sont ignorées par ces index partiels.
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_appointments_phone_day
        ON appointments(contact_normalized, requested_date)
        WHERE contact_normalized IS NOT NULL
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_appointments_slot_day
        ON appointments(requested_date, slot_id)
        WHERE slot_id IS NOT NULL
        """
    )


def _sessions_migration_applied(connection):
    """Indique si le schéma des consultations par session est installé."""
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type = 'table' AND name = 'hiar_schema_migrations'"
    ).fetchone()
    if not exists:
        return False
    return connection.execute(
        "SELECT 1 FROM hiar_schema_migrations WHERE version = 1"
    ).fetchone() is not None


def init_db():
    """Crée la base ou migre les anciennes demandes sans les supprimer."""
    with get_connection() as connection:
        if _sessions_migration_applied(connection):
            return
        exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'appointments'
            """
        ).fetchone()

        if not exists:
            _create_appointments_table(connection)
        else:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(appointments)"
                ).fetchall()
            }

            if {"legacy_status", "pass_number"}.issubset(columns):
                # La migration a déjà été appliquée.
                pass
            else:
                connection.execute("BEGIN IMMEDIATE")
                old_rows = connection.execute(
                    "SELECT * FROM appointments "
                    "ORDER BY requested_date, requested_time, id"
                ).fetchall()

                _create_appointments_table(connection, "appointments_new")

                next_pass_number = 1
                for row in old_rows:
                    old = dict(row)
                    old_status = old["status"]

                    if old_status == "PENDING":
                        status = "en attente"
                        legacy_status = "PENDING"
                        pass_number = next_pass_number
                        next_pass_number += 1
                    elif old_status in {"CONFIRMED", "REJECTED"}:
                        status = None
                        legacy_status = old_status
                        pass_number = None
                    else:
                        raise ValueError(
                            "Statut historique inconnu : "
                            f"{old_status!r}. Migration interrompue."
                        )

                    connection.execute(
                        """
                        INSERT INTO appointments_new (
                            id, patient_name, contact, reason,
                            requested_date, requested_time, status,
                            legacy_status, pass_number, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            old["id"],
                            old["patient_name"],
                            old["contact"],
                            old["reason"],
                            old["requested_date"],
                            old["requested_time"],
                            status,
                            legacy_status,
                            pass_number,
                            old["created_at"],
                        ),
                    )

                connection.execute("DROP TABLE appointments")
                connection.execute(
                    "ALTER TABLE appointments_new RENAME TO appointments"
                )

        _ensure_booking_columns(connection)

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_appointments_status_date
            ON appointments(status, requested_date, requested_time)
            """
        )


def init_sessions_db():
    """Prépare le schéma historique puis applique la migration des sessions."""
    init_db()
    from migrations.consultation_sessions import migrate
    with get_connection() as connection:
        return migrate(connection)


def list_slots(requested_date):
    """Liste les 4 créneaux du jour avec leur disponibilité."""
    with get_connection() as connection:
        taken = {
            row[0]
            for row in connection.execute(
                "SELECT slot_id FROM appointments "
                "WHERE requested_date = ? AND slot_id IS NOT NULL",
                (requested_date,),
            )
        }
    return [
        {
            "id": sid,
            "start": slot["start"],
            "end": slot["end"],
            "doctor": slot["doctor"],
            "available": sid not in taken,
        }
        for sid, slot in SLOTS.items()
    ]


def create_appointment(
    patient_name,
    contact,
    reason,
    requested_date,
    requested_time,
    slot_id=None,
    temperature_c=None,
    heart_rate_bpm=None,
    spo2_percent=None,
):
    """Enregistre une demande et lui attribue un numéro de passage."""
    fields = {
        "Nom": patient_name,
        "Contact": contact,
        "Motif": reason,
        "Date": requested_date,
        "Heure": requested_time,
    }

    for label, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Le champ « {label} » est obligatoire.")

    try:
        parsed_date = datetime.strptime(
            requested_date.strip(), "%Y-%m-%d"
        ).date()
        parsed_time = datetime.strptime(
            requested_time.strip(), "%H:%M"
        ).time()
    except ValueError as exc:
        raise ValueError(
            "Date ou heure invalide. Formats attendus : AAAA-MM-JJ et HH:MM."
        ) from exc

    if parsed_date.isoformat() != requested_date.strip():
        raise ValueError("La date doit respecter le format AAAA-MM-JJ.")

    if parsed_time.strftime("%H:%M") != requested_time.strip():
        raise ValueError("L'heure doit respecter le format HH:MM.")

    requested_at = datetime.combine(parsed_date, parsed_time)
    if requested_at <= datetime.now():
        raise ValueError("Le rendez-vous doit être demandé dans le futur.")

    slot_id = _resolve_slot(requested_time.strip(), slot_id)
    contact_normalized = normalize_phone(contact)
    doctor = SLOTS[slot_id]["doctor"]

    values = (
        patient_name.strip(),
        contact.strip(),
        reason.strip(),
        requested_date.strip(),
        requested_time.strip(),
    )
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")

    with get_connection() as connection:
        # Verrou d'écriture : les demandes concurrentes sont sérialisées.
        connection.execute("BEGIN IMMEDIATE")

        if connection.execute(
            "SELECT 1 FROM appointments "
            "WHERE contact_normalized = ? AND requested_date = ?",
            (contact_normalized, values[3]),
        ).fetchone():
            raise BookingError(
                "duplicate_phone",
                "Ce numéro a déjà un rendez-vous ce jour-là.",
            )

        if connection.execute(
            "SELECT 1 FROM appointments "
            "WHERE slot_id = ? AND requested_date = ?",
            (slot_id, values[3]),
        ).fetchone():
            raise BookingError("slot_taken", "Créneau indisponible.")

        # Le numéro de passage n'existe que si la transaction est validée :
        # en cas d'échec, tout est annulé (rollback) et rien n'est consommé.
        next_pass_number = connection.execute(
            """
            SELECT COALESCE(MAX(pass_number), 0) + 1
            FROM appointments
            """
        ).fetchone()[0]

        try:
            cursor = connection.execute(
                """
                INSERT INTO appointments (
                    patient_name, contact, reason,
                    requested_date, requested_time, status,
                    legacy_status, pass_number, created_at,
                    slot_id, doctor, contact_normalized,
                    temperature_c, heart_rate_bpm, spo2_percent
                )
                VALUES (
                    ?, ?, ?, ?, ?, 'en attente', NULL, ?, ?, ?, ?, ?,
                    ?, ?, ?
                )
                """,
                (
                    *values,
                    next_pass_number,
                    created_at,
                    slot_id,
                    doctor,
                    contact_normalized,
                    temperature_c,
                    heart_rate_bpm,
                    spo2_percent,
                ),
            )
        except sqlite3.IntegrityError as exc:
            message = str(exc)
            if "contact_normalized" in message:
                raise BookingError(
                    "duplicate_phone",
                    "Ce numéro a déjà un rendez-vous ce jour-là.",
                ) from exc
            if "slot_id" in message:
                raise BookingError(
                    "slot_taken", "Créneau indisponible."
                ) from exc
            raise
        return cursor.lastrowid


def list_appointments(status=None):
    """List active requests with their position in the time slot."""
    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError("Statut de consultation invalide.")

    with get_connection() as connection:
        if status is None:
            rows = connection.execute(
                """
                SELECT * FROM appointments
                WHERE status IS NOT NULL
                ORDER BY requested_date, requested_time, id
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM appointments
                WHERE status = ?
                ORDER BY requested_date, requested_time, id
                """,
                (status,),
            ).fetchall()

    results = []
    positions = {}
    for row in rows:
        appointment = dict(row)
        slot = (
            appointment["requested_date"],
            appointment["requested_time"],
        )
        positions[slot] = positions.get(slot, 0) + 1
        appointment["queue_position"] = positions[slot]
        results.append(appointment)

    return results


def list_historical_appointments():
    """Retourne les demandes anciennes exclues de la file active."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM appointments
            WHERE status IS NULL AND legacy_status IS NOT NULL
            ORDER BY requested_date, requested_time, id
            """
        ).fetchall()

    return [dict(row) for row in rows]


def update_appointment_status(
    appointment_id, status, exceptional_correction=False
):
    """Update an active appointment with controlled status transitions."""
    if status not in ALLOWED_STATUSES:
        raise ValueError("Statut de consultation invalide.")
    if not isinstance(exceptional_correction, bool):
        raise ValueError("Indicateur de correction exceptionnelle invalide.")

    normal_transitions = {
        "en attente": "appelé",
        "appelé": "terminé",
    }

    with get_connection() as connection:
        # Serialize concurrent status changes before reading the current state.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT status FROM appointments
            WHERE id = ? AND status IS NOT NULL
            """,
            (appointment_id,),
        ).fetchone()

        if row is None:
            return False

        current_status = row["status"]
        if current_status == status:
            raise ValueError("Le rendez-vous possède déjà ce statut.")

        if (
            not exceptional_correction
            and normal_transitions.get(current_status) != status
        ):
            raise ValueError(
                "Transition de statut interdite. "
                "Une correction exceptionnelle est nécessaire."
            )

        cursor = connection.execute(
            """
            UPDATE appointments
            SET status = ?
            WHERE id = ? AND status = ? AND status IS NOT NULL
            """,
            (status, appointment_id, current_status),
        )
        return cursor.rowcount == 1
