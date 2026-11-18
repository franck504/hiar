import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32
from std_msgs.msg import String


class ObstacleDetector(Node):

    def __init__(self):
        super().__init__('obstacle_detector')

        # Seuil de détection provisoire
        self.obstacle_threshold_cm = 20.0

        # Souscription aux 3 capteurs ultrasoniques HC-SR04 (Avant, Gauche, Droite)
        self.ultrasonic_subscription = self.create_subscription(
            Float32,
            '/sensors/ultrasonic',
            self.ultrasonic_callback,
            10
        )

        self.ultrasonic_left_subscription = self.create_subscription(
            Float32,
            '/sensors/ultrasonic_left',
            self.ultrasonic_left_callback,
            10
        )

        self.ultrasonic_right_subscription = self.create_subscription(
            Float32,
            '/sensors/ultrasonic_right',
            self.ultrasonic_right_callback,
            10
        )

        # Publication des états de détection (Avant sur /sensors/obstacle + côtés)
        self.obstacle_publisher = self.create_publisher(
            String,
            '/sensors/obstacle',
            10
        )

        self.obstacle_left_publisher = self.create_publisher(
            String,
            '/sensors/obstacle_left',
            10
        )

        self.obstacle_right_publisher = self.create_publisher(
            String,
            '/sensors/obstacle_right',
            10
        )

        self.get_logger().info(
            'Obstacle detector started (3x HC-SR04: FRONT, LEFT, RIGHT).'
        )

        self.get_logger().info(
            f'Obstacle threshold: '
            f'{self.obstacle_threshold_cm:.1f} cm'
        )

    def _publish_state(self, distance, publisher, label):

        if distance <= 0.0:
            self.get_logger().warning(
                f'Invalid {label} distance received: {distance:.2f} cm'
            )
            return

        state = 'OBSTACLE' if distance < self.obstacle_threshold_cm else 'CLEAR'

        obstacle_message = String()
        obstacle_message.data = state

        publisher.publish(obstacle_message)

        self.get_logger().info(
            f'{label} distance: {distance:.1f} cm -> {state}'
        )

    def ultrasonic_callback(self, message):
        self._publish_state(message.data, self.obstacle_publisher, 'FRONT')

    def ultrasonic_left_callback(self, message):
        self._publish_state(message.data, self.obstacle_left_publisher, 'LEFT')

    def ultrasonic_right_callback(self, message):
        self._publish_state(message.data, self.obstacle_right_publisher, 'RIGHT')


def main(args=None):

    rclpy.init(args=args)

    node = ObstacleDetector()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        node.get_logger().info(
            'Obstacle detector stopped by user.'
        )

    finally:

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
