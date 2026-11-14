"""Analyseur et classificateur d'intentions vocales en français pour HIAR.

Transforme le texte transcrit par le smartphone (voice/stt/final)
en actions normalisées pour ROS 2 et en instructions UI/TTS pour le mobile.
"""

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Dict, List, Optional


def normalize_text(text: str) -> str:
    """Normalise une chaîne : minuscules, suppression des accents et ponctuation."""
    if not text:
        return ""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s-]", " ", no_accents)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class ParsedIntent:
    intent_type: str  # "STOP", "ORIENTATION", "VITALS", "INFORMATION", "CONSULTATION", "HOME", "UNKNOWN"
    confidence: float = 1.0
    category: Optional[str] = None
    target_field: Optional[str] = None
    target_value: Optional[str] = None
    label: Optional[str] = None
    ros_request: Optional[Dict] = None
    ros_command: Optional[str] = None
    details: Dict = field(default_factory=dict)


class VoiceIntentParser:
    """Classifie le texte vocal et produit les instructions serveur/instruction."""

    DEPARTMENTS = {
        "PHARMACY": {
            "label": "Pharmacie",
            "regex": r"\b(pharmacie|medicaments?|ordonnance|remede)\b",
        },
        "LABORATORY": {
            "label": "Laboratoire d'analyses",
            "regex": r"\b(laboratoire|labo|analyses?|prise de sang|biologie)\b",
        },
        "RECEPTION": {
            "label": "Accueil",
            "regex": r"\b(accueil|reception|entree|guichet)\b",
        },
        "RADIOLOGY": {
            "label": "Radiologie",
            "regex": r"\b(radiologie|radio|scanner|irm|radiographie|imagerie)\b",
        },
    }

    TOPICS = {
        "MALARIA": {
            "label": "le paludisme",
            "regex": r"\b(paludisme|palu|malaria|moustiques?)\b",
        },
        "HIV": {
            "label": "le VIH / SIDA",
            "regex": r"\b(vih|sida|hiv)\b",
        },
        "DIABETES": {
            "label": "le diabète",
            "regex": r"\b(diabete|glycemie|sucre|insuline)\b",
        },
        "HYPERTENSION": {
            "label": "l'hypertension artérielle",
            "regex": r"\b(hypertension|tension arterielle|pression arterielle)\b",
        },
        "TUBERCULOSIS": {
            "label": "la tuberculose",
            "regex": r"\b(tuberculose|toux chronique)\b",
        },
        "MENSTRUAL_HEALTH": {
            "label": "la santé menstruelle",
            "regex": r"\b(sante menstruelle|menstruel|regles)\b",
        },
    }

    STOP_REGEX = r"\b(stop|arrete|arret|arrete-toi|arretez-vous|pause|bloque|urgence|danger|interromps|interrompre)\b"
    VITALS_REGEX = r"\b(constantes?|signes? vitaux|pouls|temperature|frequence cardiaque|oxymetre|oxymetrie|saturation|tensiometre)\b"
    CONSULTATION_REGEX = r"\b(rendez-vous|rdv|consultation|consulter|medecin|docteur|visite medicale|prendre rdv)\b"
    HOME_REGEX = r"\b(retour a l accueil|menu principal|accueil principal|quitter|fermer|retour accueil)\b"

    def parse(self, raw_text: str, confidence: float = 1.0) -> ParsedIntent:
        """Analyse le texte brut et renvoie une intention typée."""
        norm = normalize_text(raw_text)

        if not norm:
            return ParsedIntent(intent_type="UNKNOWN", confidence=0.0)

        # 1. ARRÊT D'URGENCE (Priorité absolue)
        if re.search(self.STOP_REGEX, norm):
            return ParsedIntent(
                intent_type="STOP",
                confidence=confidence,
                ros_command="STOP",
            )

        # 2. RETOUR ACCUEIL SPÉCIFIQUE
        if re.search(self.HOME_REGEX, norm):
            return ParsedIntent(
                intent_type="HOME",
                confidence=confidence,
                label="Accueil",
            )

        # 3. ORIENTATION VERS UN SERVICE
        for dest_key, info in self.DEPARTMENTS.items():
            if re.search(info["regex"], norm):
                return ParsedIntent(
                    intent_type="ORIENTATION",
                    confidence=confidence,
                    category="ORIENTATION",
                    target_field="destination",
                    target_value=dest_key,
                    label=info["label"],
                    ros_request={"category": "ORIENTATION", "destination": dest_key},
                )

        # 4. MESURE DES SIGNES VITAUX
        if re.search(self.VITALS_REGEX, norm):
            return ParsedIntent(
                intent_type="VITALS",
                confidence=confidence,
                category="CONSULTATION",
                target_field="action",
                target_value="VITAL_SIGNS",
                label="Signes vitaux",
                ros_request={"category": "CONSULTATION", "action": "VITAL_SIGNS"},
            )

        # 5. INFORMATION SANTE PUBLIQUE (Fiches OMS)
        for topic_key, info in self.TOPICS.items():
            if re.search(info["regex"], norm):
                return ParsedIntent(
                    intent_type="INFORMATION",
                    confidence=confidence,
                    category="INFORMATION",
                    target_field="topic",
                    target_value=topic_key,
                    label=info["label"],
                    ros_request={"category": "INFORMATION", "topic": topic_key},
                )

        # 6. CONSULTATION & RENDEZ-VOUS
        if re.search(self.CONSULTATION_REGEX, norm):
            return ParsedIntent(
                intent_type="CONSULTATION",
                confidence=confidence,
                category="CONSULTATION",
                target_field="action",
                target_value="APPOINTMENT",
                label="Consultation",
                ros_request={"category": "CONSULTATION", "action": "APPOINTMENT"},
            )

        # 7. INCONNU / NON ACTIONNABLE
        return ParsedIntent(
            intent_type="UNKNOWN",
            confidence=confidence,
            details={"original_text": raw_text},
        )

    def build_instruction(self, intent: ParsedIntent, raw_text: str = "") -> Dict:
        """Construit le payload conforme au topic 'server/instruction'.

        Règle d'or : aucune boîte de dialogue pop-up de confirmation ne doit
        s'ouvrir si l'action provient d'une commande vocale (require_confirmation: false).
        """
        if intent.intent_type == "STOP":
            return {
                "origin": "voice",
                "text_to_speak": "Arrêt du robot.",
                "speech_priority": "interrupt",
                "instruction_ui": {
                    "screen": "mission",
                    "action": "stop",
                    "require_confirmation": False,
                },
                "value_to_show": {
                    "field_id": "mission_state",
                    "value": "STOPPED",
                },
                "robot_status": {
                    "face_expression": "emergency",
                    "status_label": "ROBOT ARRÊTÉ",
                },
                "voice_hints": ["Reprendre", "Accueil"],
            }

        if intent.intent_type == "ORIENTATION":
            dest_label = intent.label or "votre destination"
            return {
                "origin": "voice",
                "text_to_speak": f"Très bien, suivez-moi vers {dest_label}.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "mission",
                    "destination": dest_label,
                    "require_confirmation": False,
                },
                "fields": {
                    "destination": dest_label,
                    "distance": "En calcul...",
                    "eta": "--",
                },
                "voice_hints": ["Stop", "Terminer"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": f"Guidage vers {dest_label}",
                },
            }

        if intent.intent_type == "VITALS":
            return {
                "origin": "voice",
                "text_to_speak": "Veuillez poser votre index sur le capteur de constantes et rester immobile.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "consultation",
                    "step": 4,
                    "require_confirmation": False,
                },
                "value_to_show": {
                    "field_id": "vitals_state",
                    "value": "measuring",
                },
                "fields": {
                    "temperature": "-- °C",
                    "heart_rate": "-- bpm",
                    "spo2": "-- %",
                },
                "voice_hints": ["Stop", "Annuler"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": "Mesure des signes vitaux",
                },
            }

        if intent.intent_type == "INFORMATION":
            topic_label = intent.label or "ce sujet"
            return {
                "origin": "voice",
                "text_to_speak": f"Voici les informations de prévention de l'Organisation Mondiale de la Santé concernant {topic_label}.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "information",
                    "topic": intent.target_value,
                    "require_confirmation": False,
                },
                "voice_hints": ["Accueil", "Retour"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": "Informations de santé",
                },
            }

        if intent.intent_type == "CONSULTATION":
            return {
                "origin": "voice",
                "text_to_speak": "Voici le module de consultation et de prise de rendez-vous.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "consultation",
                    "step": 1,
                    "require_confirmation": False,
                },
                "voice_hints": ["Suivant", "Annuler"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": "Consultation",
                },
            }

        if intent.intent_type == "HOME":
            return {
                "origin": "voice",
                "text_to_speak": "Retour à l'accueil.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "home",
                    "require_confirmation": False,
                },
                "voice_hints": ["Pharmacie", "Laboratoire", "Constantes", "Paludisme"],
                "robot_status": {
                    "face_expression": "neutral",
                    "status_label": "En attente",
                },
            }

        # UNKNOWN fallback
        return {
            "origin": "voice",
            "text_to_speak": "Je n'ai pas bien compris votre demande. Vous pouvez me demander la pharmacie, le laboratoire, mesurer vos constantes ou des informations de santé.",
            "speech_priority": "normal",
            "voice_hints": ["Pharmacie", "Laboratoire", "Constantes", "Paludisme"],
            "robot_status": {
                "face_expression": "neutral",
                "status_label": "En attente",
            },
        }
