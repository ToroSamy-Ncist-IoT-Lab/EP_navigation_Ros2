import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, EnvironmentVariable
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


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

        DeclareLaunchArgument('publish_odom_tf', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('odom_topic', default_value='odom'),
        DeclareLaunchArgument('imu_topic', default_value='imu'),

        DeclareLaunchArgument('arm_enabled', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('arm_rate', default_value='10'),
        DeclareLaunchArgument('gripper_enabled', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('open_gripper', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('camera_enabled', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('video_resolution', default_value='360', choices=['360', '540', '720']),
        DeclareLaunchArgument('video_raw', default_value='2',
                              description='Raw image topic mode: OFF=0, ON=1, ON_DEMAND=2, DISABLED=-1'),
        DeclareLaunchArgument('video_h264', default_value='0',
                              description='H264 topic mode: OFF=0, ON=1, ON_DEMAND=2, DISABLED=-1'),
        DeclareLaunchArgument('video_rate', default_value='-1.0',
                              description='Max camera FPS (<0 means no throttling)'),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory('robomaster_description'),
                             'launch', 'model.launch.py')
            ),
            launch_arguments={'model': 'ep'}.items(),
        ),

        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen',
            parameters=[{
                'source_list': ['joint_states_p'],
                'rate': 10.0,
            }],
            arguments=['--ros-args', '--log-level', 'warn'],
        ),

        Node(
            package='robomaster_ros',
            executable='robomaster_driver',
            name='robomaster',
            remappings=[
                ('odom', LaunchConfiguration('odom_topic')),
                ('imu', LaunchConfiguration('imu_topic')),
            ],
            output='screen',
            parameters=[{
                'serial_number': LaunchConfiguration('serial_number'),
                'conn_type': LaunchConfiguration('conn_type'),
                'chassis.enabled': True,
                'chassis.publish_odom_tf': ParameterValue(
                    LaunchConfiguration('publish_odom_tf'), value_type=bool),
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
                'arm.enabled': ParameterValue(
                    LaunchConfiguration('arm_enabled'), value_type=bool),
                'arm.rate': ParameterValue(
                    LaunchConfiguration('arm_rate'), value_type=int),
                'gripper.enabled': ParameterValue(
                    LaunchConfiguration('gripper_enabled'), value_type=bool),
                'gripper.open': ParameterValue(
                    LaunchConfiguration('open_gripper'), value_type=bool),
                'camera.enabled': ParameterValue(
                    LaunchConfiguration('camera_enabled'), value_type=bool),
                'camera.video.raw': ParameterValue(
                    LaunchConfiguration('video_raw'), value_type=int),
                'camera.video.h264': ParameterValue(
                    LaunchConfiguration('video_h264'), value_type=int),
                'camera.video.ffmpeg': -1,
                'camera.video.resolution': ParameterValue(
                    LaunchConfiguration('video_resolution'), value_type=int),
                'camera.video.rate': ParameterValue(
                    LaunchConfiguration('video_rate'), value_type=float),
                'camera.video.calibration_file': ParameterValue([
                    os.path.join(get_package_share_directory('robomaster_ros'),
                                 'config', 'rm_camera_calibration_'),
                    LaunchConfiguration('video_resolution'),
                    '.yaml',
                ], value_type=str),
                'camera.audio.raw': 0,
                'camera.audio.opus': 0,
                'camera.audio.level': 0,
            }],
        ),
    ])
