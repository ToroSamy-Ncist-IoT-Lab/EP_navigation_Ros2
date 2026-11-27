import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import TestCase

from ep_bringup import arm_camera_tool as tool


class TestArmCameraToolValidation(TestCase):
    def test_validate_relative_move_accepts_within_cap(self):
        self.assertEqual(tool.validate_relative_move(0.02, -0.05), (0.02, -0.05))
        self.assertEqual(tool.validate_relative_move(0.08, 0.0, max_step=0.10), (0.08, 0.0))

    def test_validate_relative_move_rejects_oversize_or_non_finite(self):
        with self.assertRaises(ValueError):
            tool.validate_relative_move(0.06, 0.0)
        with self.assertRaises(ValueError):
            tool.validate_relative_move(0.0, -20.0)  # millimeter typo guard
        with self.assertRaises(ValueError):
            tool.validate_relative_move(float('nan'), 0.0)
        with self.assertRaises(ValueError):
            tool.validate_relative_move(0.01, 0.0, max_step=0.0)

    def test_validate_absolute_target_bounds(self):
        self.assertEqual(tool.validate_absolute_target(0.166, 0.071), (0.166, 0.071))
        with self.assertRaises(ValueError):
            tool.validate_absolute_target(0.01, 0.07)
        with self.assertRaises(ValueError):
            tool.validate_absolute_target(0.16, 0.30)

    def test_validate_gripper_command(self):
        self.assertEqual(tool.validate_gripper_command('OPEN', 0.5), (1, 0.5))
        self.assertEqual(tool.validate_gripper_command('close', 0.8), (2, 0.8))
        self.assertEqual(tool.validate_gripper_command('pause', 0.1), (0, 0.1))
        with self.assertRaises(ValueError):
            tool.validate_gripper_command('grab', 0.5)
        with self.assertRaises(ValueError):
            tool.validate_gripper_command('open', 0.05)
        with self.assertRaises(ValueError):
            tool.validate_gripper_command('open', 1.5)

    def test_validate_image_and_save_ppm_swaps_bgr_to_rgb(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / 'frame.ppm'
            # 2x1 BGR image: pixel0=(B=10, G=20, R=30), pixel1=(B=1, G=2, R=3)
            raw = bytes([10, 20, 30, 1, 2, 3])
            saved = tool.save_raw_ppm(out, 2, 1, 'bgr8', raw)
            self.assertEqual(saved, out)
            content = out.read_bytes()
            self.assertEqual(content, b'P6\n2 1\n255\n' + bytes([30, 20, 10, 3, 2, 1]))

        with self.assertRaises(ValueError):
            tool.validate_image_buffer(640, 360, 'mono8', 640 * 360)
        with self.assertRaises(ValueError):
            tool.validate_image_buffer(640, 360, 'bgr8', 100)

    def test_format_status_report(self):
        text = tool.format_status_report({
            'battery': 99.0,
            'arm_position': (0.166, 0.0, 0.071, 'arm_base_link'),
            'servo_raw_state': {'valid': [True, True], 'value': [957, 1204]},
            'gripper': 0,
            'camera_info': (640, 360, 'camera_optical_link'),
        })
        self.assertIn('99.0%', text)
        self.assertIn('x=0.1660 m, z=0.0710 m', text)
        self.assertIn('PAUSE (0)', text)
        self.assertIn('640x360', text)

        empty_text = tool.format_status_report({})
        self.assertIn('battery      : N/A', empty_text)

    def test_cli_dry_run_and_error_codes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = tool.main(['arm-move', '--dx', '0.02', '--dz', '-0.01', '--dry-run'])
        self.assertEqual(rc, 0)
        self.assertIn('dx=+0.0200 m', out.getvalue())

        out = io.StringIO()
        with redirect_stdout(out):
            rc = tool.main(['arm-goto', '--x', '0.166', '--z', '0.071', '--dry-run'])
        self.assertEqual(rc, 0)
        self.assertIn('x=0.1660 m', out.getvalue())

        out = io.StringIO()
        with redirect_stdout(out):
            rc = tool.main(['gripper', 'open', '--power', '0.5', '--dry-run'])
        self.assertEqual(rc, 0)
        self.assertIn('OPEN (1)', out.getvalue())

        err = io.StringIO()
        with redirect_stderr(err):
            rc = tool.main(['arm-move', '--dx', '0.5', '--dry-run'])
        self.assertEqual(rc, 2)
        self.assertIn('exceeds safety cap', err.getvalue())
