"""Tests unitaires pour le moteur LLM (Gemini + rotation clés + cache LRU + Qwen fallback)
et son intégration dans VoiceIntentParser."""

import io
import json
import time
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from hospital_robot.llm_intent_engine import (
    AllKeysCooldownError,
    DEFAULT_SYSTEM_PROMPT,
    GeminiBackend,
    HybridGeminiQwenBackend,
    LLMConfig,
    LLMIntentEngine,
    LLMResponse,
    MockBackend,
    OllamaBackend,
    _LRUCache,
    load_dotenv_file,
)
from hospital_robot.voice_intent_parser import VoiceIntentParser, ParsedIntent


def _make_http_response(payload: dict):
    """Construit un faux context manager de réponse HTTP urllib."""
    raw = json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = raw
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def _make_gemini_ok(intent_payload: dict):
    return _make_http_response({
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(intent_payload)}],
                }
            }
        ]
    })


def _make_http_error(code: int, url: str = "https://generativelanguage.googleapis.com/test"):
    return urllib.error.HTTPError(
        url=url,
        code=code,
        msg=f"HTTP {code}",
        hdrs=None,
        fp=io.BytesIO(b"{}"),
    )


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
        """Si le serveur Ollama est éteint (ex: port 59999 fermé), aucune exception n'est levée."""
        config = LLMConfig(
            enabled=True,
            backend="ollama",
            host="http://127.0.0.1:59999",
            timeout_sec=0.2,
        )
        engine = LLMIntentEngine(config=config)

        assert engine.is_available() is False

        res = engine.infer("Bonjour")
        assert res.success is False
        assert res.intent == "UNKNOWN"
        assert res.error is not None


class TestGeminiKeyRotation:
    def test_loads_numbered_and_fallback_keys_from_env(self, monkeypatch):
        for i in range(1, 21):
            monkeypatch.delenv(f"GEMINI_API_KEY_{i}", raising=False)
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        monkeypatch.setenv("GEMINI_API_KEY_1", "key_alpha")
        monkeypatch.setenv("GEMINI_API_KEY_2", "key_beta")
        monkeypatch.setenv("GEMINI_API_KEY_3", "key_gamma")

        backend = GeminiBackend()
        assert backend.key_count == 3
        assert backend.available_key_count() == 3

        # Fallback GEMINI_API_KEY si aucune clé numérotée
        for i in range(1, 4):
            monkeypatch.delenv(f"GEMINI_API_KEY_{i}", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "single_paid_key")
        backend_single = GeminiBackend()
        assert backend_single.key_count == 1

    def test_round_robin_success_rotates_across_keys(self):
        backend = GeminiBackend(api_keys=["key_1", "key_2", "key_3"])
        cfg = LLMConfig(backend="gemini", gemini_model="gemini-2.5-flash-lite")
        seen_urls = []

        def fake_urlopen(req, timeout=4.0):
            seen_urls.append(req.full_url)
            return _make_gemini_ok({
                "intent": "GREETING",
                "target": None,
                "text_to_speak": "Bonjour !",
                "screen": "home",
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            backend.generate("Bonjour 1", cfg)
            assert backend._last_backend == "gemini_key#1"
            backend.generate("Bonjour 2", cfg)
            assert backend._last_backend == "gemini_key#2"
            backend.generate("Bonjour 3", cfg)
            assert backend._last_backend == "gemini_key#3"
            backend.generate("Bonjour 4", cfg)
            assert backend._last_backend == "gemini_key#1"

        assert "key=key_1" in seen_urls[0]
        assert "key=key_2" in seen_urls[1]
        assert "key=key_3" in seen_urls[2]
        assert "key=key_1" in seen_urls[3]

    def test_429_puts_key1_in_cooldown_and_switches_to_key2(self):
        backend = GeminiBackend(api_keys=["key_1", "key_2"])
        cfg = LLMConfig(backend="gemini", gemini_cooldown_sec=60)

        def fake_urlopen(req, timeout=4.0):
            if "key=key_1" in req.full_url:
                raise _make_http_error(429, req.full_url)
            return _make_gemini_ok({
                "intent": "ORIENTATION",
                "target": "PHARMACY",
                "text_to_speak": "Suivez-moi vers la pharmacie.",
                "screen": "orientation",
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            raw = backend.generate("J'ai besoin de médicaments", cfg)

        data = json.loads(raw)
        assert data["intent"] == "ORIENTATION"
        assert data["target"] == "PHARMACY"
        assert backend._last_backend == "gemini_key#2"
        assert backend.available_key_count() == 1  # key#1 en cooldown

    def test_429_cascades_across_three_keys_to_key3(self):
        backend = GeminiBackend(api_keys=["key_1", "key_2", "key_3"])
        cfg = LLMConfig(backend="gemini", gemini_cooldown_sec=60)

        def fake_urlopen(req, timeout=4.0):
            if "key=key_1" in req.full_url or "key=key_2" in req.full_url:
                raise _make_http_error(429, req.full_url)
            return _make_gemini_ok({
                "intent": "VITALS",
                "target": None,
                "text_to_speak": "Mesurons vos constantes.",
                "screen": "consultation",
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            raw = backend.generate("Prends ma tension", cfg)

        assert json.loads(raw)["intent"] == "VITALS"
        assert backend._last_backend == "gemini_key#3"
        assert backend.available_key_count() == 1

    def test_all_keys_429_raises_all_keys_cooldown_error(self):
        backend = GeminiBackend(api_keys=["key_1", "key_2"])
        cfg = LLMConfig(backend="gemini", gemini_cooldown_sec=60)

        with patch("urllib.request.urlopen", side_effect=_make_http_error(429)):
            with pytest.raises(AllKeysCooldownError):
                backend.generate("Bonjour", cfg)

        assert backend.available_key_count() == 0
        assert backend.is_available(cfg) is False

    def test_cooldown_expiration_reenables_key(self):
        backend = GeminiBackend(api_keys=["key_1"])
        cfg = LLMConfig(backend="gemini", gemini_cooldown_sec=1)
        backend._set_cooldown(0, -0.1)  # déjà expiré
        assert backend.available_key_count() == 1
        assert backend.is_available(cfg) is True


class TestLRUCache:
    def test_cache_hit_normalization_and_screen_separation(self):
        cache = _LRUCache(max_entries=4, ttl_seconds=60)
        resp_home = LLMResponse(intent="GREETING", text_to_speak="Bonjour !", success=True)
        resp_orient = LLMResponse(intent="CONFIRM_YES", text_to_speak="Suivez-moi.", success=True)

        cache.put("  Bonjour ! ", "home", resp_home)
        cache.put("oui", "orientation", resp_orient)

        # Normalisation casse/ponctuation
        assert cache.get("bonjour", "home") is resp_home
        # Séparation par écran
        assert cache.get("oui", "home") is None
        assert cache.get("OUI !", "orientation") is resp_orient

    def test_cache_eviction_and_ttl(self):
        cache = _LRUCache(max_entries=2, ttl_seconds=60)
        r1 = LLMResponse(intent="GREETING", success=True)
        r2 = LLMResponse(intent="HOME", success=True)
        r3 = LLMResponse(intent="VITALS", success=True)

        cache.put("a", "home", r1)
        cache.put("b", "home", r2)
        # Toucher "a" pour que "b" devienne le plus ancien
        assert cache.get("a", "home") is r1
        cache.put("c", "home", r3)

        assert cache.size == 2
        assert cache.get("a", "home") is r1
        assert cache.get("b", "home") is None
        assert cache.get("c", "home") is r3

    def test_engine_skips_cache_on_consultation_screen(self):
        mock_backend = MockBackend()
        mock_backend.generate = MagicMock(side_effect=mock_backend.generate)
        engine = LLMIntentEngine(config=LLMConfig(backend="mock"), backend_override=mock_backend)

        # Écran home : 2e appel = cache hit (1 seul appel backend)
        r1 = engine.infer("J'ai besoin d'aspirine", current_screen="home")
        r2 = engine.infer("J'ai besoin d'aspirine", current_screen="home")
        assert r1.cache_hit is False
        assert r2.cache_hit is True
        assert r2.backend_used == "cache"
        assert mock_backend.generate.call_count == 1

        # Écran consultation : jamais mis en cache (2 appels backend)
        engine.infer("Je veux mesurer ma tension", current_screen="consultation")
        engine.infer("Je veux mesurer ma tension", current_screen="consultation")
        assert mock_backend.generate.call_count == 3


class TestHybridGeminiQwenBackend:
    def test_uses_gemini_primary_when_available(self):
        gemini = GeminiBackend(api_keys=["key_1"])
        ollama = OllamaBackend()
        ollama.generate = MagicMock(side_effect=AssertionError("Ollama ne doit pas être appelé"))
        hybrid = HybridGeminiQwenBackend(gemini=gemini, ollama=ollama)
        cfg = LLMConfig(backend="hybrid_gemini_qwen")

        with patch(
            "urllib.request.urlopen",
            return_value=_make_gemini_ok({
                "intent": "ORIENTATION",
                "target": "LABORATORY",
                "text_to_speak": "Direction laboratoire.",
                "screen": "orientation",
            }),
        ):
            engine = LLMIntentEngine(config=cfg, backend_override=hybrid)
            res = engine.infer("Je dois faire des analyses")

        assert res.success is True
        assert res.intent == "ORIENTATION"
        assert res.target == "LABORATORY"
        assert res.backend_used == "gemini_key#1"
        ollama.generate.assert_not_called()

    def test_falls_back_to_qwen_when_all_gemini_keys_cooldown(self):
        gemini = GeminiBackend(api_keys=["key_1", "key_2"])
        ollama = OllamaBackend()
        ollama.generate = MagicMock(return_value=json.dumps({
            "intent": "ORIENTATION",
            "target": "PHARMACY",
            "text_to_speak": "Je vous guide à la pharmacie.",
            "screen": "orientation",
        }))
        ollama.is_available = MagicMock(return_value=True)
        hybrid = HybridGeminiQwenBackend(gemini=gemini, ollama=ollama)
        cfg = LLMConfig(backend="hybrid_gemini_qwen")

        with patch("urllib.request.urlopen", side_effect=_make_http_error(429)):
            engine = LLMIntentEngine(config=cfg, backend_override=hybrid)
            res = engine.infer("Où trouver mes comprimés ?")

        assert res.success is True
        assert res.intent == "ORIENTATION"
        assert res.target == "PHARMACY"
        assert res.backend_used == "qwen_local_all_cooldown"
        assert ollama.generate.call_count == 1

        status, detail = engine.get_diagnostics_status()
        assert status == "warn"
        assert "Qwen local" in detail
        assert "pause" in detail

    def test_falls_back_to_qwen_on_gemini_timeout(self):
        gemini = GeminiBackend(api_keys=["key_1"])
        ollama = OllamaBackend()
        ollama.generate = MagicMock(return_value=json.dumps({
            "intent": "GREETING",
            "target": None,
            "text_to_speak": "Bonjour !",
            "screen": "home",
        }))
        hybrid = HybridGeminiQwenBackend(gemini=gemini, ollama=ollama)
        cfg = LLMConfig(backend="hybrid_gemini_qwen")

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            engine = LLMIntentEngine(config=cfg, backend_override=hybrid)
            res = engine.infer("Bonjour")

        assert res.success is True
        assert res.intent == "GREETING"
        assert res.backend_used == "qwen_local_network_error"
        assert ollama.generate.call_count == 1

    def test_load_dotenv_file_parses_keys(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY_1", raising=False)
        monkeypatch.delenv("HIAR_GEMINI_MODEL", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# commentaire\nGEMINI_API_KEY_1='test_key_1'\nHIAR_GEMINI_MODEL=gemini-2.5-flash-lite\n",
            encoding="utf-8",
        )
        loaded = load_dotenv_file(env_file)
        assert loaded == env_file
        assert "test_key_1" == __import__("os").environ.get("GEMINI_API_KEY_1")
        assert "gemini-2.5-flash-lite" == __import__("os").environ.get("HIAR_GEMINI_MODEL")


class TestVoiceIntentParserWithLLM:
    def test_safety_stop_bypasses_llm_immediately(self):
        """Vérifie que STOP est prioritaire et ne consulte jamais le LLM (sécurité immédiate)."""
        mock_backend = MockBackend()
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

    def test_short_phrases_use_llm_and_cache_with_screen_context(self):
        """Les phrases courtes ('Oui', 'Bonjour') passent aussi par Gemini + cache avec contexte écran."""
        backend = MockBackend(canned_responses={
            "[ecran actuel: orientation] oui": json.dumps({
                "intent": "CONFIRM_YES",
                "target": None,
                "text_to_speak": "Parfait, allons-y !",
                "screen": "mission",
            }),
        })
        backend.generate = MagicMock(side_effect=backend.generate)
        engine = LLMIntentEngine(config=LLMConfig(backend="mock"), backend_override=backend)
        parser = VoiceIntentParser(enable_llm=True, llm_engine=engine)

        i1 = parser.parse("Oui", current_screen="orientation")
        assert i1.intent_type == "CONFIRM_YES"
        assert i1.details.get("llm_generated") is True
        assert i1.details.get("cache_hit") is False

        # 2e fois → cache hit, zéro appel LLM supplémentaire
        i2 = parser.parse("Oui", current_screen="orientation")
        assert i2.intent_type == "CONFIRM_YES"
        assert i2.details.get("cache_hit") is True
        assert backend.generate.call_count == 1

    def test_deterministic_safety_net_when_llm_fails_or_returns_unknown(self):
        """Si Gemini et Qwen échouent ou renvoient UNKNOWN, le filet déterministe rattrape la commande."""
        failing_backend = MockBackend()
        failing_backend.generate = MagicMock(side_effect=TimeoutError("all down"))
        engine = LLMIntentEngine(config=LLMConfig(backend="mock"), backend_override=failing_backend)
        parser = VoiceIntentParser(enable_llm=True, llm_engine=engine)

        intent = parser.parse("Emmène-moi à la pharmacie", current_screen="home")
        assert intent.intent_type == "ORIENTATION"
        assert intent.target_value == "PHARMACY"
        assert intent.details.get("deterministic_fallback") is True

        intent_yes = parser.parse("Oui", current_screen="orientation")
        assert intent_yes.intent_type == "CONFIRM_YES"
        assert intent_yes.details.get("deterministic_fallback") is True

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


class TestGeminiSoloMode:
    def test_gemini_solo_disables_cache_and_calls_gemini_every_time(self):
        gemini = GeminiBackend(api_keys=["key_1"])
        cfg = LLMConfig(backend="gemini", cache_enabled=False)
        engine = LLMIntentEngine(config=cfg, backend_override=gemini)

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_gemini_ok({
                    "intent": "CONFIRM_YES",
                    "target": None,
                    "text_to_speak": "Parfait !",
                    "screen": "mission",
                }),
                _make_gemini_ok({
                    "intent": "CONFIRM_YES",
                    "target": None,
                    "text_to_speak": "C'est parti !",
                    "screen": "mission",
                }),
            ],
        ) as mock_open:
            r1 = engine.infer("Oui", current_screen="orientation")
            r2 = engine.infer("Oui", current_screen="orientation")

        assert mock_open.call_count == 2
        assert r1.cache_hit is False and r2.cache_hit is False
        assert r1.backend_used == "gemini_key#1"
        assert r2.backend_used == "gemini_key#1"

    def test_gemini_solo_never_falls_back_to_deterministic_regex_on_error(self):
        gemini = GeminiBackend(api_keys=["key_1"])
        cfg = LLMConfig(backend="gemini", cache_enabled=False)
        engine = LLMIntentEngine(config=cfg, backend_override=gemini)
        parser = VoiceIntentParser(
            enable_llm=True,
            llm_engine=engine,
            enable_deterministic_fallback=False,
        )

        with patch("urllib.request.urlopen", side_effect=TimeoutError("gemini timeout")):
            intent = parser.parse("Emmène-moi à la pharmacie", current_screen="home")

        assert intent.intent_type == "UNKNOWN"
        assert intent.details.get("deterministic_fallback") is None
        assert intent.details.get("llm_error")
        instruction = parser.build_instruction(intent)
        assert "Gemini" in instruction["text_to_speak"]

    def test_gemini_solo_preserves_gemini_speech_on_unknown_intent(self):
        gemini = GeminiBackend(api_keys=["key_1"])
        cfg = LLMConfig(backend="gemini", cache_enabled=False)
        engine = LLMIntentEngine(config=cfg, backend_override=gemini)
        parser = VoiceIntentParser(
            enable_llm=True,
            llm_engine=engine,
            enable_deterministic_fallback=False,
        )

        with patch(
            "urllib.request.urlopen",
            return_value=_make_gemini_ok({
                "intent": "UNKNOWN",
                "target": None,
                "text_to_speak": "Je suis HIAR et je peux surtout vous guider dans l'hôpital.",
                "screen": "home",
            }),
        ):
            intent = parser.parse("Quelle est la météo aujourd'hui ?", current_screen="home")

        assert intent.intent_type == "UNKNOWN"
        assert intent.details.get("llm_generated") is True
        instruction = parser.build_instruction(intent)
        assert instruction["text_to_speak"] == "Je suis HIAR et je peux surtout vous guider dans l'hôpital."

    def test_bridge_forces_gemini_solo_even_if_env_sets_hybrid(self, monkeypatch):
        import socket
        from hospital_robot.hmi_websocket_bridge_node import HMIWebSocketBridgeNode

        monkeypatch.setenv("HIAR_LLM_BACKEND", "hybrid_gemini_qwen")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        node = HMIWebSocketBridgeNode(host="127.0.0.1", port=port)
        try:
            assert isinstance(node.intent_parser.llm_engine._backend, GeminiBackend)
            assert node.intent_parser.llm_engine.config.backend == "gemini"
            assert node.intent_parser.llm_engine.config.cache_enabled is False
            assert node.intent_parser.enable_deterministic_fallback is False
            assert node._llm_prewarming is False
        finally:
            node.destroy_node()

    def test_prompt_contains_app_routing_map_and_consultation_intents_work(self):
        from hospital_robot.llm_intent_engine import DEFAULT_SYSTEM_PROMPT

        assert "CARTE DE ROUTAGE DE L'APPLICATION HIAR" in DEFAULT_SYSTEM_PROMPT
        assert "LOGIQUE SIMPLE DE CLASSIFICATION" in DEFAULT_SYSTEM_PROMPT
        assert "Étape 4" in DEFAULT_SYSTEM_PROMPT
        assert "CONSULTATION_STEP" in DEFAULT_SYSTEM_PROMPT
        assert "CONSULTATION_REASON" in DEFAULT_SYSTEM_PROMPT

        gemini = GeminiBackend(api_keys=["key_1"])
        cfg = LLMConfig(backend="gemini", cache_enabled=False)
        engine = LLMIntentEngine(config=cfg, backend_override=gemini)
        parser = VoiceIntentParser(
            enable_llm=True,
            llm_engine=engine,
            enable_deterministic_fallback=False,
        )

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                _make_gemini_ok({
                    "intent": "CONSULTATION_REASON",
                    "target": "SUIVI_MEDICAL",
                    "text_to_speak": "Très bien, je sélectionne un suivi médical.",
                    "screen": "consultation",
                }),
                _make_gemini_ok({
                    "intent": "CONSULTATION_STEP",
                    "target": "NEXT",
                    "text_to_speak": "Passons à l'étape suivante.",
                    "screen": "consultation",
                }),
            ],
        ):
            i_reason = parser.parse("C'est pour un suivi", current_screen="consultation (étape 1/6: choix du motif)")
            i_step = parser.parse("Suivant", current_screen="consultation (étape 2/6: choix médecin et créneau)")

        assert i_reason.intent_type == "CONSULTATION_REASON"
        assert i_reason.target_value == "suivi_medical"
        assert i_step.intent_type == "CONSULTATION_STEP"
        assert i_step.target_value == "next"

    def test_bridge_builds_rich_screen_context_for_gemini(self):
        import socket
        from hospital_robot.hmi_websocket_bridge_node import HMIWebSocketBridgeNode

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        node = HMIWebSocketBridgeNode(host="127.0.0.1", port=port)
        try:
            node._current_screen = "consultation"
            node._current_step = 4
            assert "étape 4/6" in node._build_screen_context()

            node._pending_orientation = {"destination": "LABORATORY", "label": "Laboratoire d'analyses"}
            assert "attente confirmation" in node._build_screen_context()
            assert "Laboratoire d'analyses" in node._build_screen_context()
        finally:
            node.destroy_node()
