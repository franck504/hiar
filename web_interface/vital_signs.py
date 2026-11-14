"""Acquisition des signes vitaux via un ESP32 dédié (port série).

Indépendant du robot : aucun lien avec ROS ni avec /hmi/request.
Sans port configuré, ou en cas d'échec : état "indisponible".
Aucune valeur n'est jamais simulée.
"""

import os
import threading
import time
from datetime import datetime

BAUDRATE = 115200
BOOT_WAIT_S = 2.5          # l'ouverture du port redémarre souvent l'ESP32
TOTAL_TIMEOUT_S = 30.0
TEMP_RANGE = (25.0, 45.0)  # plausibilité capteur, pas une plage clinique
BPM_RANGE = (40.0, 200.0)

_lock = threading.Lock()


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _result(state, reason=None, values=None, measured_at=None):
    return {
        "state": state,
        "values": values or {
            "temperature_c": None,
            "heart_rate_bpm": None,
            "spo2_percent": None,
        },
        "measured_at": measured_at,
        "checked_at": _now(),
        "reason": reason,
    }


def _open_port(port):
    import serial  # pyserial n'est requis que si un port est configuré
    return serial.Serial(port, BAUDRATE, timeout=1)


def _parse_fields(text):
    # "RESULT,temperature_c=36.5,heart_rate_bpm=72,spo2_percent=NA"
    fields = {}
    for part in text.split(",")[1:]:
        key, sep, value = part.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _number(raw, low, high):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value != value or not (low <= value <= high):
        return None
    return value


def _build(raw):
    fields = _parse_fields(raw)
    temperature = _number(fields.get("temperature_c"), *TEMP_RANGE)
    heart = _number(fields.get("heart_rate_bpm"), *BPM_RANGE)

    if temperature is None and heart is None:
        return _result(
            "indisponible",
            "Aucune mesure valide (capteur absent ou doigt non posé).",
        )

    values = {
        "temperature_c": round(temperature, 1) if temperature is not None else None,
        "heart_rate_bpm": int(round(heart)) if heart is not None else None,
        "spo2_percent": None,  # algorithme SpO2 non implémenté
    }
    missing = []
    if temperature is None:
        missing.append("température")
    if heart is None:
        missing.append("fréquence cardiaque")
    reason = ("Non mesuré : " + ", ".join(missing)) if missing else None
    return _result("valide", reason, values, _now())


def acquire():
    port = os.environ.get("HIAR_VITALS_PORT", "").strip()
    if not port:
        return _result(
            "indisponible",
            "Capteurs non connectés à ce système.",
        )
    if not _lock.acquire(blocking=False):
        return _result("en cours", "Une mesure est déjà en cours.")

    ser = None
    try:
        try:
            ser = _open_port(port)
        except Exception:
            return _result("indisponible", "Port des capteurs inaccessible.")

        time.sleep(BOOT_WAIT_S)
        ser.reset_input_buffer()
        ser.write(b"MEASURE\n")

        deadline = time.monotonic() + TOTAL_TIMEOUT_S
        while time.monotonic() < deadline:
            raw = ser.readline().decode("ascii", errors="ignore").strip()
            if raw.startswith("ERROR,"):
                return _result("indisponible", "Capteurs indisponibles : " + raw[6:])
            if raw.startswith("RESULT,"):
                return _build(raw)
        return _result("indisponible", "Aucune réponse des capteurs.")
    except Exception:
        return _result("indisponible", "Erreur de communication avec les capteurs.")
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        _lock.release()
