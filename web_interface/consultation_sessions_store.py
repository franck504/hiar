"""Gestion des consultations par médecin et période."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from appointments_store import (
    BookingError,
    get_connection,
    normalize_phone,
)

TZ = ZoneInfo("Indian/Antananarivo")

DOCTORS = ("A", "B", "C", "D")
# Prénoms affichés (et dits par le robot). Les codes A-D restent les clés stables de la base et des
# tickets (« B-AM-3 ») ; un test vérifie l'accord avec l'application mobile et le dialogue vocal.
DOCTOR_NAMES = {"A": "Raissa", "B": "Bell", "C": "Pierrot", "D": "Alice"}
PERIODS = {
    "MAT": {"start": "08:00", "end": "12:00"},
    "AM": {"start": "13:00", "end": "18:00"},
}
CUTOFF_MINUTES = 30

REASON_LABELS = {
    "consultation_generale": "Consultation générale",
    "suivi_medical": "Suivi médical",
    "autre_motif": "Autre motif",
}

SESSION_STATUSES = {
    "en attente", "appelé", "terminé", "annulé", "non reçu"
}


def doctor_name(code):
    """Prénom du médecin (« Bell ») ; le code lui-même s'il est inconnu."""
    return DOCTOR_NAMES.get(code, code or "")


def doctor_choices():
    """Liste ordonnée pour les gabarits : [{'code': 'A', 'name': 'Raissa'}, …]."""
    return [{"code": code, "name": DOCTOR_NAMES[code]} for code in DOCTORS]


def _now(value=None):
    if value is None:
        return datetime.now(TZ)
    if not isinstance(value, datetime):
        raise ValueError("Horloge invalide.")
    if value.tzinfo is None:
        raise ValueError("L'horloge doit contenir un fuseau horaire.")
    return value.astimezone(TZ)


def _validate_session(requested_date, doctor_code, period):
    if doctor_code not in DOCTORS:
        raise ValueError("Médecin invalide.")
    if period not in PERIODS:
        raise ValueError("Période invalide.")
    try:
        parsed = datetime.strptime(requested_date, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError("Date invalide.") from exc
    if parsed.isoformat() != requested_date:
        raise ValueError("Format de date invalide.")
    return parsed


def _cutoff(requested_date, period):
    end_time = datetime.strptime(PERIODS[period]["end"], "%H:%M").time()
    end = datetime.combine(requested_date, end_time, tzinfo=TZ)
    return end - timedelta(minutes=CUTOFF_MINUTES)


def ensure_daily_sessions(now=None):
    """Crée les huit sessions du jour sans modifier celles déjà existantes."""
    current = _now(now)
    requested_date = current.date().isoformat()
    timestamp = current.isoformat(timespec="seconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany("""
            INSERT OR IGNORE INTO doctor_sessions (
                requested_date, doctor_code, period,
                is_open, opened_at, closed_at
            )
            VALUES (?, ?, ?, 1, ?, NULL)
        """, [
            (requested_date, doctor, period, timestamp)
            for doctor in DOCTORS
            for period in PERIODS
        ])

    return requested_date


def list_doctor_sessions(requested_date, now=None):
    """Liste les sessions créées et leur nombre de patients en attente."""
    parsed_date = _validate_session(requested_date, "A", "MAT")
    current = _now(now)

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                s.requested_date,
                s.doctor_code,
                s.period,
                s.is_open,
                s.manual_open,
                s.opened_at,
                s.closed_at,
                COUNT(
                    CASE WHEN a.status = 'en attente' THEN 1 END
                ) AS waiting_count
            FROM doctor_sessions AS s
            LEFT JOIN appointments AS a
              ON a.requested_date = s.requested_date
             AND a.doctor = s.doctor_code
             AND a.period = s.period
            WHERE s.requested_date = ?
            GROUP BY
                s.requested_date, s.doctor_code, s.period,
                s.is_open, s.manual_open, s.opened_at, s.closed_at
            ORDER BY s.period, s.doctor_code
        """, (requested_date,)).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["doctor_name"] = doctor_name(item["doctor_code"])
        item["registration_open"] = bool(
            item["is_open"] and (
                item["manual_open"]
                or current < _cutoff(parsed_date, item["period"])
            )
        )
        item["waiting_count"] = int(item["waiting_count"])
        result.append(item)
    return result


def set_doctor_session(
    requested_date, doctor_code, period, is_open, now=None
):
    """Ouvre ou ferme une session déterminée."""
    parsed_date = _validate_session(requested_date, doctor_code, period)
    if not isinstance(is_open, bool):
        raise ValueError("L'état de la session doit être booléen.")

    current = _now(now)
    timestamp = current.isoformat(timespec="seconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        connection.execute("""
            INSERT INTO doctor_sessions (
                requested_date, doctor_code, period,
                is_open, opened_at, closed_at, manual_open
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(requested_date, doctor_code, period)
            DO UPDATE SET
                is_open = excluded.is_open,
                manual_open = excluded.manual_open,
                opened_at = CASE
                    WHEN excluded.is_open = 1 THEN excluded.opened_at
                    ELSE doctor_sessions.opened_at
                END,
                closed_at = CASE
                    WHEN excluded.is_open = 0 THEN excluded.closed_at
                    ELSE NULL
                END
        """, (
            parsed_date.isoformat(),
            doctor_code,
            period,
            int(is_open),
            timestamp if is_open else None,
            timestamp if not is_open else None,
            int(is_open),
        ))
    return True


def create_session_appointment(
    patient_name,
    contact,
    reason_code,
    requested_date,
    doctor_code,
    period,
    temperature_c=None,
    heart_rate_bpm=None,
    spo2_percent=None,
    now=None,
    bypass_cutoff=False,
):
    """Inscrit un patient dans une session ouverte avec ticket séquentiel."""
    current = _now(now)
    parsed_date = _validate_session(requested_date, doctor_code, period)

    if parsed_date != current.date():
        raise BookingError(
            "same_day_only",
            "Les inscriptions sont limitées à la journée en cours.",
        )

    if not isinstance(patient_name, str) or not patient_name.strip():
        raise ValueError("Le nom est obligatoire.")
    if reason_code not in REASON_LABELS:
        raise ValueError("Motif de consultation invalide.")

    contact_normalized = normalize_phone(contact)
    start_time = PERIODS[period]["start"]
    created_at = current.isoformat(timespec="seconds")
    reason = REASON_LABELS[reason_code]

    # Validation de sécurité des plages physiologiques des constantes vitales
    if temperature_c is not None:
        try:
            temperature_c = round(float(temperature_c), 1)
            if not (25.0 <= temperature_c <= 45.0):
                raise ValueError("Température corporelle hors de la plage physiologique valide (25°C - 45°C).")
        except (ValueError, TypeError) as exc:
            raise BookingError("invalid_vitals", str(exc)) from exc

    if heart_rate_bpm is not None:
        try:
            heart_rate_bpm = int(round(float(heart_rate_bpm)))
            if not (30 <= heart_rate_bpm <= 240):
                raise ValueError("Fréquence cardiaque hors de la plage physiologique valide (30 - 240 bpm).")
        except (ValueError, TypeError) as exc:
            raise BookingError("invalid_vitals", str(exc)) from exc

    if spo2_percent is not None:
        try:
            spo2_percent = int(round(float(spo2_percent)))
            if not (50 <= spo2_percent <= 100):
                raise ValueError("Saturation en oxygène (SpO2) hors de la plage physiologique valide (50% - 100%).")
        except (ValueError, TypeError) as exc:
            raise BookingError("invalid_vitals", str(exc)) from exc

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        session = connection.execute("""
            SELECT is_open, manual_open
            FROM doctor_sessions
            WHERE requested_date = ?
              AND doctor_code = ?
              AND period = ?
        """, (requested_date, doctor_code, period)).fetchone()

        if session is None or not session["is_open"]:
            raise BookingError(
                "session_closed",
                "Cette consultation n'est pas ouverte actuellement.",
            )

        if (
            not bypass_cutoff
            and not session["manual_open"]
            and current >= _cutoff(parsed_date, period)
        ):
            raise BookingError(
                "registration_closed",
                "La période d'inscription pour cette consultation est terminée.",
            )

        duplicate = connection.execute("""
            SELECT 1 FROM appointments
            WHERE contact_normalized = ?
              AND requested_date = ?
        """, (contact_normalized, requested_date)).fetchone()

        if duplicate:
            raise BookingError(
                "duplicate_phone",
                "Ce numéro a déjà une inscription ce jour-là.",
            )

        ticket_number = connection.execute("""
            SELECT COALESCE(MAX(ticket_number), 0) + 1
            FROM appointments
            WHERE requested_date = ?
              AND doctor = ?
              AND period = ?
        """, (requested_date, doctor_code, period)).fetchone()[0]

        try:
            cursor = connection.execute("""
                INSERT INTO appointments (
                    patient_name, contact, reason,
                    requested_date, requested_time, status,
                    legacy_status, pass_number, created_at,
                    doctor, contact_normalized,
                    temperature_c, heart_rate_bpm, spo2_percent,
                    period, ticket_number, reason_code
                )
                VALUES (
                    ?, ?, ?, ?, ?, 'en attente',
                    NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                patient_name.strip(),
                contact.strip(),
                reason,
                requested_date,
                start_time,
                created_at,
                doctor_code,
                contact_normalized,
                temperature_c,
                heart_rate_bpm,
                spo2_percent,
                period,
                ticket_number,
                reason_code,
            ))
        except Exception:
            raise

        return {
            "appointment_id": cursor.lastrowid,
            "ticket_number": ticket_number,
            "ticket_label": f"{doctor_code}-{period}-{ticket_number}",
            "doctor": doctor_code,
            "doctor_name": doctor_name(doctor_code),
            "period": period,
            "requested_date": requested_date,
            "status": "en attente",
        }


def list_session_appointments(
    requested_date, doctor_code=None, period=None, status=None
):
    """Retourne les inscriptions du nouveau modèle."""
    _validate_session(
        requested_date,
        doctor_code if doctor_code is not None else "A",
        period if period is not None else "MAT",
    )
    if status is not None and status not in SESSION_STATUSES:
        raise ValueError("Statut de consultation invalide.")

    query = """
        SELECT * FROM appointments
        WHERE requested_date = ?
          AND ticket_number IS NOT NULL
    """
    params = [requested_date]

    if doctor_code is not None:
        if doctor_code not in DOCTORS:
            raise ValueError("Médecin invalide.")
        query += " AND doctor = ?"
        params.append(doctor_code)

    if period is not None:
        if period not in PERIODS:
            raise ValueError("Période invalide.")
        query += " AND period = ?"
        params.append(period)

    if status is not None:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY period, doctor, ticket_number"

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["doctor_name"] = doctor_name(item.get("doctor"))
        result.append(item)
    return result


def update_session_appointment_status(
    appointment_id,
    status,
    doctor_code=None,
    exceptional_correction=False,
):
    """Modifie un ticket avec contrôle atomique du propriétaire et du statut."""
    if status not in SESSION_STATUSES:
        raise ValueError("Statut de consultation invalide.")
    if doctor_code is not None and doctor_code not in DOCTORS:
        raise ValueError("Médecin invalide.")
    if not isinstance(exceptional_correction, bool):
        raise ValueError("Indicateur de correction exceptionnelle invalide.")

    transitions = {
        "en attente": {"appelé", "annulé", "non reçu"},
        "appelé": {"terminé", "annulé", "non reçu"},
        "terminé": set(),
        "annulé": set(),
        "non reçu": set(),
    }

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            """
            SELECT doctor, status
            FROM appointments
            WHERE id = ? AND ticket_number IS NOT NULL
            """,
            (appointment_id,),
        ).fetchone()

        if row is None:
            return False

        if doctor_code is not None and row["doctor"] != doctor_code:
            return False

        current_status = row["status"]
        if current_status == status:
            raise ValueError("Le rendez-vous possède déjà ce statut.")

        if (
            not exceptional_correction
            and status not in transitions.get(current_status, set())
        ):
            raise ValueError(
                "Transition de statut interdite. "
                "Une correction exceptionnelle est nécessaire."
            )

        cursor = connection.execute(
            """
            UPDATE appointments
            SET status = ?
            WHERE id = ?
              AND doctor = ?
              AND status = ?
              AND ticket_number IS NOT NULL
            """,
            (status, appointment_id, row["doctor"], current_status),
        )
        return cursor.rowcount == 1
