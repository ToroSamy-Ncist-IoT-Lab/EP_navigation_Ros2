from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from ep_bringup.hardware import include_launch


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('conn_type', default_value='rndis'),
        DeclareLaunchArgument('serial_number', default_value=''),
        DeclareLaunchArgument('arm_enabled', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('arm_rate', default_value='10'),
        DeclareLaunchArgument('gripper_enabled', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('open_gripper', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('camera_enabled', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('video_resolution', default_value='360', choices=['360', '540', '720']),
        DeclareLaunchArgument('video_raw', default_value='2'),
        DeclareLaunchArgument('video_h264', default_value='0'),
        DeclareLaunchArgument('video_rate', default_value='-1.0'),
        DeclareLaunchArgument('chassis_timeout', default_value='0.5'),
        include_launch(
            'robomaster_ros', 'ep.launch.py',
            conn_type=LaunchConfiguration('conn_type'),
            serial_number=LaunchConfiguration('serial_number'),
            arm_enabled=LaunchConfiguration('arm_enabled'),
            arm_rate=LaunchConfiguration('arm_rate'),
            gripper_enabled=LaunchConfiguration('gripper_enabled'),
            open_gripper=LaunchConfiguration('open_gripper'),
            camera_enabled=LaunchConfiguration('camera_enabled'),
            video_resolution=LaunchConfiguration('video_resolution'),
            video_raw=LaunchConfiguration('video_raw'),
            video_h264=LaunchConfiguration('video_h264'),
            video_rate=LaunchConfiguration('video_rate'),
            chassis_timeout=LaunchConfiguration('chassis_timeout'),
        ),
    ])
