"""Pont WebSocket bidirectionnel HMI pour HIAR (Raspberry Pi 4 / ROS 2).

Ce nœud héberge le serveur WebSocket central (port 5000) et fait la passerelle entre :
- Les flux du smartphone (microphone STT, tactile UI)
- Le graphe ROS 2 (/hmi/request, /navigation/command, /vitals/request, etc.)
- La commande dynamique du mobile (server/instruction, voice/tts/request, robot/mission/status)
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, Optional, Set
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
    from hospital_robot.llm_intent_engine import LLMConfig
except ImportError:
    from voice_intent_parser import ParsedIntent, VoiceIntentParser, normalize_text
    from vitals_data_parser import build_vitals_instruction, parse_vitals_frame
    try:
        from llm_intent_engine import LLMConfig
    except ImportError:
        LLMConfig = None  # type: ignore

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

        if ROS_AVAILABLE:
            self.declare_parameter("websocket_host", "0.0.0.0")
            self.declare_parameter("websocket_port", 5000)
            self.declare_parameter("enable_llm", True)
            self.declare_parameter("llm_backend", "ollama")
            self.declare_parameter("llm_host", "http://127.0.0.1:11434")
            self.declare_parameter("llm_model", "qwen2.5:0.5b")
            self.declare_parameter("llm_timeout", 15.0)

            self.host = host or str(self.get_parameter("websocket_host").value)
            self.port = port or int(self.get_parameter("websocket_port").value)
            enable_llm = bool(self.get_parameter("enable_llm").value)
            llm_backend = str(self.get_parameter("llm_backend").value)
            llm_host = str(self.get_parameter("llm_host").value)
            llm_model = str(self.get_parameter("llm_model").value)
            llm_timeout = float(self.get_parameter("llm_timeout").value)
        else:
            self.host = host or "0.0.0.0"
            self.port = port or 5000
            enable_llm = True
            llm_backend = "ollama"
            llm_host = "http://127.0.0.1:11434"
            llm_model = "qwen2.5:0.5b"
            llm_timeout = 15.0

        # Composants de traitement métier (Parseur hybride Déterministe + LLM)
        if LLMConfig is not None:
            llm_cfg = LLMConfig(
                enabled=enable_llm,
                backend=llm_backend,
                host=llm_host,
                model_name=llm_model,
                timeout_sec=llm_timeout,
            )
            self.intent_parser = VoiceIntentParser(enable_llm=enable_llm, llm_config=llm_cfg)
        else:
            self.intent_parser = VoiceIntentParser()

        # Préchauffage en arrière-plan pour garder le modèle Qwen chargé en RAM
        if getattr(self.intent_parser, "enable_llm", False) and getattr(self.intent_parser, "llm_engine", None):
            def _prewarm_llm():
                try:
                    time.sleep(1.0)
                    if self.intent_parser.llm_engine.is_available():
                        self.get_logger().info("🔥 Pre-warming LLM Qwen 2.5 in RAM...")
                        res = self.intent_parser.llm_engine.infer("Bonjour robot")
                        self.get_logger().info(f"✅ LLM Qwen 2.5 pre-warmed and ready (latency={res.latency_ms:.0f}ms).")
                except Exception as ex:
                    self.get_logger().warning(f"LLM pre-warm warning: {ex}")
            threading.Thread(target=_prewarm_llm, daemon=True).start()

        self._pending_orientation: Optional[Dict[str, Any]] = None
        self._current_screen: str = "home"
        self._current_step: int = 1
        self._current_consultation_data: Dict[str, Any] = {}
        self._last_ticket_label: Optional[str] = None
        self._last_stt_text = ""
        self._last_stt_time = 0.0

        # Clients WebSocket connectés
        self.ws_clients: Set[WSConnection] = set()
        self._ws_clients_lock = threading.Lock()

        # Gestion Asyncio & Serveur
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.server = None
        self._server_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # ----------------------------------------------------
        # Publications ROS 2
        # ----------------------------------------------------
        self.hmi_request_pub = self.create_publisher(String, "/hmi/request", 10)
        self.navigation_command_pub = self.create_publisher(String, "/navigation/command", 10)
        self.vitals_request_pub = self.create_publisher(String, "/vitals/request", 10)

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
                )
                self.get_logger().info(
                    f"WebSocket server listening on ws://{self.host}:{self.port}/ws"
                )
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

    def stop_websocket_server(self):
        """Arrête proprement le serveur WebSocket et la boucle asyncio."""
        self._stop_event.set()
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
        self.get_logger().info(f"Client connected: {websocket.remote_address}")

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
            self.get_logger().warning(f"Error handling client: {exc}")
        finally:
            with self._ws_clients_lock:
                self.ws_clients.discard(websocket)
            self.get_logger().info("Client disconnected.")

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
            welcome = make_envelope(
                "connection/welcome",
                {"server": "HIAR Central ROS2 Bridge", "status": "ready"},
                msg_type="welcome",
            )
            await websocket.send(welcome)
            return

        if msg_type == "sub":
            return

        # Publications entrantes du smartphone
        if topic == "voice/stt/final":
            await self._handle_voice_stt(payload)

        elif topic == "ui/action/request":
            await self._handle_ui_action(payload)

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
            self.get_logger().info(f"Mobile UI state updated: screen={self._current_screen} step={self._current_step}")

    # ========================================================
    # LOGIQUE VOCALE & INTENTS
    # ========================================================

    async def _handle_voice_stt(self, payload: Dict):
        """Traite la parole transcrite par le microphone du smartphone."""
        text = payload.get("text", "")
        confidence = float(payload.get("confidence", 1.0))

        if not text:
            return

        norm_incoming = normalize_text(text)

        # 0. Anti-rebond temporel (doublon Android STT émis à < 2.5s)
        now = time.time()
        if norm_incoming == self._last_stt_text and (now - self._last_stt_time) < 2.5:
            self.get_logger().info(f"⏩ Duplicate STT frame suppressed: '{text}' (elapsed={now - self._last_stt_time:.2f}s)")
            return
        self._last_stt_text = norm_incoming
        self._last_stt_time = now

        # Analyse et classification d'intention
        intent = self.intent_parser.parse(text, confidence=confidence)

        # Filtrage des fragments isolés ("je", "le", etc.) : on attend la suite sans parler
        if intent.intent_type == "IGNORED_FRAGMENT":
            self.get_logger().info(f"Silently ignored fragment: '{text}'")
            return

        is_llm = bool(intent.details.get("llm_generated", False))
        latency_ms = float(intent.details.get("latency_ms", 0.0))
        model = str(intent.details.get("model", "qwen2.5:0.5b"))

        if is_llm:
            engine_str = f"🧠 LLM {model} (Inférence Ollama | Latence: {latency_ms:.0f}ms)"
        elif intent.intent_type != "UNKNOWN":
            engine_str = "⚙️ Sécurité Déterministe (Regex Réflexe | Latence: <1ms)"
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

        elif intent.ros_request and intent.intent_type != "ORIENTATION":
            self._publish_hmi_request(intent.ros_request)

        # 3. Action ROS 2 Signes vitaux (déclenchement matériel)
        vitals_id = None
        if intent.intent_type == "VITALS":
            vitals_id = str(uuid.uuid4())
            self._publish_vitals_request(vitals_id)

        # 4. Construction de l'instruction UI & TTS pour le mobile
        instruction = self.intent_parser.build_instruction(intent, text)
        tts_text = ""
        ui_screen = ""
        if instruction:
            if is_llm:
                instruction["llm_source"] = model
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

        self.get_logger().info(f"Tactile action received: {action_id} args={args}")

        if action_id == "orientation.select":
            dest = args.get("destination", "").upper()
            if dest:
                self._publish_hmi_request({"category": "ORIENTATION", "destination": dest})

        elif action_id == "orientation.confirm":
            dest_key = args.get("destination")
            if not dest_key and self._pending_orientation:
                dest_key = self._pending_orientation.get("destination")
            dest_key = (dest_key or "PHARMACY").upper()
            dest_label = self.intent_parser.DEPARTMENTS.get(dest_key, {}).get("label", dest_key)
            self._pending_orientation = None

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
