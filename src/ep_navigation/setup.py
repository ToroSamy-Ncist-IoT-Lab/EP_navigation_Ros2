from setuptools import setup
import glob

package_name = 'ep_navigation'

setup(
    name=package_name,
    version='0.1.0',
    packages=['ep_navigation'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob.glob('config/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Student',
    maintainer_email='student@example.com',
    description='Navigation configuration for RoboMaster EP',
    license='MIT',
    entry_points={'console_scripts': ['save_map = ep_navigation.save_map:main']},
)
