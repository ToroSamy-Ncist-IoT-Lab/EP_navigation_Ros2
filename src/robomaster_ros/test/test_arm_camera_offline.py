"""Offline contract and unit tests for arm, gripper, servo, and camera integration."""

import ast
import importlib
import queue
import re
import sys
import threading
import time
import types
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch


REPO_ROOT = Path(__file__).resolve().parents[3]
MSGS_DIR = REPO_ROOT / 'src' / 'robomaster_msgs'
ROS_DIR = REPO_ROOT / 'src' / 'robomaster_ros'
BRINGUP_DIR = REPO_ROOT / 'src' / 'ep_bringup'


def _build_ros_sdk_stubs():
    """Create lightweight stub modules so robomaster_ros modules can be unit-tested offline."""
    stubs = {}

    def ensure_pkg(name):
        if name in stubs:
            return stubs[name]
        mod = types.ModuleType(name)
        mod.__path__ = []
        stubs[name] = mod
        if '.' in name:
            parent_name, child = name.rsplit('.', 1)
            parent = ensure_pkg(parent_name)
            setattr(parent, child, mod)
        return mod

    # numpy & quaternion stubs
    class _FakeArray:
        def __init__(self, data):
            self._data = data
            self.shape = (len(data), len(data[0]) if data else 0)

        @property
        def T(self):
            return self

    np_mod = ensure_pkg('numpy')
    np_mod.ndarray = _FakeArray
    np_mod.array = lambda data: _FakeArray(data)
    np_mod.linspace = lambda a, b, n: [a] * n
    np_mod.log10 = lambda x: 0.0
    np_mod.mean = lambda x: 0.0
    np_mod.power = lambda x, y: x
    np_mod.int16 = int
    np_mod.frombuffer = lambda buf, dtype=None: list(buf)

    quat_mod = ensure_pkg('quaternion')
    quat_mod.quaternion = object
    quat_mod.as_quat_array = lambda x: x

    # yaml stub
    yaml_mod = ensure_pkg('yaml')
    yaml_mod.SafeLoader = object
    yaml_mod.load = lambda *a, **kw: {}

    # rclpy & message stubs
    for name in [
        'rclpy', 'rclpy.node', 'rclpy.action', 'rclpy.action.server',
        'rclpy.callback_groups', 'rclpy.duration', 'rclpy.logging',
        'rclpy.qos', 'rclpy.time', 'rcl_interfaces', 'rcl_interfaces.msg',
        'geometry_msgs', 'geometry_msgs.msg', 'nav_msgs', 'nav_msgs.msg',
        'sensor_msgs', 'sensor_msgs.msg', 'std_msgs', 'std_msgs.msg',
        'std_srvs', 'std_srvs.srv',
        'robomaster_msgs', 'robomaster_msgs.msg', 'robomaster_msgs.action', 'robomaster_msgs.srv',
    ]:
        ensure_pkg(name)

    stubs['rcl_interfaces.msg'].ParameterDescriptor = MagicMock
    stubs['rcl_interfaces.msg'].SetParametersResult = lambda successful=True: types.SimpleNamespace(
        successful=successful
    )
    stubs['geometry_msgs.msg'].PointStamped = MagicMock
    stubs['geometry_msgs.msg'].Vector3 = MagicMock
    stubs['geometry_msgs.msg'].Point = MagicMock
    stubs['geometry_msgs.msg'].Twist = MagicMock
    stubs['geometry_msgs.msg'].TransformStamped = MagicMock
    stubs['nav_msgs.msg'].Odometry = MagicMock
    stubs['sensor_msgs.msg'].Image = MagicMock
    stubs['sensor_msgs.msg'].CameraInfo = MagicMock
    stubs['sensor_msgs.msg'].JointState = MagicMock
    stubs['sensor_msgs.msg'].BatteryState = MagicMock
    stubs['sensor_msgs.msg'].Imu = MagicMock
    stubs['std_srvs.srv'].SetBool = MagicMock
    stubs['robomaster_msgs.msg'].ArmorHit = MagicMock
    stubs['robomaster_msgs.msg'].ChassisStatus = MagicMock
    stubs['robomaster_msgs.msg'].WheelSpeeds = MagicMock
    stubs['robomaster_msgs.msg'].GripperState = MagicMock
    stubs['robomaster_msgs.msg'].CameraConfig = MagicMock
    stubs['robomaster_msgs.msg'].H264Packet = MagicMock
    stubs['robomaster_msgs.msg'].AudioData = MagicMock
    stubs['robomaster_msgs.msg'].AudioOpus = MagicMock
    stubs['robomaster_msgs.msg'].AudioLevel = MagicMock
    stubs['robomaster_msgs.msg'].ServoRawState = MagicMock
    stubs['robomaster_msgs.msg'].ServoCommand = MagicMock
    stubs['robomaster_msgs.action'].Move = MagicMock
    stubs['robomaster_msgs.action'].MoveArm = MagicMock
    stubs['robomaster_msgs.action'].GripperControl = MagicMock
    stubs['robomaster_msgs.action'].MoveServo = MagicMock
    stubs['robomaster_msgs.srv'].GetServoAngle = MagicMock

    # robomaster SDK stubs
    for name in [
        'robomaster', 'robomaster.robot', 'robomaster.robotic_arm',
        'robomaster.armor', 'robomaster.battery', 'robomaster.chassis',
        'robomaster.gripper', 'robomaster.protocol',
        'robomaster.action', 'robomaster.media', 'robomaster.config',
    ]:
        ensure_pkg(name)

    stubs['robomaster.armor'].ArmorHitEvent = type('ArmorHitEvent', (), {})
    stubs['robomaster.battery'].BatterySubject = type('BatterySubject', (), {})
    stubs['robomaster.gripper'].GripperSubject = type('GripperSubject', (), {})

    class FakeLiveView:
        def __init__(self, robot):
            self._robot = robot
            self._video_streaming = False
            self._audio_streaming = False

        def start_video_stream(self, display=False, addr=None, ip_proto='tcp'):
            self._video_streaming = True
            return True

        def stop_video_stream(self):
            self._video_streaming = False
            return True

        def start_audio_stream(self, addr=None, ip_proto='tcp'):
            self._audio_streaming = True
            return True

        def stop_audio_stream(self):
            self._audio_streaming = False
            return True

    stubs['robomaster.media'].LiveView = FakeLiveView
    stubs['robomaster.config'].ep_conf = types.SimpleNamespace(video_stream_proto='tcp')

    class FakeArmMoveAction:
        _target = 1

        def __init__(self, x, y, z=0, mode=1):
            self.x = x
            self.y = y
            self.z = z
            self.mode = mode
            self._action_id = 0

        def _get_next_action_id(self):
            return 1

    stubs['robomaster.robotic_arm'].RoboticArmMoveAction = FakeArmMoveAction
    stubs['robomaster.action'].Action = object
    stubs['robomaster.robot'].Robot = object

    return stubs


def _import_fresh(module_name: str, stubs: dict):
    ros_src = str(ROS_DIR)
    if ros_src not in sys.path:
        sys.path.insert(0, ros_src)
    for key in list(sys.modules):
        if key == 'robomaster_ros' or key.startswith('robomaster_ros.'):
            sys.modules.pop(key, None)
    with patch.dict(sys.modules, stubs):
        return importlib.import_module(module_name)


class TestPackageContracts(TestCase):
    def test_robomaster_msgs_cmakelists_matches_disk_interfaces(self):
        cmake = (MSGS_DIR / 'CMakeLists.txt').read_text(encoding='utf-8')
        declared = set(re.findall(r'"((?:msg|action|srv)/[^"]+)"', cmake))
        on_disk = {
            path.relative_to(MSGS_DIR).as_posix()
            for folder in ('msg', 'action', 'srv')
            for path in (MSGS_DIR / folder).glob('*.*')
        }
        self.assertEqual(declared, on_disk)
        self.assertIn('action/MoveArm.action', declared)
        self.assertIn('action/GripperControl.action', declared)
        self.assertIn('msg/GripperState.msg', declared)
        self.assertIn('msg/CameraConfig.msg', declared)
        self.assertIn('msg/ServoRawState.msg', declared)

    def test_launch_arguments_between_arm_camera_and_ep_launch_match(self):
        ep_tree = ast.parse((ROS_DIR / 'launch' / 'ep.launch.py').read_text(encoding='utf-8'))
        ep_declared = set()
        for node in ast.walk(ep_tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'DeclareLaunchArgument':
                if node.args and isinstance(node.args[0], ast.Constant):
                    ep_declared.add(node.args[0].value)

        ac_tree = ast.parse((BRINGUP_DIR / 'launch' / 'arm_camera.launch.py').read_text(encoding='utf-8'))
        passed_to_ep = set()
        for node in ast.walk(ac_tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'include_launch':
                for kw in node.keywords:
                    passed_to_ep.add(kw.arg)

        self.assertTrue(passed_to_ep, 'arm_camera.launch.py should forward arguments to ep.launch.py')
        self.assertEqual(passed_to_ep - ep_declared, set())

    def test_camera_calibration_yaml_files_have_valid_dimensions_and_matrices(self):
        expected_dims = {360: (640, 360), 540: (960, 540), 720: (1280, 720)}
        for res, (exp_w, exp_h) in expected_dims.items():
            cfg_path = ROS_DIR / 'config' / f'rm_camera_calibration_{res}.yaml'
            self.assertTrue(cfg_path.is_file(), f'Missing {cfg_path}')
            text = cfg_path.read_text(encoding='utf-8')
            w_match = re.search(r'^image_width:\s*(\d+)', text, re.M)
            h_match = re.search(r'^image_height:\s*(\d+)', text, re.M)
            self.assertIsNotNone(w_match)
            self.assertIsNotNone(h_match)
            self.assertEqual((int(w_match.group(1)), int(h_match.group(1))), (exp_w, exp_h))
            data_lists = re.findall(r'data:\s*\[([^\]]+)\]', text)
            lengths = [len([x for x in lst.split(',') if x.strip()]) for lst in data_lists]
            self.assertEqual(lengths, [9, 5, 9, 12], f'Unexpected calibration matrix lengths in {cfg_path.name}')


class TestCameraAndArmModuleFixes(TestCase):
    def test_camera_disabled_ffmpeg_does_not_warn_and_decoder_exits_without_hanging(self):
        stubs = _build_ros_sdk_stubs()
        cam_mod = _import_fresh('robomaster_ros.modules.camera', stubs)

        cam = cam_mod.Camera.__new__(cam_mod.Camera)
        cam.logger = MagicMock()
        cam._video_ffmpeg = cam_mod.ActiveMode.OFF
        cam._video_raw = cam_mod.ActiveMode.OFF
        cam._video_h264 = cam_mod.ActiveMode.OFF
        cam._video_raw_subscribers = 0
        cam._video_h264_subscribers = 0
        cam._video_ffmpeg_subscribers = 0
        cam.video_is_active = False
        cam.audio_is_active = False
        cam.count_subs_timer = MagicMock()
        cam.api = MagicMock()

        # DISABLED (-1) must not trigger FFmpeg warning
        cam.video_ffmpeg = cam_mod.ActiveMode.DISABLED
        cam.logger.warning.assert_not_called()

        # ON (1) still warns when FFmpeg/PyAV is absent
        cam.video_ffmpeg = cam_mod.ActiveMode.ON
        cam.logger.warning.assert_called_once()

        # Decoder task must exit promptly on stop even when _sock_queue never receives packets
        cam._video_stream_conn = types.SimpleNamespace(_sock_queue=queue.Queue())
        cam._video_streaming = True
        worker = threading.Thread(target=cam._video_decoder_task)
        worker.start()
        time.sleep(0.1)
        cam.abort()
        worker.join(timeout=1.5)
        self.assertFalse(worker.is_alive(), '_video_decoder_task hung on empty _sock_queue')

        # stop() cancels timer and stops active video stream, and is idempotent on GC __del__
        cam.video_is_active = True
        cam.stop()
        cam.stop()
        cam.count_subs_timer = MagicMock()
        cam.count_subs_timer.cancel.side_effect = RuntimeError('InvalidHandle')
        cam._stopped = False
        cam.stop()
        cam.api.stop_video_stream.assert_called_once()
        self.assertFalse(cam.video_is_active)

    def test_arm_joint_state_and_cmd_arm_before_first_position(self):
        stubs = _build_ros_sdk_stubs()
        arm_mod = _import_fresh('robomaster_ros.modules.arm', stubs)

        joints = arm_mod.arm_joint_state(left_motor=0.2, right_motor=-0.5)
        self.assertAlmostEqual(joints['arm_1_joint'], -0.5)
        self.assertAlmostEqual(joints['rod_joint'], 0.2)
        self.assertAlmostEqual(joints['rod_3_joint'], -0.7)

        arm = arm_mod.Arm.__new__(arm_mod.Arm)
        arm.x = None
        arm.z = None
        arm.logger = MagicMock()
        arm.robot = MagicMock()

        # Before first /arm_position callback, cmd_arm should be ignored safely
        arm.has_received_velocity_command(types.SimpleNamespace(x=0.01, z=0.02))
        arm.logger.warning.assert_called_once()
        arm.robot.client.send_msg.assert_not_called()

        # After receiving arm position (166mm, 71mm), cmd_arm computes absolute target and sends
        arm.x, arm.z = 166, 71
        with patch.dict(sys.modules, stubs):
            arm.has_received_velocity_command(types.SimpleNamespace(x=0.01, z=-0.02))
        arm.robot._action_dispatcher.get_msg_by_action.assert_called_once()
        sent_action = arm.robot._action_dispatcher.get_msg_by_action.call_args[0][0]
        self.assertEqual((sent_action.x, sent_action.y), (176, 51))
        arm.robot.client.send_msg.assert_called_once()
