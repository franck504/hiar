from unittest.mock import MagicMock, patch

from std_msgs.msg import String

from hospital_robot.robot_supervisor import RobotSupervisor


def make_node():
    node = MagicMock()
    node.current_state = "IDLE"
    node.obstacle_state = "UNKNOWN"
    node.current_command = "STOP"
    node.last_obstacle_time = None
    node.send_stop = MagicMock()
    node.send_motor_command = MagicMock()
    node.publish_status = MagicMock()
    node.get_logger = MagicMock()
    node.obstacle_state_is_fresh = (
        lambda: RobotSupervisor.obstacle_state_is_fresh(node)
    )
    return node


def make_message(value):
    message = String()
    message.data = value
    return message


def test_obstacle_state_is_not_fresh_before_first_measurement():
    node = make_node()

    assert RobotSupervisor.obstacle_state_is_fresh(node) is False


def test_fresh_clear_state_allows_forward():
    node = make_node()
    node.obstacle_state = "CLEAR"
    node.last_obstacle_time = 100.0

    with patch("time.monotonic", return_value=100.1):
        RobotSupervisor.command_callback(node, make_message("FORWARD"))

    node.send_motor_command.assert_called_once_with("FORWARD")
    node.send_stop.assert_not_called()


def test_stale_obstacle_state_rejects_forward():
    node = make_node()
    node.obstacle_state = "CLEAR"
    node.last_obstacle_time = 100.0

    with patch("time.monotonic", return_value=100.6):
        RobotSupervisor.command_callback(node, make_message("FORWARD"))

    node.send_stop.assert_called_once_with()
    node.send_motor_command.assert_not_called()


def test_obstacle_during_forward_triggers_stop():
    node = make_node()
    node.current_command = "FORWARD"

    with patch("time.monotonic", return_value=100.1):
        RobotSupervisor.obstacle_callback(node, make_message("OBSTACLE"))

    assert node.obstacle_state == "OBSTACLE"
    assert node.last_obstacle_time == 100.1
    node.send_stop.assert_called_once_with()


def test_watchdog_stops_forward_when_obstacle_state_is_stale():
    node = make_node()
    node.current_command = "FORWARD"
    node.last_obstacle_time = 100.0

    with patch("time.monotonic", return_value=100.6):
        RobotSupervisor.obstacle_watchdog_callback(node)

    node.send_stop.assert_called_once_with()
