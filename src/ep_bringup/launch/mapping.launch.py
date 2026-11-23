import os

from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from ep_bringup.hardware import hardware_description, rviz_node


def generate_launch_description():
    description = hardware_description()
    description.add_action(DeclareLaunchArgument('rviz', default_value='false'))
    description.add_action(DeclareLaunchArgument('teleop', default_value='false'))
    description.add_action(Node(
        package='slam_toolbox',
        executable='sync_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[os.path.join(get_package_share_directory('ep_navigation'),
                                 'config', 'mapper_params_online_async.yaml')],
    ))
    description.add_action(Node(
        package='teleop_twist_keyboard',
        executable='teleop_twist_keyboard',
        output='screen',
        prefix='xterm -e',
        condition=IfCondition(LaunchConfiguration('teleop')),
    ))
    description.add_action(rviz_node('mapping'))
    return description
