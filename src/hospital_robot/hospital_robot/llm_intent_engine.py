"""Moteur d'inférence LLM pour le robot hospitalier HIAR.

Architecture 5 niveaux :
  1. Réflexe local déterministe (STOP/ARRÊTE/URGENCE) — < 1 ms, jamais réseau
  2. Cache LRU local — < 1 ms, zéro quota
  3. Backend PRINCIPAL : Gemini API (gemini-2.5-flash-lite), rotation round-robin
     des clés avec cooldown par clé sur HTTP 429
  4. Backend FALLBACK  : Qwen 2.5 0.5B via Ollama (pré-chargé en RAM sur Pi)
  5. Filet de sécurité final : parseur déterministe (dans voice_intent_parser.py)
"""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import unicodedata
import urllib.error
import urllib.request

logger = logging.getLogger("hospital_robot.llm_intent_engine")


# ---------------------------------------------------------------------------
# Chargement léger du fichier .env (sans dépendance externe)
# ---------------------------------------------------------------------------

def load_dotenv_file(env_path: Optional[Path] = None) -> Optional[Path]:
    """Charge les variables d'un fichier .env dans os.environ (sans écraser l'existant).

    Cherche dans l'ordre :
      1. `env_path` si fourni
      2. Variable d'environnement `HIAR_ENV_FILE`
      3. `.env` dans le répertoire courant ou ses parents (jusqu'à 5 niveaux)
      4. `~/hiar-main/.env`
    """
    candidates: List[Path] = []
    if env_path is not None:
        candidates.append(Path(env_path))
    else:
        explicit = os.environ.get("HIAR_ENV_FILE", "").strip()
        if explicit:
            candidates.append(Path(explicit))
        cwd = Path.cwd()
        for parent in [cwd, *list(cwd.parents)[:4]]:
            candidates.append(parent / ".env")
        try:
            module_root = Path(__file__).resolve().parents[3]
            candidates.append(module_root / ".env")
        except IndexError:
            pass
        candidates.append(Path.home() / "hiar-main" / ".env")

    target: Optional[Path] = None
    for cand in candidates:
        if cand.is_file():
            target = cand
            break

    if target is None:
        return None

    try:
        for raw_line in target.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if not key:
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            os.environ.setdefault(key, val)
        return target
    except Exception as exc:
        logger.warning(f"[LLM] Impossible de lire {target}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Prompt système commun
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = """Tu es l'assistant vocal intelligent du robot hospitalier HIAR.
Analyse la demande du patient en français (en tenant compte du contexte d'écran si fourni) et réponds UNIQUEMENT par un objet JSON valide :
{
  "intent": "ORIENTATION" | "INFORMATION" | "INFORMATION_GENERAL" | "VITALS" | "CONSULTATION" | "CONFIRM_YES" | "CONFIRM_NO" | "RESUME" | "FINISH" | "START" | "GREETING" | "THANKS" | "HOME" | "UNKNOWN",
  "target": "PHARMACY" | "LABORATORY" | "RADIOLOGY" | "RECEPTION" | "MALARIA" | "HIV" | "DIABETES" | "HYPERTENSION" | "TUBERCULOSIS" | "MENSTRUAL_HEALTH" | null,
  "text_to_speak": "Phrase empathique très courte à prononcer en français (12 mots max)",
  "screen": "orientation" | "information" | "consultation" | "mission" | "home"
}

Règles de classification :
- ORIENTATION :
  * PHARMACY : médicaments, ordonnance, pilules, pharmacie, cachets, sirop, comprimés, remède.
  * LABORATORY : prise de sang, analyses, bilan biologique, laboratoire, labo, examen sanguin.
  * RADIOLOGY : radio, scanner, irm, radiographie, imagerie, fracture, os cassé ou foulé.
  * RECEPTION : entrée, accueil, sortie, guichet.
- INFORMATION (fiches OMS) :
  * MALARIA (paludisme, piqûre de moustique), HIV (sida), DIABETES (diabète, glycémie, sucre), HYPERTENSION (tension artérielle), TUBERCULOSIS (tuberculose), MENSTRUAL_HEALTH (santé menstruelle).
- INFORMATION_GENERAL : demande générale de renseignements ou fiches santé sans maladie précise.
- VITALS : mesure des constantes, tension, température, pouls, oxymètre, saturation.
- CONSULTATION : voir un docteur, médecin, prendre un rdv, exprimer des symptômes nécessitant un médecin.
- CONFIRM_YES : accord/validation ("oui", "d'accord", "ok", "allons-y", "confirmer", "vas-y").
- CONFIRM_NO : refus/annulation ("non", "annuler", "pas maintenant", "non merci").
- RESUME : reprendre le guidage / continuer la route.
- FINISH : mission terminée / on est arrivé / c'est bon.
- START : commencer / démarrer depuis la veille.
- GREETING : salutation ou présentation ("bonjour", "salut", "qui es-tu ?", "tu es qui", "présente-toi").
- THANKS : remerciement ("merci", "merci beaucoup").
- HOME : retour menu principal / écran d'accueil.
- UNKNOWN : incompréhensible ou hors sujet hospitalier."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """Configuration du moteur LLM."""

    enabled: bool = True
    # "hybrid_gemini_qwen" | "gemini" | "ollama" | "llama_cpp" | "mock"
    backend: str = "hybrid_gemini_qwen"
    # --- Ollama / llama.cpp (secours local) ---
    host: str = "http://127.0.0.1:11434"
    model_name: str = "qwen2.5:0.5b"
    timeout_sec: float = 15.0
    temperature: float = 0.1
    max_tokens: int = 150
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    # --- Gemini API (primaire) ---
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_timeout_sec: float = 4.0
    gemini_cooldown_sec: int = 60
    # --- Cache LRU ---
    cache_ttl_min: int = 10
    cache_max_entries: int = 64


# ---------------------------------------------------------------------------
# Réponse normalisée
# ---------------------------------------------------------------------------

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
    # Quel backend a répondu : "gemini_key#1" | "qwen_local" | "cache" | "mock" | ...
    backend_used: str = ""
    cache_hit: bool = False


# ---------------------------------------------------------------------------
# Exceptions internes
# ---------------------------------------------------------------------------

class AllKeysCooldownError(Exception):
    """Levée quand toutes les clés Gemini sont en cooldown."""


# ---------------------------------------------------------------------------
# Cache LRU thread-safe
# ---------------------------------------------------------------------------

class _LRUCache:
    """Cache LRU en mémoire, TTL en secondes, thread-safe."""

    def __init__(self, max_entries: int = 64, ttl_seconds: float = 600.0):
        self._max = max(1, max_entries)
        self._ttl = max(1.0, float(ttl_seconds))
        self._store: Dict[str, Tuple[LLMResponse, float]] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()

    @staticmethod
    def _make_key(text: str, screen: str) -> str:
        norm = unicodedata.normalize("NFKD", text.lower().strip())
        norm = "".join(c for c in norm if not unicodedata.combining(c))
        norm = re.sub(r"[^\w\s-]", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        return f"{(screen or '').lower().strip()}::{norm}"

    def get(self, text: str, screen: str) -> Optional[LLMResponse]:
        key = self._make_key(text, screen)
        with self._lock:
            if key not in self._store:
                return None
            value, expire_at = self._store[key]
            if time.monotonic() > expire_at:
                del self._store[key]
                self._order.remove(key)
                return None
            self._order.remove(key)
            self._order.append(key)
            return value

    def put(self, text: str, screen: str, response: LLMResponse) -> None:
        key = self._make_key(text, screen)
        expire_at = time.monotonic() + self._ttl
        with self._lock:
            if key in self._store:
                self._order.remove(key)
            elif len(self._order) >= self._max:
                oldest = self._order.pop(0)
                self._store.pop(oldest, None)
            self._store[key] = (response, expire_at)
            self._order.append(key)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)


# ---------------------------------------------------------------------------
# Interface abstraite
# ---------------------------------------------------------------------------

class LLMBackendInterface:
    """Interface abstraite pour les fournisseurs d'inférence LLM."""

    def is_available(self, config: LLMConfig) -> bool:
        raise NotImplementedError

    def generate(self, prompt: str, config: LLMConfig) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Backend Gemini (rotation de clés round-robin)
# ---------------------------------------------------------------------------

class GeminiBackend(LLMBackendInterface):
    """Client HTTP natif (urllib) pour l'API Gemini avec rotation round-robin des clés.

    Sources des clés (par ordre de priorité, dédupliquées) :
      - `api_keys` passé au constructeur (utile pour les tests)
      - Variables `GEMINI_API_KEY_1` .. `GEMINI_API_KEY_20`
      - Variable `GEMINI_API_KEYS` (liste séparée par des virgules)
      - Variable `GEMINI_API_KEY` (clé unique)

    En cas de HTTP 429 (quota atteint), la clé fautive est placée en cooldown
    (`config.gemini_cooldown_sec`, 60 s par défaut) et la boucle essaie
    immédiatement les autres clés disponibles. Si TOUTES les clés sont en
    cooldown, lève `AllKeysCooldownError`.
    """

    _GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_keys: Optional[List[str]] = None):
        # Liste de [api_key_str, cooldown_until_monotonic]
        self._keys: List[List[Any]] = []
        self._keys_lock = threading.Lock()
        self._current_index: int = 0
        self._last_backend: str = ""
        if api_keys is not None:
            cleaned = [k.strip() for k in api_keys if k and k.strip()]
            self._keys = [[k, 0.0] for k in dict.fromkeys(cleaned)]
        else:
            self._load_keys()

    def _load_keys(self) -> None:
        """Charge les clés API depuis l'environnement."""
        collected: List[str] = []
        for i in range(1, 21):
            k = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
            if k:
                collected.append(k)
        csv_keys = os.environ.get("GEMINI_API_KEYS", "").strip()
        if csv_keys:
            for k in csv_keys.split(","):
                k = k.strip()
                if k:
                    collected.append(k)
        if not collected:
            single = os.environ.get("GEMINI_API_KEY", "").strip()
            if single:
                collected.append(single)

        unique_keys = list(dict.fromkeys(collected))
        self._keys = [[k, 0.0] for k in unique_keys]
        if unique_keys:
            logger.info(f"[LLM] GeminiBackend : {len(unique_keys)} clé(s) API chargée(s).")
        else:
            logger.info("[LLM] GeminiBackend : aucune clé GEMINI_API_KEY_N configurée.")

    def reload_keys(self) -> None:
        """Recharge les clés depuis l'environnement sans redémarrer le nœud."""
        with self._keys_lock:
            self._current_index = 0
            self._load_keys()

    @property
    def key_count(self) -> int:
        with self._keys_lock:
            return len(self._keys)

    def available_key_count(self) -> int:
        now = time.monotonic()
        with self._keys_lock:
            return sum(1 for _, cd in self._keys if now >= cd)

    def _get_available_key(self) -> Optional[Tuple[int, str]]:
        """Retourne (index, key_str) de la prochaine clé disponible (round-robin).
        Retourne None si toutes les clés sont en cooldown ou aucune clé."""
        now = time.monotonic()
        with self._keys_lock:
            n = len(self._keys)
            if n == 0:
                return None
            for offset in range(n):
                idx = (self._current_index + offset) % n
                key, cooldown_until = self._keys[idx]
                if now >= cooldown_until:
                    self._current_index = (idx + 1) % n
                    return idx, key
        return None

    def _set_cooldown(self, idx: int, seconds: float) -> None:
        with self._keys_lock:
            if 0 <= idx < len(self._keys):
                self._keys[idx][1] = time.monotonic() + seconds

    def cooldown_status(self) -> str:
        """Retourne une chaîne lisible de l'état des cooldowns (sans exposer les clés)."""
        now = time.monotonic()
        with self._keys_lock:
            if not self._keys:
                return "aucune clé"
            parts = []
            for i, (_, cd) in enumerate(self._keys):
                remaining = cd - now
                if remaining > 0:
                    parts.append(f"clé#{i + 1} pause {remaining:.0f}s")
                else:
                    parts.append(f"clé#{i + 1} OK")
            return ", ".join(parts)

    def is_available(self, config: LLMConfig) -> bool:
        return self.available_key_count() > 0

    def _build_request_bytes(self, user_prompt: str, config: LLMConfig) -> bytes:
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{config.system_prompt}\n\nMessage patient: {user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": config.temperature,
                "maxOutputTokens": config.max_tokens,
            },
        }
        return json.dumps(body).encode("utf-8")

    def generate(self, user_prompt: str, config: LLMConfig) -> str:
        """Appelle l'API Gemini en tournant sur les clés disponibles.

        Lève `AllKeysCooldownError` si aucune clé n'est disponible ou si toutes
        les clés actives renvoient HTTP 429.
        """
        n_keys = self.key_count
        if n_keys == 0:
            raise AllKeysCooldownError("Aucune clé API Gemini configurée.")

        data = self._build_request_bytes(user_prompt, config)
        tried_indices: set = set()
        switched_from: Optional[int] = None

        for _ in range(n_keys):
            result = self._get_available_key()
            if result is None:
                raise AllKeysCooldownError("Toutes les clés Gemini sont en cooldown.")

            idx, api_key = result
            if idx in tried_indices:
                raise AllKeysCooldownError("Toutes les clés Gemini disponibles ont déjà échoué.")
            tried_indices.add(idx)

            url = (
                f"{self._GEMINI_BASE}/{config.gemini_model}:generateContent"
                f"?key={api_key}"
            )
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=config.gemini_timeout_sec) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                    text = (
                        raw.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    self._last_backend = f"gemini_key#{idx + 1}"
                    if switched_from is not None:
                        logger.info(
                            f"[LLM] Key#{switched_from + 1} cooldown, bascule → key#{idx + 1} OK"
                        )
                    else:
                        logger.debug(f"[LLM] Gemini key#{idx + 1} OK → {text[:80]}")
                    return text

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    logger.warning(
                        f"[LLM] Key#{idx + 1} quota atteint (HTTP 429) → "
                        f"cooldown {config.gemini_cooldown_sec}s"
                    )
                    self._set_cooldown(idx, config.gemini_cooldown_sec)
                    switched_from = idx
                    continue
                if e.code in (401, 403):
                    # Clé révoquée ou invalide : mise en pause longue pour ne pas bloquer les autres
                    logger.warning(
                        f"[LLM] Key#{idx + 1} refusée (HTTP {e.code}) → pause 300s"
                    )
                    self._set_cooldown(idx, 300.0)
                    switched_from = idx
                    continue
                raise

        raise AllKeysCooldownError("Toutes les clés Gemini sont en cooldown.")


# ---------------------------------------------------------------------------
# Backend Ollama (Qwen local)
# ---------------------------------------------------------------------------

class OllamaBackend(LLMBackendInterface):
    """Client HTTP natif ultra-léger pour Ollama."""

    def __init__(self):
        self._last_backend: str = "qwen_local"

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
            self._last_backend = "qwen_local"
            return body.get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Backend llama.cpp
# ---------------------------------------------------------------------------

class LlamaCppBackend(LLMBackendInterface):
    """Client HTTP natif pour llama-server / llama.cpp."""

    def __init__(self):
        self._last_backend: str = "llama_cpp"

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


# ---------------------------------------------------------------------------
# Backend Hybride Gemini (primaire) + Qwen (fallback)
# ---------------------------------------------------------------------------

class HybridGeminiQwenBackend(LLMBackendInterface):
    """Gemini API en primaire, Qwen Ollama en fallback automatique.

    Flux :
      1. Clés Gemini dispo → appel Gemini (avec rotation round-robin)
      2. AllKeysCooldownError ou erreur réseau/timeout → bascule sur Qwen local
      3. Si Qwen échoue aussi → propage l'erreur au moteur (qui laisse place au filet déterministe)
    """

    def __init__(
        self,
        gemini: Optional[GeminiBackend] = None,
        ollama: Optional[OllamaBackend] = None,
    ):
        self.gemini = gemini or GeminiBackend()
        self.ollama = ollama or OllamaBackend()
        self._last_backend: str = ""

    def is_available(self, config: LLMConfig) -> bool:
        return self.gemini.is_available(config) or self.ollama.is_available(config)

    def generate(self, user_prompt: str, config: LLMConfig) -> str:
        fallback_reason = "qwen_local_no_keys"

        if self.gemini.key_count > 0:
            try:
                text = self.gemini.generate(user_prompt, config)
                self._last_backend = self.gemini._last_backend or "gemini_key#1"
                return text
            except AllKeysCooldownError:
                n_keys = self.gemini.key_count
                logger.warning(
                    f"[LLM] Toutes les clés Gemini ({n_keys}) en pause → secours Qwen local"
                )
                fallback_reason = "qwen_local_all_cooldown"
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                logger.warning(f"[LLM] Gemini réseau/timeout → secours Qwen local : {e}")
                fallback_reason = "qwen_local_network_error"
            except Exception as e:
                logger.warning(f"[LLM] Gemini erreur inattendue → secours Qwen local : {e}")
                fallback_reason = "qwen_local_error"
        else:
            logger.debug("[LLM] Aucune clé Gemini configurée → Qwen local direct")

        # Fallback Qwen local
        text = self.ollama.generate(user_prompt, config)
        self._last_backend = fallback_reason
        return text


# ---------------------------------------------------------------------------
# Backend Mock (tests unitaires)
# ---------------------------------------------------------------------------

class MockBackend(LLMBackendInterface):
    """Backend simulé pour les tests unitaires déconnectés."""

    def __init__(self, canned_responses: Optional[Dict[str, str]] = None):
        self.canned_responses = canned_responses or {}
        self.available = True
        self._last_backend = "mock"

    @staticmethod
    def _norm(text: str) -> str:
        nfkd = unicodedata.normalize("NFKD", text.lower())
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def is_available(self, config: LLMConfig) -> bool:
        return self.available

    def generate(self, user_prompt: str, config: LLMConfig) -> str:
        norm = self._norm(user_prompt)
        for pattern, response in self.canned_responses.items():
            if self._norm(pattern) in norm:
                return response

        if any(w in norm for w in ["medicament", "comprime", "aspirine", "ordonnance", "pharmacie"]):
            return json.dumps({
                "intent": "ORIENTATION",
                "target": "PHARMACY",
                "text_to_speak": "Je vous guide vers la pharmacie pour vos médicaments.",
                "screen": "orientation",
            })
        if any(w in norm for w in ["prise de sang", "sang", "biologie", "analyse", "laboratoire", "labo"]):
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
        if any(w in norm for w in [
            "qui es-tu", "tu es qui", "qui etes-vous", "vous etes qui",
            "presente-toi", "ton nom", "bonjour",
        ]):
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


# ---------------------------------------------------------------------------
# Moteur central
# ---------------------------------------------------------------------------

class LLMIntentEngine:
    """Moteur central d'analyse et classification d'intentions vocales.

    Flux d'appel de infer() :
      1. Cache LRU (hit → retour immédiat <1ms, zéro quota)
      2. Backend sélectionné (Gemini rotatif → Qwen local)
      3. Mise en cache du résultat réussi (hors écran consultation)
    """

    # Écrans de consultation → ne pas mettre en cache (données personnelles/étapes)
    _NO_CACHE_SCREENS = {"consultation"}

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
        elif self.config.backend == "gemini":
            self._backend = GeminiBackend()
        elif self.config.backend == "hybrid_gemini_qwen":
            self._backend = HybridGeminiQwenBackend()
        elif self.config.backend == "llama_cpp":
            self._backend = LlamaCppBackend()
        else:
            self._backend = OllamaBackend()

        self._cache = _LRUCache(
            max_entries=self.config.cache_max_entries,
            ttl_seconds=self.config.cache_ttl_min * 60,
        )
        self._last_availability_check = 0.0
        self._is_available_cached = False
        self._qwen_warmed = False

    def is_available(self) -> bool:
        """Vérifie si le backend LLM est joignable (mis en cache 5 s)."""
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

    def prewarm_local_fallback(self) -> Dict[str, Any]:
        """Pré-charge Qwen 2.5 en RAM (Option 2 : secours immédiat) sans consommer de quota Gemini."""
        ollama: Optional[OllamaBackend] = None
        if isinstance(self._backend, HybridGeminiQwenBackend):
            ollama = self._backend.ollama
        elif isinstance(self._backend, OllamaBackend):
            ollama = self._backend

        if ollama is None:
            return {"qwen_available": False, "warmed": False, "latency_ms": 0.0}

        if not ollama.is_available(self.config):
            self._qwen_warmed = False
            return {"qwen_available": False, "warmed": False, "latency_ms": 0.0}

        start = time.time()
        try:
            ollama.generate("Bonjour robot", self.config)
            latency_ms = (time.time() - start) * 1000.0
            self._qwen_warmed = True
            return {"qwen_available": True, "warmed": True, "latency_ms": latency_ms}
        except Exception as exc:
            latency_ms = (time.time() - start) * 1000.0
            self._qwen_warmed = False
            return {
                "qwen_available": True,
                "warmed": False,
                "latency_ms": latency_ms,
                "error": str(exc),
            }

    def get_diagnostics_status(self) -> Tuple[str, str]:
        """Retourne (status, detail) pour les diagnostics temps réel du mobile."""
        if not self.config.enabled:
            return "offline", "Désactivé"

        b = self._backend
        if isinstance(b, HybridGeminiQwenBackend):
            total_keys = b.gemini.key_count
            avail_keys = b.gemini.available_key_count()
            qwen_ok = b.ollama.is_available(self.config)
            qwen_tag = "Qwen secours prêt" if qwen_ok else "Qwen hors ligne"

            if total_keys > 0 and avail_keys == total_keys:
                return "ok", f"Gemini actif ({total_keys} clé(s)) + {qwen_tag}"
            if total_keys > 0 and avail_keys > 0:
                cooling = total_keys - avail_keys
                return "ok", f"Gemini ({avail_keys}/{total_keys} clés, {cooling} en pause) + {qwen_tag}"
            if total_keys > 0 and avail_keys == 0:
                if qwen_ok:
                    return "warn", f"Qwen local (Gemini {total_keys}/{total_keys} en pause)"
                return "offline", "Gemini en pause et Qwen hors ligne"
            # Aucune clé Gemini configurée
            if qwen_ok:
                return "ok", "Qwen local actif (aucune clé Gemini)"
            return "offline", "Aucune clé Gemini et Ollama indisponible"

        if isinstance(b, GeminiBackend):
            total_keys = b.key_count
            avail_keys = b.available_key_count()
            if total_keys == 0:
                return "offline", "Aucune clé Gemini configurée"
            if avail_keys > 0:
                return "ok", f"Gemini seul ({avail_keys}/{total_keys} clé(s) actives)"
            return "warn", f"Gemini en pause ({b.cooldown_status()})"

        if isinstance(b, OllamaBackend):
            if b.is_available(self.config):
                return "ok", f"Qwen local ({self.config.model_name})"
            return "offline", "Ollama indisponible"

        if isinstance(b, MockBackend):
            return "ok", "Mock (tests)"

        return "ok" if self.is_available() else "offline", self.config.backend

    def get_backend_status(self) -> str:
        """Retourne uniquement la description lisible du backend."""
        return self.get_diagnostics_status()[1]

    def infer(self, user_text: str, current_screen: str = "") -> LLMResponse:
        """Effectue l'inférence sur le texte utilisateur.

        Args:
            user_text: texte vocal transcrit.
            current_screen: écran actif dans le mobile (ex. "home", "orientation", "consultation").
        """
        clean_text = user_text.strip()
        if not clean_text:
            return LLMResponse(intent="UNKNOWN", error="Empty input", success=False)
        if not self.config.enabled:
            return LLMResponse(intent="UNKNOWN", error="LLM disabled in config", success=False)

        screen_norm = (current_screen or "").lower().strip()

        # 1. Cache LRU (sauf écrans de consultation)
        use_cache = screen_norm not in self._NO_CACHE_SCREENS
        if use_cache:
            cached = self._cache.get(clean_text, screen_norm)
            if cached is not None:
                logger.info(f"[LLM] ⚡ Cache hit (<1ms) pour : « {clean_text[:40]} »")
                return LLMResponse(
                    intent=cached.intent,
                    target=cached.target,
                    text_to_speak=cached.text_to_speak,
                    screen=cached.screen,
                    raw_reply=cached.raw_reply,
                    latency_ms=0.1,
                    success=True,
                    confidence=cached.confidence,
                    backend_used="cache",
                    cache_hit=True,
                )

        # Injection du contexte d'écran pour le LLM
        prompt_text = (
            f"[Écran actuel: {screen_norm}] {clean_text}" if screen_norm else clean_text
        )

        start_time = time.time()
        backend_used = self.config.backend
        try:
            raw_output = self._backend.generate(prompt_text, self.config)
            latency_ms = (time.time() - start_time) * 1000.0

            if hasattr(self._backend, "_last_backend") and self._backend._last_backend:
                backend_used = self._backend._last_backend

            self._log_inference(backend_used, latency_ms)

            parsed_data = self._clean_and_parse_json(raw_output)
            if not parsed_data:
                return LLMResponse(
                    intent="UNKNOWN",
                    raw_reply=raw_output,
                    latency_ms=latency_ms,
                    success=False,
                    error="JSON parse error",
                    backend_used=backend_used,
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

            response = LLMResponse(
                intent=intent,
                target=target,
                text_to_speak=text_to_speak,
                screen=screen,
                raw_reply=raw_output,
                latency_ms=latency_ms,
                success=True,
                backend_used=backend_used,
                cache_hit=False,
            )

            if use_cache and response.intent != "UNKNOWN":
                self._cache.put(clean_text, screen_norm, response)

            return response

        except AllKeysCooldownError as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.warning(f"[LLM] Toutes les clés Gemini en pause : {e}")
            return LLMResponse(
                intent="UNKNOWN",
                latency_ms=latency_ms,
                success=False,
                error=f"All Gemini keys on cooldown: {e}",
                backend_used="gemini_all_cooldown",
            )
        except urllib.error.URLError as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.warning(f"[LLM] Serveur LLM injoignable ({self.config.backend}): {e}")
            return LLMResponse(
                intent="UNKNOWN",
                latency_ms=latency_ms,
                success=False,
                error=f"Connection error: {e}",
                backend_used=backend_used,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.warning(f"[LLM] Erreur d'inférence: {e}")
            return LLMResponse(
                intent="UNKNOWN",
                latency_ms=latency_ms,
                success=False,
                error=f"Inference error: {e}",
                backend_used=backend_used,
            )

    def _log_inference(self, backend_used: str, latency_ms: float) -> None:
        if backend_used.startswith("gemini_key#"):
            logger.info(f"[LLM] ✅ {backend_used} OK ({latency_ms:.0f}ms)")
        elif "qwen_local" in backend_used or "cooldown" in backend_used:
            logger.info(
                f"[LLM] 🔄 Qwen local (secours) ({latency_ms:.0f}ms) [{backend_used}]"
            )
        elif backend_used == "mock":
            logger.debug(f"[LLM] 🧪 Mock backend ({latency_ms:.0f}ms)")
        else:
            logger.info(f"[LLM] Backend {backend_used} ({latency_ms:.0f}ms)")

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
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]

        try:
            return json.loads(text)
        except Exception:
            try:
                return json.loads(text.replace("'", '"'))
            except Exception:
                pass

        # Récupération robuste par regex si JSON tronqué
        salvaged: Dict[str, Any] = {}
        m = re.search(r'"intent"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        if m:
            salvaged["intent"] = m.group(1).upper()
        m = re.search(r'"target"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        if m:
            salvaged["target"] = m.group(1).upper()
        m = re.search(r'"text_to_speak"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"?', text)
        if m:
            salvaged["text_to_speak"] = m.group(1)
        m = re.search(r'"screen"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        if m:
            salvaged["screen"] = m.group(1).lower()

        if salvaged.get("intent") or salvaged.get("target"):
            return salvaged

        return None
