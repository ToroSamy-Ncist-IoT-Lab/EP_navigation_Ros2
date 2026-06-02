from setuptools import setup
import glob

package_name = 'robomaster_ros'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name, package_name + '.modules'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob.glob('launch/*.launch')),
        ('share/' + package_name + '/launch', glob.glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'numpy', 'numpy-quaternion', 'pyyaml', 'robomaster'],
    zip_safe=True,
    maintainer='Student',
    maintainer_email='student@example.com',
    description='RoboMaster EP ROS 2 driver for navigation',
    license='MIT',
    entry_points={
        'console_scripts': [
            'robomaster_driver = robomaster_ros.robomaster_driver:main',
        ],
    },
)
