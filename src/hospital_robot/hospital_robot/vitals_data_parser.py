"""Convertisseur et formateur de données de signes vitaux (ESP32 ➔ HMI).

Convertit les trames série provenant d'esp32_interface_node via /vitals/result
en instructions riches (champs formatés + synthèse vocale naturelle) pour le mobile.
"""

from typing import Dict, Optional, Tuple


TEMP_RANGE = (25.0, 45.0)
BPM_RANGE = (40.0, 220.0)
SPO2_RANGE = (70.0, 100.0)


def parse_vitals_frame(line: str) -> Dict:
    """Analyse la trame brute émise par l'ESP32.

    Formats acceptés :
    - 'RESULT,temperature_c=36.8,heart_rate_bpm=72,spo2_percent=98'
    - 'RESULT,temp=36.8,heart_rate=72,spo2=98'
    - 'ERROR,TIMEOUT', 'ERROR,BUSY', 'ERROR,SERIAL_COMMUNICATION'
    """
    if not isinstance(line, str):
        return {"ok": False, "error": "INVALID_TYPE", "raw": line}

    line = line.strip()

    if line.startswith("ERROR,"):
        code = line.split(",", 1)[1] if "," in line else "UNKNOWN"
        return {"ok": False, "error": code, "raw": line}

    if not line.startswith("RESULT,"):
        return {"ok": False, "error": "UNKNOWN_FRAME", "raw": line}

    parts = line.split(",")[1:]
    raw_dict = {}
    for part in parts:
        k, sep, v = part.partition("=")
        if sep:
            raw_dict[k.strip().lower()] = v.strip()

    # Extraction Température
    temp_raw = raw_dict.get("temperature_c") or raw_dict.get("temperature") or raw_dict.get("temp")
    temp = _parse_float(temp_raw, *TEMP_RANGE)

    # Extraction Fréquence Cardiaque
    hr_raw = raw_dict.get("heart_rate_bpm") or raw_dict.get("heart_rate") or raw_dict.get("bpm")
    hr = _parse_int(hr_raw, *BPM_RANGE)

    # Extraction SpO2
    spo2_raw = raw_dict.get("spo2_percent") or raw_dict.get("spo2")
    spo2 = _parse_int(spo2_raw, *SPO2_RANGE)

    if temp is None and hr is None and spo2 is None:
        return {
            "ok": False,
            "error": "NO_VALID_MEASURE",
            "reason": "Aucune mesure valide (capteur absent ou doigt non posé)",
            "raw": line,
        }

    return {
        "ok": True,
        "temperature": temp,
        "heart_rate": hr,
        "spo2": spo2,
        "raw": line,
    }


def _parse_float(val: Optional[str], low: float, high: float) -> Optional[float]:
    if not val or val.upper() in {"NA", "NONE", "NULL"}:
        return None
    try:
        f = float(val)
        if low <= f <= high:
            return round(f, 1)
    except (ValueError, TypeError):
        pass
    return None


def _parse_int(val: Optional[str], low: float, high: float) -> Optional[int]:
    if not val or val.upper() in {"NA", "NONE", "NULL"}:
        return None
    try:
        f = float(val)
        if low <= f <= high:
            return int(round(f))
    except (ValueError, TypeError):
        pass
    return None


def format_speech_fr(temp: Optional[float], hr: Optional[int], spo2: Optional[int]) -> str:
    """Génère une phrase naturelle en français pour le TTS sans prononcer les valeurs mesurées."""
    return "Mesure des constantes terminée. Vos résultats s'affichent à l'écran. Vous pouvez passer à l'étape suivante."


def build_vitals_instruction(parsed: Dict) -> Dict:
    """Construit l'instruction unifiée 'server/instruction' à partir du bilan."""
    if not parsed.get("ok"):
        error_code = parsed.get("error", "UNKNOWN")
        error_msg = "La mesure des constantes n'a pas pu aboutir. Veuillez repositionner votre doigt sur le capteur."
        if error_code == "TIMEOUT":
            error_msg = "Délai dépassé. Veuillez laisser votre doigt immobile sur le capteur."

        return {
            "origin": "server",
            "text_to_speak": error_msg,
            "speech_priority": "normal",
            "instruction_ui": {
                "screen": "consultation",
                "step": 4,
                "require_confirmation": False,
            },
            "value_to_show": {
                "field_id": "vitals_state",
                "value": "error",
            },
            "voice_hints": ["Réessayer", "Annuler"],
            "robot_status": {
                "face_expression": "speaking",
                "status_label": "Erreur capteur",
            },
        }

    temp = parsed.get("temperature")
    hr = parsed.get("heart_rate")
    spo2 = parsed.get("spo2")

    speech = format_speech_fr(temp, hr, spo2)

    fields = {}
    if temp is not None:
        fields["temperature"] = temp
        fields["temperature_c"] = temp
        fields["temperature_formatted"] = f"{temp} °C"
    if hr is not None:
        fields["heart_rate"] = hr
        fields["heart_rate_bpm"] = hr
        fields["heart_rate_formatted"] = f"{hr} bpm"
    if spo2 is not None:
        fields["spo2"] = spo2
        fields["spo2_percent"] = spo2
        fields["spo2_formatted"] = f"{spo2} %"

    return {
        "origin": "server",
        "text_to_speak": speech,
        "speech_priority": "normal",
        "instruction_ui": {
            "screen": "consultation",
            "step": 4,
            "require_confirmation": False,
        },
        "value_to_show": {
            "field_id": "vitals_state",
            "value": "done",
        },
        "fields": fields,
        "voice_hints": ["Valider", "Suivant"],
        "robot_status": {
            "face_expression": "happy",
            "status_label": "Constantes mesurées",
        },
    }
