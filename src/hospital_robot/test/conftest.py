"""Pytest configuration for hospital_robot tests.

If ROS 2 (rclpy, std_msgs) is not installed on the development machine,
provides lightweight mock modules so that tests can be collected and executed.
On the Raspberry Pi (or machines with ROS 2 installed), real ROS 2 is preserved.
"""

import sys
from unittest.mock import MagicMock

import pytest


def _ensure_ros_mocked():
    if "rclpy" not in sys.modules:
        try:
            import rclpy  # noqa: F401
        except ImportError:
            # Mock rclpy
            rclpy_mock = MagicMock()
            rclpy_mock.ok.return_value = True

            class MockNode:
                def __init__(self, name="mock_node", **kwargs):
                    self.name = name
                    self._params = {}
                def get_logger(self):
                    return MagicMock()
                def declare_parameter(self, name, value=None):
                    self._params[name] = value
                    return value
                def get_parameter(self, name):
                    class _P:
                        def __init__(self, val):
                            self.value = val
                    return _P(self._params.get(name))
                def create_publisher(self, *args, **kwargs):
                    pub = MagicMock()
                    pub.published = []
                    def _pub(msg):
                        pub.published.append(msg)
                    pub.publish = MagicMock(side_effect=_pub)
                    return pub
                def create_subscription(self, *args, **kwargs):
                    return MagicMock()
                def create_timer(self, *args, **kwargs):
                    return MagicMock()
                def destroy_node(self):
                    pass

            node_module = MagicMock()
            node_module.Node = MockNode
            rclpy_mock.node = node_module

            sys.modules["rclpy"] = rclpy_mock
            sys.modules["rclpy.node"] = node_module

            # Mock std_msgs and std_msgs.msg
            std_msgs_mock = MagicMock()
            std_msgs_msg_mock = MagicMock()

            class MockString:
                def __init__(self, data=""):
                    self.data = data
                def __repr__(self):
                    return f"String(data='{self.data}')"

            class MockFloat32:
                def __init__(self, data=0.0):
                    self.data = data

            class MockInt32:
                def __init__(self, data=0):
                    self.data = data

            std_msgs_msg_mock.String = MockString
            std_msgs_msg_mock.Float32 = MockFloat32
            std_msgs_msg_mock.Int32 = MockInt32

            std_msgs_mock.msg = std_msgs_msg_mock
            sys.modules["std_msgs"] = std_msgs_mock
            sys.modules["std_msgs.msg"] = std_msgs_msg_mock

    # Mock ament linters if not installed
    for ament_mod in [
        "ament_copyright",
        "ament_copyright.main",
        "ament_flake8",
        "ament_flake8.main",
        "ament_pep257",
        "ament_pep257.main",
    ]:
        if ament_mod not in sys.modules:
            try:
                __import__(ament_mod)
            except ImportError:
                m = MagicMock()
                m.main = MagicMock(return_value=0)
                m.main_with_errors = MagicMock(return_value=(0, []))
                sys.modules[ament_mod] = m


_ensure_ros_mocked()


def _ensure_web_interface_importable():
    """Rend `web_interface/` importable (le pont réserve via ses modules SQLite)."""
    from pathlib import Path

    web = Path(__file__).resolve().parents[3] / "web_interface"
    if web.is_dir() and str(web) not in sys.path:
        sys.path.insert(0, str(web))


_ensure_web_interface_importable()


@pytest.fixture(autouse=True)
def _isolated_appointments_db(tmp_path, monkeypatch):
    """Isole chaque test dans une base SQLite temporaire.

    Sans cela, les tests du pont (réservation « Alice Dupont »…) écrivaient dans la VRAIE base
    ``web_interface/instance/appointments.sqlite3`` : faux patients dans la file des médecins.
    """
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(tmp_path / "test_appointments.sqlite3"))
    yield
