"""ROS 2 driver for the HiPNUC HI12 in HI91 serial mode."""

from binascii import crc_hqx
from math import hypot, isfinite, radians
from struct import unpack_from
from time import monotonic

HI91_SYNC = b'\x5a\xa5'
HI91_PAYLOAD_SIZE = 76
HI91_FRAME_SIZE = 6 + HI91_PAYLOAD_SIZE


class Hi91Stream:
    """Decode valid HI91 frames across arbitrary serial reads."""

    def __init__(self):
        self.buffer = bytearray()

    def frames(self, data):
        self.buffer.extend(data)
        while True:
            start = self.buffer.find(HI91_SYNC)
            if start < 0:
                self.buffer[:] = self.buffer[-1:] if self.buffer.endswith(b'\x5a') else b''
                return
            del self.buffer[:start]
            if len(self.buffer) < 6:
                return
            size, checksum = unpack_from('<HH', self.buffer, 2)
            if size != HI91_PAYLOAD_SIZE:
                del self.buffer[:2]
                continue
            if len(self.buffer) < HI91_FRAME_SIZE:
                return
            frame = self.buffer[:HI91_FRAME_SIZE]
            if crc_hqx(frame[:4] + frame[6:], 0) != checksum:
                del self.buffer[:1]
                continue
            del self.buffer[:HI91_FRAME_SIZE]
            if frame[6] != 0x91:
                continue

            acceleration = unpack_from('<3f', frame, 18)
            gyro = unpack_from('<3f', frame, 30)
            w, x, y, z = unpack_from('<4f', frame, 66)
            norm = hypot(w, x, y, z)
            if not all(isfinite(value) for value in (*acceleration, *gyro, norm)):
                continue
            if norm < 1e-6:
                continue
            yield (
                (x / norm, y / norm, z / norm, w / norm),
                tuple(radians(value) for value in gyro),
                tuple(value * 9.80665 for value in acceleration),
            )


def main(args=None):
    import rclpy
    import serial
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Imu

    class Hi12Imu(Node):
        def __init__(self):
            super().__init__('hi12_imu')
            self.port = self.declare_parameter('port', '/dev/hi12_imu').value
            self.baud = self.declare_parameter('baud', 115200).value
            self.frame_id = self.declare_parameter('frame_id', 'hi12_link').value
            self.stream = Hi91Stream()
            self.serial = None
            self.retry_at = 0.0
            self.publisher = self.create_publisher(Imu, '/imu/hi12', qos_profile_sensor_data)
            self.create_timer(0.02, self.poll)

        def poll(self):
            now = monotonic()
            if now < self.retry_at:
                return
            try:
                if self.serial is None:
                    self.serial = serial.Serial(self.port, self.baud, timeout=0)
                    self.get_logger().info(f'Opened HI12 at {self.port} ({self.baud} baud)')
                latest = None
                for sample in self.stream.frames(self.serial.read(4096)):
                    latest = sample
            except (serial.SerialException, OSError) as error:
                self.close()
                self.retry_at = now + 2.0
                self.get_logger().warning(f'HI12 unavailable, retrying: {error}')
                return

            if latest is None:
                return
            orientation, gyro, acceleration = latest
            msg = Imu()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.frame_id
            msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w = orientation
            msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = gyro
            msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = acceleration
            msg.orientation_covariance = [0.01, 0., 0., 0., 0.01, 0., 0., 0., 0.02]
            msg.angular_velocity_covariance = [0.0001, 0., 0., 0., 0.0001, 0., 0., 0., 0.0001]
            msg.linear_acceleration_covariance = [0.01, 0., 0., 0., 0.01, 0., 0., 0., 0.01]
            self.publisher.publish(msg)

        def close(self):
            if self.serial is not None:
                try:
                    self.serial.close()
                except OSError:
                    pass
                self.serial = None
            self.stream.buffer.clear()

    rclpy.init(args=args)
    node = Hi12Imu()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()
