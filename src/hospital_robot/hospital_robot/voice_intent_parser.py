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
    intent_type: str
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

    GREETING_REGEX = r"\b(bonjour|salut|bonsoir|coucou|hello|hey|allo)\b"
    THANKS_REGEX = r"\b(merci|merci beaucoup|remercie|parfait merci|super merci)\b"
    INFO_GENERAL_REGEX = r"\b(renseignements?|rense|informations?|fiches? de sante|conseils? sante|fiches? oms|prevention)\b"

    CONSULT_REASON_SUIVI = r"\b(suivi medical|suivi|controle)\b"
    CONSULT_REASON_GENERALE = r"\b(consultation generale|generale|standard)\b"
    CONSULT_STEP_NEXT = r"\b(etape suivante|suivant|suivante|continuer|valider|confirmer)\b"
    CONSULT_STEP_PREV = r"\b(etape precedente|precedent|precedente|reculer)\b"
    CONSULT_TICKET = r"\b(ticket|mon ticket|voir le ticket|billet)\b"

    STOPWORDS_FRAGMENTS = {
        "je", "tu", "il", "elle", "on", "nous", "vous", "ils",
        "le", "la", "les", "de", "des", "du", "un", "une",
        "et", "ou", "a", "au", "en", "ce", "ces", "c"
    }

    def parse(self, raw_text: str, confidence: float = 1.0) -> ParsedIntent:
        """Analyse le texte brut et renvoie une intention typée."""
        norm = normalize_text(raw_text)

        if not norm:
            return ParsedIntent(intent_type="UNKNOWN", confidence=0.0)

        # 0. FRAGMENTS ISOLÉS / PAUSES DE PAROLE (ignorer silencieusement)
        if norm in self.STOPWORDS_FRAGMENTS or len(norm) <= 2:
            return ParsedIntent(
                intent_type="IGNORED_FRAGMENT",
                confidence=confidence,
                details={"fragment": norm},
            )

        # 1. ARRÊT D'URGENCE (Priorité absolue)
        if re.search(self.STOP_REGEX, norm):
            return ParsedIntent(
                intent_type="STOP",
                confidence=confidence,
                ros_command="STOP",
            )

        # 2. POLITESSE : MERCI
        if re.search(self.THANKS_REGEX, norm):
            return ParsedIntent(
                intent_type="THANKS",
                confidence=confidence,
                label="Remerciement",
            )

        # 3. POLITESSE : BONJOUR
        if re.search(self.GREETING_REGEX, norm):
            return ParsedIntent(
                intent_type="GREETING",
                confidence=confidence,
                label="Salutation",
            )

        # 4. RETOUR ACCUEIL
        if re.search(self.HOME_REGEX, norm):
            return ParsedIntent(
                intent_type="HOME",
                confidence=confidence,
                label="Accueil",
            )

        # 5. ORIENTATION VERS UN SERVICE
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

        # 6. MESURE DES SIGNES VITAUX
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

        # 7. INFORMATION SANTE PUBLIQUE SPÉCIFIQUE (Fiches OMS)
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

        # 8. RENSEIGNEMENTS / INFORMATIONS GÉNÉRALES
        if re.search(self.INFO_GENERAL_REGEX, norm):
            return ParsedIntent(
                intent_type="INFORMATION_GENERAL",
                confidence=confidence,
                category="INFORMATION",
                label="Fiches de santé",
                ros_request={"category": "INFORMATION", "topic": "MALARIA"},
            )

        # 9. TICKET DE CONSULTATION
        if re.search(self.CONSULT_TICKET, norm):
            return ParsedIntent(
                intent_type="CONSULTATION_TICKET",
                confidence=confidence,
                label="Ticket",
            )

        # 10. SAISIE VOCALE DU MOTIF DE CONSULTATION
        if re.search(self.CONSULT_REASON_SUIVI, norm):
            return ParsedIntent(
                intent_type="CONSULTATION_REASON",
                confidence=confidence,
                target_value="suivi_medical",
                label="Suivi médical",
            )
        if re.search(self.CONSULT_REASON_GENERALE, norm):
            return ParsedIntent(
                intent_type="CONSULTATION_REASON",
                confidence=confidence,
                target_value="consultation_generale",
                label="Consultation générale",
            )

        # 11. NAVIGATION DANS LES ÉTAPES DE CONSULTATION
        if re.search(self.CONSULT_STEP_NEXT, norm):
            return ParsedIntent(
                intent_type="CONSULTATION_STEP",
                confidence=confidence,
                target_value="next",
                label="Suivant",
            )
        if re.search(self.CONSULT_STEP_PREV, norm):
            return ParsedIntent(
                intent_type="CONSULTATION_STEP",
                confidence=confidence,
                target_value="prev",
                label="Précédent",
            )

        # 12. OUVERTURE DE CONSULTATION & RENDEZ-VOUS
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

        # 13. INCONNU / NON ACTIONNABLE
        return ParsedIntent(
            intent_type="UNKNOWN",
            confidence=confidence,
            details={"original_text": raw_text},
        )

    def build_instruction(self, intent: ParsedIntent, raw_text: str = "") -> Dict:
        """Construit le payload conforme au topic 'server/instruction'."""
        if intent.intent_type == "IGNORED_FRAGMENT":
            return {}

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

        if intent.intent_type == "GREETING":
            return {
                "origin": "voice",
                "text_to_speak": "Bonjour ! Je suis le robot hospitalier HIAR. Que puis-je faire pour vous ?",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "home",
                    "require_confirmation": False,
                },
                "voice_hints": ["Pharmacie", "Laboratoire", "Consultation", "Constantes"],
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "Bonjour !",
                },
            }

        if intent.intent_type == "THANKS":
            return {
                "origin": "voice",
                "text_to_speak": "Je vous en prie ! N'hésitez pas si vous avez une autre question.",
                "speech_priority": "normal",
                "voice_hints": ["Accueil", "Pharmacie", "Consultation"],
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "Avec plaisir",
                },
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

        if intent.intent_type == "INFORMATION_GENERAL":
            return {
                "origin": "voice",
                "text_to_speak": "Voici les fiches d'information et de prévention de l'Organisation Mondiale de la Santé.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "information",
                    "require_confirmation": False,
                },
                "voice_hints": ["Paludisme", "Diabète", "VIH", "Hypertension"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": "Fiches de santé OMS",
                },
            }

        if intent.intent_type == "CONSULTATION_REASON":
            reason_label = intent.label or "Consultation"
            return {
                "origin": "voice",
                "text_to_speak": f"Motif sélectionné : {reason_label}.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "consultation",
                    "step": 1,
                    "require_confirmation": False,
                },
                "fields": {
                    "selected_reason": intent.target_value,
                },
                "voice_hints": ["Suivant", "Médecin A", "Médecin B"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": reason_label,
                },
            }

        if intent.intent_type == "CONSULTATION_STEP":
            action = intent.target_value or "next"
            speech = "Étape suivante." if action == "next" else "Étape précédente."
            return {
                "origin": "voice",
                "text_to_speak": speech,
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "consultation",
                    "action": action,
                    "require_confirmation": False,
                },
                "voice_hints": ["Suivant", "Précédent", "Annuler"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": speech,
                },
            }

        if intent.intent_type == "CONSULTATION_TICKET":
            return {
                "origin": "voice",
                "text_to_speak": "Votre rendez-vous est confirmé. Voici votre ticket de passage numéro A-MAT-3.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "consultation",
                    "step": 6,
                    "require_confirmation": False,
                },
                "fields": {
                    "ticket_label": "A-MAT-3",
                },
                "voice_hints": ["Terminer", "Accueil"],
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "Ticket A-MAT-3",
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
