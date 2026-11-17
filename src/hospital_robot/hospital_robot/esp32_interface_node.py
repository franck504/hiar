import json
import time

import serial
import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from std_msgs.msg import Float32
from std_msgs.msg import Int32


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
        self.last_ir_left = None
        self.last_ir_left_at = None
        self.last_ir_left_raw = None
        self.last_ir_right = None
        self.last_ir_right_at = None
        self.last_ir_right_raw = None
        self.ds18b20_ready = None
        self.max30102_ready = None
        self.us_reported_ok = None
        self.motors_ready = None
        self.motor_mode = 'IDLE'
        self.last_health_at = None
        self.last_poll_at = 0.0
        self.firmware_has_health = False

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

        self.ir_left_publisher = self.create_publisher(
            Int32, '/sensors/ir_left', 10
        )

        self.ir_right_publisher = self.create_publisher(
            Int32, '/sensors/ir_right', 10
        )

        self.serial_timer = self.create_timer(0.01, self.read_serial)
        self.diagnostics_timer = self.create_timer(2.0, self.diagnostics_tick)

        self.get_logger().info('ESP32 interface node started.')
        self.publish_diagnostics()

    def _try_connect_serial(self, initial=False):
        if self.serial_connection is not None:
            return True
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.05
            )
            self.get_logger().info(f'Connected to ESP32 on {self.port}')
            self.last_rx_at = time.monotonic()
            # Demander immédiatement l'état matériel après connexion
            self._send_health_probe()
            return True
        except serial.SerialException as error:
            self.serial_connection = None
            now = time.monotonic()
            if initial or (now - self._last_connect_err_logged_at >= 30.0):
                self.get_logger().error(f'Unable to connect to ESP32: {error}')
                self._last_connect_err_logged_at = now
            return False

    def _send_health_probe(self):
        if self.serial_connection is None or self.active_vitals_request_id is not None:
            return
        try:
            self.serial_connection.write(b'PING\nSTATUS\n')
            self.last_poll_at = time.monotonic()
        except serial.SerialException as error:
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

        # 1. Ultrason HC-SR04
        dist_age = (now - self.last_dist_at) if self.last_dist_at is not None else None
        if not esp_alive:
            us_info = {'status': 'offline', 'distance_cm': None, 'detail': 'ESP32 hors ligne'}
        elif self.us_reported_ok is False and (dist_age is None or dist_age > 2.5):
            us_info = {'status': 'absent', 'distance_cm': None, 'detail': 'Timeout / Non détecté'}
        elif dist_age is not None and dist_age <= 3.0 and self.last_dist_cm is not None:
            us_info = {
                'status': 'ok',
                'distance_cm': round(self.last_dist_cm, 1),
                'detail': f'{self.last_dist_cm:.1f} cm',
            }
        else:
            us_info = {'status': 'warn', 'distance_cm': None, 'detail': 'Aucun écho récent'}

        # 2. IR Gauche & Droite
        def _ir_entry(state, last_at, raw_adc):
            if not esp_alive:
                return {'status': 'offline', 'state': None, 'raw': None, 'detail': 'ESP32 hors ligne'}
            age = (now - last_at) if last_at is not None else None
            if age is None or age > 3.5 or state is None:
                return {'status': 'warn', 'state': None, 'raw': raw_adc, 'detail': 'Pas de signal récent'}
            label = 'Libre' if state == 1 else 'Obstacle'
            detail = f'{label} (ADC {raw_adc})' if raw_adc is not None else label
            return {'status': 'ok', 'state': state, 'raw': raw_adc, 'detail': detail}

        ir_left_info = _ir_entry(self.last_ir_left, self.last_ir_left_at, self.last_ir_left_raw)
        ir_right_info = _ir_entry(self.last_ir_right, self.last_ir_right_at, self.last_ir_right_raw)

        # 3. Température DS18B20 (1-Wire)
        if not esp_alive:
            ds_info = {'status': 'offline', 'detail': 'ESP32 hors ligne'}
        elif self.ds18b20_ready is True:
            ds_info = {'status': 'ok', 'detail': '1-Wire OK (GPIO 23)'}
        elif self.ds18b20_ready is False:
            ds_info = {'status': 'absent', 'detail': 'Non détecté (1-Wire)'}
        else:
            ds_info = {'status': 'unknown', 'detail': 'En attente de sonde'}

        # 4. Pouls MAX30102 (I2C 0x57)
        if not esp_alive:
            pulse_info = {'status': 'offline', 'detail': 'ESP32 hors ligne'}
        elif self.max30102_ready is True:
            pulse_info = {'status': 'ok', 'detail': 'I²C OK (0x57)'}
        elif self.max30102_ready is False:
            pulse_info = {'status': 'absent', 'detail': 'Non détecté (I²C 0x57)'}
        else:
            pulse_info = {'status': 'unknown', 'detail': 'En attente de sonde'}

        # 5. Moteurs L298N
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
                'ir_left': ir_left_info,
                'ir_right': ir_right_info,
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

        ir_l = _to_int_or_none(kv.get('ir_l'))
        if ir_l in (0, 1):
            self.last_ir_left = ir_l
            self.last_ir_left_at = now
        ir_l_raw = _to_int_or_none(kv.get('ir_l_raw'))
        if ir_l_raw is not None:
            self.last_ir_left_raw = ir_l_raw

        ir_r = _to_int_or_none(kv.get('ir_r'))
        if ir_r in (0, 1):
            self.last_ir_right = ir_r
            self.last_ir_right_at = now
        ir_r_raw = _to_int_or_none(kv.get('ir_r_raw'))
        if ir_r_raw is not None:
            self.last_ir_right_raw = ir_r_raw

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

                if response.startswith('IR_RAW,'):
                    parts = response.split(',')
                    if len(parts) == 3:
                        side = parts[1].upper()
                        raw_val = _to_int_or_none(parts[2])
                        if raw_val is not None:
                            if side == 'LEFT':
                                self.last_ir_left_raw = raw_val
                            elif side == 'RIGHT':
                                self.last_ir_right_raw = raw_val
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
                    self.last_dist_cm = distance
                    self.last_dist_at = now
                    self.us_reported_ok = True
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
                        self.last_ir_left = state
                        self.last_ir_left_at = now
                        self.ir_left_publisher.publish(message)
                    elif side == 'RIGHT':
                        self.last_ir_right = state
                        self.last_ir_right_at = now
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
