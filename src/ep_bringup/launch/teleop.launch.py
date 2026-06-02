from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([

        LogInfo(msg=[
            '========================================\n',
            '  teleop_twist_keyboard 键位图:\n',
            '        前进 (i)\n',
            '  左转(j) 停止(k)  右转(l)\n',
            '        后退 (,)\n',
            '   u=前+左  o=前+右  m=后+左  .=后+右\n',
            '========================================',
        ]),

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
            package='teleop_twist_keyboard',
            executable='teleop_twist_keyboard',
            output='screen',
            prefix='xterm -e',
        ),
    ])
