"""Validation stricte des paramètres d'entrée REST contre les injections (Item 18).

Assure le filtrage préventif des paramètres avant toute manipulation
métier ou requête en base de données.
"""

import re
from typing import Optional

RE_DATE = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$")
RE_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
RE_DOCTOR_CODE = re.compile(r"^[a-zA-Z0-9_\-]{1,32}$")
RE_PERIOD = re.compile(r"^(MAT|AM|APM)$")
RE_REASON_CODE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
RE_PIN = re.compile(r"^\d{4,8}$")
DANGEROUS_CHARS = {"<", ">", ";", "`", "$", "{", "}", "\x00"}


def validate_phone(phone: Optional[str]) -> bool:
    """Valide strictement le format d'un numéro de téléphone (8 à 15 chiffres)."""
    if not phone or not isinstance(phone, str):
        return False
    # Caractères autorisés uniquement : chiffres, +, espaces, tirets, points, parenthèses
    if not re.match(r"^[\d\s.\-()+]{8,25}$", phone):
        return False
    cleaned = re.sub(r"[\s.\-()]", "", phone)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("261") and len(cleaned) == 12:
        digits = cleaned
    elif cleaned.startswith("0") and len(cleaned) == 10:
        digits = "261" + cleaned[1:]
    else:
        digits = cleaned
    return digits.isdigit() and 8 <= len(digits) <= 15


def validate_date(date_str: Optional[str]) -> bool:
    """Valide strictement une date au format ISO AAAA-MM-JJ."""
    if not date_str or not isinstance(date_str, str):
        return False
    return bool(RE_DATE.match(date_str.strip()))


def validate_time(time_str: Optional[str]) -> bool:
    """Valide strictement une heure au format HH:MM."""
    if not time_str or not isinstance(time_str, str):
        return False
    return bool(RE_TIME.match(time_str.strip()))


def validate_doctor_code(code: Optional[str]) -> bool:
    """Valide un identifiant médecin (alphanumérique, tiret, underscore)."""
    if not code or not isinstance(code, str):
        return False
    return bool(RE_DOCTOR_CODE.match(code.strip()))


def validate_period(period: Optional[str]) -> bool:
    """Valide une période de consultation (MAT ou APM)."""
    if not period or not isinstance(period, str):
        return False
    return bool(RE_PERIOD.match(period.strip()))


def validate_reason_code(code: Optional[str]) -> bool:
    """Valide un motif de consultation structuré."""
    if not code or not isinstance(code, str):
        return False
    return bool(RE_REASON_CODE.match(code.strip()))


def validate_pin(pin: Optional[str]) -> bool:
    """Valide un code PIN (4 à 8 chiffres)."""
    if not pin or not isinstance(pin, str):
        return False
    return bool(RE_PIN.match(pin.strip()))


def validate_safe_text(text: Optional[str], max_len: int = 120) -> bool:
    """Vérifie l'absence de caractères d'injection/contrôle dans une chaîne libre."""
    if not text or not isinstance(text, str):
        return False
    s = text.strip()
    if not s or len(s) > max_len:
        return False
    if any(c in DANGEROUS_CHARS for c in s):
        return False
    return True
