"""Tests unitaires pour esp32_interface_node (inversion de direction moteurs)."""

from unittest.mock import MagicMock
from std_msgs.msg import String

from hospital_robot.esp32_interface_node import ESP32Interface


def make_esp32_node(invert_steering=True):
    node = MagicMock()
    node.serial_connection = MagicMock()
    node.serial_connection.write = MagicMock()
    node.get_logger = MagicMock()
    node.invert_steering = invert_steering
    node.active_vitals_request_id = None
    node.vitals_started_at = None
    node.compute_auth_response = lambda nonce: ESP32Interface.compute_auth_response(node, nonce)
    return node


def make_command_msg(cmd: str):
    msg = String()
    msg.data = cmd
    return msg


def test_command_callback_inverts_left_to_right_when_enabled():
    node = make_esp32_node(invert_steering=True)
    ESP32Interface.command_callback(node, make_command_msg("LEFT"))

    node.serial_connection.write.assert_called_once_with(b"RIGHT\n")


def test_command_callback_inverts_right_to_left_when_enabled():
    node = make_esp32_node(invert_steering=True)
    ESP32Interface.command_callback(node, make_command_msg("RIGHT"))

    node.serial_connection.write.assert_called_once_with(b"LEFT\n")


def test_command_callback_keeps_forward_and_backward():
    node = make_esp32_node(invert_steering=True)
    ESP32Interface.command_callback(node, make_command_msg("FORWARD"))
    node.serial_connection.write.assert_called_with(b"FORWARD\n")

    ESP32Interface.command_callback(node, make_command_msg("BACKWARD"))
    node.serial_connection.write.assert_called_with(b"BACKWARD\n")

    ESP32Interface.command_callback(node, make_command_msg("STOP"))
    node.serial_connection.write.assert_called_with(b"STOP\n")


def test_command_callback_does_not_invert_when_disabled():
    node = make_esp32_node(invert_steering=False)
    ESP32Interface.command_callback(node, make_command_msg("LEFT"))
    node.serial_connection.write.assert_called_with(b"LEFT\n")

    ESP32Interface.command_callback(node, make_command_msg("RIGHT"))
    node.serial_connection.write.assert_called_with(b"RIGHT\n")


def test_auth_challenge_generation_and_verification():
    node = make_esp32_node()
    node.auth_key = "test_esp32_key_123"
    node.require_auth = True
    node.authenticated = False

    ESP32Interface.send_auth_challenge(node)
    nonce = node.current_challenge_nonce
    assert nonce is not None
    assert len(nonce) == 8
    node.serial_connection.write.assert_called_once_with(f"AUTH,{nonce}\n".encode("utf-8"))

    # Vérification HMAC valide
    valid_hmac = ESP32Interface.compute_auth_response(node, nonce)
    assert len(valid_hmac) == 64


def test_unauthenticated_esp32_blocks_commands_when_auth_required():
    node = make_esp32_node()
    node.require_auth = True
    node.authenticated = False

    ESP32Interface.command_callback(node, make_command_msg("FORWARD"))
    node.serial_connection.write.assert_not_called()
    node.get_logger().error.assert_called_with(
        "Refusing motor command: ESP32 firmware authenticity not verified!"
    )


def test_read_serial_authenticates_on_valid_hmac():
    node = make_esp32_node()
    node.auth_key = "secret_key"
    node.require_auth = True
    node.authenticated = False
    node.current_challenge_nonce = "abcdef0123456789"
    node.status_publisher = MagicMock()

    valid_hmac = ESP32Interface.compute_auth_response(node, node.current_challenge_nonce)
    fake_line = f"AUTH_RESPONSE,hmac={valid_hmac}\n".encode("utf-8")

    node.serial_connection.in_waiting = 1
    # Premier appel renvoie la trame, 2e appel renvoie b""
    node.serial_connection.readline.side_effect = [fake_line, b""]

    ESP32Interface.read_serial(node)

    assert node.authenticated is True
    node.get_logger().info.assert_any_call("ESP32 integrity handshake verified: AUTH_OK")


def test_read_serial_rejects_on_invalid_hmac():
    node = make_esp32_node()
    node.auth_key = "secret_key"
    node.require_auth = True
    node.authenticated = False
    node.current_challenge_nonce = "abcdef0123456789"
    node.status_publisher = MagicMock()
    node.close_serial_connection = MagicMock()

    fake_line = b"AUTH_RESPONSE,hmac=invalid_signature_hex_00000000000000000000000000000000\n"

    node.serial_connection.in_waiting = 1
    node.serial_connection.readline.side_effect = [fake_line, b""]

    ESP32Interface.read_serial(node)

    assert node.authenticated is False
    node.close_serial_connection.assert_called_once()


def test_try_connect_serial_does_not_send_auth_challenge_when_auth_not_required(monkeypatch):
    node = make_esp32_node()
    node.require_auth = False
    node.authenticated = True
    node.port = "/dev/ttyUSB0"
    node._candidate_serial_ports = MagicMock(return_value=["/dev/ttyUSB0"])
    node._send_health_probe = MagicMock()
    node.send_auth_challenge = MagicMock()

    class FakeSerial:
        def __init__(self, *args, **kwargs):
            self.is_open = True
            self.in_waiting = 0

    monkeypatch.setattr("serial.Serial", FakeSerial)

    node.serial_connection = None
    res = ESP32Interface._try_connect_serial(node)
    assert res is True
    # send_auth_challenge ne DOIT PAS être appelé pour ne pas saturer le buffer ESP32 existant
    node.send_auth_challenge.assert_not_called()
    node._send_health_probe.assert_called_once()


