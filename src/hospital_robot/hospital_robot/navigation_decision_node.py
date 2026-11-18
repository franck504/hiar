
import json

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32
from std_msgs.msg import String


# ============================================================
# CONFIGURATION
# ============================================================

# Distance minimale considérée comme libre devant et sur les côtés
OBSTACLE_CM = 20.0
SIDE_OBSTACLE_CM = 20.0

# Fraîcheur maximale d'une mesure ultrason (cycle 3x HC-SR04 ~105 ms)
CENTER_TIMEOUT_S = 0.6
SIDE_TIMEOUT_S = 0.6

# Intervalle entre deux vérifications
LOOP_PERIOD_S = 0.1

# Intervalle minimum entre deux FORWARD
FORWARD_RESEND_S = 0.5
MAX_MISSION_DURATION_S = 30

# Durée d'une rotation courte
TURN_DURATION_S = 0.6

# Temps d'arrêt avant de relire les capteurs
RECHECK_DELAY_S = 0.2


# ============================================================
# NAVIGATION DECISION NODE
# ============================================================

class NavigationDecision(Node):

    def __init__(self):

        super().__init__('navigation_decision')

        # ----------------------------------------------------
        # État général
        # ----------------------------------------------------

        self.state = 'IDLE'
        self.destination = None
        self.mission_start_time = None

        # Moment où l'état courant a commencé
        self.state_start_time = self.now()

        # ----------------------------------------------------
        # ULTRASON AVANT (HC-SR04 GPIO 13/34)
        # ----------------------------------------------------

        self.center_distance = None
        self.last_center_time = 0.0

        # ----------------------------------------------------
        # ULTRASON GAUCHE (HC-SR04 GPIO 2/4)
        # ----------------------------------------------------

        self.left_distance = None
        self.last_left_time = 0.0

        # ----------------------------------------------------
        # ULTRASON DROIT (HC-SR04 GPIO 5/16)
        # ----------------------------------------------------

        self.right_distance = None
        self.last_right_time = 0.0

        # ----------------------------------------------------
        # Gestion des mouvements
        # ----------------------------------------------------

        self.last_forward_sent = 0.0

        # Permet d'éviter d'envoyer STOP toutes les 100 ms
        self.sensor_stop_sent = False

        # Direction actuelle de rotation
        self.turn_direction = None

        # ----------------------------------------------------
        # Subscriptions
        # ----------------------------------------------------

        # Ultrason frontal
        self.create_subscription(
            Float32,
            '/sensors/ultrasonic',
            self.center_callback,
            10
        )

        # Ultrason gauche
        self.create_subscription(
            Float32,
            '/sensors/ultrasonic_left',
            self.left_callback,
            10
        )

        # Ultrason droit
        self.create_subscription(
            Float32,
            '/sensors/ultrasonic_right',
            self.right_callback,
            10
        )

        # Statut ESP32
        self.create_subscription(
            String,
            '/esp32/status',
            self.esp32_status_callback,
            10
        )

        # Commande navigation
        self.create_subscription(
            String,
            '/navigation/command',
            self.nav_command_callback,
            10
        )

        # Demandes de destination validées par le récepteur HMI.
        self.create_subscription(
            String,
            '/navigation/request',
            self.navigation_request_callback,
            10
        )

        # ----------------------------------------------------
        # Publications
        # ----------------------------------------------------

        self.command_publisher = self.create_publisher(
            String,
            '/robot/command',
            10
        )

        self.decision_publisher = self.create_publisher(
            String,
            '/navigation/decision',
            10
        )

        self.status_publisher = self.create_publisher(
            String,
            '/navigation/status',
            10
        )

        # ----------------------------------------------------
        # Boucle principale
        # ----------------------------------------------------

        self.create_timer(
            LOOP_PERIOD_S,
            self.step
        )

        self.get_logger().info(
            'Navigation decision node started.'
        )

        self.get_logger().info(
            'Sensors: 3x HC-SR04 ultrasonic (FRONT, LEFT, RIGHT).'
        )

    # ========================================================
    # TEMPS
    # ========================================================

    def now(self):

        return self.get_clock().now().nanoseconds / 1e9

    # ========================================================
    # ENVOI COMMANDE ROBOT
    # ========================================================

    def send(self, command):

        message = String()
        message.data = command

        self.command_publisher.publish(message)

        self.get_logger().info(
            f'Navigation command: {command}'
        )

    # ========================================================
    # PUBLICATION TEXTE
    # ========================================================

    def publish_text(self, publisher, text):

        message = String()
        message.data = text

        publisher.publish(message)

    # ========================================================
    # DEMANDE DE DESTINATION HMI
    # ========================================================

    def navigation_request_callback(self, message):

        try:
            request = json.loads(message.data)
        except (json.JSONDecodeError, TypeError):
            self.get_logger().warning(
                'Invalid navigation request JSON rejected.'
            )
            return

        if (
            not isinstance(request, dict)
            or set(request.keys()) != {'category', 'destination'}
            or request.get('category') != 'ORIENTATION'
            or request.get('destination') not in {
                'PHARMACY', 'LABORATORY', 'RECEPTION'
            }
        ):
            self.get_logger().warning(
                'Invalid navigation destination request rejected.'
            )
            return

        if self.state != 'IDLE':
            self.publish_text(
                self.status_publisher,
                'REQUEST_REJECTED:MISSION_ACTIVE'
            )
            return

        self.destination = request['destination']
        self.publish_text(
            self.status_publisher,
            f'REQUEST_RECEIVED:{self.destination}'
        )
        self.start_mission()

    # ========================================================
    # CHANGEMENT D'ÉTAT
    # ========================================================

    def change_state(self, new_state):

        if self.state == new_state:
            return

        self.get_logger().info(
            f'State: {self.state} -> {new_state}'
        )

        self.state = new_state

        # Mémorise le début du nouvel état
        self.state_start_time = self.now()

    # ========================================================
    # CALLBACK ULTRASON AVANT
    # ========================================================

    def center_callback(self, message):

        distance = float(message.data)

        # Mesure invalide
        if distance <= 0.0:
            return

        self.center_distance = distance
        self.last_center_time = self.now()

    # ========================================================
    # CALLBACK ULTRASON GAUCHE
    # ========================================================

    def left_callback(self, message):

        distance = float(message.data)

        if distance <= 0.0:
            return

        self.left_distance = distance
        self.last_left_time = self.now()

    # ========================================================
    # CALLBACK ULTRASON DROIT
    # ========================================================

    def right_callback(self, message):

        distance = float(message.data)

        if distance <= 0.0:
            return

        self.right_distance = distance
        self.last_right_time = self.now()

    # ========================================================
    # CALLBACK STATUT ESP32
    # ========================================================

    def esp32_status_callback(self, message):

        text = message.data.strip().upper()

        # L'ESP32 signale un obstacle pendant l'avance.
        if 'OBSTACLE' in text and self.state == 'FORWARD':

            self.get_logger().warning(
                f'ESP32 safety reported: {message.data}'
            )

            self.send('STOP')

            self.change_state('DECIDE')

    # ========================================================
    # COMMANDE START / STOP
    # ========================================================

    def start_mission(self):
        """Start a bounded demo mission only with a valid destination and fresh sensors."""
        if self.state != 'IDLE':
            self.publish_text(self.status_publisher, 'START_REJECTED:MISSION_ACTIVE')
            return False

        if self.destination not in {
            'PHARMACY', 'LABORATORY', 'RECEPTION'
        }:
            self.publish_text(self.status_publisher, 'START_REJECTED:NO_DESTINATION')
            self.get_logger().warning(
                'START rejected: no valid destination selected.'
            )
            return False

        if not self.sensors_ready():
            self.send('STOP')
            self.mission_start_time = None
            self.publish_text(
                self.status_publisher,
                'START_REJECTED:SENSORS_NOT_READY'
            )
            return False

        self.last_forward_sent = 0.0
        self.sensor_stop_sent = False
        self.turn_direction = None
        self.mission_start_time = self.now()
        self.publish_text(self.status_publisher, 'RUNNING')
        self.change_state('DECIDE')
        self.get_logger().info(
            f'Bounded demo mission started: {self.destination}.'
        )
        return True

    def nav_command_callback(self, message):

        command = message.data.strip().upper()

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        if command == 'START':
            self.start_mission()

        # ----------------------------------------------------
        # STOP
        # ----------------------------------------------------

        elif command == 'STOP':

            self.send('STOP')

            self.publish_text(
                self.status_publisher,
                'IDLE'
            )

            self.change_state('IDLE')

            self.destination = None
            self.mission_start_time = None
            self.sensor_stop_sent = False
            self.turn_direction = None

            self.get_logger().info(
                'Navigation stopped.'
            )

        # ----------------------------------------------------
        # COMMANDE INCONNUE
        # ----------------------------------------------------

        else:

            self.get_logger().warning(
                f'Unknown navigation command: {command}'
            )

    # ========================================================
    # VÉRIFICATION DES CAPTEURS
    # ========================================================

    def sensors_ready(self):

        current_time = self.now()

        # Ultrason avant disponible ?
        center_ready = (
            self.center_distance is not None
            and
            current_time - self.last_center_time
            <= CENTER_TIMEOUT_S
        )

        # Ultrason gauche disponible ?
        left_ready = (
            self.left_distance is not None
            and
            current_time - self.last_left_time
            <= SIDE_TIMEOUT_S
        )

        # Ultrason droit disponible ?
        right_ready = (
            self.right_distance is not None
            and
            current_time - self.last_right_time
            <= SIDE_TIMEOUT_S
        )

        return center_ready and left_ready and right_ready

    # ========================================================
    # DÉCISION DE NAVIGATION (3x HC-SR04)
    # ========================================================

    def decide(self):

        center = self.center_distance
        left = self.left_distance
        right = self.right_distance

        # ----------------------------------------------------
        # DEVANT LIBRE
        # ----------------------------------------------------

        if center >= OBSTACLE_CM:

            return 'FORWARD'

        # ----------------------------------------------------
        # DEVANT BLOQUÉ
        # ----------------------------------------------------

        left_clear = left is not None and left >= SIDE_OBSTACLE_CM
        right_clear = right is not None and right >= SIDE_OBSTACLE_CM

        # Gauche = libre, Droite = obstacle
        if left_clear and not right_clear:

            return 'LEFT'

        # Gauche = obstacle, Droite = libre
        if right_clear and not left_clear:

            return 'RIGHT'

        # Les deux côtés libres : privilégier le côté le plus dégagé
        # (priorité à gauche en cas d'égalité à ±5 cm).
        if left_clear and right_clear:

            if right > left + 5.0:
                return 'RIGHT'

            return 'LEFT'

        # Les deux côtés bloqués
        return 'STOP'

    # ========================================================
    # BOUCLE PRINCIPALE
    # ========================================================

    def step(self):

        current_time = self.now()

        # Limite globale indépendante des renvois périodiques de FORWARD.
        if (
            self.mission_start_time is not None
            and current_time - self.mission_start_time
            >= MAX_MISSION_DURATION_S
        ):
            self.send('STOP')
            self.change_state('IDLE')
            self.destination = None
            self.mission_start_time = None
            self.sensor_stop_sent = False
            self.turn_direction = None
            self.publish_text(self.status_publisher, 'MISSION_TIMEOUT')
            self.get_logger().warning(
                'Mission stopped: maximum duration reached.'
            )
            return

        if self.state == 'IDLE':
            return

        # ====================================================
        # BLOCKED
        # ====================================================

        if self.state == 'BLOCKED':

            # Ne pas reprendre le mouvement avec des capteurs périmés.
            if not self.sensors_ready():
                return

            # Si une direction devient sûre, refaire une décision
            # dans l'état DECIDE au prochain cycle.
            if self.decide() != 'STOP':
                self.change_state('DECIDE')

            return

        # ====================================================
        # FORWARD
        # ====================================================

        if self.state == 'FORWARD':

            # ------------------------------------------------
            # Vérifier la fraîcheur des capteurs
            # ------------------------------------------------

            if not self.sensors_ready():

                # STOP envoyé une seule fois
                if not self.sensor_stop_sent:

                    self.send('STOP')

                    self.sensor_stop_sent = True

                    self.publish_text(
                        self.status_publisher,
                        'SENSOR_NOT_READY'
                    )

                    self.get_logger().warning(
                        'Waiting for fresh sensor data.'
                    )

                self.change_state('DECIDE')
                return

            # Capteurs de nouveau disponibles
            self.sensor_stop_sent = False

            # ------------------------------------------------
            # Obstacle frontal
            # ------------------------------------------------

            if self.center_distance < OBSTACLE_CM:

                self.send('STOP')

                self.publish_text(
                    self.decision_publisher,
                    'OBSTACLE'
                )

                self.get_logger().warning(
                    f'Obstacle detected: '
                    f'{self.center_distance:.1f} cm'
                )

                self.change_state('DECIDE')

                return

            # ------------------------------------------------
            # Envoi périodique de FORWARD
            # ------------------------------------------------

            if (
                current_time - self.last_forward_sent
                >= FORWARD_RESEND_S
            ):

                self.send('FORWARD')

                self.last_forward_sent = current_time

            return

        # ====================================================
        # DECIDE
        # ====================================================

        if self.state == 'DECIDE':

            # Les capteurs doivent être valides avant décision
            if not self.sensors_ready():

                if not self.sensor_stop_sent:

                    self.send('STOP')

                    self.sensor_stop_sent = True

                    self.publish_text(
                        self.status_publisher,
                        'SENSOR_NOT_READY'
                    )

                    self.get_logger().warning(
                        'Waiting for fresh sensor data.'
                    )

                return

            self.sensor_stop_sent = False

            decision = self.decide()

            self.publish_text(
                self.decision_publisher,
                decision
            )

            left_str = f'{self.left_distance:.1f} cm' if self.left_distance is not None else 'NA'
            right_str = f'{self.right_distance:.1f} cm' if self.right_distance is not None else 'NA'
            self.get_logger().info(
                f'RECHECK: '
                f'FRONT={self.center_distance:.1f} cm | '
                f'LEFT={left_str} | '
                f'RIGHT={right_str} | '
                f'DECISION={decision}'
            )

            # ------------------------------------------------
            # Devant libre
            # ------------------------------------------------

            if decision == 'FORWARD':

                self.change_state('FORWARD')

                return

            # ------------------------------------------------
            # Tourner à gauche
            # ------------------------------------------------

            if decision == 'LEFT':

                self.send('STOP')

                self.turn_direction = 'LEFT'

                self.send('LEFT')

                self.change_state('TURN_LEFT')

                return

            # ------------------------------------------------
            # Tourner à droite
            # ------------------------------------------------

            if decision == 'RIGHT':

                self.send('STOP')

                self.turn_direction = 'RIGHT'

                self.send('RIGHT')

                self.change_state('TURN_RIGHT')

                return

            # ------------------------------------------------
            # Bloqué
            # ------------------------------------------------

            if decision == 'STOP':

                self.send('STOP')

                self.publish_text(
                    self.status_publisher,
                    'BLOCKED'
                )

                self.get_logger().warning(
                    'Robot blocked: '
                    'LEFT and RIGHT obstacles.'
                )

                self.change_state('BLOCKED')

                return

        # ====================================================
        # TURN LEFT
        # ====================================================

        if self.state == 'TURN_LEFT':

            elapsed = current_time - self.state_start_time

            if elapsed >= TURN_DURATION_S:

                self.send('STOP')

                self.turn_direction = None

                self.change_state('RECHECK')

            return

        # ====================================================
        # TURN RIGHT
        # ====================================================

        if self.state == 'TURN_RIGHT':

            elapsed = current_time - self.state_start_time

            if elapsed >= TURN_DURATION_S:

                self.send('STOP')

                self.turn_direction = None

                self.change_state('RECHECK')

            return

        # ====================================================
        # RECHECK
        # ====================================================

        if self.state == 'RECHECK':

            elapsed = current_time - self.state_start_time

            if elapsed >= RECHECK_DELAY_S:

                self.change_state('DECIDE')

            return

    # ========================================================
    # FERMETURE
    # ========================================================

    def stop_robot(self):

        self.send('STOP')


# ============================================================
# MAIN
# ============================================================

def main(args=None):

    rclpy.init(args=args)

    node = NavigationDecision()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        node.get_logger().info(
            'Navigation decision node stopped by user.'
        )

    finally:

        if rclpy.ok():

            node.stop_robot()

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == '__main__':

    main()
