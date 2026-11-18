"""Analyseur et classificateur d'intentions vocales en français pour HIAR.

Transforme le texte transcrit par le smartphone (voice/stt/final)
en actions normalisées pour ROS 2 et en instructions UI/TTS pour le mobile.
"""

from dataclasses import dataclass, field
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hospital_robot.voice_intent_parser")

try:
    from hospital_robot.llm_intent_engine import LLMConfig, LLMIntentEngine, LLMResponse
except ImportError:
    try:
        from llm_intent_engine import LLMConfig, LLMIntentEngine, LLMResponse
    except ImportError:
        LLMConfig = None  # type: ignore
        LLMIntentEngine = None  # type: ignore
        LLMResponse = None  # type: ignore


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
    RESUME_REGEX = r"\b(reprendre|reprends|repartir|repars|reprise|en route|recommencer|recommence|continuer le guidage|poursuivre le guidage|resume)\b"
    FINISH_REGEX = r"\b(terminer|termine|fin de mission|mission terminee|c'est bon|c est bon|on est arrive|on est arrives|dismiss)\b"
    START_REGEX = r"\b(commencer|commence|debuter|debute|demarrer|demarre|start)\b"
    CONFIRM_YES_REGEX = r"\b(oui|ouais|d'accord|d accord|d'ac|dac|confirmer|confirme|c'est ca|c est ca|exactement|allons[- ]y|vas[- ]y|ok|yes|absolument|volontiers|je veux bien)\b"
    CONFIRM_NO_REGEX = r"\b(non|nan|pas du tout|annuler|annule|non merci|pas maintenant|laisse tomber|laisser tomber|refuser|refuse|plus tard|pas la peine)\b"
    VITALS_REGEX = r"\b(constantes?|signes? vitaux|pouls|temperature|frequence cardiaque|oxymetre|oxymetrie|saturation|tensiometre|mesurer|demarrer la mesure|prise de mesure)\b"
    CONSULTATION_REGEX = r"\b(rendez-vous|rdv|consultation|consulter|medecin|docteur|visite medicale|prendre rdv)\b"
    HOME_REGEX = r"\b(retour.*accueil|page d'accueil|ecran d'accueil|aller.*accueil|revenir.*accueil|retour au menu|menu principal|ecran principal|revenir au debut|accueil principal|quitter|fermer|retour accueil)\b|^accueil$|^menu$|^retour$"

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

    INCOMPLETE_PREFIXES_REGEX = (
        r"^(je veux( aller)?( au| a| vers)?|"
        r"aller( au| a| vers)?|"
        r"emmene[- ]moi( a| au| vers)?|"
        r"direction( la| le)?|"
        r"ou est( le| la| les)?|"
        r"c'?etait|"
        r"elle est( au| a)?|"
        r"il y a des?)$"
    )

    def __init__(
        self,
        enable_llm: bool = True,
        llm_config: Optional[Any] = None,
        llm_engine: Optional[Any] = None,
        enable_deterministic_fallback: bool = True,
    ):
        """Initialise le parseur d'intentions avec support optionnel d'un LLM."""
        self.enable_llm = enable_llm
        self.enable_deterministic_fallback = enable_deterministic_fallback
        if llm_engine is not None:
            self.llm_engine = llm_engine
        elif enable_llm and LLMIntentEngine is not None:
            self.llm_engine = LLMIntentEngine(config=llm_config)
        else:
            self.llm_engine = None

    def parse(
        self,
        raw_text: str,
        confidence: float = 1.0,
        use_llm: bool = True,
        current_screen: str = "",
    ) -> ParsedIntent:
        """Analyse le texte brut selon l'architecture à 5 niveaux :
          1. Réflexe de sécurité local (STOP) — < 1 ms, jamais réseau
          2. Cache LRU local — < 1 ms, zéro quota
          3. Gemini API primaire (rotation de clés)
          4. Qwen 2.5 local (fallback automatique)
          5. Parseur déterministe (filet de sécurité final)
        """
        norm = normalize_text(raw_text)

        if not norm:
            return ParsedIntent(intent_type="UNKNOWN", confidence=0.0)

        # 0. FRAGMENTS ISOLÉS / PAUSES DE PAROLE (ignorer silencieusement)
        if (
            norm in self.STOPWORDS_FRAGMENTS
            or len(norm) <= 2
            or re.match(self.INCOMPLETE_PREFIXES_REGEX, norm)
        ):
            return ParsedIntent(
                intent_type="IGNORED_FRAGMENT",
                confidence=confidence,
                details={"fragment": norm},
            )

        # 1. ARRÊT D'URGENCE — RÉFLEXE LOCAL ABSOLU (< 1 ms, jamais de réseau/LLM)
        if re.search(self.STOP_REGEX, norm):
            return ParsedIntent(
                intent_type="STOP",
                confidence=confidence,
                ros_command="STOP",
            )

        # 2-4. TRAITEMENT LLM (Gemini solo si cache/Qwen désactivés, sinon hybride)
        llm_attempted = False
        llm_latency_ms = 0.0
        llm_backend_used = ""
        llm_error: Optional[str] = None
        if use_llm and self.enable_llm and self.llm_engine:
            if self.llm_engine.is_available():
                llm_attempted = True
                try:
                    llm_res = self.llm_engine.infer(raw_text, current_screen=current_screen)
                    llm_latency_ms = getattr(llm_res, "latency_ms", 0.0) if llm_res else 0.0
                    llm_backend_used = getattr(llm_res, "backend_used", "") if llm_res else ""
                    llm_error = getattr(llm_res, "error", None) if llm_res else None
                    if llm_res and llm_res.success:
                        intent = self._convert_llm_response(llm_res, confidence, raw_text)
                        if intent is not None:
                            return intent
                        # En mode Gemini solo, conserver la réponse vocale de Gemini même sur UNKNOWN
                        if not self.enable_deterministic_fallback and llm_res.text_to_speak:
                            return ParsedIntent(
                                intent_type="UNKNOWN",
                                confidence=confidence,
                                details={
                                    "llm_text_to_speak": llm_res.text_to_speak,
                                    "llm_generated": True,
                                    "cache_hit": bool(getattr(llm_res, "cache_hit", False)),
                                    "backend_used": llm_backend_used,
                                    "original_text": raw_text,
                                    "latency_ms": llm_latency_ms,
                                    "model": self._active_model_label(llm_backend_used),
                                },
                            )
                except Exception as e:
                    llm_error = str(e)
                    logger.warning(f"Error during LLM inference: {e}")
            elif not self.enable_deterministic_fallback:
                llm_attempted = True
                llm_error = "Gemini indisponible (aucune clé active ou toutes en pause)"

        # 5. FILET DE SÉCURITÉ DÉTERMINISTE (uniquement si activé)
        if self.enable_deterministic_fallback:
            det_intent = self._parse_deterministic(norm, confidence)
            if det_intent is not None:
                if llm_attempted:
                    det_intent.details["deterministic_fallback"] = True
                    det_intent.details["llm_attempted"] = True
                    det_intent.details["latency_ms"] = llm_latency_ms
                    det_intent.details["backend_used"] = llm_backend_used
                return det_intent

        # 6. INCONNU / NON ACTIONNABLE DÉFINITIF
        details: Dict[str, Any] = {"original_text": raw_text}
        if llm_attempted:
            details["llm_attempted"] = True
            details["latency_ms"] = llm_latency_ms
            details["backend_used"] = llm_backend_used
            details["model"] = self._active_model_label(llm_backend_used)
            if llm_error:
                details["llm_error"] = llm_error
                if not self.enable_deterministic_fallback:
                    details["llm_text_to_speak"] = (
                        "Le service Gemini est momentanément indisponible. Veuillez réessayer."
                    )
        return ParsedIntent(
            intent_type="UNKNOWN",
            confidence=confidence,
            details=details,
        )

    def _parse_deterministic(self, norm: str, confidence: float) -> Optional[ParsedIntent]:
        """Parseur déterministe par mots-clés (filet de sécurité final / mode hors LLM)."""
        # REPRENDRE LE GUIDAGE
        if re.search(self.RESUME_REGEX, norm):
            return ParsedIntent(
                intent_type="RESUME",
                confidence=confidence,
                label="Reprendre",
                ros_command="RESUME",
            )

        # TERMINER LA MISSION OU RETOUR ACCUEIL
        if re.search(self.FINISH_REGEX, norm):
            return ParsedIntent(
                intent_type="FINISH",
                confidence=confidence,
                label="Terminer",
                ros_command="HOME",
            )

        # COMMENCER (Depuis l'écran de veille)
        if re.search(self.START_REGEX, norm):
            return ParsedIntent(
                intent_type="START",
                confidence=confidence,
                label="Commencer",
            )

        # CONFIRMATION VOCALE (OUI / NON)
        if re.search(self.CONFIRM_YES_REGEX, norm):
            return ParsedIntent(
                intent_type="CONFIRM_YES",
                confidence=confidence,
                label="Confirmer",
            )
        if re.search(self.CONFIRM_NO_REGEX, norm):
            return ParsedIntent(
                intent_type="CONFIRM_NO",
                confidence=confidence,
                label="Annuler",
            )

        # POLITESSE : MERCI
        if re.search(self.THANKS_REGEX, norm):
            return ParsedIntent(
                intent_type="THANKS",
                confidence=confidence,
                label="Remerciement",
            )

        # POLITESSE : BONJOUR
        if re.search(self.GREETING_REGEX, norm):
            return ParsedIntent(
                intent_type="GREETING",
                confidence=confidence,
                label="Salutation",
            )

        # RETOUR ACCUEIL
        if re.search(self.HOME_REGEX, norm):
            return ParsedIntent(
                intent_type="HOME",
                confidence=confidence,
                label="Accueil",
            )

        # ORIENTATION VERS UN SERVICE
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

        # MESURE DES SIGNES VITAUX
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

        # INFORMATION SANTE PUBLIQUE SPÉCIFIQUE (Fiches OMS)
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

        # RENSEIGNEMENTS / INFORMATIONS GÉNÉRALES
        if re.search(self.INFO_GENERAL_REGEX, norm):
            return ParsedIntent(
                intent_type="INFORMATION_GENERAL",
                confidence=confidence,
                category="INFORMATION",
                label="Fiches de santé",
                ros_request={"category": "INFORMATION", "topic": "MALARIA"},
            )

        # TICKET DE CONSULTATION
        if re.search(self.CONSULT_TICKET, norm):
            return ParsedIntent(
                intent_type="CONSULTATION_TICKET",
                confidence=confidence,
                label="Ticket",
            )

        # SAISIE VOCALE DU MOTIF DE CONSULTATION
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

        # NAVIGATION DANS LES ÉTAPES DE CONSULTATION
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

        # OUVERTURE DE CONSULTATION & RENDEZ-VOUS
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

        return None

    def _active_model_label(self, backend_used: str = "") -> str:
        if not self.llm_engine:
            return "qwen2.5:0.5b"
        cfg = self.llm_engine.config
        if backend_used.startswith("gemini"):
            return getattr(cfg, "gemini_model", "gemini-3.5-flash-lite")
        if backend_used == "cache":
            return "cache-lru"
        return getattr(cfg, "model_name", "qwen2.5:0.5b")

    def _convert_llm_response(
        self,
        res: Any,
        confidence: float,
        raw_text: str,
    ) -> Optional[ParsedIntent]:
        """Convertit un LLMResponse en ParsedIntent compatible ROS 2."""
        target = res.target
        intent_type = res.intent
        backend_used = getattr(res, "backend_used", "")
        cache_hit = bool(getattr(res, "cache_hit", False))
        model_name = self._active_model_label(backend_used)
        latency_ms = getattr(res, "latency_ms", 0.0)

        def _make_details(extra_screen: Optional[str] = None):
            return {
                "llm_text_to_speak": res.text_to_speak,
                "llm_generated": True,
                "cache_hit": cache_hit,
                "backend_used": backend_used,
                "screen": res.screen or extra_screen,
                "original_text": raw_text,
                "latency_ms": latency_ms,
                "model": model_name,
            }

        if self.enable_deterministic_fallback:
            norm = normalize_text(raw_text)
            if any(w in norm for w in ["qui es-tu", "tu es qui", "qui etes-vous", "vous etes qui", "presente-toi", "ton nom"]):
                return ParsedIntent(
                    intent_type="GREETING",
                    confidence=confidence,
                    label="Bonjour",
                    details=_make_details("home"),
                )

        if intent_type == "CONFIRM_YES":
            return ParsedIntent(
                intent_type="CONFIRM_YES",
                confidence=confidence,
                label="Confirmer",
                details=_make_details(),
            )

        if intent_type == "CONFIRM_NO":
            return ParsedIntent(
                intent_type="CONFIRM_NO",
                confidence=confidence,
                label="Annuler",
                details=_make_details("home"),
            )

        if intent_type == "RESUME":
            return ParsedIntent(
                intent_type="RESUME",
                confidence=confidence,
                label="Reprendre",
                ros_command="RESUME",
                details=_make_details("mission"),
            )

        if intent_type == "FINISH":
            return ParsedIntent(
                intent_type="FINISH",
                confidence=confidence,
                label="Terminer",
                ros_command="HOME",
                details=_make_details("home"),
            )

        if intent_type == "START":
            return ParsedIntent(
                intent_type="START",
                confidence=confidence,
                label="Commencer",
                details=_make_details("home"),
            )

        if intent_type == "THANKS":
            return ParsedIntent(
                intent_type="THANKS",
                confidence=confidence,
                label="Remerciement",
                details=_make_details(),
            )

        if (target and target in self.DEPARTMENTS) or intent_type == "ORIENTATION":
            dest_key = target if (target and target in self.DEPARTMENTS) else "PHARMACY"
            label = self.DEPARTMENTS.get(dest_key, {}).get("label", dest_key)
            return ParsedIntent(
                intent_type="ORIENTATION",
                confidence=confidence,
                category="ORIENTATION",
                target_field="destination",
                target_value=dest_key,
                label=label,
                ros_request={"category": "ORIENTATION", "destination": dest_key},
                details=_make_details("mission"),
            )

        if (target and target in self.TOPICS) or intent_type == "INFORMATION":
            topic_key = target if (target and target in self.TOPICS) else "MALARIA"
            label = self.TOPICS.get(topic_key, {}).get("label", topic_key)
            return ParsedIntent(
                intent_type="INFORMATION",
                confidence=confidence,
                category="INFORMATION",
                target_field="topic",
                target_value=topic_key,
                label=label,
                ros_request={"category": "INFORMATION", "topic": topic_key},
                details=_make_details("information"),
            )

        if intent_type == "INFORMATION_GENERAL":
            return ParsedIntent(
                intent_type="INFORMATION_GENERAL",
                confidence=confidence,
                category="INFORMATION",
                label="Fiches de santé",
                ros_request={"category": "INFORMATION", "topic": "MALARIA"},
                details=_make_details("information"),
            )

        if intent_type == "VITALS":
            return ParsedIntent(
                intent_type="VITALS",
                confidence=confidence,
                category="CONSULTATION",
                target_field="action",
                target_value="VITAL_SIGNS",
                label="Signes vitaux",
                ros_request={"category": "CONSULTATION", "action": "VITAL_SIGNS"},
                details=_make_details("consultation"),
            )

        if intent_type == "CONSULTATION":
            return ParsedIntent(
                intent_type="CONSULTATION",
                confidence=confidence,
                category="CONSULTATION",
                target_field="action",
                target_value="APPOINTMENT",
                label="Consultation",
                ros_request={"category": "CONSULTATION", "action": "APPOINTMENT"},
                details=_make_details("consultation"),
            )

        if intent_type == "CONSULTATION_REASON":
            is_suivi = (target or "").upper() in ("SUIVI_MEDICAL", "SUIVI")
            return ParsedIntent(
                intent_type="CONSULTATION_REASON",
                confidence=confidence,
                target_value="suivi_medical" if is_suivi else "consultation_generale",
                label="Suivi médical" if is_suivi else "Consultation générale",
                details=_make_details("consultation"),
            )

        if intent_type == "CONSULTATION_STEP":
            is_prev = (target or "").upper() in ("PREV", "PREVIOUS", "PRECEDENT")
            return ParsedIntent(
                intent_type="CONSULTATION_STEP",
                confidence=confidence,
                target_value="prev" if is_prev else "next",
                label="Précédent" if is_prev else "Suivant",
                details=_make_details("consultation"),
            )

        if intent_type == "CONSULTATION_TICKET":
            return ParsedIntent(
                intent_type="CONSULTATION_TICKET",
                confidence=confidence,
                label="Ticket",
                details=_make_details("consultation"),
            )

        if intent_type == "GREETING":
            return ParsedIntent(
                intent_type="GREETING",
                confidence=confidence,
                label="Bonjour",
                details=_make_details("home"),
            )

        if intent_type == "HOME":
            return ParsedIntent(
                intent_type="HOME",
                confidence=confidence,
                label="Accueil",
                details=_make_details("home"),
            )

        return None

    def build_instruction(self, intent: ParsedIntent, raw_text: str = "") -> Dict:
        """Construit le payload conforme au topic 'server/instruction'."""
        if intent.intent_type == "IGNORED_FRAGMENT":
            return {}

        if intent.intent_type == "STOP":
            return {
                "origin": "voice",
                "text_to_speak": "Arrêt du robot. Vous pouvez reprendre ou terminer le guidage.",
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
                "voice_hints": ["Reprendre", "Terminer", "Accueil"],
            }

        if intent.intent_type == "RESUME":
            return {
                "origin": "voice",
                "text_to_speak": "Reprise du guidage. Suivez-moi.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "mission",
                    "action": "resume",
                    "require_confirmation": False,
                },
                "value_to_show": {
                    "field_id": "mission_state",
                    "value": "RUNNING",
                },
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "En route",
                },
                "voice_hints": ["Stop", "Terminer"],
            }

        if intent.intent_type == "FINISH":
            return {
                "origin": "voice",
                "text_to_speak": "Mission terminée. N'hésitez pas si vous avez besoin d'autre chose.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "home",
                    "require_confirmation": False,
                },
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "Robot prêt",
                },
                "voice_hints": ["Orientation", "Renseignements", "Consultation"],
            }

        if intent.intent_type == "START":
            return {
                "origin": "voice",
                "text_to_speak": "Bonjour ! Choisissez un service ou dites-moi ce que vous souhaitez.",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "home",
                    "require_confirmation": False,
                },
                "voice_hints": ["Pharmacie", "Laboratoire", "Consultation", "Constantes"],
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "Robot prêt",
                },
            }

        if intent.intent_type == "GREETING":
            speech = intent.details.get("llm_text_to_speak")
            if not speech or any(w in speech.lower() for w in ["pas compris", "comprends pas", "pas votre", "préciser"]):
                speech = "Bonjour ! Je suis le robot hospitalier HIAR. Que puis-je faire pour vous ?"
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
            speech = intent.details.get("llm_text_to_speak") or "Je vous en prie ! N'hésitez pas si vous avez une autre question."
            return {
                "origin": "voice",
                "text_to_speak": speech,
                "speech_priority": "normal",
                "voice_hints": ["Accueil", "Pharmacie", "Consultation"],
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "Avec plaisir",
                },
            }

        if intent.intent_type == "ORIENTATION":
            dest_label = intent.label or "votre destination"
            dest_key = intent.target_value or "PHARMACY"
            speech = f"Voulez-vous que je vous guide vers {dest_label} ?"
            return {
                "origin": "voice",
                "text_to_speak": speech,
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "orientation",
                    "destination": dest_label,
                    "target": dest_key,
                    "require_confirmation": True,
                },
                "fields": {
                    "destination": dest_label,
                    "target": dest_key,
                    "pending_destination": dest_key,
                    "confirmation_required": True,
                },
                "voice_hints": ["Oui", "Non", "Confirmer", "Annuler"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": f"Confirmer {dest_label} ?",
                },
            }

        if intent.intent_type == "CONFIRM_YES":
            dest_label = intent.label if (intent.label and intent.label != "Confirmer") else ""
            speech = f"Très bien, suivez-moi vers {dest_label}." if dest_label else "Très bien, suivez-moi."
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
                    "status_label": f"Guidage vers {dest_label}" if dest_label else "Guidage en cours",
                },
            }

        if intent.intent_type == "CONFIRM_NO":
            return {
                "origin": "voice",
                "text_to_speak": "D'accord, guidage annulé. Que puis-je faire pour vous ?",
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "home",
                    "require_confirmation": False,
                },
                "robot_status": {
                    "face_expression": "happy",
                    "status_label": "Robot prêt",
                },
                "voice_hints": ["Orientation", "Renseignements", "Consultation"],
            }

        if intent.intent_type == "VITALS":
            speech = intent.details.get("llm_text_to_speak") or "Veuillez poser votre index sur le capteur de constantes et rester immobile."
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
            speech = intent.details.get("llm_text_to_speak") or f"Voici les informations de prévention de l'Organisation Mondiale de la Santé concernant {topic_label}."
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
            speech = intent.details.get("llm_text_to_speak") or "Voici les fiches d'information et de prévention de l'Organisation Mondiale de la Santé."
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
            speech = intent.details.get("llm_text_to_speak") or f"Motif sélectionné : {reason_label}."
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
            speech = intent.details.get("llm_text_to_speak") or "Voici le module de consultation et de prise de rendez-vous."
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
            speech = intent.details.get("llm_text_to_speak") or "Retour à l'accueil."
            return {
                "origin": "voice",
                "text_to_speak": speech,
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
        speech = intent.details.get("llm_text_to_speak") or "Je n'ai pas bien compris votre demande. Vous pouvez me demander la pharmacie, le laboratoire, mesurer vos constantes ou des informations de santé."
        return {
            "origin": "voice",
            "text_to_speak": speech,
            "speech_priority": "normal",
            "voice_hints": ["Pharmacie", "Laboratoire", "Constantes", "Paludisme"],
            "robot_status": {
                "face_expression": "neutral",
                "status_label": "En attente",
            },
        }
