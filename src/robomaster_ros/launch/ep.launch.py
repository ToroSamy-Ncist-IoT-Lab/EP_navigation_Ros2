import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, EnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'serial_number',
            default_value=EnvironmentVariable('RM_SERIAL_NUMBER', default_value=''),
            description='EP serial number. Leave empty to auto-detect.'),
        DeclareLaunchArgument(
            'conn_type', default_value='rndis',
            description='Connection type: sta (router), ap (direct), or rndis (USB)'),
        DeclareLaunchArgument(
            'chassis_timeout', default_value='0.5',
            description='Cmd vel timeout in seconds.'),
        DeclareLaunchArgument(
            'chassis_rate', default_value='10',
            description='Chassis update rate: 0, 1, 5, 10, 20, 50'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory('robomaster_description'),
                             'launch', 'model.launch.py')
            ),
            launch_arguments={'model': 'ep'}.items(),
        ),

        Node(
            package='robomaster_ros',
            executable='robomaster_driver',
            name='robomaster',
            output='screen',
            parameters=[{
                'serial_number': LaunchConfiguration('serial_number'),
                'conn_type': LaunchConfiguration('conn_type'),
                'chassis.enabled': True,
                'chassis.rate': LaunchConfiguration('chassis_rate'),
                'chassis.timeout': LaunchConfiguration('chassis_timeout'),
                'chassis.status.rate': 1,
                'chassis.error.linear_velocity.xy': 0.005,
                'chassis.error.angular_velocity.xy': 0.01,
                'chassis.error.angular_velocity.z': 0.03,
                'chassis.error.linear_acceleration.xyz': 0.1,
                'battery.enabled': True,
                'armor.enabled': True,
                'armor.sensitivity': 0.5,
            }],
        ),
    ])
