"""Catalogue de la consultation HIAR et utilitaires du dialogue vocal.

Module « feuille » (aucune dépendance ROS, ni vers voice_intent_parser) partagé par :
  - voice_intent_parser : reconnaissance des médecins, motifs et périodes ;
  - consultation_voice  : déroulé vocal pas à pas de la prise de rendez-vous ;
  - les tests (cohérence avec l'application mobile et l'interface web).

Identifiants stables : les codes A/B/C/D restent la clé en base de données et dans les tickets
(« B-AM-3 »). Seul l'affichage et la voix utilisent le prénom du médecin.
"""

import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

# Même ordre, mêmes prénoms et mêmes périodes que hiar_mobile/lib/features/consultation/doctors.dart
# et web_interface/consultation_sessions_store.py (un test vérifie la cohérence des trois).
DOCTORS: Dict[str, Dict[str, Any]] = {
    "A": {
        "name": "Raissa",
        "period": "MAT",
        # Variantes que le STT français écrit pour ce prénom (déjà sans accent ni majuscule).
        "aliases": ("raissa", "raisa", "raysa", "rayssa", "reissa", "reisa", "raiza", "raissah"),
    },
    "B": {
        "name": "Bell",
        "period": "AM",
        "aliases": ("bell", "belle", "bel", "belles"),
    },
    "C": {
        "name": "Pierrot",
        "period": "MAT",
        "aliases": ("pierrot", "pierro", "pierrault", "pierrots", "pierot", "piero"),
    },
    "D": {
        "name": "Alice",
        "period": "AM",
        "aliases": ("alice", "alis", "alisse", "alyce"),
    },
}

PERIODS: Dict[str, Dict[str, str]] = {
    "MAT": {"label": "Matin", "hours": "08 h 00 – 12 h 00", "spoken": "le matin"},
    "AM": {"label": "Après-midi", "hours": "13 h 00 – 18 h 00", "spoken": "l'après-midi"},
}

REASONS: Dict[str, Dict[str, Any]] = {
    "consultation_generale": {
        "label": "Consultation générale",
        "spoken": "une consultation générale",
        "targets": ("CONSULTATION_GENERALE", "GENERALE", "GENERAL", "CONSULTATION"),
    },
    "suivi_medical": {
        "label": "Suivi médical",
        "spoken": "un suivi médical",
        "targets": ("SUIVI_MEDICAL", "SUIVI", "CONTROLE"),
    },
    "autre_motif": {
        "label": "Autre motif",
        "spoken": "un autre motif",
        "targets": ("AUTRE_MOTIF", "AUTRE", "AUTRES", "OTHER"),
    },
}


def norm(text: Optional[str]) -> str:
    """Minuscules, sans accents ni ponctuation (identique à voice_intent_parser.normalize_text)."""
    if not text:
        return ""
    lowered = text.lower().strip()
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(c)
    )
    cleaned = re.sub(r"[^\w\s-]", " ", stripped)
    return re.sub(r"\s+", " ", cleaned).strip()


# ---------------------------------------------------------------------------
# Médecins
# ---------------------------------------------------------------------------

_DOCTOR_PREFIX = r"(?:docteur|doc|dr|medecin|dokotera)"
_ALIAS_TO_CODE: Dict[str, str] = {
    alias: code for code, info in DOCTORS.items() for alias in (info["name"].lower(), *info["aliases"])
}
_ALIAS_REGEX = re.compile(r"\b(" + "|".join(sorted(_ALIAS_TO_CODE, key=len, reverse=True)) + r")\b")
# « médecin B », « docteur c » : la lettre doit terminer la phrase (ou précéder la période),
# sinon « le médecin a besoin de… » serait compris comme le médecin A.
_CODE_REGEX = re.compile(
    r"\b" + _DOCTOR_PREFIX + r"\s+([abcd])(?=\s*$|\s+(?:le\s+)?(?:matin|apres[- ]midi|svp|s il vous plait|merci)\b)"
)


def doctor_name(code: Optional[str]) -> str:
    return DOCTORS[code]["name"] if code in DOCTORS else ""


def doctor_label(code: Optional[str]) -> str:
    """Libellé affiché : « Dr Raissa »."""
    return f"Dr {doctor_name(code)}" if code in DOCTORS else "Médecin"


def doctor_spoken(code: Optional[str]) -> str:
    """Forme parlée : « le docteur Raissa »."""
    return f"le docteur {doctor_name(code)}" if code in DOCTORS else "le médecin"


def doctor_period(code: Optional[str]) -> Optional[str]:
    return DOCTORS[code]["period"] if code in DOCTORS else None


def doctors_for_period(period: Optional[str]) -> List[str]:
    return [code for code, info in DOCTORS.items() if info["period"] == period]


def resolve_doctor(value: Any) -> Optional[str]:
    """Code (A-D) d'un médecin à partir d'un code, d'un prénom ou d'une variante STT.

    Accepte aussi bien ce que renvoie le LLM (« RAISSA », « B », « Dr Bell ») que ce qui est dit.
    """
    if value is None:
        return None
    text = norm(str(value))
    text = re.sub(r"^(?:le |la |l )?" + _DOCTOR_PREFIX + r"\s+", "", text).strip()
    if not text:
        return None
    if len(text) == 1 and text.upper() in DOCTORS:
        return text.upper()
    return _ALIAS_TO_CODE.get(text)


def find_doctors_in_text(text: str, *, name_only_ok: bool = True) -> List[str]:
    """Médecins cités dans une phrase, dans l'ordre d'apparition, sans doublon.

    `name_only_ok=False` (hors écran de consultation) exige un préfixe « docteur / médecin » devant
    le prénom, pour ne pas confondre une phrase quelconque avec le prénom d'un médecin.
    """
    n = norm(text)
    found: List[Tuple[int, str]] = []
    for match in _ALIAS_REGEX.finditer(n):
        before = n[: match.start()].rstrip()
        prefixed = bool(re.search(r"\b" + _DOCTOR_PREFIX + r"$", before))
        if name_only_ok or prefixed:
            found.append((match.start(), _ALIAS_TO_CODE[match.group(1)]))
    for match in _CODE_REGEX.finditer(n):
        found.append((match.start(1), match.group(1).upper()))
    found.sort()
    ordered: List[str] = []
    for _, code in found:
        if code not in ordered:
            ordered.append(code)
    return ordered


# ---------------------------------------------------------------------------
# Périodes et motifs
# ---------------------------------------------------------------------------

_PERIOD_TARGETS = {
    "MAT": "MAT", "MATIN": "MAT", "MORNING": "MAT", "MATINEE": "MAT",
    "AM": "AM", "APM": "AM", "PM": "AM", "AFTERNOON": "AM",
    "APRES_MIDI": "AM", "APRES-MIDI": "AM", "APRES MIDI": "AM", "APREM": "AM",
}


def resolve_period(value: Any) -> Optional[str]:
    if value is None:
        return None
    key = norm(str(value)).upper().replace(" ", "_")
    return _PERIOD_TARGETS.get(key) or _PERIOD_TARGETS.get(key.replace("_", "-"))


def find_period_in_text(text: str) -> Optional[str]:
    n = norm(text)
    if re.search(r"\b(apres[- ]midi|aprem|apm)\b", n):
        return "AM"
    if re.search(r"\b(matin|matinee)\b", n):
        return "MAT"
    return None


def resolve_reason(value: Any) -> Optional[str]:
    """Code motif (« suivi_medical »…) depuis le texte du LLM ou un code existant."""
    if value is None:
        return None
    raw = str(value).strip()
    if raw in REASONS:
        return raw
    key = norm(raw).upper().replace(" ", "_")
    for code, info in REASONS.items():
        if key in info["targets"]:
            return code
    return None


# ---------------------------------------------------------------------------
# Formulaire de consultation (vue normalisée des données)
# ---------------------------------------------------------------------------

def form_from_data(data: Optional[Mapping[str, Any]]) -> Dict[str, Optional[str]]:
    """Extrait reason / doctor / period / name / phone d'un dictionnaire de consultation.

    Les deux familles de clés coexistent (mobile : `selected_*`, base : `*_code`).
    """
    data = data or {}

    def pick(*keys: str) -> Optional[str]:
        for key in keys:
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    doctor = pick("doctor_code", "selected_doctor")
    return {
        "reason": resolve_reason(pick("reason_code", "selected_reason")),
        "doctor": doctor.upper() if doctor and doctor.upper() in DOCTORS else None,
        "period": resolve_period(pick("period", "selected_period")),
        "name": pick("patient_name"),
        "phone": pick("contact", "patient_phone"),
    }


def form_fields(form: Mapping[str, Optional[str]]) -> Dict[str, Any]:
    """Champs `fields` d'une instruction serveur pour que le mobile applique ces valeurs."""
    fields: Dict[str, Any] = {}
    if form.get("reason"):
        fields["selected_reason"] = form["reason"]
    if form.get("doctor"):
        fields["selected_doctor"] = form["doctor"]
    if form.get("period"):
        fields["selected_period"] = form["period"]
    if form.get("name"):
        fields["patient_name"] = form["name"]
    if form.get("phone"):
        fields["patient_phone"] = form["phone"]
    return fields


def first_missing_step(form: Mapping[str, Optional[str]]) -> Optional[int]:
    """Première étape (1-3) dont une donnée obligatoire manque, sinon None."""
    if not form.get("reason"):
        return 1
    if not form.get("doctor") or not form.get("period"):
        return 2
    if not form.get("name") or not form.get("phone"):
        return 3
    return None


def doctors_choice_speech() -> str:
    parts = []
    for period in ("MAT", "AM"):
        names = [doctor_name(c) for c in doctors_for_period(period)]
        if names:
            parts.append(f"{PERIODS[period]['spoken'].capitalize()} : {' ou '.join(names)}.")
    return " ".join(parts)


def doctors_of_period_speech(period: str) -> str:
    names = [doctor_name(c) for c in doctors_for_period(period)]
    when = PERIODS[period]["spoken"]
    if not names:
        return f"Aucun médecin n'est prévu {when}."
    if len(names) == 1:
        return f"{when.capitalize()}, c'est {names[0]}."
    return f"{when.capitalize()}, vous pouvez voir {' ou '.join(names)}."


def reason_choice_speech() -> str:
    return "Consultation générale, suivi médical, ou autre motif."


def validation_message(step: int, form: Mapping[str, Optional[str]], *, with_choices: bool = True) -> str:
    """Pourquoi on ne peut pas quitter l'étape (même rôle que le message du mobile).

    `with_choices=False` quand l'invite de l'étape sera annoncée juste après (évite la répétition).
    """
    if step == 1:
        return "Je ne peux pas continuer sans motif." + (" " + reason_choice_speech() if with_choices else "")
    if step == 2:
        return "Je ne peux pas continuer sans médecin." + (" " + doctors_choice_speech() if with_choices else "")
    if step == 3:
        if not form.get("name") and not form.get("phone"):
            return "Il me faut votre nom complet et votre numéro de téléphone."
        if not form.get("name"):
            return "Il me manque votre nom complet."
        return "Il me manque votre numéro de téléphone."
    return "Veuillez compléter cette étape avant de continuer."


def recap_speech(form: Mapping[str, Optional[str]]) -> str:
    """Récapitulatif oral SANS donnée personnelle ni constantes (lieu public)."""
    reason = REASONS.get(form.get("reason") or "", {}).get("spoken", "une consultation")
    doctor = form.get("doctor")
    period = form.get("period") or doctor_period(doctor)
    when = f", {PERIODS[period]['spoken']}" if period in PERIODS else ""
    return (
        f"Récapitulatif : {reason} avec {doctor_spoken(doctor)}{when}. "
        "Dites Confirmer pour valider, ou Précédent pour modifier."
    )


# ---------------------------------------------------------------------------
# Téléphone dicté
# ---------------------------------------------------------------------------

_UNITS = {"zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
          "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9}
_TEENS = {"dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16}
_TENS = {"vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60, "quatrevingt": 80}


def _parse_group(tokens: List[str], i: int) -> Tuple[Optional[str], int]:
    """Lit un nombre français (0-999) à partir de tokens[i] et renvoie (chiffres, indice suivant)."""
    n = len(tokens)
    t = tokens[i]
    if t == "zero":
        return "0", i + 1

    value, j, hundreds = 0, i, False
    if t in _UNITS and _UNITS[t] >= 1 and j + 1 < n and tokens[j + 1] in ("cent", "cents"):
        value, j, hundreds = _UNITS[t] * 100, j + 2, True
    elif t in ("cent", "cents"):
        value, j, hundreds = 100, j + 1, True

    if j < n:
        cur = tokens[j]
        if cur in _TENS:
            base = _TENS[cur]
            j += 1
            if base in (60, 80) and j < n and tokens[j] in _TEENS:
                base += _TEENS[tokens[j]]
                j += 1
                if tokens[j - 1] == "dix" and j < n and tokens[j] in ("sept", "huit", "neuf"):
                    base += _UNITS[tokens[j]]
                    j += 1
            elif j < n and tokens[j] in _UNITS and _UNITS[tokens[j]] >= 1:
                base += _UNITS[tokens[j]]
                j += 1
            value += base
        elif cur in _TEENS:
            base = _TEENS[cur]
            j += 1
            if cur == "dix" and j < n and tokens[j] in ("sept", "huit", "neuf"):
                base += _UNITS[tokens[j]]
                j += 1
            value += base
        elif cur in _UNITS and _UNITS[cur] >= 1:
            value += _UNITS[cur]
            j += 1

    if j == i:
        return None, i
    return str(value), j


def spoken_to_digits(text: str) -> str:
    """Chiffres contenus dans une phrase, qu'ils soient écrits en chiffres ou en toutes lettres.

    « zéro trente-quatre douze trois cent quarante-cinq soixante-sept » -> « 0341234567 ».
    Les mots inconnus (« mon numéro est… ») sont ignorés.
    """
    n = norm(text).replace("-", " ")
    n = re.sub(r"\bquatre vingts?\b", "quatrevingt", n)
    tokens = [t for t in n.split() if t != "et"]
    out: List[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isdigit():
            out.append(token)
            i += 1
            continue
        digits, j = _parse_group(tokens, i)
        if digits is not None:
            out.append(digits)
            i = j
        else:
            i += 1
    return "".join(out)


def national_phone(digits: str) -> Optional[str]:
    """Numéro malgache complet au format national (10 chiffres, « 0 » initial) ou None."""
    d = re.sub(r"\D", "", digits or "")
    if d.startswith("00261"):
        d = "0" + d[5:]
    elif d.startswith("261") and len(d) == 12:
        d = "0" + d[3:]
    return d if len(d) == 10 and d.startswith("0") else None


def format_phone_display(national: str) -> str:
    """« 0341234567 » -> « 034 12 345 67 »."""
    d = re.sub(r"\D", "", national or "")
    if len(d) != 10:
        return d
    return f"{d[:3]} {d[3:5]} {d[5:8]} {d[8:]}"


def format_phone_spoken(national: str) -> str:
    """Chiffre par chiffre pour la vérification orale : « 0 3 4, 1 2, 3 4 5, 6 7 »."""
    d = re.sub(r"\D", "", national or "")
    groups = [d[:3], d[3:5], d[5:8], d[8:]] if len(d) == 10 else [d]
    return ", ".join(" ".join(g) for g in groups if g)


# ---------------------------------------------------------------------------
# Nom dicté
# ---------------------------------------------------------------------------

_NAME_INTRO = re.compile(
    r"^\s*(?:(?:bonjour|salut|bonsoir)[\s,.!]*)?"
    r"(?:je\s+m['’ ]?\s*appelle|je\s+me\s+nomme|mon\s+(?:nom|prenom|prénom)(?:\s+complet)?\s+(?:est|c['’]est)|"
    r"moi\s+c['’]est|c['’]est|je\s+suis|le\s+nom\s+(?:est|c['’]est)|my\s+name\s+is)\s+",
    re.IGNORECASE,
)
_NAME_OUTRO = re.compile(r"[\s,.!]*(?:s['’ ]?il\s+(?:vous|te)\s+pla[iî]t|svp|merci)[\s.!]*$", re.IGNORECASE)
_NAME_WORD = re.compile(r"^[^\W\d_]+(?:['’-][^\W\d_]+)*$", re.UNICODE)
_NAME_PARTICLES = {"de", "du", "des", "la", "le", "van", "von", "el", "al", "ben", "ibn", "di", "da"}
# Mots qui prouvent que la phrase n'est PAS un nom : commandes, questions, lieux, vocabulaire médical…
_NOT_A_NAME = {
    "oui", "non", "suivant", "suivante", "precedent", "precedente", "retour", "annuler", "annule", "continuer",
    "passer", "valider", "confirmer", "merci", "bonjour", "salut", "bonsoir", "stop", "pause", "terminer",
    "pharmacie", "laboratoire", "radiologie", "reception", "accueil", "consultation", "medecin", "docteur",
    "rendez", "aide", "comment", "pourquoi", "quoi", "ou", "est", "sont", "veux", "veut", "voudrais",
    "peux", "peut", "besoin", "quel", "quelle", "quels", "je", "tu", "nous", "vous", "mon", "ma", "mes",
    "numero", "telephone", "nom", "prenom", "suivi", "medical", "generale", "autre", "motif", "matin",
    "midi", "mesurer", "constantes", "temperature", "pouls", "orientation", "menu", "robot", "modifier",
    "changer", "corriger", "recommencer", "reprendre", "pas", "plus", "svp",
}


def _capitalize_name(word: str) -> str:
    if word.lower() in _NAME_PARTICLES:
        return word.lower()
    return re.sub(r"(^|[-'’])([^\W\d_])", lambda m: m.group(1) + m.group(2).upper(), word.lower())


def has_name_intro(text: str) -> bool:
    return bool(_NAME_INTRO.match(text or ""))


def clean_name(text: str) -> Optional[str]:
    """Nom du patient extrait d'une phrase dictée, ou None si ce n'est pas un nom.

    « je m'appelle jean-pierre dupont » -> « Jean-Pierre Dupont ».
    Refuse les chiffres, les phrases longues et tout ce qui ressemble à une commande ou une question.
    """
    stripped = _NAME_INTRO.sub("", (text or "").strip(), count=1)
    stripped = _NAME_OUTRO.sub("", stripped).strip(" ,.;:!?")
    words = stripped.split()
    if not 1 <= len(words) <= 5:
        return None
    if any(not _NAME_WORD.match(w) for w in words):
        return None
    if sum(len(w) for w in words) < 2:
        return None
    if any(norm(w) in _NOT_A_NAME for w in words):
        return None
    return " ".join(_capitalize_name(w) for w in words)


# Commandes fermées reconnues localement pendant la saisie des coordonnées (sans LLM).
_COMMAND_NEXT = re.compile(r"^(?:suivant|suivante|continuer|etape suivante|valider|on continue|passer)$")
_COMMAND_PREV = re.compile(r"^(?:precedent|precedente|retour|reculer|etape precedente|revenir|en arriere)$")
_COMMAND_CANCEL = re.compile(r"^(?:annuler|annule|quitter|abandonner|laisse tomber)$")
_WHICH_NAME = re.compile(r"\b(nom|prenom)\b")
_WHICH_PHONE = re.compile(r"\b(numero|telephone|phone|chiffres?)\b")
_WHICH_BOTH = re.compile(r"\b(les deux|tout|tous|depuis le debut|recommencer)\b")


def closed_command(text: str) -> Optional[str]:
    """'next' | 'prev' | 'cancel' si la phrase entière est une de ces commandes, sinon None."""
    n = norm(text)
    if _COMMAND_NEXT.match(n):
        return "next"
    if _COMMAND_PREV.match(n):
        return "prev"
    if _COMMAND_CANCEL.match(n):
        return "cancel"
    return None


def which_field_to_correct(text: str) -> Optional[str]:
    """'name' | 'phone' | 'both' d'après « le nom », « le numéro », « les deux »."""
    n = norm(text)
    if _WHICH_BOTH.search(n):
        return "both"
    wants_name, wants_phone = bool(_WHICH_NAME.search(n)), bool(_WHICH_PHONE.search(n))
    if wants_name and wants_phone:
        return "both"
    if wants_name:
        return "name"
    if wants_phone:
        return "phone"
    return None
