"""Scénarios vocaux complets de la consultation, joués sur le vrai pont (LLM scripté, base temporaire)."""

import asyncio
import json
import logging
import re
import sqlite3

import pytest

from hospital_robot.hmi_websocket_bridge_node import HMIWebSocketBridgeNode
from hospital_robot.llm_intent_engine import MockBackend
from hospital_robot import consultation_catalog as cat

from appointments_store import get_db_path, init_sessions_db


def llm(intent, target=None, say="", screen=None):
    return {"intent": intent, "target": target, "text_to_speak": say, "screen": screen}


class ScriptedLLM(MockBackend):
    """LLM simulé : renvoie la réponse du premier motif trouvé dans la phrase, sinon UNKNOWN muet."""

    def __init__(self, script):
        super().__init__()
        self.script = script
        self.calls = []
        self._last_backend = "groq_key#1"

    def generate(self, prompt, config):
        self.calls.append(prompt)
        # le prompt est « [Écran actuel: …] phrase » : on ne lit que la phrase (le contexte cite « le matin »…)
        n = cat.norm(prompt.rsplit("] ", 1)[-1])
        for key, response in self.script.items():
            if re.search(r"\b" + re.escape(cat.norm(key)) + r"\b", n):  # mots entiers (« gazouillis » ≠ « oui »)
                return json.dumps(response)
        return json.dumps(llm("UNKNOWN"))


SCRIPT = {
    "voir un medecin": llm("CONSULTATION", None, "Voici la consultation.", "consultation"),
    "rendez-vous": llm("CONSULTATION", None, "Voici la consultation.", "consultation"),
    "suivi medical": llm("CONSULTATION_REASON", "SUIVI_MEDICAL", "", "consultation"),
    "consultation generale": llm("CONSULTATION_REASON", "CONSULTATION_GENERALE", "", "consultation"),
    "autre motif": llm("CONSULTATION_REASON", "AUTRE_MOTIF", "", "consultation"),
    "docteur bell": llm("CONSULTATION_DOCTOR", "BELL", "", "consultation"),
    "docteur raissa": llm("CONSULTATION_DOCTOR", "RAISSA", "", "consultation"),
    "docteur alice": llm("CONSULTATION_DOCTOR", "ALICE", "", "consultation"),
    "docteur martin": llm("CONSULTATION_DOCTOR", None, "Je n'ai pas reconnu ce médecin.", "consultation"),
    "le matin": llm("CONSULTATION_PERIOD", "MORNING", "", "consultation"),
    "suivant": llm("CONSULTATION_STEP", "NEXT", "", "consultation"),
    "passer": llm("CONSULTATION_STEP", "NEXT", "", "consultation"),
    "precedent": llm("CONSULTATION_STEP", "PREV", "", "consultation"),
    "oui": llm("CONFIRM_YES", None, "", "consultation"),
    "confirmer": llm("CONFIRM_YES", None, "", "consultation"),
    "non": llm("CONFIRM_NO", None, "", "home"),
    "annuler": llm("CONFIRM_NO", None, "", "home"),
    "terminer": llm("FINISH", None, "", "home"),
}


class Harness:
    def __init__(self, node, backend):
        self.node, self.backend, self.sent = node, backend, []

    async def say(self, text):
        self.sent.clear()
        self.node._last_stt_text = ""  # neutralise l'anti-rebond de 2,5 s entre deux phrases de test
        await self.node._handle_voice_stt({"text": text, "confidence": 0.95})
        return self.last()

    async def ui(self, action_id, **args):
        self.sent.clear()
        await self.node._handle_ui_action({"action_id": action_id, "args": args})
        return self.last()

    async def state(self, screen, step=None, consultation_data=None):
        payload = {"screen": screen, "step": step}
        if consultation_data is not None:
            payload["consultation_data"] = consultation_data
        await self.node._process_incoming_frame(
            None, json.dumps({"v": 1, "type": "pub", "topic": "ui/state", "payload": payload})
        )

    def last(self):
        instructions = [p for topic, p in self.sent if topic == "server/instruction"]
        return instructions[-1] if instructions else None

    def speech(self):
        last = self.last()
        return (last or {}).get("text_to_speak", "")

    def ui_step(self):
        return ((self.last() or {}).get("instruction_ui") or {}).get("step")

    @property
    def data(self):
        return self.node._current_consultation_data

    def rows(self):
        con = sqlite3.connect(str(get_db_path()))
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute("SELECT * FROM appointments ORDER BY id")]
        finally:
            con.close()


@pytest.fixture
def h():
    init_sessions_db()
    node = HMIWebSocketBridgeNode(host="127.0.0.1", port=0)
    backend = ScriptedLLM(SCRIPT)
    engine = node.intent_parser.llm_engine
    engine._backend = backend
    engine.config.cache_enabled = False
    node._auth_required = False
    harness = Harness(node, backend)

    async def record(topic, payload):
        harness.sent.append((topic, payload))

    node.broadcast = record
    return harness


def run(coro):
    return asyncio.run(coro)


# ======================================================================================
# Parcours complet à la voix
# ======================================================================================

def test_full_booking_by_voice_only(h):
    async def scenario():
        # accueil -> consultation
        await h.say("je voudrais voir un médecin")
        assert h.ui_step() == 1 and "motif" in h.speech().lower()

        await h.say("suivi médical")
        assert h.ui_step() == 2 and h.last()["fields"]["selected_reason"] == "suivi_medical"
        for name in ("Raissa", "Pierrot", "Bell", "Alice"):
            assert name in h.speech()

        await h.say("docteur Bell")
        assert h.ui_step() == 3
        assert "docteur Bell" in h.speech() and "l'après-midi" in h.speech() and "nom complet" in h.speech()
        assert h.last()["fields"]["selected_doctor"] == "B" and h.last()["fields"]["selected_period"] == "AM"

        calls_before = len(h.backend.calls)
        await h.say("jean dupont")
        assert "numéro de téléphone" in h.speech()
        await h.say("zéro trente-quatre douze trois cent quarante-cinq soixante-sept")
        assert "0 3 4, 1 2, 3 4 5, 6 7" in h.speech() and "Est-ce correct" in h.speech()
        assert h.last()["fields"]["patient_phone"] == "034 12 345 67"
        await h.say("oui")
        assert h.ui_step() == 4 and "signes vitaux" in h.speech().lower()
        # le nom et le téléphone n'ont JAMAIS été envoyés au LLM (cloud)
        asked = " ".join(h.backend.calls[calls_before:])
        assert "dupont" not in asked.lower() and "345" not in asked

        await h.say("passer")
        assert h.ui_step() == 5 and "Récapitulatif" in h.speech() and "docteur Bell" in h.speech()
        assert "Dupont" not in h.speech() and "034" not in h.speech()

        await h.say("confirmer")
        assert h.ui_step() == 6 and "B-AM-1" in h.speech() and "docteur Bell" in h.speech()
        return h.rows()

    rows = run(scenario())
    assert len(rows) == 1
    row = rows[0]
    assert (row["patient_name"], row["doctor"], row["period"], row["reason_code"]) == (
        "Jean Dupont", "B", "AM", "suivi_medical",
    )
    assert row["contact_normalized"] == "+261341234567"
    assert row["temperature_c"] is None  # constantes non mesurées : jamais inventées
    assert h.data == {}  # dossier vidé après l'enregistrement


def test_other_reason_is_saved_as_other(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("autre motif")
        return h.data

    data = run(scenario())
    assert data["reason_code"] == "autre_motif"  # et non « consultation générale »


def test_naming_a_doctor_first_then_reason_skips_the_doctor_step(h):
    async def scenario():
        await h.say("je voudrais voir le docteur Raissa")  # depuis l'accueil
        assert h.ui_step() == 1 and "motif" in h.speech().lower()
        assert h.data["doctor_code"] == "A" and h.data["period"] == "MAT"
        await h.say("consultation générale")
        return h.ui_step(), h.speech()

    step, speech = run(scenario())
    assert step == 3 and "nom complet" in speech  # le médecin est déjà choisi : saut de l'étape 2


# ======================================================================================
# Navigation et validations
# ======================================================================================

def test_next_without_data_explains_what_is_missing_and_does_not_advance(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("suivant")
        assert h.ui_step() is None and "sans motif" in h.speech()
        assert "Étape suivante" not in h.speech()
        await h.say("consultation générale")           # -> étape 2
        await h.say("suivant")
        assert "sans médecin" in h.speech() and "Bell" in h.speech()
        return h.node._current_step

    assert run(scenario()) == 2


def test_previous_on_first_step_does_not_cancel_the_consultation(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("précédent")
        return h.speech(), h.node._current_screen

    speech, screen = run(scenario())
    assert "première étape" in speech and "Annuler" in speech
    assert screen == "consultation"


def test_period_question_lists_that_periods_doctors(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("plutôt le matin")
        return h.speech()

    speech = run(scenario())
    assert "Raissa" in speech and "Pierrot" in speech and "Bell" not in speech and speech.endswith("?")


def test_unknown_doctor_lists_the_four_doctors_and_stays_on_step(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("docteur Martin")
        return h.speech(), h.ui_step(), "doctor_code" in h.data

    speech, step, chosen = run(scenario())
    assert "pas reconnu" in speech and all(n in speech for n in ("Raissa", "Pierrot", "Bell", "Alice"))
    assert step is None and not chosen


def test_consultation_request_while_already_in_it_does_not_restart(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("docteur Alice")
        step_before = h.node._current_step
        await h.say("je voudrais voir un médecin")
        return step_before, h.node._current_step, h.speech(), dict(h.data)

    before, after, speech, data = run(scenario())
    assert before == after == 3
    assert "déjà dans la prise de rendez-vous" in speech
    assert data["doctor_code"] == "D"  # rien n'est perdu


def test_changing_doctor_from_the_recap_updates_the_recap(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("docteur Bell")
        h.data.update({"patient_name": "Jean Dupont", "contact": "034 12 345 67"})
        h.node._current_step = 5
        await h.say("docteur Raissa")
        return h.speech(), h.ui_step(), h.data["doctor_code"], h.data["period"]

    speech, step, doctor, period = run(scenario())
    assert step == 5 and "docteur Raissa" in speech and "le matin" in speech
    assert (doctor, period) == ("A", "MAT")


# ======================================================================================
# Annulation (action destructrice)
# ======================================================================================

def test_plain_no_asks_before_cancelling_and_no_again_continues(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("suivi médical")
        await h.say("non")
        assert "annuler la consultation" in h.speech() and h.node._current_screen == "consultation"
        await h.say("non")
        assert "on continue" in h.speech() and h.node._pending_cancel is False
        assert h.data["reason_code"] == "suivi_medical"  # rien perdu

    run(scenario())


def test_plain_no_then_yes_cancels_and_clears_everything(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("suivi médical")
        await h.say("non")
        await h.say("oui")
        return h.last()["instruction_ui"]["screen"], h.node._current_screen, dict(h.data)

    screen, current, data = run(scenario())
    assert screen == "home" and current == "home" and data == {}


def test_explicit_cancel_quits_immediately_like_the_button(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("annuler")
        return h.last()["instruction_ui"]["screen"], "annulée" in h.speech()

    assert run(scenario()) == ("home", True)


def test_no_at_the_recap_does_not_cancel(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        h.node._current_step = 5
        await h.say("non")
        return h.speech(), h.node._current_screen

    speech, screen = run(scenario())
    assert "ne valide pas" in speech and screen == "consultation"


def test_stray_yes_reprompts_the_current_step_instead_of_doing_something(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("oui")
        return h.speech(), h.node._current_step

    speech, step = run(scenario())
    assert "rien à confirmer" in speech and "médecin" in speech and step == 2


# ======================================================================================
# Identité dictée (nom + téléphone)
# ======================================================================================

def _at_identity(h):
    async def go():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("docteur Bell")
    return go


def test_a_patient_named_like_a_doctor_is_taken_as_a_name(h):
    async def scenario():
        await _at_identity(h)()
        await h.say("Alice Martin")
        return h.data.get("patient_name"), h.data["doctor_code"]

    assert run(scenario()) == ("Alice Martin", "B")  # « Alice » ici n'est pas le docteur Alice


def test_phone_dictated_in_two_fragments_is_accumulated(h):
    async def scenario():
        await _at_identity(h)()
        await h.say("Jean Dupont")
        await h.say("zéro trois quatre")
        assert "3 chiffres" in h.speech() and "Continuez" in h.speech()
        await h.say("12 345 67")
        return h.data.get("contact"), h.node._identity_stage

    assert run(scenario()) == ("034 12 345 67", "confirm")


def test_invalid_phone_is_refused_then_suggests_the_screen(h):
    async def scenario():
        await _at_identity(h)()
        await h.say("Jean Dupont")
        await h.say("un deux trois")             # ne commence pas par 0 : irrécupérable
        first = h.speech()
        await h.say("quatre cinq six sept huit neuf un deux")  # 11 chiffres cumulés : toujours invalide
        return first, h.speech(), "contact" in h.data

    first, second, saved = run(scenario())
    assert "pas bien saisi" in first and "écran" not in first
    assert "pas bien saisi" in second and "à l'écran" in second
    assert saved is False


def test_phone_first_then_name(h):
    async def scenario():
        await _at_identity(h)()
        await h.say("mon numéro est le 034 12 345 67")
        assert "nom complet" in h.speech()
        await h.say("je m'appelle Marie Rakoto")
        return h.node._identity_stage, h.data["patient_name"], "Est-ce correct" in h.speech()

    assert run(scenario()) == ("confirm", "Marie Rakoto", True)


def test_wrong_read_back_lets_the_patient_fix_only_the_name(h):
    async def scenario():
        await _at_identity(h)()
        await h.say("Jean Dupond")
        await h.say("0341234567")
        await h.say("non")
        assert "nom, le numéro, ou les deux" in h.speech()
        await h.say("le nom")
        assert "nom complet" in h.speech() and "patient_name" not in h.data
        assert h.data["contact"] == "034 12 345 67"  # le numéro est conservé
        await h.say("Jean Dupont")
        return h.data["patient_name"], h.node._identity_stage

    assert run(scenario()) == ("Jean Dupont", "confirm")


def test_identity_is_never_logged_in_clear(h, caplog):
    caplog.set_level(logging.INFO)

    async def scenario():
        await _at_identity(h)()
        await h.say("Rakotondrasoa Hery")
        await h.say("0341234567")

    run(scenario())
    logs = caplog.text.lower()
    assert "rakotondrasoa" not in logs and "0341234567" not in logs and "034 12 345 67" not in logs


def test_emergency_stop_still_works_during_identity_capture(h):
    published = []
    h.node.navigation_command_pub.publish = lambda msg: published.append(msg.data)

    async def scenario():
        await _at_identity(h)()
        await h.say("stop")

    run(scenario())
    assert "STOP" in published


def test_navigation_words_work_during_identity_without_the_llm(h):
    async def scenario():
        await _at_identity(h)()
        calls = len(h.backend.calls)
        await h.say("suivant")           # rien saisi : on explique ce qui manque
        explained = h.speech()
        await h.say("précédent")
        return explained, h.ui_step(), len(h.backend.calls) - calls

    explained, step, llm_calls = run(scenario())
    assert "nom complet" in explained and "numéro" in explained
    assert step == 2 and llm_calls == 0


# ======================================================================================
# Cohérence mobile <-> serveur
# ======================================================================================

def test_voice_confirmation_works_when_the_form_was_filled_by_touch(h):
    """Le mobile renvoie le formulaire à chaque étape : « oui » à l'étape 5 doit réserver."""
    async def scenario():
        await h.state("consultation", 1)
        await h.ui("consult.step_changed", step=5, fields={
            "reason_code": "suivi_medical", "selected_reason": "suivi_medical",
            "doctor_code": "D", "selected_doctor": "D", "period": "AM", "selected_period": "AM",
            "patient_name": "Hery Rakoto", "contact": "0321234567", "patient_phone": "0321234567",
        })
        assert "Récapitulatif" in h.speech() and "docteur Alice" in h.speech()
        await h.say("oui")
        return h.speech()

    speech = run(scenario())
    assert "docteur Alice" in speech and "D-AM-1" in speech


def test_booking_error_keeps_the_data_and_sends_back_to_the_faulty_step(h):
    async def scenario():
        await h.ui("consult.confirm", patient_name="Premier Patient", contact="0341234567",
                   reason_code="consultation_generale", doctor_code="B", period="AM")
        assert "B-AM-1" in h.speech()
        # un second patient saisit le même numéro
        h.node._current_screen, h.node._current_step = "consultation", 5
        h.data.update({"patient_name": "Second Patient", "contact": "0341234567",
                       "reason_code": "suivi_medical", "doctor_code": "B", "period": "AM"})
        await h.say("oui")
        return h.last(), dict(h.data), h.node._identity_stage

    last, data, stage = run(scenario())
    assert last["instruction_ui"]["step"] == 3
    assert "déjà inscrit" in last["text_to_speak"] and "autre numéro" in last["text_to_speak"]
    assert data["patient_name"] == "Second Patient" and data["doctor_code"] == "B"  # rien d'effacé
    assert "contact" not in data and last["fields"]["patient_phone"] == ""
    assert stage == "phone"


def test_leaving_the_consultation_screen_wipes_the_previous_patient(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("suivi médical")
        h.data["patient_name"] = "Patient Précédent"
        await h.state("home", 1)
        assert h.data == {} and h.node._identity_stage is None
        await h.say("je voudrais voir un médecin")   # nouveau patient
        return dict(h.data), h.ui_step()

    data, step = run(scenario())
    assert data == {} and step == 1


def test_mobile_report_cannot_blank_a_dictated_value(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("docteur Bell")
        await h.state("consultation", 3, {"patient_name": "", "contact": None, "doctor_code": ""})
        return h.data["doctor_code"]

    assert run(scenario()) == "B"


def test_step_reached_by_touch_is_announced_and_arms_the_identity_dialog(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.ui("consult.step_changed", step=3)
        return h.speech(), h.node._identity_stage

    speech, stage = run(scenario())
    assert "nom complet" in speech and stage == "name"


def test_step_announced_by_the_server_is_not_repeated_when_the_mobile_confirms_it(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("docteur Bell")
        await h.say("Jean Dupont")
        await h.say("0341234567")
        await h.say("oui")                      # le serveur annonce l'étape 4
        assert h.ui_step() == 4
        h.sent.clear()
        await h.ui("consult.step_changed", step=4)   # le mobile confirme son arrivée à l'étape 4
        return h.sent

    assert run(scenario()) == []


def test_next_on_vitals_step_waits_while_a_measurement_is_running(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        h.node._current_step = 4
        h.node._publish_vitals_request("req-1")
        await h.say("suivant")
        waiting = h.speech()
        h.node._vitals_started_at = None            # mesure terminée
        await h.say("suivant")
        return waiting, h.ui_step()

    waiting, step = run(scenario())
    assert "mesure est en cours" in waiting and step == 5


def test_unknown_reply_at_a_step_reprompts_instead_of_staying_mute(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("consultation générale")
        await h.say("blablabla gazouillis")
        return h.speech()

    speech = run(scenario())
    assert "pas bien compris" in speech and "médecin" in speech


def test_touch_start_prompts_for_the_reason(h):
    async def scenario():
        await h.ui("consult.start")
        return h.speech(), h.node._current_step

    speech, step = run(scenario())
    assert "motif" in speech.lower() and step == 1


# ======================================================================================
# Séquences incomplètes détectées à l'audit
# ======================================================================================

import time
import urllib.error

from hospital_robot.llm_intent_engine import LLMBackendInterface


class _LLMDown(LLMBackendInterface):
    """Point d'accès Wi-Fi du robot sans Internet : Groq injoignable."""

    def is_available(self, config):
        return True

    def generate(self, prompt, config):
        raise urllib.error.URLError("pas d'Internet")


def _pending_guidance(h, age_s=0.0):
    sent = []
    h.node.hmi_request_pub.publish = lambda msg: sent.append(json.loads(msg.data))
    h.node._current_screen = "orientation"
    h.node._pending_orientation = {
        "destination": "PHARMACY", "label": "Pharmacie",
        "ros_request": {"category": "ORIENTATION", "destination": "PHARMACY"},
        "at": time.monotonic() - age_s,
    }
    return sent


def test_fresh_guidance_confirmation_still_starts_the_mission(h):
    sent = _pending_guidance(h, age_s=5)
    run(h.say("oui"))
    assert sent == [{"category": "ORIENTATION", "destination": "PHARMACY"}]


def test_stale_guidance_confirmation_does_not_move_the_robot(h):
    """Un « oui » dit 10 minutes plus tard par quelqu'un d'autre ne doit rien déclencher."""
    sent = _pending_guidance(h, age_s=600)
    run(h.say("oui"))
    assert sent == []
    assert h.node._pending_orientation is None
    assert "rien à confirmer" in h.speech()


def test_greeting_in_the_middle_of_a_consultation_does_not_lose_the_file(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")
        await h.say("suivi médical")
        h.node.intent_parser.llm_engine._backend.script["bonjour"] = llm("GREETING", None, "Bonjour !", "home")
        await h.say("bonjour")
        return h.last().get("instruction_ui"), h.speech(), h.node._current_screen, dict(h.data)

    ui, speech, screen, data = run(scenario())
    assert ui is None and screen == "consultation"          # pas de retour à l'accueil
    assert speech.startswith("Bonjour !") and "médecin" in speech
    assert data["reason_code"] == "suivi_medical"


def test_consultation_keeps_working_by_voice_when_the_llm_is_unreachable(h):
    async def scenario():
        await h.say("je voudrais voir un médecin")          # ouverture (LLM encore là)
        h.node.intent_parser.llm_engine._backend = _LLMDown()
        out = []
        await h.say("suivi médical")
        out.append((h.ui_step(), h.data.get("reason_code")))
        await h.say("docteur Pierrot")
        out.append((h.ui_step(), h.data.get("doctor_code"), h.data.get("period")))
        await h.say("précédent")
        out.append(h.ui_step())
        return out

    assert run(scenario()) == [(2, "suivi_medical"), (3, "C", "MAT"), 2]


def test_llm_down_does_not_widen_what_is_understood_offline(h):
    """Hors consultation, rien n'est deviné : on dit simplement que le service est indisponible."""
    async def scenario():
        h.node.intent_parser.llm_engine._backend = _LLMDown()
        await h.say("je veux le docteur Bell")
        return h.speech(), h.node._current_screen

    speech, screen = run(scenario())
    assert "indisponible" in speech and screen != "consultation"


def test_llm_down_still_understands_yes_no_of_a_pending_guidance_but_nothing_else(h):
    sent = _pending_guidance(h, age_s=1)

    async def scenario():
        h.node.intent_parser.llm_engine._backend = _LLMDown()
        await h.say("emmène-moi à la radiologie")             # autre destination : pas comprise hors LLM
        assert sent == [] and "indisponible" in h.speech()
        await h.say("oui")                                    # le oui/non, lui, reste compris

    run(scenario())
    assert sent == [{"category": "ORIENTATION", "destination": "PHARMACY"}]
