"""Pont WebSocket bidirectionnel HMI pour HIAR (Raspberry Pi 4 / ROS 2).

Ce nœud héberge le serveur WebSocket central (port 5000) et fait la passerelle entre :
- Les flux du smartphone (microphone STT, tactile UI)
- Le graphe ROS 2 (/hmi/request, /navigation/command, /vitals/request, etc.)
- La commande dynamique du mobile (server/instruction, voice/tts/request, robot/mission/status)
"""

import asyncio
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False

    class Node:  # type: ignore
        def __init__(self, node_name: str, **kwargs):
            self._node_name = node_name
            self._logger = logging.getLogger(node_name)

        def get_logger(self):
            return self._logger

        def declare_parameter(self, name, value=None):
            return value

        def get_parameter(self, name):
            class _Param:
                value = None
            p = _Param()
            p.value = "0.0.0.0" if "host" in name else 5000
            return p

        def create_publisher(self, msg_type, topic, qos):
            class _Pub:
                def __init__(self, t):
                    self.topic = t
                    self.published = []
                def publish(self, msg):
                    self.published.append(msg)
            return _Pub(topic)

        def create_subscription(self, msg_type, topic, cb, qos):
            class _Sub:
                def __init__(self, t, c):
                    self.topic = t
                    self.callback = c
            return _Sub(topic, cb)

        def destroy_node(self):
            pass

    class String:  # type: ignore
        def __init__(self, data: str = ""):
            self.data = data

try:
    from hospital_robot.voice_intent_parser import ParsedIntent, VoiceIntentParser, normalize_text
    from hospital_robot.vitals_data_parser import build_vitals_instruction, parse_vitals_frame
    from hospital_robot.llm_intent_engine import LLMConfig, load_dotenv_file
except ImportError:
    from voice_intent_parser import ParsedIntent, VoiceIntentParser, normalize_text
    from vitals_data_parser import build_vitals_instruction, parse_vitals_frame
    try:
        from llm_intent_engine import LLMConfig, load_dotenv_file
    except ImportError:
        LLMConfig = None  # type: ignore
        load_dotenv_file = None  # type: ignore

import websockets
try:
    from websockets.asyncio.server import ServerConnection as WSConnection
except ImportError:
    try:
        from websockets.server import WebSocketServerProtocol as WSConnection
    except ImportError:
        WSConnection = object  # type: ignore


def make_envelope(topic: str, payload: dict, msg_type: str = "pub") -> str:
    """Emballe un message selon le standard Envelope Protocol v4."""
    return json.dumps({
        "v": 1,
        "type": msg_type,
        "ts": int(time.time()),
        "topic": topic,
        "payload": payload,
        "qos": 1,
    })


class HMIWebSocketBridgeNode(Node):
    """Nœud ROS 2 et serveur WebSocket unifié pour le pilotage HMI."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        node_name: str = "hmi_websocket_bridge",
    ):
        super().__init__(node_name)

        # Charger .env si présent (GEMINI_API_KEY_1..N, HIAR_GEMINI_MODEL, ...)
        if load_dotenv_file is not None:
            env_loaded = load_dotenv_file()
            if env_loaded is not None:
                self.get_logger().info(f"[LLM] Variables chargées depuis {env_loaded}")

        default_backend = os.environ.get("HIAR_LLM_BACKEND", "hybrid_gemini_qwen").strip() or "hybrid_gemini_qwen"
        default_gemini_model = os.environ.get("HIAR_GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
        try:
            default_gemini_timeout = float(os.environ.get("HIAR_GEMINI_TIMEOUT", "8.0"))
        except ValueError:
            default_gemini_timeout = 8.0
        try:
            default_gemini_cooldown = int(os.environ.get("HIAR_GEMINI_COOLDOWN", "60"))
        except ValueError:
            default_gemini_cooldown = 60

        if ROS_AVAILABLE:
            self.declare_parameter("websocket_host", "0.0.0.0")
            self.declare_parameter("websocket_port", 5000)
            self.declare_parameter("enable_llm", True)
            self.declare_parameter("llm_backend", default_backend)
            self.declare_parameter("llm_host", "http://127.0.0.1:11434")
            self.declare_parameter("llm_model", "qwen2.5:0.5b")
            self.declare_parameter("llm_timeout", 15.0)
            self.declare_parameter("gemini_model", default_gemini_model)
            self.declare_parameter("gemini_timeout", default_gemini_timeout)
            self.declare_parameter("gemini_cooldown", default_gemini_cooldown)

            self.host = host or str(self.get_parameter("websocket_host").value)
            self.port = port or int(self.get_parameter("websocket_port").value)
            enable_llm = bool(self.get_parameter("enable_llm").value)
            llm_backend = str(self.get_parameter("llm_backend").value)
            llm_host = str(self.get_parameter("llm_host").value)
            llm_model = str(self.get_parameter("llm_model").value)
            llm_timeout = float(self.get_parameter("llm_timeout").value)
            gemini_model = str(self.get_parameter("gemini_model").value)
            gemini_timeout = float(self.get_parameter("gemini_timeout").value)
            gemini_cooldown = int(self.get_parameter("gemini_cooldown").value)
        else:
            self.host = host or "0.0.0.0"
            self.port = port or 5000
            enable_llm = True
            llm_backend = default_backend
            llm_host = "http://127.0.0.1:11434"
            llm_model = "qwen2.5:0.5b"
            llm_timeout = 15.0
            gemini_model = default_gemini_model
            gemini_timeout = default_gemini_timeout
            gemini_cooldown = default_gemini_cooldown

        # Composants de traitement métier (Sécurité locale → Cache → Gemini → Qwen → Déterministe)
        if LLMConfig is not None:
            llm_cfg = LLMConfig(
                enabled=enable_llm,
                backend=llm_backend,
                host=llm_host,
                model_name=llm_model,
                timeout_sec=llm_timeout,
                gemini_model=gemini_model,
                gemini_timeout_sec=gemini_timeout,
                gemini_cooldown_sec=gemini_cooldown,
            )
            self.intent_parser = VoiceIntentParser(enable_llm=enable_llm, llm_config=llm_cfg)
        else:
            self.intent_parser = VoiceIntentParser()

        # Préchauffage en arrière-plan de Qwen 2.5 en RAM (Option 2 : secours immédiat)
        self._llm_status: str = "offline"
        self._llm_detail: str = "Désactivé"
        self._llm_prewarming: bool = False
        if getattr(self.intent_parser, "enable_llm", False) and getattr(self.intent_parser, "llm_engine", None):
            engine = self.intent_parser.llm_engine
            self._llm_status, self._llm_detail = engine.get_diagnostics_status()
            self._llm_prewarming = True

            def _prewarm_llm():
                try:
                    time.sleep(1.0)
                    backend_obj = getattr(engine, "_backend", None)
                    gemini_keys = getattr(getattr(backend_obj, "gemini", backend_obj), "key_count", 0)
                    if gemini_keys > 0:
                        self.get_logger().info(
                            f"[LLM] ☁️ Gemini API primaire prêt ({gemini_keys} clé(s), modèle={engine.config.gemini_model})."
                        )
                    else:
                        self.get_logger().info(
                            "[LLM] ℹ️ Aucune clé GEMINI_API_KEY_N dans .env — fonctionnement sur Qwen local."
                        )

                    self.get_logger().info("[LLM] 🔥 Pré-chauffage secours Qwen 2.5 en RAM...")
                    res = engine.prewarm_local_fallback()
                    if res.get("warmed"):
                        self.get_logger().info(
                            f"[LLM] ✅ Qwen 2.5 secours prêt en RAM ({res.get('latency_ms', 0.0):.0f}ms)."
                        )
                    elif res.get("qwen_available"):
                        self.get_logger().warning(
                            f"[LLM] ⚠️ Pré-chauffage Qwen 2.5 partiel : {res.get('error', 'timeout')}"
                        )
                    else:
                        self.get_logger().info("[LLM] ℹ️ Ollama (Qwen secours) non démarré localement.")
                except Exception as ex:
                    self.get_logger().warning(f"[LLM] Pre-warm warning: {ex}")
                finally:
                    self._llm_prewarming = False
                    self._llm_status, self._llm_detail = engine.get_diagnostics_status()

            threading.Thread(target=_prewarm_llm, daemon=True).start()

        self._pending_orientation: Optional[Dict[str, Any]] = None
        self._active_destination_label: Optional[str] = None
        self._current_screen: str = "home"
        self._current_step: int = 1
        self._current_consultation_data: Dict[str, Any] = {}
        self._last_ticket_label: Optional[str] = None
        self._last_stt_text = ""
        self._last_stt_time = 0.0
        self._esp32_diagnostics: Optional[Dict[str, Any]] = None
        self._esp32_diagnostics_at: float = 0.0

        # Clients WebSocket connectés
        self.ws_clients: Set[WSConnection] = set()
        self._diagnostics_subscribers: Set[WSConnection] = set()
        self._ws_clients_lock = threading.Lock()

        # Gestion Asyncio & Serveur
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.server = None
        self._server_thread: Optional[threading.Thread] = None
        self._discovery_thread: Optional[threading.Thread] = None
        self.discovery_port: int = 5005
        self._stop_event = threading.Event()

        # ----------------------------------------------------
        # Publications ROS 2
        # ----------------------------------------------------
        self.hmi_request_pub = self.create_publisher(String, "/hmi/request", 10)
        self.navigation_command_pub = self.create_publisher(String, "/navigation/command", 10)
        self.vitals_request_pub = self.create_publisher(String, "/vitals/request", 10)
        self.diagnostics_request_pub = self.create_publisher(String, "/esp32/diagnostics/request", 10)

        # ----------------------------------------------------
        # Souscriptions ROS 2
        # ----------------------------------------------------
        self.robot_status_sub = self.create_subscription(
            String, "/robot/status", self._on_robot_status, 10
        )
        self.navigation_status_sub = self.create_subscription(
            String, "/navigation/status", self._on_navigation_status, 10
        )
        self.vitals_result_sub = self.create_subscription(
            String, "/vitals/result", self._on_vitals_result, 10
        )
        self.obstacle_sub = self.create_subscription(
            String, "/sensors/obstacle", self._on_obstacle, 10
        )
        self.esp32_diagnostics_sub = self.create_subscription(
            String, "/esp32/diagnostics", self._on_esp32_diagnostics, 10
        )

        self.get_logger().info(
            f"HMI WebSocket Bridge initialized. Binding to {self.host}:{self.port}..."
        )

    # ========================================================
    # GESTION DU CYCLE DE VIE SERVEUR
    # ========================================================

    def start_websocket_server(self):
        """Démarre le serveur WebSocket dans un thread asyncio dédié."""
        if self._server_thread is not None and self._server_thread.is_alive():
            return

        self._stop_event.clear()
        ready_event = threading.Event()

        def _thread_target():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            async def _start():
                self.server = await websockets.serve(
                    self._handle_client,
                    self.host,
                    self.port,
                    ping_interval=15,
                    ping_timeout=10,
                )
                self.get_logger().info(
                    f"WebSocket server listening on ws://{self.host}:{self.port}/ws"
                )
                self.loop.create_task(self._diagnostics_broadcast_loop())
                ready_event.set()

            self.loop.create_task(_start())
            self.loop.run_forever()

            # Nettoyage à l'arrêt
            if self.server:
                self.server.close()
                self.loop.run_until_complete(self.server.wait_closed())
            self.loop.close()

        self._server_thread = threading.Thread(
            target=_thread_target,
            name="hiar-ws-server",
            daemon=True,
        )
        self._server_thread.start()
        ready_event.wait(timeout=5.0)

        # Lancer la balise de découverte UDP sur le réseau local / Wi-Fi
        if self.host != "127.0.0.1":
            self._start_discovery_beacon()

    def _collect_network_info(self) -> Tuple[str, List[str], List[str]]:
        """Retourne (ip_principale, toutes_ips, cibles_broadcast_udp)."""
        wlan_ips: List[str] = []
        other_ips: List[str] = []
        targets: Set[str] = {"255.255.255.255"}

        try:
            out = subprocess.check_output(
                ["ip", "-4", "-o", "addr", "show"],
                text=True,
                timeout=2.0,
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 4:
                    continue
                iface = parts[1]
                if iface == "lo":
                    continue
                ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", line)
                if ip_match:
                    ip_addr = ip_match.group(1)
                    if iface.startswith("wl"):
                        wlan_ips.append(ip_addr)
                    else:
                        other_ips.append(ip_addr)
                brd_match = re.search(r"brd\s+(\d+\.\d+\.\d+\.\d+)", line)
                if brd_match:
                    targets.add(brd_match.group(1))
        except Exception:
            pass

        # Ajouter la passerelle Wi-Fi (ex: 192.168.43.1 si le téléphone partage sa connexion)
        try:
            route_out = subprocess.check_output(
                ["ip", "-4", "route", "show"],
                text=True,
                timeout=2.0,
            )
            for line in route_out.splitlines():
                if "default via" in line and "wl" in line:
                    gw_match = re.search(r"default via\s+(\d+\.\d+\.\d+\.\d+)", line)
                    if gw_match:
                        targets.add(gw_match.group(1))
        except Exception:
            pass

        all_ips = wlan_ips + other_ips
        primary_ip = all_ips[0] if all_ips else "127.0.0.1"
        return primary_ip, all_ips, sorted(targets)

    def _build_discovery_payload(self) -> bytes:
        primary_ip, all_ips, _ = self._collect_network_info()
        payload = {
            "service": "hiar_robot",
            "hostname": socket.gethostname(),
            "ip": primary_ip,
            "ips": all_ips,
            "ws_port": self.port,
            "web_port": 5001,
        }
        return json.dumps(payload).encode("utf-8")

    def _start_discovery_beacon(self):
        """Démarre un répondeur + diffuseur UDP (port 5005) pour auto-découverte Wi-Fi par le mobile."""
        if self._discovery_thread is not None and self._discovery_thread.is_alive():
            return

        def _beacon_loop():
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind(("0.0.0.0", self.discovery_port))
                sock.settimeout(0.5)
                self.get_logger().info(
                    f"📡 Balise de découverte Wi-Fi UDP active sur le port {self.discovery_port}"
                )
            except Exception as err:
                self.get_logger().warning(f"Impossible de démarrer la balise UDP {self.discovery_port}: {err}")
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                return

            last_broadcast = 0.0
            try:
                while not self._stop_event.is_set():
                    now = time.monotonic()
                    if now - last_broadcast >= 2.0:
                        last_broadcast = now
                        _, _, targets = self._collect_network_info()
                        data = self._build_discovery_payload()
                        for target in targets:
                            try:
                                sock.sendto(data, (target, self.discovery_port))
                            except Exception:
                                pass

                    try:
                        msg, addr = sock.recvfrom(1024)
                        if b"HIAR_DISCOVER" in msg:
                            sock.sendto(self._build_discovery_payload(), addr)
                    except socket.timeout:
                        continue
                    except Exception:
                        continue
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

        self._discovery_thread = threading.Thread(
            target=_beacon_loop,
            name="hiar-udp-discovery",
            daemon=True,
        )
        self._discovery_thread.start()

    def stop_websocket_server(self):
        """Arrête proprement le serveur WebSocket et la boucle asyncio."""
        self._stop_event.set()
        if self._discovery_thread and self._discovery_thread.is_alive():
            self._discovery_thread.join(timeout=2.0)
            self._discovery_thread = None
        if self.loop and self.loop.is_running():
            with self._ws_clients_lock:
                for ws in list(self.ws_clients):
                    try:
                        asyncio.run_coroutine_threadsafe(ws.close(), self.loop)
                    except Exception:
                        pass
                self.ws_clients.clear()

            self.loop.call_soon_threadsafe(self.loop.stop)

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=3.0)
            self._server_thread = None

    # ========================================================
    # GESTION DES CLIENTS ET DES MESSAGES WEBSOCKET
    # ========================================================

    async def _handle_client(self, websocket: WSConnection):
        """Gère une connexion client mobile active."""
        with self._ws_clients_lock:
            self.ws_clients.add(websocket)
        self.get_logger().info(f"[MOBILE] Client connecté: {websocket.remote_address}")

        try:
            # Envoi du message welcome
            welcome_msg = make_envelope(
                "connection/welcome",
                {
                    "server": "HIAR Central ROS2 Bridge",
                    "version": "1.0.0",
                    "status": "ready",
                },
                msg_type="welcome",
            )
            await websocket.send(welcome_msg)

            async for raw_message in websocket:
                await self._process_incoming_frame(websocket, raw_message)

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as exc:
            self.get_logger().warning(f"[MOBILE] Erreur client {websocket.remote_address}: {exc}")
        finally:
            with self._ws_clients_lock:
                self.ws_clients.discard(websocket)
                self._diagnostics_subscribers.discard(websocket)
            self.get_logger().info(f"[MOBILE] Client déconnecté: {websocket.remote_address}")

    async def _process_incoming_frame(
        self, websocket: WSConnection, raw_message: str
    ):
        """Traite une enveloppe JSON entrante."""
        try:
            data = json.loads(raw_message)
        except Exception:
            return

        msg_type = data.get("type", "pub")
        topic = data.get("topic", "")
        payload = data.get("payload", {})

        # Réponse au heartbeat ping
        if msg_type == "ping":
            pong = json.dumps({"v": 1, "type": "pong", "ts": int(time.time())})
            await websocket.send(pong)
            return

        if msg_type == "hello":
            self.get_logger().info(
                f"[MOBILE] Handshake hello: device={data.get('device_id', 'mobile')} role={data.get('role', 'kiosk')}"
            )
            welcome = make_envelope(
                "connection/welcome",
                {"server": "HIAR Central ROS2 Bridge", "status": "ready"},
                msg_type="welcome",
            )
            await websocket.send(welcome)
            return

        if msg_type == "sub":
            if topic == "robot/diagnostics":
                with self._ws_clients_lock:
                    self._diagnostics_subscribers.add(websocket)
                diag_env = make_envelope("robot/diagnostics", self.build_system_diagnostics())
                try:
                    await websocket.send(diag_env)
                except Exception:
                    pass
            return

        # Publications entrantes du smartphone
        if topic == "voice/stt/final":
            await self._handle_voice_stt(payload)

        elif topic == "ui/action/request":
            await self._handle_ui_action(payload)

        elif topic == "mobile/log":
            level = str(payload.get("level", "INFO")).upper()
            msg_text = str(payload.get("message", "")).strip()
            if msg_text:
                if level == "ERROR":
                    self.get_logger().error(f"[MOBILE] {msg_text}")
                elif level in {"WARN", "WARNING"}:
                    self.get_logger().warning(f"[MOBILE] {msg_text}")
                else:
                    self.get_logger().info(f"[MOBILE] {msg_text}")

        elif topic == "ui/state":
            screen = payload.get("screen")
            step = payload.get("step")
            if screen:
                self._current_screen = str(screen)
            if step is not None:
                try:
                    self._current_step = int(step)
                except (ValueError, TypeError):
                    pass
            if isinstance(payload.get("consultation_data"), dict):
                self._current_consultation_data.update(payload["consultation_data"])
            self.get_logger().info(f"[MOBILE] Écran actif: screen={self._current_screen} step={self._current_step}")

    # ========================================================
    # LOGIQUE VOCALE & INTENTS
    # ========================================================

    async def _handle_voice_stt(self, payload: Dict):
        """Traite la parole transcrite par le microphone du smartphone."""
        text = payload.get("text", "")
        confidence = float(payload.get("confidence", payload.get("conf", 1.0)))

        if not text:
            return

        norm_incoming = normalize_text(text)

        # 0. Anti-rebond temporel (doublon Android STT émis à < 2.5s)
        now = time.time()
        if norm_incoming == self._last_stt_text and (now - self._last_stt_time) < 2.5:
            self.get_logger().info(f"[MOBILE] ⏩ Doublon STT ignoré: '{text}' (elapsed={now - self._last_stt_time:.2f}s)")
            return
        self._last_stt_text = norm_incoming
        self._last_stt_time = now
        self.get_logger().info(f"[MOBILE] 🎤 Voix STT: \"{text}\" (conf={confidence:.2f})")

        # Analyse et classification d'intention (avec contexte écran courant)
        intent = self.intent_parser.parse(
            text,
            confidence=confidence,
            current_screen=self._current_screen,
        )

        # Filtrage des fragments isolés ("je", "le", etc.) : on attend la suite sans parler
        if intent.intent_type == "IGNORED_FRAGMENT":
            self.get_logger().info(f"Silently ignored fragment: '{text}'")
            return

        is_llm = bool(intent.details.get("llm_generated", False))
        is_cache = bool(intent.details.get("cache_hit", False))
        backend_used = str(intent.details.get("backend_used", ""))
        latency_ms = float(intent.details.get("latency_ms", 0.0))
        model = str(intent.details.get("model", "qwen2.5:0.5b"))

        if is_cache:
            engine_str = "⚡ Cache LRU local (Zéro quota | Latence: <1ms)"
        elif is_llm and backend_used.startswith("gemini"):
            engine_str = f"☁️ Gemini API {model} ({backend_used} | Latence: {latency_ms:.0f}ms)"
        elif is_llm:
            engine_str = f"🧠 Qwen local {model} ({backend_used or 'ollama'} | Latence: {latency_ms:.0f}ms)"
        elif intent.intent_type == "STOP":
            engine_str = "🛑 Réflexe Sécurité Local (STOP prioritaire | Latence: <1ms)"
        elif intent.intent_type != "UNKNOWN":
            engine_str = "⚙️ Filet Déterministe (Regex local | Latence: <1ms)"
        else:
            engine_str = f"❓ Non reconnu / Hors périmètre (Inconnu | Latence: {latency_ms:.0f}ms)"

        # 1. Action ROS 2 Navigation Command (ex: STOP, RESUME, HOME)
        if intent.ros_command:
            self._publish_navigation_command(intent.ros_command)

        # 2. Gestion de l'orientation vocale avec confirmation obligatoire
        confirmed_dest_label = None
        if intent.intent_type == "ORIENTATION":
            dest_key = intent.target_value or "PHARMACY"
            dest_label = intent.label or self.intent_parser.DEPARTMENTS.get(dest_key, {}).get("label", dest_key)
            self._pending_orientation = {
                "destination": dest_key,
                "label": dest_label,
                "ros_request": intent.ros_request or {"category": "ORIENTATION", "destination": dest_key},
            }
            self.get_logger().info(f"⏸️ [ORIENTATION EN ATTENTE] Destination : {dest_label} ({dest_key}). En attente de confirmation vocale (Oui/Non).")

        elif intent.intent_type == "CONFIRM_YES":
            if self._pending_orientation:
                req = self._pending_orientation.get("ros_request")
                confirmed_dest_label = self._pending_orientation.get("label", "votre destination")
                self.get_logger().info(f"✅ [ORIENTATION CONFIRMÉE] Guidage validé vers {confirmed_dest_label} ! Publication sur /hmi/request.")
                self._pending_orientation = None
                self._active_destination_label = confirmed_dest_label
                if req:
                    self._publish_hmi_request(req)
                intent.label = confirmed_dest_label
            elif self._current_screen == "consultation" and self._current_step == 5:
                self.get_logger().info("✅ [CONSULTATION CONFIRMÉE] Confirmation vocale à l'étape 5, réservation en base !")
                await self._handle_ui_action({
                    "action_id": "consult.confirm",
                    "args": self._current_consultation_data,
                })
                return
            else:
                self.get_logger().info("ℹ️ Confirmation reçue sans action en attente.")

        elif intent.intent_type == "CONFIRM_NO":
            if self._pending_orientation:
                cancelled_label = self._pending_orientation.get("label", "")
                self.get_logger().info(f"🚫 [ORIENTATION ANNULÉE] Guidage vers {cancelled_label} annulé par l'utilisateur.")
                self._pending_orientation = None
            elif self._current_screen == "consultation":
                self.get_logger().info("🚫 [CONSULTATION ANNULÉE] Annulation vocale par l'utilisateur.")
                await self._handle_ui_action({"action_id": "consult.cancel", "args": {}})
                cancel_instruction = {
                    "origin": "voice",
                    "text_to_speak": "Consultation annulée. Retour à l'accueil.",
                    "speech_priority": "normal",
                    "instruction_ui": {"screen": "home", "require_confirmation": False},
                    "robot_status": {"face_expression": "neutral", "status_label": "Robot prêt"},
                }
                await self.broadcast("server/instruction", cancel_instruction)
                await self.broadcast("voice/tts/request", {"text": cancel_instruction["text_to_speak"], "priority": "normal"})
                return
            else:
                self.get_logger().info("ℹ️ Annulation reçue sans action en attente.")

        elif self._current_screen == "consultation" and self._current_step == 5 and intent.intent_type == "CONSULTATION_STEP" and (intent.target_value or "next") == "next":
            self.get_logger().info("✅ [CONSULTATION ÉTAPE 5] Suivant/Valider reçu vocalement, réservation en base !")
            await self._handle_ui_action({
                "action_id": "consult.confirm",
                "args": self._current_consultation_data,
            })
            return

        # 2b. RÈGLE MÉTIER : la prise de mesure (VITALS) par vocal est INTERDITE hors étape 4 de Consultation.
        # L'utilisateur est redirigé vers la consultation d'abord.
        vitals_blocked_redirect = False
        if intent.intent_type == "VITALS" and not (
            self._current_screen == "consultation" and self._current_step == 4
        ):
            vitals_blocked_redirect = True
            target_step = (
                self._current_step
                if (self._current_screen == "consultation" and 1 <= self._current_step <= 3)
                else 1
            )
            self._current_screen = "consultation"
            self._current_step = target_step
            self.get_logger().info(
                f"🚫 [RÈGLE CONSULTATION] Mesure vocale bloquée hors étape 4 → redirection vers consultation étape {target_step}."
            )
            redirect_speech = (
                "Veuillez d'abord compléter les étapes de votre consultation avant de prendre vos constantes."
                if target_step > 1
                else "Pour mesurer vos constantes vitales, vous devez d'abord passer par l'étape de consultation. Je vous y conduis."
            )
            instruction = {
                "origin": "voice",
                "text_to_speak": redirect_speech,
                "speech_priority": "normal",
                "instruction_ui": {
                    "screen": "consultation",
                    "step": target_step,
                    "require_confirmation": False,
                },
                "voice_hints": ["Suivant", "Annuler"],
                "robot_status": {
                    "face_expression": "speaking",
                    "status_label": "Consultation requise d'abord",
                },
            }
            if is_llm:
                instruction["llm_source"] = model
            await self.broadcast("server/instruction", instruction)
            await self.broadcast(
                "voice/tts/request",
                {"text": redirect_speech, "priority": "normal"},
            )
            return

        if intent.intent_type == "CONSULTATION":
            self._current_screen = "consultation"
            self._current_step = 1

        if intent.ros_request and intent.intent_type != "ORIENTATION":
            self._publish_hmi_request(intent.ros_request)

        # 3. Action ROS 2 Signes vitaux (uniquement autorisée à l'étape 4 de Consultation)
        vitals_id = None
        if intent.intent_type == "VITALS" and not vitals_blocked_redirect:
            vitals_id = str(uuid.uuid4())
            self._publish_vitals_request(vitals_id)

        # 4. Construction de l'instruction UI & TTS pour le mobile
        instruction = self.intent_parser.build_instruction(intent, text)
        tts_text = ""
        ui_screen = ""
        if instruction:
            if is_llm:
                instruction["llm_source"] = model
            if intent.intent_type == "FINISH":
                self._active_destination_label = None
            ui_block = instruction.get("instruction_ui")
            if isinstance(ui_block, dict) and ui_block.get("screen") == "mission":
                if not ui_block.get("destination") and self._active_destination_label:
                    ui_block["destination"] = self._active_destination_label
                    fields_block = instruction.setdefault("fields", {})
                    if isinstance(fields_block, dict) and not fields_block.get("destination"):
                        fields_block["destination"] = self._active_destination_label
            if intent.intent_type == "CONSULTATION_TICKET" and self._last_ticket_label:
                instruction["text_to_speak"] = f"Votre rendez-vous est confirmé. Voici votre ticket de passage numéro {self._last_ticket_label}."
                if "fields" in instruction:
                    instruction["fields"]["ticket_label"] = self._last_ticket_label
                if "robot_status" in instruction:
                    instruction["robot_status"]["status_label"] = f"Ticket {self._last_ticket_label}"
            tts_text = instruction.get("text_to_speak", "")
            ui_screen = instruction.get("instruction_ui", {}).get("screen") or instruction.get("screen", "")

            await self.broadcast("server/instruction", instruction)

            # Diffusion synchronisée sur le topic TTS dédié si texte à prononcer
            if tts_text:
                await self.broadcast(
                    "voice/tts/request",
                    {
                        "text": tts_text,
                        "priority": instruction.get("speech_priority", "normal"),
                    },
                )

        # Journalisation complète et structurée (Source -> Décision -> Récepteurs)
        self.get_logger().info("┌────────────────────────────────────────────────────────────────────────")
        self.get_logger().info(f"│ 🎤 [INTERACTION VOCALE]")
        self.get_logger().info(f"│ 📥 SOURCE       : Smartphone Android (Micro STT) [Confiance: {confidence * 100:.0f}%]")
        self.get_logger().info(f"│    Texte reçu   : « {text} »")
        self.get_logger().info(f"│ ⚙️ DÉCISION     : {engine_str}")
        self.get_logger().info(f"│    Intention    : {intent.intent_type} (Cible: {intent.target_value or intent.label or 'N/A'})")
        self.get_logger().info(f"│ 📤 RÉCEPTEURS   :")
        if tts_text:
            self.get_logger().info(f"│    📱 Mobile (TTS): « {tts_text} »")
        if ui_screen:
            self.get_logger().info(f"│    📱 Mobile (UI) : Affichage écran '{ui_screen}'")
        if intent.ros_command:
            self.get_logger().info(f"│    🤖 ROS 2 (Nav) : /navigation/command ➔ {intent.ros_command} (Nœuds: navigation_decision, supervisor)")
        if intent.intent_type == "ORIENTATION":
            self.get_logger().info(f"│    🤖 ROS 2 (HMI) : [EN ATTENTE] Aucun ordre moteur émis avant confirmation vocale.")
        elif intent.intent_type == "CONFIRM_YES" and confirmed_dest_label:
            self.get_logger().info(f"│    🤖 ROS 2 (HMI) : /hmi/request ➔ {req} (Nœud: hmi_request_receiver)")
        elif intent.intent_type == "CONFIRM_NO":
            self.get_logger().info(f"│    🤖 ROS 2 (HMI) : [ANNULÉ] Guidage annulé, robot reste à l'arrêt.")
        elif intent.ros_request:
            self.get_logger().info(f"│    🤖 ROS 2 (HMI) : /hmi/request ➔ {intent.ros_request} (Nœud: hmi_request_receiver)")
        if vitals_id:
            self.get_logger().info(f"│    🤖 ROS 2 (ESP) : /vitals/request ➔ {vitals_id} (Nœud: esp32_interface)")
        if not intent.ros_command and intent.intent_type not in ["ORIENTATION", "CONFIRM_YES"] and not intent.ros_request and not vitals_id:
            self.get_logger().info(f"│    🤖 ROS 2       : Aucun ordre moteur nécessaire")
        self.get_logger().info("└────────────────────────────────────────────────────────────────────────")

    # ========================================================
    # LOGIQUE TACTILE UI ACTION
    # ========================================================

    async def _handle_ui_action(self, payload: Dict):
        """Traite les actions tactiles provenant de l'écran du mobile."""
        action_id = payload.get("action_id", "")
        args = payload.get("args", {})

        self.get_logger().info(f"[MOBILE] 👆 Action tactile: {action_id} args={args}")

        if action_id == "orientation.pending":
            dest_key = (args.get("destination") or "PHARMACY").upper()
            dest_label = args.get("label") or self.intent_parser.DEPARTMENTS.get(dest_key, {}).get("label", dest_key)
            self._pending_orientation = {
                "destination": dest_key,
                "label": dest_label,
                "ros_request": {"category": "ORIENTATION", "destination": dest_key},
            }
            self.get_logger().info(
                f"⏸️ [ORIENTATION TACTILE EN ATTENTE] Destination : {dest_label} ({dest_key}). Attente confirmation."
            )

        elif action_id == "orientation.select":
            dest = args.get("destination", "").upper()
            if dest:
                self._active_destination_label = self.intent_parser.DEPARTMENTS.get(dest, {}).get("label", dest)
                self._publish_hmi_request({"category": "ORIENTATION", "destination": dest})

        elif action_id == "orientation.confirm":
            dest_key = args.get("destination")
            if not dest_key and self._pending_orientation:
                dest_key = self._pending_orientation.get("destination")
            dest_key = (dest_key or "PHARMACY").upper()
            dest_label = self.intent_parser.DEPARTMENTS.get(dest_key, {}).get("label", dest_key)
            self._pending_orientation = None
            self._active_destination_label = dest_label

            self._publish_hmi_request({"category": "ORIENTATION", "destination": dest_key})

            instruction = {
                "origin": "ui",
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
            await self.broadcast("server/instruction", instruction)
            await self.broadcast(
                "voice/tts/request",
                {"text": instruction["text_to_speak"], "priority": "normal"},
            )

        elif action_id == "orientation.cancel":
            self._pending_orientation = None
            instruction = {
                "origin": "ui",
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
            await self.broadcast("server/instruction", instruction)
            await self.broadcast(
                "voice/tts/request",
                {"text": instruction["text_to_speak"], "priority": "normal"},
            )

        elif action_id in {"vitals.acquire", "vitals.measure", "consult.measure_vitals"}:
            req_id = str(uuid.uuid4())
            self._publish_vitals_request(req_id)
            prompt_text = "Veuillez poser votre index sur le capteur de constantes et rester immobile."
            await self.broadcast(
                "server/instruction",
                {
                    "origin": "server",
                    "text_to_speak": prompt_text,
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
                        "vitals_state": "measuring",
                        "temperature": None,
                        "heart_rate": None,
                        "spo2": None,
                    },
                    "voice_hints": ["Annuler", "Suivant"],
                    "robot_status": {
                        "face_expression": "speaking",
                        "status_label": "Mesure des constantes en cours...",
                    },
                },
            )
            await self.broadcast(
                "voice/tts/request",
                {"text": prompt_text, "priority": "normal"},
            )

        elif action_id in {"robot.stop", "mission.stop", "navigation.cancel"}:
            self._publish_navigation_command("STOP")

        elif action_id in {"robot.resume", "mission.resume"}:
            self._publish_navigation_command("RESUME")

        elif action_id in {"mission.dismiss", "mission.finish"}:
            self._publish_navigation_command("HOME")

        elif action_id == "splash.start":
            self._publish_hmi_request({"category": "SYSTEM", "command": "START"})

        elif action_id == "info.select":
            topic = args.get("topic", "").upper()
            if topic:
                self._publish_hmi_request({"category": "INFORMATION", "topic": topic})

        elif action_id == "diagnostics.refresh":
            msg = String()
            msg.data = "REFRESH"
            self.diagnostics_request_pub.publish(msg)
            await self._broadcast_diagnostics_to_subscribers()

        elif action_id in {"consult.confirm", "consult.book", "consult.create"}:
            if args:
                self._current_consultation_data.update(args)
            data_to_book = self._current_consultation_data if self._current_consultation_data else args
            res = self._book_appointment(data_to_book)
            if res.get("ok"):
                ticket_label = res.get("ticket_label", "A-MAT-1")
                appt_id = res.get("appointment_id")
                doctor = res.get("doctor", data_to_book.get("doctor_code", "A"))
                period = res.get("period", data_to_book.get("period", "MAT"))
                patient_name = data_to_book.get("patient_name", "Jean Dupont")

                self._publish_hmi_request({
                    "category": "CONSULTATION",
                    "action": "APPOINTMENT",
                    "appointment_id": appt_id,
                    "ticket_label": ticket_label,
                })

                speech = f"Votre rendez-vous a bien été enregistré. Votre numéro de passage est {ticket_label}."
                instruction = {
                    "origin": "server",
                    "text_to_speak": speech,
                    "speech_priority": "normal",
                    "instruction_ui": {
                        "screen": "consultation",
                        "step": 6,
                        "require_confirmation": False,
                    },
                    "fields": {
                        "ticket_label": ticket_label,
                        "appointment_id": appt_id,
                        "doctor": doctor,
                        "period": period,
                        "patient_name": patient_name,
                    },
                    "robot_status": {
                        "face_expression": "happy",
                        "status_label": f"Ticket {ticket_label} confirmé",
                    },
                    "voice_hints": ["Terminer", "Accueil"],
                }
                await self.broadcast("server/instruction", instruction)
                await self.broadcast("voice/tts/request", {"text": speech, "priority": "normal"})
            else:
                err_msg = res.get("error", "Impossible d'enregistrer le rendez-vous.")
                speech = f"Attention : {err_msg}"
                instruction = {
                    "origin": "server",
                    "text_to_speak": speech,
                    "speech_priority": "normal",
                    "instruction_ui": {
                        "screen": "consultation",
                        "step": 5,
                        "require_confirmation": False,
                    },
                    "fields": {
                        "booking_error": err_msg,
                    },
                    "robot_status": {
                        "face_expression": "thinking",
                        "status_label": "Erreur d'inscription",
                    },
                    "voice_hints": ["Réessayer", "Annuler"],
                }
                await self.broadcast("server/instruction", instruction)
                await self.broadcast("voice/tts/request", {"text": speech, "priority": "normal"})

        elif action_id == "consult.start":
            self._current_screen = "consultation"
            self._current_step = 1

        elif action_id == "consult.step_changed":
            step = args.get("step")
            if step is not None:
                try:
                    self._current_step = int(step)
                except (ValueError, TypeError):
                    pass
            self._current_screen = "consultation"
            if "fields" in args and isinstance(args["fields"], dict):
                self._current_consultation_data.update(args["fields"])

        elif action_id == "consult.cancel":
            self._current_screen = "home"
            self._current_step = 1
            self._current_consultation_data.clear()

        elif action_id == "consult.finish":
            self._current_screen = "home"
            self._current_step = 1
            self._current_consultation_data.clear()

    def _book_appointment(self, args: Dict) -> Dict:
        """Enregistre un rendez-vous dans la base SQLite du serveur."""
        try:
            try:
                from consultation_sessions_store import (
                    create_session_appointment,
                    ensure_daily_sessions,
                    set_doctor_session,
                    TZ,
                    BookingError,
                )
                from appointments_store import init_db
            except ImportError:
                import sys
                from pathlib import Path
                for cand in [
                    Path(__file__).resolve().parents[3] / "web_interface",
                    Path.home() / "hiar-main" / "web_interface",
                    Path("/home/cecilia/hiar-main/web_interface"),
                ]:
                    if cand.exists() and str(cand) not in sys.path:
                        sys.path.insert(0, str(cand))
                from consultation_sessions_store import (
                    create_session_appointment,
                    ensure_daily_sessions,
                    set_doctor_session,
                    TZ,
                    BookingError,
                )
                from appointments_store import init_db

            from datetime import datetime

            init_db()
            now_dt = datetime.now(TZ)
            today_iso = now_dt.date().isoformat()
            requested_date = str(args.get("requested_date") or today_iso).strip()

            patient_name = str(args.get("patient_name") or "Jean Dupont").strip()
            contact = str(args.get("contact") or args.get("patient_phone") or "0341234567").strip()
            reason_code = str(args.get("reason_code") or args.get("selected_reason") or "consultation_generale").strip()
            doctor_code = str(args.get("doctor_code") or args.get("selected_doctor") or "A").strip()
            period = str(args.get("period") or args.get("selected_period") or "MAT").strip()

            if requested_date == today_iso:
                ensure_daily_sessions()
                try:
                    set_doctor_session(requested_date, doctor_code, period, True)
                except Exception as sess_err:
                    self.get_logger().warn(f"Could not ensure session open for {doctor_code}/{period}: {sess_err}")

            temp = args.get("temperature_c") if args.get("temperature_c") is not None else args.get("temperature")
            hr = args.get("heart_rate_bpm") if args.get("heart_rate_bpm") is not None else args.get("heart_rate")
            spo2 = args.get("spo2_percent") if args.get("spo2_percent") is not None else args.get("spo2")

            temp_c = float(temp) if temp is not None else None
            hr_bpm = int(hr) if hr is not None else None
            spo2_pct = int(spo2) if spo2 is not None else None

            res = create_session_appointment(
                patient_name=patient_name,
                contact=contact,
                reason_code=reason_code,
                requested_date=requested_date,
                doctor_code=doctor_code,
                period=period,
                temperature_c=temp_c,
                heart_rate_bpm=hr_bpm,
                spo2_percent=spo2_pct,
                bypass_cutoff=True,
            )
            self._last_ticket_label = res.get("ticket_label")
            self.get_logger().info(f"💾 [BASE DE DONNÉES] Rendez-vous créé : {res.get('ticket_label')} (ID: {res.get('appointment_id')})")
            return {"ok": True, **res}
        except BookingError as be:
            self.get_logger().warn(f"Règle de consultation : {be}")
            msg = "Cette consultation n'est pas ouverte actuellement." if be.code == "session_closed" else (
                "Ce numéro de téléphone est déjà inscrit aujourd'hui." if be.code == "duplicate_phone" else str(be)
            )
            return {"ok": False, "code": be.code, "error": msg}
        except Exception as err:
            self.get_logger().error(f"Échec enregistrement rendez-vous : {err}")
            return {"ok": False, "error": str(err)}

    # ========================================================
    # RETOURS ROS 2 VERS WEBSOCKET (BROADCAST)
    # ========================================================

    def _on_robot_status(self, msg):
        """Reçoit /robot/status (IDLE, NAVIGATING, BLOCKED, EMERGENCY_STOP)."""
        status_text = msg.data.strip()
        self.broadcast_threadsafe(
            "robot/mission/status",
            {"status": status_text},
        )

        if status_text == "EMERGENCY_STOP":
            interrupt_instruction = {
                "origin": "server",
                "text_to_speak": "Arrêt d'urgence du robot.",
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
            }
            self.broadcast_threadsafe("server/instruction", interrupt_instruction)

    def _on_navigation_status(self, msg):
        """Reçoit /navigation/status (RUNNING, MISSION_TIMEOUT, BLOCKED, etc.)."""
        nav_status = msg.data.strip()
        self.broadcast_threadsafe(
            "robot/mission/status",
            {"navigation_status": nav_status},
        )

        if nav_status == "MISSION_TIMEOUT":
            timeout_instruction = {
                "origin": "server",
                "text_to_speak": "La mission a expiré. Retour en veille.",
                "instruction_ui": {"screen": "home"},
                "fields": {"mission_state": "IDLE"},
            }
            self.broadcast_threadsafe("server/instruction", timeout_instruction)

    def _on_vitals_result(self, msg):
        """Reçoit /vitals/result (format JSON contenant line: RESULT,... ou ERROR,...)."""
        try:
            payload = json.loads(msg.data)
            line = payload.get("line", "")
        except Exception:
            line = msg.data

        parsed = parse_vitals_frame(line)
        instruction = build_vitals_instruction(parsed)
        self.broadcast_threadsafe("server/instruction", instruction)

        text_to_speak = instruction.get("text_to_speak")
        if text_to_speak:
            self.broadcast_threadsafe(
                "voice/tts/request",
                {"text": text_to_speak, "priority": "normal"},
            )

    def _on_obstacle(self, msg):
        """Reçoit /sensors/obstacle."""
        obs_text = msg.data.strip()
        if obs_text in {"WARNING", "CRITICAL", "DANGER"}:
            self.broadcast_threadsafe(
                "server/instruction",
                {
                    "fields": {"obstacle_state": obs_text},
                    "robot_status": {"status_label": f"Obstacle détecté : {obs_text}"},
                },
            )

    def _on_esp32_diagnostics(self, msg):
        """Reçoit /esp32/diagnostics (JSON) publié périodiquement par esp32_interface."""
        try:
            data = json.loads(msg.data)
            if isinstance(data, dict):
                self._esp32_diagnostics = data
                self._esp32_diagnostics_at = time.monotonic()
        except Exception:
            pass

    def build_system_diagnostics(self) -> Dict[str, Any]:
        """Agrège l'état de l'ESP32, des capteurs, des nœuds ROS 2 et du LLM."""
        now_mono = time.monotonic()
        esp_fresh = (
            self._esp32_diagnostics is not None
            and (now_mono - self._esp32_diagnostics_at) <= 8.0
        )

        if esp_fresh and self._esp32_diagnostics is not None:
            esp32_info = self._esp32_diagnostics.get("esp32", {
                "status": "unknown", "port": "/dev/ttyUSB0", "detail": "Inconnu"
            })
            sensors = self._esp32_diagnostics.get("sensors", {})
            fw_mode = self._esp32_diagnostics.get("firmware_diagnostics", "unknown")
        else:
            esp32_info = {
                "status": "offline",
                "port": "/dev/ttyUSB0",
                "detail": "Nœud esp32_interface hors ligne",
            }
            sensors = {
                "ultrasonic": {"status": "offline", "distance_cm": None, "detail": "ESP32 hors ligne"},
                "ultrasonic_left": {"status": "offline", "distance_cm": None, "detail": "ESP32 hors ligne"},
                "ultrasonic_right": {"status": "offline", "distance_cm": None, "detail": "ESP32 hors ligne"},
                "ds18b20": {"status": "offline", "detail": "ESP32 hors ligne"},
                "max30102": {"status": "offline", "detail": "ESP32 hors ligne"},
                "motors": {"status": "offline", "mode": "OFFLINE", "detail": "ESP32 hors ligne"},
            }
            fw_mode = "offline"

        expected_nodes = [
            "esp32_interface",
            "obstacle_detector",
            "robot_supervisor",
            "navigation_decision",
            "hmi_request_receiver",
            "hmi_websocket_bridge",
        ]
        if ROS_AVAILABLE and hasattr(self, "get_node_names"):
            try:
                raw_names = {n.lstrip("/") for n in self.get_node_names()}
                active_nodes = [n for n in expected_nodes if n in raw_names]
                missing_nodes = [n for n in expected_nodes if n not in raw_names]
                nodes_status = "ok" if not missing_nodes else ("warn" if active_nodes else "offline")
                nodes_detail = (
                    f"{len(active_nodes)}/{len(expected_nodes)} actifs"
                    if not missing_nodes
                    else f"{len(active_nodes)}/{len(expected_nodes)} (manque: {', '.join(missing_nodes[:2])})"
                )
            except Exception:
                active_nodes = ["hmi_websocket_bridge"]
                missing_nodes = []
                nodes_status = "warn"
                nodes_detail = "Vérification ROS 2 indisponible"
        else:
            active_nodes = ["hmi_websocket_bridge"]
            missing_nodes = []
            nodes_status = "ok"
            nodes_detail = "Mode autonome (hors ROS 2)"

        primary_ip, all_ips, _ = self._collect_network_info()

        llm_status, llm_detail = self._llm_status, self._llm_detail
        engine = getattr(self.intent_parser, "llm_engine", None)
        if engine is not None and hasattr(engine, "get_diagnostics_status") and not self._llm_prewarming:
            try:
                llm_status, llm_detail = engine.get_diagnostics_status()
            except Exception:
                pass

        return {
            "ts": round(time.time(), 2),
            "firmware_diagnostics": fw_mode,
            "esp32": esp32_info,
            "sensors": sensors,
            "ros_nodes": {
                "status": nodes_status,
                "active_count": len(active_nodes),
                "total_count": len(expected_nodes),
                "active": active_nodes,
                "missing": missing_nodes,
                "detail": nodes_detail,
            },
            "llm": {
                "status": llm_status,
                "detail": llm_detail,
            },
            "network": {
                "hostname": socket.gethostname(),
                "ip": primary_ip,
                "ips": all_ips,
                "ws_port": self.port,
                "web_port": 5001,
            },
        }

    def _write_diagnostics_snapshot(self, diag: Optional[Dict[str, Any]] = None) -> None:
        """Écrit un instantané atomique des diagnostics pour l'interface Web Médecin."""
        path = os.environ.get("HIAR_DIAGNOSTICS_FILE", "/tmp/hiar_diagnostics.json").strip()
        if not path:
            return
        try:
            payload = diag if diag is not None else self.build_system_diagnostics()
            tmp_path = f"{path}.{os.getpid()}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp_path, path)
        except Exception:
            pass

    async def _broadcast_diagnostics_to_subscribers(self):
        diag = self.build_system_diagnostics()
        self._write_diagnostics_snapshot(diag)
        with self._ws_clients_lock:
            subs = list(self._diagnostics_subscribers)
        if not subs:
            return
        envelope = make_envelope("robot/diagnostics", diag)
        for client in subs:
            try:
                await client.send(envelope)
            except Exception:
                pass

    async def _diagnostics_broadcast_loop(self):
        """Diffuse périodiquement robot/diagnostics (WebSocket + snapshot UI Web)."""
        self._write_diagnostics_snapshot()
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(2.5)
                if self._stop_event.is_set():
                    break
                await self._broadcast_diagnostics_to_subscribers()
            except asyncio.CancelledError:
                break
            except Exception:
                continue

    # ========================================================
    # DIFFUSION WEBSOCKET MULTI-CLIENTS
    # ========================================================

    async def broadcast(self, topic: str, payload: dict):
        """Diffuse un message à tous les smartphones connectés (coroutine)."""
        with self._ws_clients_lock:
            clients_snapshot = list(self.ws_clients)

        if not clients_snapshot:
            return

        envelope = make_envelope(topic, payload)
        for client in clients_snapshot:
            try:
                await client.send(envelope)
            except Exception:
                pass

    def broadcast_threadsafe(self, topic: str, payload: dict):
        """Permet aux callbacks ROS 2 (thread ROS) d'émettre sur la boucle asyncio."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast(topic, payload),
                self.loop,
            )

    # ========================================================
    # PUBLICATIONS VERS ROS 2
    # ========================================================

    def _publish_hmi_request(self, request_dict: dict):
        msg = String()
        msg.data = json.dumps(request_dict, separators=(",", ":"))
        self.hmi_request_pub.publish(msg)
        self.get_logger().info(f"Published to /hmi/request: {msg.data}")

    def _publish_navigation_command(self, command: str):
        msg = String()
        msg.data = command.strip().upper()
        self.navigation_command_pub.publish(msg)
        self.get_logger().info(f"Published to /navigation/command: {msg.data}")

    def _publish_vitals_request(self, request_id: str):
        msg = String()
        msg.data = json.dumps({"request_id": request_id})
        self.vitals_request_pub.publish(msg)
        self.get_logger().info(f"Published to /vitals/request: {msg.data}")


def main(args=None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if ROS_AVAILABLE:
        rclpy.init(args=args)

    node = HMIWebSocketBridgeNode()
    node.start_websocket_server()

    try:
        if ROS_AVAILABLE:
            rclpy.spin(node)
        else:
            # Mode serveur pur sans ROS
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_websocket_server()
        node.destroy_node()
        if ROS_AVAILABLE and rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
