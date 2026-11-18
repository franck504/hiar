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
