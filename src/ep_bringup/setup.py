from setuptools import setup
import glob

package_name = 'ep_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob.glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob.glob('config/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Student',
    maintainer_email='student@example.com',
    description='Launch files for RoboMaster EP navigation',
    license='MIT',
    entry_points={
        'console_scripts': [
            'hi12_imu = ep_bringup.hi12_imu:main',
            'arm_camera_tool = ep_bringup.arm_camera_tool:main',
        ],
    },
)
