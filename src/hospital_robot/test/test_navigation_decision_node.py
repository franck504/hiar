from unittest.mock import MagicMock

from hospital_robot.navigation_decision_node import NavigationDecision


def make_node(state):
    node = MagicMock()
    node.state = state
    node.now.return_value = 100.0
    node.state_start_time = 99.0
    node.mission_start_time = None
    node.center_distance = 10.0
    node.ir_left_state = 0
    node.ir_right_state = 0
    node.sensor_stop_sent = False
    node.turn_direction = None
    return node


def test_decide_enters_blocked_when_both_ir_sensors_are_blocked():
    node = make_node("DECIDE")
    node.sensors_ready.return_value = True
    node.decide.return_value = "STOP"

    NavigationDecision.step(node)

    node.send.assert_called_once_with("STOP")
    node.change_state.assert_called_once_with("BLOCKED")
    assert node.publish_text.call_count == 2


def test_blocked_does_not_resume_when_sensors_are_stale():
    node = make_node("BLOCKED")
    node.sensors_ready.return_value = False

    NavigationDecision.step(node)

    node.send.assert_not_called()
    node.change_state.assert_not_called()


def test_blocked_stays_blocked_when_both_directions_remain_blocked():
    node = make_node("BLOCKED")
    node.sensors_ready.return_value = True
    node.decide.return_value = "STOP"

    NavigationDecision.step(node)

    node.send.assert_not_called()
    node.change_state.assert_not_called()


def test_blocked_returns_to_decide_when_a_direction_is_safe():
    node = make_node("BLOCKED")
    node.sensors_ready.return_value = True
    node.decide.return_value = "LEFT"

    NavigationDecision.step(node)

    node.change_state.assert_called_once_with("DECIDE")
    node.send.assert_not_called()


def make_request_node(state="IDLE"):
    node = make_node(state)
    node.destination = None
    node.mission_start_time = None
    node.status_publisher = MagicMock()
    node.publish_text = MagicMock()
    node.get_logger = MagicMock()
    node.start_mission = MagicMock(
        side_effect=lambda: NavigationDecision.start_mission(node)
    )
    return node


def test_valid_navigation_request_starts_mission_when_sensors_are_ready():
    import json
    from std_msgs.msg import String

    node = make_request_node()
    node.sensors_ready.return_value = True
    message = String()
    message.data = json.dumps({
        "category": "ORIENTATION",
        "destination": "PHARMACY",
    })

    NavigationDecision.navigation_request_callback(node, message)

    assert node.destination == "PHARMACY"
    node.start_mission.assert_called_once_with()
    node.change_state.assert_called_once_with("DECIDE")
    node.publish_text.assert_any_call(
        node.status_publisher,
        "REQUEST_RECEIVED:PHARMACY",
    )


def test_invalid_navigation_destination_is_rejected():
    from std_msgs.msg import String

    node = make_request_node()
    message = String()
    message.data = (
        '{"category":"ORIENTATION","destination":"CAFETERIA"}'
    )

    NavigationDecision.navigation_request_callback(node, message)

    assert node.destination is None
    assert node.state == "IDLE"
    node.send.assert_not_called()
    node.publish_text.assert_not_called()
    node.get_logger().warning.assert_called_once()


def test_invalid_navigation_request_json_is_rejected():
    from std_msgs.msg import String

    node = make_request_node()
    message = String()
    message.data = '{"category":'

    NavigationDecision.navigation_request_callback(node, message)

    assert node.destination is None
    assert node.state == "IDLE"
    node.send.assert_not_called()
    node.publish_text.assert_not_called()
    node.get_logger().warning.assert_called_once()


def test_decide_treats_exactly_20_cm_as_clear():
    node = make_node("DECIDE")
    node.center_distance = 20.0

    assert NavigationDecision.decide(node) == "FORWARD"


def test_decide_treats_just_under_20_cm_as_blocked():
    node = make_node("DECIDE")
    node.center_distance = 19.9
    node.ir_left_state = 0
    node.ir_right_state = 0

    assert NavigationDecision.decide(node) == "STOP"


def test_start_is_rejected_without_valid_destination():
    from std_msgs.msg import String

    node = make_request_node("IDLE")
    message = String()
    message.data = "START"

    NavigationDecision.nav_command_callback(node, message)

    assert node.state == "IDLE"
    node.change_state.assert_not_called()
    node.send.assert_not_called()
    node.publish_text.assert_called_once_with(
        node.status_publisher,
        "START_REJECTED:NO_DESTINATION",
    )
    node.get_logger().warning.assert_called_once()


def test_stop_clears_selected_destination():
    from std_msgs.msg import String

    node = make_request_node("FORWARD")
    node.destination = "PHARMACY"
    message = String()
    message.data = "STOP"

    NavigationDecision.nav_command_callback(node, message)

    assert node.destination is None
    node.send.assert_called_once_with("STOP")
    node.change_state.assert_called_once_with("IDLE")


def test_start_mission_rejects_when_sensors_are_not_ready():
    node = make_request_node()
    node.destination = "PHARMACY"
    node.sensors_ready.return_value = False

    NavigationDecision.start_mission(node)

    node.send.assert_called_once_with("STOP")
    node.change_state.assert_not_called()
    node.publish_text.assert_called_once_with(
        node.status_publisher,
        "START_REJECTED:SENSORS_NOT_READY",
    )
    assert node.mission_start_time is None


def test_start_mission_records_start_time_when_sensors_are_ready():
    node = make_request_node()
    node.destination = "PHARMACY"
    node.sensors_ready.return_value = True

    NavigationDecision.start_mission(node)

    assert node.mission_start_time == 100.0
    node.change_state.assert_called_once_with("DECIDE")
    node.publish_text.assert_called_once_with(
        node.status_publisher,
        "RUNNING",
    )


def test_mission_timeout_sends_stop_and_returns_to_idle():
    node = make_request_node("FORWARD")
    node.destination = "PHARMACY"
    node.mission_start_time = 97.0

    NavigationDecision.step(node)

    node.send.assert_called_once_with("STOP")
    node.change_state.assert_called_once_with("IDLE")
    node.publish_text.assert_called_once_with(
        node.status_publisher,
        "MISSION_TIMEOUT",
    )
    assert node.destination is None
    assert node.mission_start_time is None


def test_forward_stops_and_rechecks_when_sensors_are_stale():
    node = make_node("FORWARD")
    node.sensors_ready.return_value = False

    NavigationDecision.step(node)

    node.send.assert_called_once_with("STOP")
    node.change_state.assert_called_once_with("DECIDE")
    assert node.sensor_stop_sent is True
    node.publish_text.assert_called_once_with(
        node.status_publisher,
        "SENSOR_NOT_READY",
    )
