import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def include_launch(package, filename, **arguments):
    path = os.path.join(get_package_share_directory(package), 'launch', filename)
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(path), launch_arguments=arguments.items(),
    )


def hardware_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_hi12', default_value='false', choices=['true', 'false']),
        DeclareLaunchArgument('hi12_port', default_value='/dev/hi12_imu'),
        DeclareLaunchArgument('hi12_baud', default_value='115200'),
        DeclareLaunchArgument('hi12_yaw', default_value='0.0',
                              description='Physical IMU mounting yaw in radians'),
        DeclareLaunchArgument('lidar_port', default_value='/dev/ttyUSB0'),
        DeclareLaunchArgument('lidar_baud', default_value='256000'),
        OpaqueFunction(function=_hardware_nodes),
    ])


def _hardware_nodes(context):
    use_hi12 = IfCondition(LaunchConfiguration('use_hi12')).evaluate(context)
    lidar_port = LaunchConfiguration('lidar_port')
    if use_hi12:
        imu_path = LaunchConfiguration('hi12_port').perform(context)
        lidar_path = lidar_port.perform(context)
        if not os.path.exists(imu_path):
            raise RuntimeError(f'HI12 device is unavailable: {imu_path}')
        if not os.path.exists(lidar_path):
            raise RuntimeError(f'Lidar device is unavailable: {lidar_path}')
        if os.stat(imu_path).st_rdev == os.stat(lidar_path).st_rdev:
            raise RuntimeError('HI12 and lidar resolve to the same serial device')

    nodes = [
        include_launch(
            'robomaster_ros', 'ep.launch.py',
            publish_odom_tf='false' if use_hi12 else 'true',
            odom_topic='/odom/raw' if use_hi12 else '/odom',
            imu_topic='/imu/ep' if use_hi12 else '/imu',
        ),
        include_launch('ep_description', 'static_tf.launch.py'),
        Node(
            package='rplidar_ros',
            executable='rplidar_node',
            name='rplidar_node',
            output='screen',
            parameters=[{
                'channel_type': 'serial',
                'serial_port': lidar_port,
                'serial_baudrate': ParameterValue(LaunchConfiguration('lidar_baud'), value_type=int),
                'frame_id': 'laser_link',
                'inverted': False,
                'angle_compensate': True,
            }],
        ),
    ]
    if use_hi12:
        nodes.extend([
            Node(
                package='ep_bringup', executable='hi12_imu', output='screen',
                parameters=[{
                    'port': LaunchConfiguration('hi12_port'),
                    'baud': ParameterValue(LaunchConfiguration('hi12_baud'), value_type=int),
                }],
            ),
            Node(
                package='tf2_ros', executable='static_transform_publisher',
                arguments=['--x', '0', '--y', '-0.06', '--z', '0.10',
                           '--yaw', LaunchConfiguration('hi12_yaw'),
                           '--frame-id', 'base_link', '--child-frame-id', 'hi12_link'],
            ),
            Node(
                package='robot_localization', executable='ekf_node',
                name='ep_ekf', output='screen',
                parameters=[os.path.join(get_package_share_directory('ep_navigation'),
                                         'config', 'ekf_hi12.yaml')],
                remappings=[('odometry/filtered', '/odom')],
            ),
        ])
    return nodes


def rviz_node(mode):
    return Node(
        package='rviz2', executable='rviz2', output='screen',
        condition=IfCondition(LaunchConfiguration('rviz')),
        arguments=['-d', os.path.join(get_package_share_directory('ep_bringup'),
                                     'config', mode + '.rviz')],
    )
