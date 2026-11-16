"""Moteur d'inférence LLM pour le robot hospitalier HIAR.

Permet d'utiliser un modèle de langage compact (comme Qwen 2.5 0.5B Instruct)
pour classifier les intentions en langage naturel, comprendre les formulations complexes
et générer des réponses vocales empathiques et concises en français.

Fonctionne avec Ollama (par défaut sur le Pi), llama.cpp ou en mode Mock/Hors-ligne.
"""

from dataclasses import dataclass, field
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

logger = logging.getLogger("hospital_robot.llm_intent_engine")


DEFAULT_SYSTEM_PROMPT = """Tu es l'assistant vocal intelligent du robot hospitalier HIAR.
Analyse la demande du patient en français et réponds UNIQUEMENT par un objet JSON valide :
{
  "intent": "ORIENTATION" | "INFORMATION" | "VITALS" | "CONSULTATION" | "GREETING" | "HOME" | "UNKNOWN",
  "target": "PHARMACY" | "LABORATORY" | "RADIOLOGY" | "RECEPTION" | "MALARIA" | "HIV" | "DIABETES" | "HYPERTENSION" | "TUBERCULOSIS" | "MENSTRUAL_HEALTH" | null,
  "text_to_speak": "Phrase très courte à prononcer (12 mots max)",
  "screen": "orientation" | "information" | "consultation" | "home"
}

Règles de classification :
- ORIENTATION :
  * PHARMACY : médicaments, ordonnance, pilules, pharmacie, cachets, sirop, comprimés, remède.
  * LABORATORY : prise de sang, analyses, bilan biologique, laboratoire, labo, examen sanguin.
  * RADIOLOGY : radio, scanner, irm, radiographie, imagerie, fracture, os cassé ou foulé.
  * RECEPTION : entrée, accueil, sortie, guichet.
- INFORMATION (fiches OMS) :
  * MALARIA (paludisme, piqûre de moustique), HIV (sida), DIABETES (diabète, glycémie, sucre), HYPERTENSION (tension artérielle), TUBERCULOSIS (tuberculose), MENSTRUAL_HEALTH (santé menstruelle).
- VITALS : mesure des constantes, tension, température, pouls, oxymètre, saturation.
- CONSULTATION : voir un docteur, médecin, prendre un rdv , dire des symptomes .
- GREETING : salutation ou présentation ("bonjour", "qui es-tu ?", "tu es qui", "qui êtes-vous", "vous êtes qui", "présente-toi").
- HOME : retour menu, accueil, annuler.
- UNKNOWN : incompréhensible ou hors sujet."""


@dataclass
class LLMConfig:
    """Configuration du moteur LLM."""

    enabled: bool = True
    backend: str = "ollama"  # "ollama", "llama_cpp", "mock"
    host: str = "http://127.0.0.1:11434"
    model_name: str = "qwen2.5:0.5b"
    timeout_sec: float = 15.0
    temperature: float = 0.1
    max_tokens: int = 120
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


@dataclass
class LLMResponse:
    """Résultat normalisé retourné par le LLM."""

    intent: str = "UNKNOWN"
    target: Optional[str] = None
    text_to_speak: str = ""
    screen: Optional[str] = None
    raw_reply: str = ""
    latency_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None
    confidence: float = 0.95


class LLMBackendInterface:
    """Interface abstraite pour les fournisseurs d'inférence LLM."""

    def is_available(self, config: LLMConfig) -> bool:
        raise NotImplementedError

    def generate(self, prompt: str, config: LLMConfig) -> str:
        raise NotImplementedError


class OllamaBackend(LLMBackendInterface):
    """Client HTTP natif ultra-léger pour Ollama."""

    def is_available(self, config: LLMConfig) -> bool:
        url = f"{config.host.rstrip('/')}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, user_prompt: str, config: LLMConfig) -> str:
        url = f"{config.host.rstrip('/')}/api/chat"
        payload = {
            "model": config.model_name,
            "messages": [
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "keep_alive": "24h",
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=config.timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("message", {}).get("content", "")


class LlamaCppBackend(LLMBackendInterface):
    """Client HTTP natif pour llama-server / llama.cpp."""

    def is_available(self, config: LLMConfig) -> bool:
        url = f"{config.host.rstrip('/')}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, user_prompt: str, config: LLMConfig) -> str:
        url = f"{config.host.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": config.model_name,
            "messages": [
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=config.timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return ""


class MockBackend(LLMBackendInterface):
    """Backend simulé pour les tests unitaires déconnectés et sans serveur."""

    def __init__(self, canned_responses: Optional[Dict[str, str]] = None):
        self.canned_responses = canned_responses or {}
        self.available = True

    @staticmethod
    def _norm(text: str) -> str:
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text.lower())
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def is_available(self, config: LLMConfig) -> bool:
        return self.available

    def generate(self, user_prompt: str, config: LLMConfig) -> str:
        norm = self._norm(user_prompt)
        for pattern, response in self.canned_responses.items():
            if self._norm(pattern) in norm:
                return response

        # Réponses par défaut pré-calculées selon mots-clés typiques
        if any(w in norm for w in ["medicament", "comprime", "aspirine", "ordonnance"]):
            return json.dumps({
                "intent": "ORIENTATION",
                "target": "PHARMACY",
                "text_to_speak": "Je vous guide vers la pharmacie pour vos médicaments.",
                "screen": "orientation",
            })
        if any(w in norm for w in ["prise de sang", "sang", "biologie", "analyse"]):
            return json.dumps({
                "intent": "ORIENTATION",
                "target": "LABORATORY",
                "text_to_speak": "Suivez-moi, nous allons au laboratoire d'analyses.",
                "screen": "orientation",
            })
        if any(w in norm for w in ["paludisme", "moustique", "fievre tropicale"]):
            return json.dumps({
                "intent": "INFORMATION",
                "target": "MALARIA",
                "text_to_speak": "Voici les informations essentielles sur la prévention du paludisme.",
                "screen": "information",
            })
        if any(w in norm for w in ["tension", "pouls", "constantes", "mesurer"]):
            return json.dumps({
                "intent": "VITALS",
                "target": "VITAL_SIGNS",
                "text_to_speak": "Préparons la prise de vos constantes vitales.",
                "screen": "consultation",
            })
        if any(w in norm for w in ["qui es-tu", "tu es qui", "qui etes-vous", "vous etes qui", "presente-toi", "ton nom", "bonjour"]):
            return json.dumps({
                "intent": "GREETING",
                "target": None,
                "text_to_speak": "Bonjour ! Je suis HIAR, votre robot d'accueil hospitalier.",
                "screen": "home",
            })

        return json.dumps({
            "intent": "UNKNOWN",
            "target": None,
            "text_to_speak": "Je n'ai pas bien compris votre demande. Vous pouvez me demander la pharmacie ou le laboratoire.",
            "screen": "home",
        })


class LLMIntentEngine:
    """Moteur central d'analyse et classification d'intentions vocales via LLM."""

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        backend_override: Optional[LLMBackendInterface] = None,
    ):
        self.config = config or LLMConfig()
        if backend_override:
            self._backend = backend_override
        elif self.config.backend == "mock":
            self._backend = MockBackend()
        elif self.config.backend == "llama_cpp":
            self._backend = LlamaCppBackend()
        else:
            self._backend = OllamaBackend()

        self._last_availability_check = 0.0
        self._is_available_cached = False

    def is_available(self) -> bool:
        """Vérifie si le serveur LLM est joignable (avec mise en cache de 5s)."""
        if not self.config.enabled:
            return False

        now = time.time()
        if (now - self._last_availability_check) < 5.0:
            return self._is_available_cached

        self._last_availability_check = now
        try:
            self._is_available_cached = self._backend.is_available(self.config)
        except Exception as e:
            logger.debug(f"LLM availability check error: {e}")
            self._is_available_cached = False

        return self._is_available_cached

    def infer(self, user_text: str) -> LLMResponse:
        """Effectue l'inférence sur le texte utilisateur et renvoie un LLMResponse structuré."""
        clean_text = user_text.strip()
        if not clean_text:
            return LLMResponse(intent="UNKNOWN", error="Empty input", success=False)

        if not self.config.enabled:
            return LLMResponse(intent="UNKNOWN", error="LLM disabled in config", success=False)

        start_time = time.time()
        try:
            raw_output = self._backend.generate(clean_text, self.config)
            latency_ms = (time.time() - start_time) * 1000.0

            parsed_data = self._clean_and_parse_json(raw_output)
            if not parsed_data:
                return LLMResponse(
                    intent="UNKNOWN",
                    raw_reply=raw_output,
                    latency_ms=latency_ms,
                    success=False,
                    error="JSON parse error",
                )

            intent = str(parsed_data.get("intent", "UNKNOWN")).upper()
            target = parsed_data.get("target")
            if target and str(target).upper() not in ["NONE", "NULL"]:
                target = str(target).upper()
            else:
                target = None

            text_to_speak = str(parsed_data.get("text_to_speak", "")).strip()
            screen = parsed_data.get("screen")
            if screen:
                screen = str(screen).lower().strip()

            return LLMResponse(
                intent=intent,
                target=target,
                text_to_speak=text_to_speak,
                screen=screen,
                raw_reply=raw_output,
                latency_ms=latency_ms,
                success=True,
            )

        except urllib.error.URLError as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.warning(f"LLM server unreachable ({self.config.backend}): {e}")
            return LLMResponse(
                intent="UNKNOWN",
                latency_ms=latency_ms,
                success=False,
                error=f"Connection error: {e}",
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.warning(f"LLM inference error: {e}")
            return LLMResponse(
                intent="UNKNOWN",
                latency_ms=latency_ms,
                success=False,
                error=f"Inference error: {e}",
            )

    @staticmethod
    def _clean_and_parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        """Extrait et nettoie un bloc JSON même si le LLM inclut du Markdown ou du texte autour."""
        if not raw_text:
            return None

        text = raw_text.strip()

        # 1. Suppression des blocs Markdown ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            # 2. Chercher le premier '{' et le dernier '}'
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]

        try:
            return json.loads(text)
        except Exception:
            # 3. Tentative de correction si guillemets simples
            try:
                text_fixed = text.replace("'", '"')
                return json.loads(text_fixed)
            except Exception:
                pass

        # 4. Récupération robuste par regex si le JSON est tronqué en fin de génération
        salvaged = {}
        intent_m = re.search(r'"intent"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        if intent_m:
            salvaged["intent"] = intent_m.group(1).upper()
        target_m = re.search(r'"target"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        if target_m:
            salvaged["target"] = target_m.group(1).upper()
        speech_m = re.search(r'"text_to_speak"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"?', text)
        if speech_m:
            salvaged["text_to_speak"] = speech_m.group(1)
        screen_m = re.search(r'"screen"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        if screen_m:
            salvaged["screen"] = screen_m.group(1).lower()

        if salvaged.get("intent") or salvaged.get("target"):
            return salvaged

        return None
