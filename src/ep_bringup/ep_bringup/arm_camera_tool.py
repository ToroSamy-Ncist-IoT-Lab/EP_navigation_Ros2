"""Safe CLI helper for inspecting and exercising EP arm, gripper, and camera."""

import argparse
import math
from pathlib import Path
import sys
import time
from typing import Dict, Optional, Sequence, Tuple


# Conservative workspace limits in arm_base_link (meters) to avoid mechanical stops.
ARM_X_MIN_M = 0.07
ARM_X_MAX_M = 0.22
ARM_Z_MIN_M = -0.07
ARM_Z_MAX_M = 0.16
DEFAULT_MAX_STEP_M = 0.05
GRIPPER_POWER_MIN = 0.1
GRIPPER_POWER_MAX = 1.0

GRIPPER_STATE_NAMES: Dict[int, str] = {
    0: 'PAUSE',
    1: 'OPEN',
    2: 'CLOSE',
}
GRIPPER_ACTION_TO_STATE: Dict[str, int] = {
    'pause': 0,
    'open': 1,
    'close': 2,
}


def _require_finite(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite, got {value!r}')
    return float(value)


def validate_relative_move(
    dx: float, dz: float, max_step: float = DEFAULT_MAX_STEP_M
) -> Tuple[float, float]:
    """Validate relative arm displacement (meters) against a single-step safety cap."""
    dx = _require_finite('dx', dx)
    dz = _require_finite('dz', dz)
    max_step = _require_finite('max_step', max_step)
    if max_step <= 0.0:
        raise ValueError(f'max_step must be > 0, got {max_step}')
    if abs(dx) > max_step or abs(dz) > max_step:
        raise ValueError(
            f'Relative step ({dx:+.4f}, {dz:+.4f}) m exceeds safety cap +/-{max_step:.4f} m. '
            'Check units (meters, not millimeters) or raise --max-step explicitly.'
        )
    return dx, dz


def validate_absolute_target(x: float, z: float) -> Tuple[float, float]:
    """Validate absolute arm target coordinates (meters) against workspace bounds."""
    x = _require_finite('x', x)
    z = _require_finite('z', z)
    if not (ARM_X_MIN_M <= x <= ARM_X_MAX_M):
        raise ValueError(
            f'Target x={x:.4f} m outside safe range [{ARM_X_MIN_M:.2f}, {ARM_X_MAX_M:.2f}] m'
        )
    if not (ARM_Z_MIN_M <= z <= ARM_Z_MAX_M):
        raise ValueError(
            f'Target z={z:.4f} m outside safe range [{ARM_Z_MIN_M:.2f}, {ARM_Z_MAX_M:.2f}] m'
        )
    return x, z


def validate_gripper_command(action: str, power: float) -> Tuple[int, float]:
    """Validate gripper action name and power ratio."""
    key = action.strip().lower()
    if key not in GRIPPER_ACTION_TO_STATE:
        raise ValueError(f'Unknown gripper action {action!r}; choose from open, close, pause')
    power = _require_finite('power', power)
    if not (GRIPPER_POWER_MIN <= power <= GRIPPER_POWER_MAX):
        raise ValueError(
            f'Gripper power {power:.2f} outside safe range '
            f'[{GRIPPER_POWER_MIN:.1f}, {GRIPPER_POWER_MAX:.1f}]'
        )
    return GRIPPER_ACTION_TO_STATE[key], power


def validate_image_buffer(width: int, height: int, encoding: str, byte_len: int) -> str:
    """Validate basic sensor_msgs/Image dimensions and encoding for snapshot saving."""
    if width <= 0 or height <= 0:
        raise ValueError(f'Invalid image dimensions: {width}x{height}')
    enc = encoding.lower()
    if enc not in ('bgr8', 'rgb8'):
        raise ValueError(f'Unsupported image encoding {encoding!r}; expected bgr8 or rgb8')
    expected = width * height * 3
    if byte_len < expected:
        raise ValueError(f'Image buffer too small: got {byte_len} bytes, expected >= {expected}')
    return enc


def save_raw_ppm(path: Path, width: int, height: int, encoding: str, data: bytes) -> Path:
    """Pure-Python PPM fallback writer when OpenCV is unavailable."""
    enc = validate_image_buffer(width, height, encoding, len(data))
    pixel_bytes = data[: width * height * 3]
    if enc == 'bgr8':
        rgb = bytearray(len(pixel_bytes))
        rgb[0::3] = pixel_bytes[2::3]
        rgb[1::3] = pixel_bytes[1::3]
        rgb[2::3] = pixel_bytes[0::3]
        payload = bytes(rgb)
    else:
        payload = pixel_bytes
    header = f'P6\n{width} {height}\n255\n'.encode('ascii')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + payload)
    return path


def format_status_report(snapshot: Dict[str, object]) -> str:
    """Render collected telemetry dict into a concise human-readable report."""
    lines = ['EP Arm & Camera Status:']
    battery = snapshot.get('battery')
    lines.append(f'  battery      : {battery:.1f}%' if isinstance(battery, (int, float)) else '  battery      : N/A')

    arm_pos = snapshot.get('arm_position')
    if isinstance(arm_pos, tuple) and len(arm_pos) >= 3:
        frame = arm_pos[3] if len(arm_pos) > 3 else 'arm_base_link'
        lines.append(f'  arm_position : x={arm_pos[0]:.4f} m, z={arm_pos[2]:.4f} m ({frame})')
    else:
        lines.append('  arm_position : N/A')

    servos = snapshot.get('servo_raw_state')
    if isinstance(servos, dict):
        lines.append(f"  servos       : valid={servos.get('valid')} value={servos.get('value')}")
    else:
        lines.append('  servos       : N/A')

    gripper = snapshot.get('gripper')
    if isinstance(gripper, int):
        label = GRIPPER_STATE_NAMES.get(gripper, f'UNKNOWN({gripper})')
        lines.append(f'  gripper      : {label} ({gripper})')
    else:
        lines.append('  gripper      : N/A')

    cam_info = snapshot.get('camera_info')
    if isinstance(cam_info, tuple) and len(cam_info) >= 3:
        lines.append(f'  camera_info  : {cam_info[0]}x{cam_info[1]} ({cam_info[2]})')
    else:
        lines.append('  camera_info  : N/A (published once video stream is active)')

    return '\n'.join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='arm_camera_tool',
        description='Safe CLI helper for RoboMaster EP arm, gripper, and camera.',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    p_status = sub.add_parser('status', help='Read current battery, arm, servo, gripper, and camera info')
    p_status.add_argument('--timeout', type=float, default=3.0, help='Wait timeout in seconds')

    p_snap = sub.add_parser('snapshot', help='Capture one frame from /camera/image_color and save it')
    p_snap.add_argument('--out', default='/tmp/ep_snapshot.jpg', help='Output image path')
    p_snap.add_argument('--warmup', type=int, default=10, help='Frames to skip for auto-exposure')
    p_snap.add_argument('--timeout', type=float, default=8.0, help='Wait timeout in seconds')

    p_move = sub.add_parser('arm-move', help='Move arm relatively (meters) with safety step limit')
    p_move.add_argument('--dx', type=float, default=0.0, help='Forward delta in meters')
    p_move.add_argument('--dz', type=float, default=0.0, help='Upward delta in meters')
    p_move.add_argument(
        '--max-step', type=float, default=DEFAULT_MAX_STEP_M,
        help=f'Per-axis safety limit in meters (default {DEFAULT_MAX_STEP_M})',
    )
    p_move.add_argument('--timeout', type=float, default=10.0, help='Action timeout in seconds')
    p_move.add_argument('--dry-run', action='store_true', help='Validate command without sending')

    p_goto = sub.add_parser('arm-goto', help='Move arm to absolute (x, z) in arm_base_link (meters)')
    p_goto.add_argument('--x', type=float, required=True, help='Target x in meters')
    p_goto.add_argument('--z', type=float, required=True, help='Target z in meters')
    p_goto.add_argument('--timeout', type=float, default=10.0, help='Action timeout in seconds')
    p_goto.add_argument('--dry-run', action='store_true', help='Validate command without sending')

    p_grip = sub.add_parser('gripper', help='Open, close, or pause the EP gripper')
    p_grip.add_argument('action', choices=['open', 'close', 'pause'], help='Target gripper action')
    p_grip.add_argument('--power', type=float, default=0.5, help='Power ratio in [0.1, 1.0]')
    p_grip.add_argument('--timeout', type=float, default=10.0, help='Action timeout in seconds')
    p_grip.add_argument('--dry-run', action='store_true', help='Validate command without sending')

    return parser


def _run_status(timeout: float) -> int:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from geometry_msgs.msg import PointStamped
    from robomaster_msgs.msg import GripperState, ServoRawState
    from sensor_msgs.msg import BatteryState, CameraInfo

    rclpy.init()
    node = Node('ep_arm_camera_status')
    got: Dict[str, object] = {}
    latched_qos = QoSProfile(
        depth=1,
        history=HistoryPolicy.KEEP_LAST,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        reliability=ReliabilityPolicy.RELIABLE,
    )
    try:
        node.create_subscription(
            BatteryState, '/battery',
            lambda m: got.setdefault('battery', m.percentage * 100.0), 10,
        )
        node.create_subscription(
            PointStamped, '/arm_position',
            lambda m: got.setdefault('arm_position', (m.point.x, m.point.y, m.point.z, m.header.frame_id)),
            10,
        )
        node.create_subscription(
            ServoRawState, '/servo_raw_state',
            lambda m: got.setdefault('servo_raw_state', {'valid': list(m.valid[:2]), 'value': list(m.value[:2])}),
            10,
        )
        node.create_subscription(
            GripperState, '/gripper',
            lambda m: got.setdefault('gripper', int(m.state)), latched_qos,
        )
        node.create_subscription(
            CameraInfo, '/camera/camera_info',
            lambda m: got.setdefault('camera_info', (m.width, m.height, m.header.frame_id)), 10,
        )
        deadline = time.monotonic() + max(timeout, 0.5)
        while time.monotonic() < deadline and len(got) < 4:
            rclpy.spin_once(node, timeout_sec=0.1)
        print(format_status_report(got))
        return 0 if got else 1
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


def _run_snapshot(out_path: str, warmup: int, timeout: float) -> int:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Image

    rclpy.init()
    node = Node('ep_arm_camera_snapshot')
    captured: Dict[str, object] = {'count': 0, 'msg': None}
    warmup = max(0, warmup)

    def on_image(msg: Image) -> None:
        captured['count'] = int(captured['count']) + 1
        if int(captured['count']) > warmup and captured['msg'] is None:
            captured['msg'] = msg

    sub = node.create_subscription(Image, '/camera/image_color', on_image, 1)
    try:
        deadline = time.monotonic() + max(timeout, 1.0)
        while time.monotonic() < deadline and captured['msg'] is None:
            rclpy.spin_once(node, timeout_sec=0.05)
        msg = captured['msg']
        if msg is None:
            print('Timed out waiting for /camera/image_color', file=sys.stderr)
            return 1
        raw = bytes(msg.data)
        enc = validate_image_buffer(msg.width, msg.height, msg.encoding, len(raw))
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            import cv2
            import numpy as np

            frame = np.frombuffer(raw, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            if enc == 'rgb8':
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            if not cv2.imwrite(str(target), frame):
                raise RuntimeError(f'cv2.imwrite failed for {target}')
            saved_path = target
        except ImportError:
            saved_path = target.with_suffix('.ppm')
            save_raw_ppm(saved_path, msg.width, msg.height, enc, raw)
        print(f'Saved {msg.width}x{msg.height} ({enc}) snapshot to {saved_path}')
        return 0
    finally:
        node.destroy_subscription(sub)
        node.destroy_node()
        rclpy.try_shutdown()


def _run_arm_action(x: float, z: float, relative: bool, timeout: float) -> int:
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from robomaster_msgs.action import MoveArm

    rclpy.init()
    node = Node('ep_arm_action_client')
    client = ActionClient(node, MoveArm, '/move_arm')
    try:
        if not client.wait_for_server(timeout_sec=min(timeout, 5.0)):
            print('Action server /move_arm is unavailable', file=sys.stderr)
            return 1
        goal = MoveArm.Goal()
        goal.x = float(x)
        goal.z = float(z)
        goal.relative = bool(relative)
        send_future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, send_future, timeout_sec=timeout)
        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            print('MoveArm goal rejected or timed out', file=sys.stderr)
            return 1
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future, timeout_sec=timeout)
        res = result_future.result()
        if res is None:
            print('MoveArm result timed out', file=sys.stderr)
            return 1
        print(f'MoveArm finished (status={res.status})')
        return 0
    finally:
        client.destroy()
        node.destroy_node()
        rclpy.try_shutdown()


def _run_gripper_action(target_state: int, power: float, timeout: float) -> int:
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from robomaster_msgs.action import GripperControl

    rclpy.init()
    node = Node('ep_gripper_action_client')
    client = ActionClient(node, GripperControl, '/gripper')
    try:
        if not client.wait_for_server(timeout_sec=min(timeout, 5.0)):
            print('Action server /gripper is unavailable', file=sys.stderr)
            return 1
        goal = GripperControl.Goal()
        goal.target_state = int(target_state)
        goal.power = float(power)
        send_future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, send_future, timeout_sec=timeout)
        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            print('GripperControl goal rejected or timed out', file=sys.stderr)
            return 1
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future, timeout_sec=timeout)
        res = result_future.result()
        if res is None:
            print('GripperControl result timed out', file=sys.stderr)
            return 1
        print(f'GripperControl finished (status={res.status})')
        return 0
    finally:
        client.destroy()
        node.destroy_node()
        rclpy.try_shutdown()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'status':
            return _run_status(args.timeout)
        if args.command == 'snapshot':
            return _run_snapshot(args.out, args.warmup, args.timeout)
        if args.command == 'arm-move':
            dx, dz = validate_relative_move(args.dx, args.dz, args.max_step)
            if args.dry_run:
                print(f'[dry-run] MoveArm relative dx={dx:+.4f} m, dz={dz:+.4f} m')
                return 0
            return _run_arm_action(dx, dz, relative=True, timeout=args.timeout)
        if args.command == 'arm-goto':
            x, z = validate_absolute_target(args.x, args.z)
            if args.dry_run:
                print(f'[dry-run] MoveArm absolute x={x:.4f} m, z={z:.4f} m')
                return 0
            return _run_arm_action(x, z, relative=False, timeout=args.timeout)
        if args.command == 'gripper':
            state, power = validate_gripper_command(args.action, args.power)
            if args.dry_run:
                print(f'[dry-run] GripperControl state={GRIPPER_STATE_NAMES[state]} ({state}), power={power:.2f}')
                return 0
            return _run_gripper_action(state, power, timeout=args.timeout)
    except ValueError as exc:
        print(f'Invalid arguments: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
