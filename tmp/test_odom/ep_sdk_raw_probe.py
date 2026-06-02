#!/usr/bin/env python3
import time
import argparse
from robomaster import robot

STATUS_NAMES = [
    "static_flag",
    "up_hill",
    "down_hill",
    "on_slope",
    "is_pickup",
    "slip_flag",
    "impact_x",
    "impact_y",
    "impact_z",
    "roll_over",
    "hill_static",
]


def print_tuple(name, fields):
    def cb(data):
        ts = time.time()
        items = []
        for k, v in zip(fields, data):
            if isinstance(v, float):
                items.append(f"{k}={v:+.5f}")
            else:
                items.append(f"{k}={v}")
        print(f"{ts:.3f} {name:<10} " + "  ".join(items), flush=True)
    return cb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conn", default="rndis", choices=["ap", "sta", "rndis"])
    parser.add_argument("--freq", type=int, default=20)
    parser.add_argument("--cs", type=int, default=1, choices=[0, 1])
    parser.add_argument("--test", choices=["none", "forward", "backward", "rotate_ccw", "rotate_cw"], default="none")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--speed", type=float, default=0.15)
    parser.add_argument("--yaw_speed", type=float, default=20.0)
    args = parser.parse_args()

    ep = robot.Robot()
    ep.initialize(conn_type=args.conn)
    ch = ep.chassis

    ch.sub_position(
        cs=args.cs,
        freq=args.freq,
        callback=print_tuple("position", ["x_m", "y_m", "z_deg_or_m"]),
    )

    ch.sub_velocity(
        freq=args.freq,
        callback=print_tuple("velocity", ["vgx", "vgy", "vgz", "vbx", "vby", "vbz"]),
    )

    ch.sub_attitude(
        freq=args.freq,
        callback=print_tuple("attitude", ["yaw_deg", "pitch_deg", "roll_deg"]),
    )

    ch.sub_imu(
        freq=args.freq,
        callback=print_tuple("imu", ["acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"]),
    )

    ch.sub_status(
        freq=5,
        callback=print_tuple("status", STATUS_NAMES),
    )

    print("Connected. Start raw SDK probe.", flush=True)
    print(f"conn={args.conn}, freq={args.freq}, cs={args.cs}, test={args.test}", flush=True)

    try:
        start = time.time()

        if args.test == "forward":
            print("TEST: forward", flush=True)
            while time.time() - start < args.duration:
                ch.drive_speed(x=args.speed, y=0, z=0, timeout=0.5)
                time.sleep(0.1)

        elif args.test == "backward":
            print("TEST: backward", flush=True)
            while time.time() - start < args.duration:
                ch.drive_speed(x=-args.speed, y=0, z=0, timeout=0.5)
                time.sleep(0.1)

        elif args.test == "rotate_ccw":
            print("TEST: rotate counterclockwise", flush=True)
            while time.time() - start < args.duration:
                ch.drive_speed(x=0, y=0, z=args.yaw_speed, timeout=0.5)
                time.sleep(0.1)

        elif args.test == "rotate_cw":
            print("TEST: rotate clockwise", flush=True)
            while time.time() - start < args.duration:
                ch.drive_speed(x=0, y=0, z=-args.yaw_speed, timeout=0.5)
                time.sleep(0.1)

        else:
            print("TEST: static observation only", flush=True)
            while time.time() - start < args.duration:
                time.sleep(0.2)

    finally:
        ch.drive_speed(x=0, y=0, z=0, timeout=1)
        ch.unsub_position()
        ch.unsub_velocity()
        ch.unsub_attitude()
        ch.unsub_imu()
        ch.unsub_status()
        ep.close()
        print("Stopped and closed.", flush=True)


if __name__ == "__main__":
    main()
