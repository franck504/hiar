"""Tests unitaires pour le classificateur d'intentions vocales HIAR."""

import pytest
from hospital_robot.voice_intent_parser import VoiceIntentParser, normalize_text


@pytest.fixture
def parser():
    return VoiceIntentParser()


def test_normalize_text():
    assert normalize_text("  OÙ EST LA PHARMACIE ???  ") == "ou est la pharmacie"
    assert normalize_text("Arrête-toi tout de suite !") == "arrete-toi tout de suite"
    assert normalize_text("élève, infirmière & médecin") == "eleve infirmiere medecin"
    assert normalize_text("") == ""


# ============================================================
# TESTS D'ARRÊT D'URGENCE (Priorité absolue)
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Stop !",
    "Arrête",
    "Arrête-toi immédiatement",
    "Arrêt d'urgence",
    "Bloque le robot",
    "Danger arrête",
    "Interromps la mission",
    "Pause s'il te plaît",
])
def test_stop_intent_detected(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "STOP"
    assert intent.ros_command == "STOP"

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["speech_priority"] == "interrupt"
    assert instruction["instruction_ui"]["screen"] == "mission"
    assert instruction["instruction_ui"]["action"] == "stop"
    assert instruction["instruction_ui"]["require_confirmation"] is False
    assert instruction["value_to_show"]["value"] == "STOPPED"


# ============================================================
# TESTS DE REPRISE DE GUIDAGE (RESUME)
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Reprendre",
    "Reprends",
    "Repartir",
    "Repars",
    "En route",
    "Continuer le guidage",
    "Resume",
])
def test_resume_intent_detected(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "RESUME"
    assert intent.ros_command == "RESUME"

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["speech_priority"] == "normal"
    assert instruction["instruction_ui"]["screen"] == "mission"
    assert instruction["instruction_ui"]["action"] == "resume"
    assert instruction["value_to_show"]["value"] == "RUNNING"


# ============================================================
# TESTS DE FIN DE MISSION (FINISH)
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Terminer",
    "Termine",
    "Fin de mission",
    "Mission terminée",
    "C'est bon",
    "On est arrivé",
    "Dismiss",
])
def test_finish_intent_detected(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "FINISH"
    assert intent.ros_command == "HOME"

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["instruction_ui"]["screen"] == "home"


# ============================================================
# TESTS DE DÉMARRAGE (START)
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Commencer",
    "Commence",
    "Débuter",
    "Démarrer",
    "Start",
])
def test_start_intent_detected(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "START"

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["instruction_ui"]["screen"] == "home"


# ============================================================
# TESTS D'ORIENTATION (Services hospitaliers)
# ============================================================

@pytest.mark.parametrize("phrase,expected_dest", [
    ("Emmène-moi à la pharmacie", "PHARMACY"),
    ("Où sont les médicaments ?", "PHARMACY"),
    ("Je cherche la pharmacie centrale", "PHARMACY"),
    ("Où se trouve le laboratoire d'analyses ?", "LABORATORY"),
    ("Je dois faire une prise de sang au labo", "LABORATORY"),
    ("Direction le laboratoire", "LABORATORY"),
    ("Je cherche l'accueil", "RECEPTION"),
    ("Où est la réception ?", "RECEPTION"),
    ("Emmène-moi à l'entrée", "RECEPTION"),
    ("Où est la radiologie ?", "RADIOLOGY"),
    ("Je dois passer une radio", "RADIOLOGY"),
    ("Emmène-moi passer un scanner", "RADIOLOGY"),
])
def test_orientation_intents(parser, phrase, expected_dest):
    intent = parser.parse(phrase)
    assert intent.intent_type == "ORIENTATION"
    assert intent.category == "ORIENTATION"
    assert intent.target_value == expected_dest
    assert intent.ros_request == {"category": "ORIENTATION", "destination": expected_dest}

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["instruction_ui"]["screen"] == "mission"
    assert instruction["instruction_ui"]["require_confirmation"] is False
    assert instruction["speech_priority"] == "normal"
    assert len(instruction["text_to_speak"]) > 5


# ============================================================
# TESTS MESURE DES SIGNES VITAUX
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Prends ma température",
    "Je veux mesurer mes constantes",
    "Mesure mes signes vitaux",
    "Prends mon pouls",
    "Peux-tu mesurer ma fréquence cardiaque ?",
    "Oxymètre s'il te plaît",
    "Tensiomètre et température",
])
def test_vitals_intent(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "VITALS"
    assert intent.ros_request == {"category": "CONSULTATION", "action": "VITAL_SIGNS"}

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["instruction_ui"]["screen"] == "consultation"
    assert instruction["instruction_ui"]["step"] == 4
    assert instruction["instruction_ui"]["require_confirmation"] is False
    assert instruction["value_to_show"]["field_id"] == "vitals_state"
    assert instruction["value_to_show"]["value"] == "measuring"


# ============================================================
# TESTS FICHES SANTE PUBLIQUE OMS
# ============================================================

@pytest.mark.parametrize("phrase,expected_topic", [
    ("Parle-moi du paludisme", "MALARIA"),
    ("Qu'est-ce que le palu et les moustiques ?", "MALARIA"),
    ("Donne-moi des informations sur le VIH", "HIV"),
    ("Qu'est-ce que le sida ?", "HIV"),
    ("Informations sur le diabète et le sucre", "DIABETES"),
    ("Je veux en savoir plus sur l'hypertension artérielle", "HYPERTENSION"),
    ("Qu'est-ce que la tuberculose ?", "TUBERCULOSIS"),
    ("Parle-moi de la santé menstruelle", "MENSTRUAL_HEALTH"),
])
def test_information_leaflets(parser, phrase, expected_topic):
    intent = parser.parse(phrase)
    assert intent.intent_type == "INFORMATION"
    assert intent.target_value == expected_topic
    assert intent.ros_request == {"category": "INFORMATION", "topic": expected_topic}

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["instruction_ui"]["screen"] == "information"
    assert instruction["instruction_ui"]["topic"] == expected_topic
    assert instruction["instruction_ui"]["require_confirmation"] is False


# ============================================================
# TESTS CONSULTATION & RENDEZ-VOUS
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Je veux prendre un rendez-vous",
    "Je viens pour une consultation",
    "Je veux voir un médecin",
    "Prendre rdv avec un docteur",
])
def test_consultation_intent(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "CONSULTATION"
    assert intent.ros_request == {"category": "CONSULTATION", "action": "APPOINTMENT"}

    instruction = parser.build_instruction(intent, phrase)
    assert instruction["instruction_ui"]["screen"] == "consultation"
    assert instruction["instruction_ui"]["step"] == 1
    assert instruction["instruction_ui"]["require_confirmation"] is False


# ============================================================
# TESTS ACCUEIL & INCONNU (FALLBACK)
# ============================================================

def test_home_intent(parser):
    intent = parser.parse("Retour à l'accueil")
    assert intent.intent_type == "HOME"
    instruction = parser.build_instruction(intent)
    assert instruction["instruction_ui"]["screen"] == "home"
    assert instruction["instruction_ui"]["require_confirmation"] is False


def test_unknown_intent(parser):
    intent = parser.parse("Raconte-moi une blague sur les astronautes")
    assert intent.intent_type == "UNKNOWN"
    assert intent.ros_request is None
    assert intent.ros_command is None

    instruction = parser.build_instruction(intent)
    assert "Je n'ai pas bien compris" in instruction["text_to_speak"]
    assert "voice_hints" in instruction


# ============================================================
# TESTS POLITESSE & DIALOGUE NATUREL
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Bonjour",
    "Salut !",
    "Bonsoir",
    "Coucou",
])
def test_greeting_intent(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "GREETING"
    instruction = parser.build_instruction(intent)
    assert "Bonjour" in instruction["text_to_speak"]
    assert instruction["instruction_ui"]["screen"] == "home"


@pytest.mark.parametrize("phrase", [
    "Merci",
    "Merci beaucoup",
    "Parfait merci",
])
def test_thanks_intent(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "THANKS"
    instruction = parser.build_instruction(intent)
    assert "Je vous en prie" in instruction["text_to_speak"]


# ============================================================
# TESTS RENSEIGNEMENTS GÉNÉRAUX & MOTIFS DE CONSULTATION
# ============================================================

@pytest.mark.parametrize("phrase", [
    "Renseignements",
    "Rense",
    "Informations",
    "Fiches de santé",
])
def test_general_info_intent(parser, phrase):
    intent = parser.parse(phrase)
    assert intent.intent_type == "INFORMATION_GENERAL"
    instruction = parser.build_instruction(intent)
    assert instruction["instruction_ui"]["screen"] == "information"
    assert "fiches" in instruction["text_to_speak"].lower()


@pytest.mark.parametrize("phrase,expected_reason", [
    ("C'est plutôt suivi médical", "suivi_medical"),
    ("Suivi médical", "suivi_medical"),
    ("Consultation générale", "consultation_generale"),
])
def test_consultation_reason_intent(parser, phrase, expected_reason):
    intent = parser.parse(phrase)
    assert intent.intent_type == "CONSULTATION_REASON"
    assert intent.target_value == expected_reason
    instruction = parser.build_instruction(intent)
    assert instruction["fields"]["selected_reason"] == expected_reason
    assert "Motif sélectionné" in instruction["text_to_speak"]


@pytest.mark.parametrize("phrase,expected_action", [
    ("Étape suivante", "next"),
    ("Suivant", "next"),
    ("Continuer", "next"),
    ("Étape précédente", "prev"),
    ("Précédent", "prev"),
])
def test_consultation_step_navigation(parser, phrase, expected_action):
    intent = parser.parse(phrase)
    assert intent.intent_type == "CONSULTATION_STEP"
    assert intent.target_value == expected_action
    instruction = parser.build_instruction(intent)
    assert instruction["instruction_ui"]["action"] == expected_action


def test_consultation_ticket_intent(parser):
    intent = parser.parse("Quel est mon ticket ?")
    assert intent.intent_type == "CONSULTATION_TICKET"
    instruction = parser.build_instruction(intent)
    assert instruction["instruction_ui"]["screen"] == "consultation"
    assert instruction["instruction_ui"]["step"] == 6
    assert instruction["fields"]["ticket_label"] == "A-MAT-3"


def test_ignored_fragments_do_not_trigger_tts(parser):
    for frag in ["je", "le", "de", "un", "a"]:
        intent = parser.parse(frag)
        assert intent.intent_type == "IGNORED_FRAGMENT"
        instruction = parser.build_instruction(intent)
        assert instruction == {}


def test_empty_input(parser):
    intent = parser.parse("   ")
    assert intent.intent_type == "UNKNOWN"
