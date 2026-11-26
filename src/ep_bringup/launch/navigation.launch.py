import os

from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from ep_bringup.hardware import hardware_description, include_launch, rviz_node


def generate_launch_description():
    description = hardware_description()
    description.add_action(DeclareLaunchArgument(
        'map', description='Path to the 2D occupancy map YAML'))
    description.add_action(DeclareLaunchArgument('autostart', default_value='false'))
    description.add_action(DeclareLaunchArgument('rviz', default_value='true'))
    description.add_action(include_launch(
        'nav2_bringup', 'bringup_launch.py',
        map=LaunchConfiguration('map'),
        params_file=os.path.join(get_package_share_directory('ep_navigation'),
                                 'config', 'nav2_params.yaml'),
        slam='False',
        use_sim_time='False',
        use_composition='False',
        autostart=LaunchConfiguration('autostart'),
    ))
    description.add_action(rviz_node('navigation'))
    return description
