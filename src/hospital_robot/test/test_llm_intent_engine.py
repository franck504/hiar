"""Tests unitaires pour le moteur LLM et son intégration dans VoiceIntentParser."""

import json
from unittest.mock import MagicMock, patch
import pytest

from hospital_robot.llm_intent_engine import (
    DEFAULT_SYSTEM_PROMPT,
    LLMConfig,
    LLMIntentEngine,
    LLMResponse,
    MockBackend,
    OllamaBackend,
)
from hospital_robot.voice_intent_parser import VoiceIntentParser, ParsedIntent


class TestLLMIntentEngine:
    def test_mock_backend_canned_responses(self):
        backend = MockBackend()
        config = LLMConfig(enabled=True, backend="mock")
        engine = LLMIntentEngine(config=config, backend_override=backend)

        assert engine.is_available() is True

        # 1. Orientation Pharmacie
        res = engine.infer("J'ai besoin de comprimés d'aspirine")
        assert res.success is True
        assert res.intent == "ORIENTATION"
        assert res.target == "PHARMACY"
        assert "pharmacie" in res.text_to_speak.lower()

        # 2. Orientation Laboratoire
        res = engine.infer("Je dois faire une prise de sang")
        assert res.success is True
        assert res.intent == "ORIENTATION"
        assert res.target == "LABORATORY"

        # 3. Information Paludisme
        res = engine.infer("Comment éviter le paludisme et les piqûres de moustiques ?")
        assert res.success is True
        assert res.intent == "INFORMATION"
        assert res.target == "MALARIA"

        # 4. Signes vitaux
        res = engine.infer("Je souhaite mesurer ma tension artérielle")
        assert res.success is True
        assert res.intent == "VITALS"

        # 5. Salutation / Présentation
        res = engine.infer("Bonjour qui es-tu ?")
        assert res.success is True
        assert res.intent == "GREETING"

    def test_json_cleaner_handles_markdown_and_noise(self):
        clean = LLMIntentEngine._clean_and_parse_json

        # Markdown standard
        md_text = '```json\n{"intent": "ORIENTATION", "target": "PHARMACY", "text_to_speak": "Suivez-moi"}\n```'
        data = clean(md_text)
        assert data is not None
        assert data["intent"] == "ORIENTATION"

        # Texte parasite avant/après
        noisy_text = 'Voici ma réponse :\n{"intent": "VITALS", "target": null, "text_to_speak": "Prise de tension"}\nJ\'espère que cela aide.'
        data = clean(noisy_text)
        assert data is not None
        assert data["intent"] == "VITALS"

        # Guillemets simples tolérés
        single_quote_text = "{'intent': 'GREETING', 'text_to_speak': 'Bonjour'}"
        data = clean(single_quote_text)
        assert data is not None
        assert data["intent"] == "GREETING"

    def test_offline_unreachable_server_graceful_handling(self):
        """Si le serveur Ollama est éteint (ex: port 11434 fermé), aucune exception n'est levée."""
        config = LLMConfig(
            enabled=True,
            backend="ollama",
            host="http://127.0.0.1:59999",  # Port inexistant
            timeout_sec=0.2,
        )
        engine = LLMIntentEngine(config=config)

        # is_available renvoie False proprement
        assert engine.is_available() is False

        # infer renvoie un LLMResponse d'erreur sans crasher
        res = engine.infer("Bonjour")
        assert res.success is False
        assert res.intent == "UNKNOWN"
        assert res.error is not None


class TestVoiceIntentParserWithLLM:
    def test_safety_stop_bypasses_llm_immediately(self):
        """Vérifie que STOP est prioritaire et ne consulte jamais le LLM (sécurité immédiate)."""
        mock_backend = MockBackend()
        # On remplace generate par une exception pour prouver qu'il n'est pas appelé
        mock_backend.generate = MagicMock(side_effect=RuntimeError("LLM should not be called on STOP!"))

        config = LLMConfig(enabled=True, backend="mock")
        engine = LLMIntentEngine(config=config, backend_override=mock_backend)
        parser = VoiceIntentParser(enable_llm=True, llm_engine=engine)

        intent = parser.parse("Stop arrête-toi !")
        assert intent.intent_type == "STOP"
        assert intent.ros_command == "STOP"
        mock_backend.generate.assert_not_called()

    def test_natural_speech_fallback_to_llm(self):
        """Une phrase complexe non gérée par regex est correctement interceptée par le LLM."""
        backend = MockBackend()
        config = LLMConfig(enabled=True, backend="mock")
        engine = LLMIntentEngine(config=config, backend_override=backend)
        parser = VoiceIntentParser(enable_llm=True, llm_engine=engine)

        # "J'ai la tête qui tourne et je veux des comprimés" -> Échoue au regex déterministe car pas de mot "pharmacie"
        intent = parser.parse("J'ai la tête qui tourne et je veux des comprimés")
        assert intent.intent_type == "ORIENTATION"
        assert intent.target_value == "PHARMACY"
        assert intent.category == "ORIENTATION"
        assert intent.ros_request == {"category": "ORIENTATION", "destination": "PHARMACY"}
        assert intent.details.get("llm_generated") is True

        instruction = parser.build_instruction(intent)
        assert "pharmacie" in instruction["text_to_speak"].lower()
        assert instruction["instruction_ui"]["screen"] == "orientation"
        assert instruction["instruction_ui"]["require_confirmation"] is True

    def test_health_education_with_llm(self):
        """Questions ouvertes sur la santé résolues par le LLM."""
        backend = MockBackend()
        config = LLMConfig(enabled=True, backend="mock")
        engine = LLMIntentEngine(config=config, backend_override=backend)
        parser = VoiceIntentParser(enable_llm=True, llm_engine=engine)

        intent = parser.parse("Comment se protéger des moustiques et du paludisme ?")
        assert intent.intent_type == "INFORMATION"
        assert intent.target_value == "MALARIA"
        assert intent.ros_request == {"category": "INFORMATION", "topic": "MALARIA"}

        instruction = parser.build_instruction(intent)
        assert "paludisme" in instruction["text_to_speak"].lower()
        assert instruction["instruction_ui"]["screen"] == "information"

    def test_greeting_presentation_with_llm(self):
        """Présentation personnalisée générée par le LLM lorsque le texte ne contient pas 'bonjour'."""
        backend = MockBackend()
        config = LLMConfig(enabled=True, backend="mock")
        engine = LLMIntentEngine(config=config, backend_override=backend)
        parser = VoiceIntentParser(enable_llm=True, llm_engine=engine)

        intent = parser.parse("Qui es-tu et que fais-tu dans cet hôpital ?")
        assert intent.intent_type == "GREETING"
        assert intent.details.get("llm_generated") is True

        intent2 = parser.parse("tu es qui")
        assert intent2.intent_type == "GREETING"
        assert intent2.details.get("llm_generated") is True

        intent3 = parser.parse("vous êtes qui")
        assert intent3.intent_type == "GREETING"
        assert intent3.details.get("llm_generated") is True

        instruction = parser.build_instruction(intent)
        assert "hiar" in instruction["text_to_speak"].lower()
        assert instruction["instruction_ui"]["screen"] == "home"

    def test_parser_falls_back_to_unknown_if_llm_disabled(self):
        """Si le LLM est désactivé, le comportement historique UNKNOWN est conservé."""
        parser = VoiceIntentParser(enable_llm=False)
        intent = parser.parse("Une phrase totalement imprévue et inconnue")
        assert intent.intent_type == "UNKNOWN"
        instruction = parser.build_instruction(intent)
        assert "Je n'ai pas bien compris votre demande" in instruction["text_to_speak"]
