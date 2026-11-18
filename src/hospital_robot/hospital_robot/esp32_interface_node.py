import glob
import json
import time

import serial
import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from std_msgs.msg import Float32


def parse_kv_frame(line, expected_prefix):
    """Parse une trame de type PREFIX,k1=v1,k2=v2 en dictionnaire."""
    parts = [p.strip() for p in line.split(',')]
    if not parts or parts[0] != expected_prefix:
        return None
    parsed = {}
    for item in parts[1:]:
        if '=' not in item:
            continue
        k, v = item.split('=', 1)
        parsed[k.strip()] = v.strip()
    return parsed


def _to_bool_flag(val):
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ('1', 'true', 'yes', 'ok'):
        return True
    if s in ('0', 'false', 'no'):
        return False
    return None


def _to_int_or_none(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _to_float_or_none(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class ESP32Interface(Node):

    def __init__(self):
        super().__init__('esp32_interface')

        self.port = '/dev/ttyUSB0'
        self.baudrate = 115200
        self.serial_connection = None
        self._last_connect_err_logged_at = 0.0

        # Etat vitaux
        self.active_vitals_request_id = None
        self.vitals_started_at = None
        self.vitals_timeout_s = 32.0

        # Etat diagnostics temps reel
        self.last_rx_at = None
        self.last_pong_at = None
        self.last_dist_cm = None
        self.last_dist_at = None
        self.last_dist_left_cm = None
        self.last_dist_left_at = None
        self.last_dist_right_cm = None
        self.last_dist_right_at = None
        self.ds18b20_ready = None
        self.max30102_ready = None
        self.us_reported_ok = None
        self.us_left_reported_ok = None
        self.us_right_reported_ok = None
        self.motors_ready = None
        self.motor_mode = 'IDLE'
        self.last_health_at = None
        self.last_poll_at = 0.0
        self.firmware_has_health = False

        # Inversion matérielle de direction (compense le sens des moteurs gauche/droite)
        self.declare_parameter('invert_steering', True)
        self.invert_steering = self.get_parameter('invert_steering').value

        self._try_connect_serial(initial=True)

        self.command_subscription = self.create_subscription(
            String, '/robot/motor_command', self.command_callback, 10
        )

        self.status_publisher = self.create_publisher(
            String, '/esp32/status', 10
        )

        self.diagnostics_publisher = self.create_publisher(
            String, '/esp32/diagnostics', 10
        )

        self.diagnostics_request_subscription = self.create_subscription(
            String, '/esp32/diagnostics/request', self.diagnostics_request_callback, 10
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

        self.ultrasonic_left_publisher = self.create_publisher(
            Float32, '/sensors/ultrasonic_left', 10
        )

        self.ultrasonic_right_publisher = self.create_publisher(
            Float32, '/sensors/ultrasonic_right', 10
        )

        self.serial_timer = self.create_timer(0.01, self.read_serial)
        self.diagnostics_timer = self.create_timer(2.0, self.diagnostics_tick)

        self.get_logger().info('ESP32 interface node started.')
        self.publish_diagnostics()

    def _candidate_serial_ports(self):
        candidates = [self.port]
        for pattern in ('/dev/ttyUSB*', '/dev/ttyACM*'):
            for found in sorted(glob.glob(pattern)):
                if found not in candidates:
                    candidates.append(found)
        return candidates

    def _try_connect_serial(self, initial=False):
        if self.serial_connection is not None:
            return True
        last_error = None
        for candidate in self._candidate_serial_ports():
            try:
                self.serial_connection = serial.Serial(
                    port=candidate,
                    baudrate=self.baudrate,
                    timeout=0.05
                )
                self.port = candidate
                self.get_logger().info(f'Connected to ESP32 on {self.port}')
                self.last_rx_at = time.monotonic()
                # Demander immédiatement l'état matériel après connexion
                self._send_health_probe()
                return True
            except (serial.SerialException, OSError) as error:
                self.serial_connection = None
                last_error = error

        now = time.monotonic()
        if initial or (now - self._last_connect_err_logged_at >= 30.0):
            self.get_logger().error(f'Unable to connect to ESP32: {last_error}')
            self._last_connect_err_logged_at = now
        return False

    def _send_health_probe(self):
        if self.serial_connection is None or self.active_vitals_request_id is not None:
            return
        try:
            self.serial_connection.write(b'PING\nSTATUS\n')
            self.last_poll_at = time.monotonic()
        except (serial.SerialException, OSError) as error:
            self.get_logger().error(f'Serial health probe error: {error}')
            self.close_serial_connection()

    def diagnostics_request_callback(self, message):
        """Déclenche une sonde santé immédiate à la demande (ex: popup Paramètres mobile)."""
        if self.serial_connection is None:
            self._try_connect_serial(initial=False)
        else:
            self._send_health_probe()
        self.publish_diagnostics()

    def diagnostics_tick(self):
        """Reconnexion auto USB + sonde santé périodique + publication /esp32/diagnostics."""
        if self.serial_connection is None:
            self._try_connect_serial(initial=False)
        else:
            now = time.monotonic()
            if (
                self.active_vitals_request_id is None
                and (now - self.last_poll_at >= 2.5)
            ):
                self._send_health_probe()

        self.publish_diagnostics()

    def build_diagnostics_dict(self, now=None):
        """Construit le snapshot JSON complet de l'état de l'ESP32 et de ses capteurs."""
        if now is None:
            now = time.monotonic()

        serial_open = self.serial_connection is not None and getattr(self.serial_connection, 'is_open', True)
        rx_age = (now - self.last_rx_at) if self.last_rx_at is not None else None
        esp_alive = serial_open and (rx_age is not None and rx_age <= 6.0)

        if not serial_open:
            esp_status = 'offline'
            esp_detail = f'Non branché ({self.port})'
        elif esp_alive:
            esp_status = 'ok'
            esp_detail = f'Connecté ({self.port})'
        else:
            esp_status = 'warn'
            esp_detail = f'Port ouvert sans réponse ({self.port})'

        # 1. Capteurs Ultrasons HC-SR04 (Avant, Gauche, Droite)
        def _us_entry(reported_ok, dist_cm, last_at):
            if not esp_alive:
                return {'status': 'offline', 'distance_cm': None, 'detail': 'ESP32 hors ligne'}
            age = (now - last_at) if last_at is not None else None
            if reported_ok is False and (age is None or age > 2.5):
                return {'status': 'absent', 'distance_cm': None, 'detail': 'Timeout / Non détecté'}
            if age is not None and age <= 3.0 and dist_cm is not None:
                return {
                    'status': 'ok',
                    'distance_cm': round(dist_cm, 1),
                    'detail': f'{dist_cm:.1f} cm',
                }
            return {'status': 'warn', 'distance_cm': None, 'detail': 'Aucun écho récent'}

        us_info = _us_entry(self.us_reported_ok, self.last_dist_cm, self.last_dist_at)
        us_left_info = _us_entry(
            self.us_left_reported_ok, self.last_dist_left_cm, self.last_dist_left_at
        )
        us_right_info = _us_entry(
            self.us_right_reported_ok, self.last_dist_right_cm, self.last_dist_right_at
        )

        # 2. Température DS18B20 (1-Wire)
        if not esp_alive:
            ds_info = {'status': 'offline', 'detail': 'ESP32 hors ligne'}
        elif self.ds18b20_ready is True:
            ds_info = {'status': 'ok', 'detail': '1-Wire OK (GPIO 23)'}
        elif self.ds18b20_ready is False:
            ds_info = {'status': 'absent', 'detail': 'Non détecté (1-Wire)'}
        else:
            ds_info = {'status': 'unknown', 'detail': 'En attente de sonde'}

        # 3. Pouls MAX30102 (I2C 0x57)
        if not esp_alive:
            pulse_info = {'status': 'offline', 'detail': 'ESP32 hors ligne'}
        elif self.max30102_ready is True:
            pulse_info = {'status': 'ok', 'detail': 'I²C OK (0x57)'}
        elif self.max30102_ready is False:
            pulse_info = {'status': 'absent', 'detail': 'Non détecté (I²C 0x57)'}
        else:
            pulse_info = {'status': 'unknown', 'detail': 'En attente de sonde'}

        # 4. Moteurs L298N
        if not esp_alive:
            motors_info = {'status': 'offline', 'mode': 'OFFLINE', 'detail': 'ESP32 hors ligne'}
        elif self.motors_ready is False:
            motors_info = {'status': 'warn', 'mode': self.motor_mode, 'detail': 'PWM non initialisé'}
        else:
            motors_info = {
                'status': 'ok',
                'mode': self.motor_mode,
                'detail': f'Prêt ({self.motor_mode})' if self.motor_mode == 'IDLE' else f'Actif ({self.motor_mode})',
            }

        return {
            'ts': round(time.time(), 2),
            'firmware_diagnostics': 'option_b' if self.firmware_has_health else 'legacy_status',
            'esp32': {
                'status': esp_status,
                'port': self.port,
                'detail': esp_detail,
            },
            'sensors': {
                'ultrasonic': us_info,
                'ultrasonic_left': us_left_info,
                'ultrasonic_right': us_right_info,
                'ds18b20': ds_info,
                'max30102': pulse_info,
                'motors': motors_info,
            },
        }

    def publish_diagnostics(self):
        payload = self.build_diagnostics_dict()
        msg = String()
        msg.data = json.dumps(payload)
        self.diagnostics_publisher.publish(msg)

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

        except (serial.SerialException, OSError) as error:
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

        # Inversion de direction gauche/droite pour compenser le câblage moteur
        serial_cmd = command
        if getattr(self, 'invert_steering', False):
            if command == 'LEFT':
                serial_cmd = 'RIGHT'
            elif command == 'RIGHT':
                serial_cmd = 'LEFT'

        try:
            self.serial_connection.write(f'{serial_cmd}\n'.encode('utf-8'))
            if serial_cmd != command:
                self.get_logger().info(
                    f'Sent to ESP32: {serial_cmd} (inverted steering from {command})'
                )
            else:
                self.get_logger().info(f'Sent to ESP32: {serial_cmd}')

        except (serial.SerialException, OSError) as error:
            self.get_logger().error(f'Serial communication error: {error}')
            self.get_logger().error('Communication with ESP32 lost. Robot must STOP.')
            self.close_serial_connection()

    def _handle_health_line(self, response, now):
        kv = parse_kv_frame(response, 'HEALTH')
        if not kv:
            return
        self.firmware_has_health = True
        self.last_health_at = now

        temp_flag = _to_bool_flag(kv.get('temp'))
        if temp_flag is not None:
            self.ds18b20_ready = temp_flag

        pulse_flag = _to_bool_flag(kv.get('pulse'))
        if pulse_flag is not None:
            self.max30102_ready = pulse_flag

        us_flag = _to_bool_flag(kv.get('us'))
        if us_flag is not None:
            self.us_reported_ok = us_flag

        dist_val = _to_float_or_none(kv.get('dist'))
        if dist_val is not None and 2.0 <= dist_val <= 400.0:
            self.last_dist_cm = dist_val
            self.last_dist_at = now

        us_l_flag = _to_bool_flag(kv.get('us_l'))
        if us_l_flag is not None:
            self.us_left_reported_ok = us_l_flag

        dist_l_val = _to_float_or_none(kv.get('dist_l'))
        if dist_l_val is not None and 2.0 <= dist_l_val <= 400.0:
            self.last_dist_left_cm = dist_l_val
            self.last_dist_left_at = now

        us_r_flag = _to_bool_flag(kv.get('us_r'))
        if us_r_flag is not None:
            self.us_right_reported_ok = us_r_flag

        dist_r_val = _to_float_or_none(kv.get('dist_r'))
        if dist_r_val is not None and 2.0 <= dist_r_val <= 400.0:
            self.last_dist_right_cm = dist_r_val
            self.last_dist_right_at = now

        motors_flag = _to_bool_flag(kv.get('motors'))
        if motors_flag is not None:
            self.motors_ready = motors_flag

        mode = kv.get('mode')
        if mode:
            self.motor_mode = mode

        self.publish_diagnostics()

    def _handle_ready_line(self, response, now):
        kv = parse_kv_frame(response, 'READY')
        if not kv:
            return
        temp_flag = _to_bool_flag(kv.get('temp'))
        if temp_flag is not None:
            self.ds18b20_ready = temp_flag
        pulse_flag = _to_bool_flag(kv.get('pulse'))
        if pulse_flag is not None:
            self.max30102_ready = pulse_flag
        self.last_health_at = now
        self.publish_diagnostics()

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

                now = time.monotonic()
                self.last_rx_at = now

                if response == 'PONG':
                    self.last_pong_at = now
                    continue

                if response.startswith('HEALTH,'):
                    self._handle_health_line(response, now)
                    continue

                if response.startswith('READY,'):
                    self._handle_ready_line(response, now)
                    continue

                if response.startswith(('DIST,', 'DIST_L,', 'DIST_R,')):
                    parts = response.split(',')
                    if len(parts) != 2:
                        self.get_logger().warning(f'Invalid DIST frame: {response}')
                        continue
                    prefix = parts[0]
                    try:
                        distance = float(parts[1])
                    except ValueError:
                        self.get_logger().warning(f'Invalid DIST value: {response}')
                        continue
                    # HC-SR04 : plage utile 2-400 cm, hors plage = lecture parasite
                    if distance < 2.0 or distance > 400.0:
                        self.get_logger().warning(
                            f'Ultrasonic reading ({prefix}) out of range ignored: {distance:.1f} cm',
                            throttle_duration_sec=2.0
                        )
                        continue
                    message = Float32()
                    message.data = distance
                    if prefix == 'DIST':
                        self.last_dist_cm = distance
                        self.last_dist_at = now
                        self.us_reported_ok = True
                        self.ultrasonic_publisher.publish(message)
                    elif prefix == 'DIST_L':
                        self.last_dist_left_cm = distance
                        self.last_dist_left_at = now
                        self.us_left_reported_ok = True
                        self.ultrasonic_left_publisher.publish(message)
                    elif prefix == 'DIST_R':
                        self.last_dist_right_cm = distance
                        self.last_dist_right_at = now
                        self.us_right_reported_ok = True
                        self.ultrasonic_right_publisher.publish(message)
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

        except (serial.SerialException, OSError) as error:
            self.get_logger().error(f'Serial communication error: {error}')
            self.get_logger().error('Communication with ESP32 lost. Robot must STOP.')
            self.close_serial_connection()

    def close_serial_connection(self):
        if self.serial_connection is not None:
            try:
                if self.serial_connection.is_open:
                    self.serial_connection.close()
                    self.get_logger().info('ESP32 serial connection closed.')
            except (serial.SerialException, OSError) as error:
                self.get_logger().error(f'Error closing serial connection: {error}')
            self.serial_connection = None
            self.publish_diagnostics()


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
