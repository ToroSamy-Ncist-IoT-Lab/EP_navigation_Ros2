from binascii import crc_hqx
from math import isclose, pi
from struct import pack, pack_into
from unittest import TestCase

from ep_bringup.hi12_imu import Hi91Stream


class TestHi91Stream(TestCase):
    def test_recovers_split_frames_after_invalid_crc(self):
        payload = bytearray(76)
        payload[0] = 0x91
        pack_into('<3f', payload, 12, 0.0, 0.0, 1.0)
        pack_into('<3f', payload, 24, 0.0, 0.0, 180.0)
        pack_into('<4f', payload, 60, 2.0, 0.0, 0.0, 0.0)
        header = b'\x5a\xa5' + pack('<H', len(payload))
        frame = header + pack('<H', crc_hqx(header + payload, 0)) + payload
        damaged = frame[:-1] + b'\x01'

        stream = Hi91Stream()
        self.assertEqual(list(stream.frames(b'noise' + damaged + frame[:1])), [])
        samples = list(stream.frames(frame[1:]))
        self.assertEqual(len(samples), 1)
        orientation, gyro, acceleration = samples[0]
        self.assertEqual(orientation, (0.0, 0.0, 0.0, 1.0))
        self.assertTrue(isclose(gyro[2], pi))
        self.assertTrue(isclose(acceleration[2], 9.80665))
