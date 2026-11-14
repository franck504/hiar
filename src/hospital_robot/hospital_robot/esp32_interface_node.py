import json
import time

import serial
import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from std_msgs.msg import Float32
from std_msgs.msg import Int32


class ESP32Interface(Node):

    def __init__(self):
        super().__init__('esp32_interface')

        self.port = '/dev/ttyUSB0'
        self.baudrate = 115200

        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.05
            )
            self.get_logger().info(f'Connected to ESP32 on {self.port}')

        except serial.SerialException as error:
            self.serial_connection = None
            self.get_logger().error(f'Unable to connect to ESP32: {error}')

        self.active_vitals_request_id = None
        self.vitals_started_at = None
        self.vitals_timeout_s = 32.0

        self.command_subscription = self.create_subscription(
            String, '/robot/motor_command', self.command_callback, 10
        )

        self.status_publisher = self.create_publisher(
            String, '/esp32/status', 10
        )

        self.vitals_result_publisher = self.create_publisher(
            String, '/vitals/result', 10
        )

        self.vitals_request_subscription = self.create_subscription(
            String, '/vitals/request', self.vitals_request_callback, 10
        )

        self.ultrasonic_publisher = self.create_publisher(
            Float32, '/sensors/ultrasonic', 10
        )

        self.ir_left_publisher = self.create_publisher(
            Int32, '/sensors/ir_left', 10
        )

        self.ir_right_publisher = self.create_publisher(
            Int32, '/sensors/ir_right', 10
        )

        self.serial_timer = self.create_timer(0.01, self.read_serial)

        self.get_logger().info('ESP32 interface node started.')

    def publish_vitals_result(self, request_id, line):
        message = String()
        message.data = json.dumps({
            'request_id': request_id,
            'line': line
        })
        self.vitals_result_publisher.publish(message)

        if self.active_vitals_request_id == request_id:
            self.active_vitals_request_id = None
            self.vitals_started_at = None

    def vitals_request_callback(self, message):
        try:
            payload = json.loads(message.data)
            request_id = str(payload.get('request_id', '')).strip()
        except (ValueError, AttributeError):
            self.get_logger().warning('Invalid vitals request JSON.')
            return

        if not request_id:
            self.get_logger().warning('Vitals request without request_id.')
            return

        if self.active_vitals_request_id is not None:
            self.publish_vitals_result(request_id, 'ERROR,BUSY')
            return

        if self.serial_connection is None:
            self.publish_vitals_result(request_id, 'ERROR,SERIAL_UNAVAILABLE')
            return

        try:
            self.active_vitals_request_id = request_id
            self.vitals_started_at = time.monotonic()
            self.serial_connection.write(b'MEASURE\n')
            self.get_logger().info(f'Vitals measurement requested: {request_id}')

        except serial.SerialException as error:
            self.publish_vitals_result(request_id, 'ERROR,SERIAL_COMMUNICATION')
            self.get_logger().error(f'Vitals measurement serial error: {error}')
            self.close_serial_connection()

    def command_callback(self, message):
        command = message.data.strip().upper()

        allowed_commands = ['FORWARD', 'BACKWARD', 'LEFT', 'RIGHT', 'STOP']

        if command not in allowed_commands:
            self.get_logger().warning(f'Invalid command rejected: {command}')
            return

        if self.serial_connection is None:
            self.get_logger().error('ESP32 is not connected.')
            return

        try:
            self.serial_connection.write(f'{command}\n'.encode('utf-8'))
            self.get_logger().info(f'Sent to ESP32: {command}')

        except serial.SerialException as error:
            self.get_logger().error(f'Serial communication error: {error}')
            self.get_logger().error('Communication with ESP32 lost. Robot must STOP.')
            self.close_serial_connection()

    def read_serial(self):
        if (
            self.active_vitals_request_id is not None
            and self.vitals_started_at is not None
            and time.monotonic() - self.vitals_started_at > self.vitals_timeout_s
        ):
            request_id = self.active_vitals_request_id
            self.publish_vitals_result(request_id, 'ERROR,TIMEOUT')

        if self.serial_connection is None:
            return

        try:
            while self.serial_connection.in_waiting > 0:
                raw_line = self.serial_connection.readline()

                if not raw_line:
                    break

                response = raw_line.decode('utf-8', errors='replace').strip()

                if not response:
                    continue

                if response.startswith('DIST,'):
                    parts = response.split(',')
                    if len(parts) != 2:
                        self.get_logger().warning(f'Invalid DIST frame: {response}')
                        continue
                    try:
                        distance = float(parts[1])
                    except ValueError:
                        self.get_logger().warning(f'Invalid DIST value: {response}')
                        continue
                    # HC-SR04 : plage utile 2-400 cm, hors plage = lecture parasite
                    if distance < 2.0 or distance > 400.0:
                        self.get_logger().warning(
                            f'Ultrasonic reading out of range ignored: {distance:.1f} cm',
                            throttle_duration_sec=2.0
                        )
                        continue
                    message = Float32()
                    message.data = distance
                    self.ultrasonic_publisher.publish(message)
                    continue

                if response.startswith('IR,'):
                    parts = response.split(',')
                    if len(parts) != 3:
                        self.get_logger().warning(f'Invalid IR frame: {response}')
                        continue
                    side = parts[1].upper()
                    try:
                        state = int(parts[2])
                    except ValueError:
                        self.get_logger().warning(f'Invalid IR state: {response}')
                        continue
                    if state not in [0, 1]:
                        self.get_logger().warning(f'Invalid IR state: {response}')
                        continue
                    message = Int32()
                    message.data = state
                    if side == 'LEFT':
                        self.ir_left_publisher.publish(message)
                    elif side == 'RIGHT':
                        self.ir_right_publisher.publish(message)
                    else:
                        self.get_logger().warning(f'Unknown IR side: {side}')
                    continue

                if response.startswith('RESULT,'):
                    if self.active_vitals_request_id is not None:
                        self.publish_vitals_result(
                            self.active_vitals_request_id, response
                        )
                    else:
                        self.get_logger().warning(
                            f'Unsolicited vitals result: {response}'
                        )
                    continue

                if response.startswith('ERROR,'):
                    if self.active_vitals_request_id is not None:
                        self.publish_vitals_result(
                            self.active_vitals_request_id, response
                        )
                    else:
                        self.get_logger().warning(
                            f'ESP32 error without active request: {response}'
                        )
                    continue

                if response.startswith(('ACK,', 'REJECTED,', 'SAFETY,')):
                    status_message = String()
                    status_message.data = response
                    self.status_publisher.publish(status_message)
                    self.get_logger().info(f'ESP32 response: {response}')
                    continue

                self.get_logger().debug(f'ESP32: {response}')

        except serial.SerialException as error:
            self.get_logger().error(f'Serial communication error: {error}')
            self.get_logger().error('Communication with ESP32 lost. Robot must STOP.')
            self.close_serial_connection()

    def close_serial_connection(self):
        if self.serial_connection is not None:
            try:
                if self.serial_connection.is_open:
                    self.serial_connection.close()
                    self.get_logger().info('ESP32 serial connection closed.')
            except serial.SerialException as error:
                self.get_logger().error(f'Error closing serial connection: {error}')
            self.serial_connection = None


def main(args=None):
    rclpy.init(args=args)
    node = ESP32Interface()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close_serial_connection()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
