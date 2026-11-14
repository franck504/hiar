import time

import rclpy
from rclpy.node import Node

from std_msgs.msg import String

OBSTACLE_STATE_TIMEOUT_S = 0.5
SUPERVISOR_WATCHDOG_INTERVAL_S = 0.1


class RobotSupervisor(Node):

    def __init__(self):
        super().__init__('robot_supervisor')

        self.current_state = 'IDLE'
        self.obstacle_state = 'UNKNOWN'
        self.last_obstacle_time = None
        self.current_command = 'STOP'

        # Commandes demandées par le système
        self.command_subscription = self.create_subscription(
            String,
            '/robot/command',
            self.command_callback,
            10
        )

        # État de perception
        self.obstacle_subscription = self.create_subscription(
            String,
            '/sensors/obstacle',
            self.obstacle_callback,
            10
        )

        # Commandes réellement envoyées à l'ESP32
        self.motor_command_publisher = self.create_publisher(
            String,
            '/robot/motor_command',
            10
        )

        # État du robot
        self.status_publisher = self.create_publisher(
            String,
            '/robot/status',
            10
        )

        self.watchdog_timer = self.create_timer(
            SUPERVISOR_WATCHDOG_INTERVAL_S,
            self.obstacle_watchdog_callback
        )

        self.get_logger().info(
            'Robot supervisor started.'
        )

        self.publish_status()

    def command_callback(self, message):

        command = message.data.strip().upper()

        allowed_commands = [
            'FORWARD',
            'BACKWARD',
            'LEFT',
            'RIGHT',
            'STOP'
        ]

        if command not in allowed_commands:

            self.get_logger().warning(
                f'Invalid command rejected: {command}'
            )

            return

        # Aucun mouvement sans état d'obstacle récent.
        if (
            command != 'STOP'
            and not self.obstacle_state_is_fresh()
        ):
            self.get_logger().warning(
                'Motion command rejected: obstacle state missing or stale.'
            )
            self.send_stop()
            return

        # Sécurité : FORWARD interdit si obstacle
        if (
            command == 'FORWARD'
            and self.obstacle_state == 'OBSTACLE'
        ):

            self.get_logger().warning(
                'FORWARD rejected: obstacle detected.'
            )

            self.send_stop()
            return

        self.current_command = command

        if command == 'STOP':
            self.current_state = 'IDLE'

        else:
            self.current_state = 'NAVIGATING'

        self.send_motor_command(command)
        self.publish_status()

        self.get_logger().info(
            f'Command accepted: {command}'
        )

    def obstacle_callback(self, message):

        obstacle_state = message.data.strip().upper()

        if obstacle_state not in [
            'CLEAR',
            'OBSTACLE'
        ]:

            self.get_logger().warning(
                f'Invalid obstacle state: {obstacle_state}'
            )

            return

        self.obstacle_state = obstacle_state
        self.last_obstacle_time = time.monotonic()

        self.get_logger().info(
            f'Obstacle state: {obstacle_state}'
        )

        # Arrêt automatique si obstacle pendant FORWARD
        if (
            obstacle_state == 'OBSTACLE'
            and self.current_command == 'FORWARD'
        ):

            self.get_logger().warning(
                'Obstacle detected during FORWARD.'
            )

            self.send_stop()

    def obstacle_state_is_fresh(self):

        if self.last_obstacle_time is None:
            return False

        return (
            time.monotonic() - self.last_obstacle_time
            <= OBSTACLE_STATE_TIMEOUT_S
        )

    def obstacle_watchdog_callback(self):

        if (
            self.current_command != 'STOP'
            and not self.obstacle_state_is_fresh()
        ):
            self.get_logger().warning(
                'Obstacle state became stale during movement.'
            )
            self.send_stop()

    def send_motor_command(self, command):

        message = String()
        message.data = command

        self.motor_command_publisher.publish(message)

        self.get_logger().info(
            f'Motor command published: {command}'
        )

    def send_stop(self):

        self.current_command = 'STOP'
        self.current_state = 'IDLE'

        self.send_motor_command('STOP')
        self.publish_status()

        self.get_logger().warning(
            'STOP command published.'
        )

    def publish_status(self):

        message = String()
        message.data = self.current_state

        self.status_publisher.publish(message)


def main(args=None):

    rclpy.init(args=args)

    node = RobotSupervisor()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        node.get_logger().info(
            'Robot supervisor stopped by user.'
        )

    finally:

        node.send_stop()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
