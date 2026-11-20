"""
Pont HMI / ROS2 / ESP32.
Publie les demandes HMI et assure le transfert des demandes
et résultats de mesure des signes vitaux.
"""

import json
import threading
import uuid

TOPIC = "/hmi/request"
VITALS_REQUEST_TOPIC = "/vitals/request"
VITALS_RESULT_TOPIC = "/vitals/result"


try:
    import rclpy
    from std_msgs.msg import String
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False


class RosBridge:

    def __init__(self):
        self._node = None
        self._publisher = None
        self._navigation_command_publisher = None
        self._robot_command_publisher = None
        self._motor_command_publisher = None

        self._vitals_request_publisher = None
        self._vitals_result_subscription = None

        self._lock = threading.Lock()
        self._pending_vitals = {}
        self._spin_thread = None

        self.error = None

    @property
    def active(self):
        return self._publisher is not None

    def start(self):
        """Démarre le node ROS2 et sa boucle de réception."""

        if not ROS_AVAILABLE:
            self.error = "rclpy indisponible (ROS2 non chargé)"
            return False

        try:
            if not rclpy.ok():
                rclpy.init()

            self._node = rclpy.create_node("hmi_bridge")

            self._publisher = self._node.create_publisher(
                String, TOPIC, 10
            )

            self._navigation_command_publisher = (
                self._node.create_publisher(
                    String, "/navigation/command", 10
                )
            )

            self._robot_command_publisher = (
                self._node.create_publisher(
                    String, "/robot/command", 10
                )
            )

            self._motor_command_publisher = (
                self._node.create_publisher(
                    String, "/robot/motor_command", 10
                )
            )

            self._vitals_request_publisher = (
                self._node.create_publisher(
                    String, VITALS_REQUEST_TOPIC, 10
                )
            )

            self._vitals_result_subscription = (
                self._node.create_subscription(
                    String,
                    VITALS_RESULT_TOPIC,
                    self._on_vitals_result,
                    10
                )
            )

            self._spin_thread = threading.Thread(
                target=rclpy.spin,
                args=(self._node,),
                name="hiar-ros-spin",
                daemon=True
            )

            self._spin_thread.start()

            self.error = None
            return True

        except Exception as err:
            self.error = str(err)
            return False

    def publish(self, request_dict):
        """
        Publie une demande HMI sur /hmi/request.
        """

        if not self.active:
            self.error = "Pont ROS2 inactif"
            return False

        try:
            message = String()
            message.data = json.dumps(
                request_dict,
                ensure_ascii=False
            )

            with self._lock:
                self._publisher.publish(message)

            self.error = None
            return True

        except Exception as err:
            self.error = str(err)
            return False

    def cancel_navigation(self):
        """Publie STOP sur /navigation/command, /robot/command et /robot/motor_command."""

        if (
            self._navigation_command_publisher is None
            and self._robot_command_publisher is None
            and self._motor_command_publisher is None
        ):
            self.error = (
                "Publication de commande de navigation indisponible"
            )
            return False

        try:
            message = String()
            message.data = "STOP"

            with self._lock:
                if self._navigation_command_publisher:
                    self._navigation_command_publisher.publish(message)
                if self._robot_command_publisher:
                    self._robot_command_publisher.publish(message)
                if self._motor_command_publisher:
                    self._motor_command_publisher.publish(message)

            self.error = None
            return True

        except Exception as err:
            self.error = str(err)
            return False

    def _on_vitals_result(self, message):
        """
        Reçoit les réponses de esp32_interface sur /vitals/result.
        """

        try:
            payload = json.loads(message.data)

            request_id = str(
                payload.get("request_id", "")
            )

            if not request_id:
                return

        except (ValueError, AttributeError, TypeError):
            self.error = "Réponse de signes vitaux JSON invalide"
            return

        with self._lock:
            pending = self._pending_vitals.get(request_id)

            if pending is not None:
                pending["response"] = payload
                pending["event"].set()

    def acquire_vitals(self, timeout=35.0):
        """
        Demande une acquisition réelle à l'ESP32 via ROS2.

        Retourne :
          {"ok": True, "request_id": ..., "line": ...}
        ou
          {"ok": False, "error": ...}
        """

        if (
            not self.active
            or self._vitals_request_publisher is None
        ):
            self.error = "Pont ROS2 ou acquisition vitale indisponible"
            return {
                "ok": False,
                "error": self.error
            }

        request_id = str(uuid.uuid4())
        event = threading.Event()

        pending = {
            "event": event,
            "response": None
        }

        with self._lock:
            self._pending_vitals[request_id] = pending

        try:
            message = String()
            message.data = json.dumps({
                "request_id": request_id
            })

            with self._lock:
                self._vitals_request_publisher.publish(message)

        except Exception as err:
            with self._lock:
                self._pending_vitals.pop(request_id, None)

            self.error = str(err)

            return {
                "ok": False,
                "error": self.error
            }

        received = event.wait(timeout)

        with self._lock:
            completed = self._pending_vitals.pop(
                request_id, None
            )

        if not received or completed is None:
            self.error = "Délai dépassé pendant l'acquisition des signes vitaux"
            return {
                "ok": False,
                "error": self.error
            }

        response = completed["response"]

        if not isinstance(response, dict):
            self.error = "Réponse de signes vitaux invalide"
            return {
                "ok": False,
                "error": self.error
            }

        line = response.get("line")

        if not isinstance(line, str):
            self.error = "Résultat de mesure absent"
            return {
                "ok": False,
                "error": self.error
            }

        self.error = None

        return {
            "ok": True,
            "request_id": request_id,
            "line": line
        }

    def stop(self):
        """Arrête proprement le pont ROS2."""

        with self._lock:
            for pending in self._pending_vitals.values():
                pending["response"] = {
                    "line": "ERROR,BRIDGE_STOPPED"
                }
                pending["event"].set()

        if ROS_AVAILABLE:
            try:
                if rclpy.ok():
                    rclpy.shutdown()
            except Exception:
                pass

        if self._spin_thread is not None:
            self._spin_thread.join(timeout=3.0)
            self._spin_thread = None

        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:
                pass

            self._node = None

        self._publisher = None
        self._navigation_command_publisher = None
        self._vitals_request_publisher = None
        self._vitals_result_subscription = None

        with self._lock:
            self._pending_vitals.clear()
