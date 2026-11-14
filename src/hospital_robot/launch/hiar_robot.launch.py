from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg = 'hospital_robot'
    return LaunchDescription([
        Node(package=pkg, executable='esp32_interface', output='screen'),
        Node(package=pkg, executable='obstacle_detector', output='screen'),
        Node(package=pkg, executable='robot_supervisor', output='screen'),
        Node(package=pkg, executable='navigation_decision', output='screen'),
        Node(package=pkg, executable='hmi_request_receiver', output='screen'),
    ])
