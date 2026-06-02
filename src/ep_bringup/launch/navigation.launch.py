import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    map_arg = DeclareLaunchArgument(
        'map',
        default_value=os.path.expanduser('~/R_v1.1/maps/my_map.yaml'),
        description='Full path to map yaml file to load',
    )

    return LaunchDescription([
        map_arg,

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

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                get_package_share_directory('nav2_bringup'),
                '/launch/navigation_launch.py',
            ]),
            launch_arguments={
                'use_sim_time': 'False',
                'params_file': os.path.join(
                    get_package_share_directory('ep_navigation'),
                    'config', 'nav2_params.yaml'),
                'map': LaunchConfiguration('map'),
            }.items(),
        ),

        Node(
            package='rviz2',
            executable='rviz2',
            output='screen',
            arguments=['-d', os.path.join(
                get_package_share_directory('ep_bringup'),
                'config', 'navigation.rviz')],
        ),
    ])
