import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                get_package_share_directory('robomaster_ros'), '/launch/ep.launch.py'
            ]),
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                get_package_share_directory('ep_description'), '/launch/static_tf.launch.py'
            ]),
        ),

        Node(
            package='rplidar_ros',
            executable='rplidar_node',
            name='rplidar_node',
            output='screen',
            parameters=[{
                'channel_type': 'serial',
                'serial_port': '/dev/ttyUSB0',
                'serial_baudrate': 256000,
                'frame_id': 'laser_link',
                'inverted': False,
                'angle_compensate': True,
            }],
        ),

        Node(
            package='slam_toolbox',
            executable='sync_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            parameters=[os.path.join(
                get_package_share_directory('ep_navigation'),
                'config', 'mapper_params_online_async.yaml'
            )],
        ),

        Node(
            package='teleop_twist_keyboard',
            executable='teleop_twist_keyboard',
            output='screen',
            prefix='xterm -e',
        ),

        Node(
            package='rviz2',
            executable='rviz2',
            output='screen',
            arguments=['-d', os.path.join(
                get_package_share_directory('ep_bringup'),
                'config', 'mapping.rviz')],
        ),
    ])
