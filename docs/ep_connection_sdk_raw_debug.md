# DJI RoboMaster EP 连接电脑与 SDK 原始状态调试手册

本文目标是先绕开 ROS、EKF、TF 和导航栈，直接查看 RoboMaster EP SDK 返回的底盘原始状态值。这样可以判断问题到底来自 EP 原始里程计/IMU，还是来自 ROS 坐标转换、`/odom` 发布或 EKF 配置。

参考资料：

- [RoboMaster SDK 连接方式](https://robomaster-dev-en.readthedocs.io/en/latest/python_sdk/connection.html)
- [RoboMaster SDK EP 入门](https://robomaster-dev.readthedocs.io/en/latest/python_sdk/beginner_ep.html)
- [RoboMaster SDK chassis 接口](https://robomaster-dev.readthedocs.io/zh-cn/latest/python_sdk/robomaster.html?highlight=chassis)

## 1. 连接方式选择

EP 支持三种 SDK 连接方式：

| 方式 | SDK 参数 | 适合场景 | 说明 |
|---|---|---|---|
| WiFi 直连 | `conn_type="ap"` | 首次调试、单车测试 | 电脑直接连接 EP 发出的 WiFi 热点 |
| WiFi 组网 | `conn_type="sta"` | 多设备、路由器环境 | EP 和电脑连接同一个路由器 |
| USB RNDIS | `conn_type="rndis"` | 车载电脑长期运行 | 通过 USB 把 EP 智能中控虚拟成网卡 |

建议顺序：

1. 首次验证用 `ap`，最简单。
2. 车载 Xavier / 工控机长期运行用 `rndis`。
3. 多台设备或固定实验室网络再用 `sta`。

## 2. WiFi 直连 AP 模式

操作步骤：

1. 打开 EP 电源。
2. 将智能中控连接模式切到直连/AP 模式。
3. 电脑连接 EP 的 WiFi 热点，名称通常类似 `RoboMaster-xxxx`。
4. 安装 SDK 后运行最小测试脚本。

最小测试：

```python
from robomaster import robot

ep = robot.Robot()
ep.initialize(conn_type="ap")

print(ep.get_version())

ep.close()
```

如果能打印版本号，说明 SDK 已经连接到 EP。

## 3. USB RNDIS 模式

操作步骤：

1. 用 USB 线连接电脑和 EP 智能中控 USB 口。
2. 电脑会识别出一个虚拟网卡。
3. EP 默认 IP 通常是 `192.168.42.2`。
4. 运行 RNDIS 测试。

Ubuntu / Xavier 上先检查：

```bash
ip addr
ping 192.168.42.2
```

最小测试：

```python
from robomaster import robot

ep = robot.Robot()
ep.initialize(conn_type="rndis")

print(ep.get_version())

ep.close()
```

如果 `ping` 通但 SDK 连不上，先检查是否有 ROS driver 或其他脚本正在占用 EP。

## 4. WiFi 组网 STA 模式

STA 方式需要先让 EP 加入路由器网络，电脑也连接同一个路由器。

最小测试：

```python
from robomaster import robot

ep = robot.Robot()
ep.initialize(conn_type="sta")

print(ep.get_version())

ep.close()
```

如果电脑有多个网卡，SDK 可能自动选择错误的本地 IP。可以手动指定：

```python
import robomaster
from robomaster import robot

robomaster.config.LOCAL_IP_STR = "你的电脑在该连接下的IP"

ep = robot.Robot()
ep.initialize(conn_type="sta")
print(ep.get_version())
ep.close()
```

例如电脑和 EP 都在 `192.168.2.x` 网段，电脑 IP 是 `192.168.2.20`，则：

```python
robomaster.config.LOCAL_IP_STR = "192.168.2.20"
```

## 5. 安装 Python SDK

在连接 EP 的电脑或 Xavier 上执行：

```bash
pip3 install robomaster
```

验证：

```bash
python3 -c "from robomaster import robot; print('robomaster sdk ok')"
```

如果是 Windows：

```powershell
python -m pip install robomaster
python -c "from robomaster import robot; print('robomaster sdk ok')"
```

## 6. 调试前先停掉 ROS driver

同一时间不要让 ROS driver、SDK 调试脚本、其他控制程序同时连接 EP。

ROS 环境中可以先停掉原 driver：

```bash
rosnode list
rosnode kill /你的_ep_driver_node
```

如果只是现场快速测试，也可以直接停掉所有 ROS 节点：

```bash
rosnode kill -a
```

## 7. SDK 原始状态查看脚本

新建文件：

```bash
ep_sdk_raw_probe.py
```

内容如下：

```python
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
    parser.add_argument("--conn", default="ap", choices=["ap", "sta", "rndis"])
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
```

赋权：

```bash
chmod +x ep_sdk_raw_probe.py
```

## 8. 静止测试

AP 直连：

```bash
python3 ep_sdk_raw_probe.py --conn ap --freq 20 --test none --duration 20
```

USB RNDIS：

```bash
python3 ep_sdk_raw_probe.py --conn rndis --freq 20 --test none --duration 20
```

STA 组网：

```bash
python3 ep_sdk_raw_probe.py --conn sta --freq 20 --test none --duration 20
```

静止时重点看：

```text
position: x_m, y_m
velocity: vbx, vby
attitude: yaw_deg
imu: gyro_z
status: slip_flag, is_pickup, on_slope
```

正常现象：

```text
position x/y 基本不变
vbx/vby 接近 0
yaw_deg 基本不变
gyro_z 接近 0
slip_flag = 0
is_pickup = 0
on_slope = 0
```

## 9. 前进测试

让小车沿地面胶带或直线标尺低速前进：

```bash
python3 ep_sdk_raw_probe.py --conn ap --freq 20 --test forward --duration 6 --speed 0.15
```

正常期望：

```text
velocity.vbx 为正
velocity.vby 接近 0
position.x 增加
position.y 接近 0
attitude.yaw_deg 不应明显变化
status.slip_flag 不应变 1
```

如果出现：

```text
vbx 正常
vby 接近 0
但 position.y 明显漂
```

说明 EP SDK 的 `sub_position` 平面位置估计本身不适合直接作为 ROS `/odom.pose`。

此时更推荐：

```text
odom.pose.x/y = vbx + yaw + dt 自己积分
sub_position 只作为调试值
```

## 10. 后退测试

```bash
python3 ep_sdk_raw_probe.py --conn ap --freq 20 --test backward --duration 6 --speed 0.15
```

正常期望：

```text
velocity.vbx 为负
position.x 减小或回到接近初始值
position.y 不应明显漂
```

如果前进和后退都导致 `position.y` 同向漂移，优先怀疑 EP 内部位置估计或坐标转换问题。

## 11. 原地旋转测试

逆时针旋转：

```bash
python3 ep_sdk_raw_probe.py --conn ap --freq 20 --test rotate_ccw --duration 5 --yaw_speed 20
```

顺时针旋转：

```bash
python3 ep_sdk_raw_probe.py --conn ap --freq 20 --test rotate_cw --duration 5 --yaw_speed 20
```

重点看：

```text
attitude.yaw_deg 是否稳定变化
imu.gyro_z 是否与 yaw_deg 同方向
position.x/y 是否在原地旋转时大幅跳变
```

如果原地旋转时 `position.x/y` 大幅变化，说明 `sub_position` 不适合直接进入导航栈。

## 12. 坐标与数据来源判定表

| 观测现象 | 可能结论 | 推荐处理 |
|---|---|---|
| `sub_position.y` 漂，但 `vby` 接近 0 | EP position 不可靠 | 不用 `sub_position` 做最终 `/odom.pose` |
| `vby` 本身明显不为 0 | 底盘真实横向滑移或轮组问题 | 检查轮子、地面、麦克纳姆轮安装方向 |
| `yaw_deg` 静止时明显漂 | EP 内置姿态不稳 | 使用外置 IMU，如 HI04 |
| `gyro_z` 和 ROS yaw 方向相反 | 坐标符号转换问题 | ROS 发布前反号 |
| `slip_flag=1` | EP 判断底盘打滑 | 这段数据不要用于标定 |
| 原地旋转时 `position.x/y` 跳 | EP 平面位置估计不稳 | 用 `vbx + yaw` 积分替代 |

## 13. 最终推荐数据链路

当前问题是 EP 前进时 `/odom` 的 x/y 都变，所以第一版不要直接相信 `sub_position`。

推荐：

```text
sub_velocity.vbx      -> odom.twist.linear.x
sub_velocity.vby      -> 第一版强制不用，odom.twist.linear.y = 0
sub_attitude.yaw      -> odom.pose.orientation
sub_imu.gyro_z        -> odom.twist.angular.z 或 /imu
sub_imu.acc_x/y/z     -> 只发布 /imu，不用来二次积分算位置
sub_position.x/y      -> 只发布 debug topic，不进 EKF
```

第一版 `/odom.pose.x/y` 用：

```python
dt = now - last_time
yaw = -math.radians(ep_yaw_deg) - yaw0
vx = vbx

x += vx * math.cos(yaw) * dt
y += vx * math.sin(yaw) * dt
```

如果以后胶带测试证明 `sub_position` 很稳定，再考虑把 pose 来源切回：

```text
x = ep_x
y = -ep_y
```

但切换前必须满足：

```text
直行 1m：x 接近 1m，y 接近 0
后退 1m：x 回到接近 0
原地旋转：x/y 不明显跳
逆时针转：ROS yaw 增加
```

## 14. 常见连接问题

### SDK 一直连接不上

检查：

```text
1. EP 是否开机
2. 电脑是否连接到 EP WiFi 或 USB RNDIS 网卡
3. 是否有 ROS driver 正在占用连接
4. conn_type 是否正确：ap / sta / rndis
5. 多网卡环境是否需要设置 LOCAL_IP_STR
```

### USB RNDIS ping 不通

检查：

```text
1. USB 线是否支持数据传输，不只是充电线
2. 电脑是否识别出新网卡
3. EP 是否处于正常开机状态
4. Ubuntu 是否需要重新插拔或重启网络管理器
```

### AP 模式能连 WiFi 但 SDK 失败

检查：

```text
1. 电脑是否真的拿到 EP 热点的 IP
2. 防火墙是否阻止 Python
3. 是否同时连接了有线网、校园网、虚拟网卡导致 SDK 选错 IP
```

多网卡时手动设置：

```python
import robomaster
robomaster.config.LOCAL_IP_STR = "电脑连接 EP 后的本地 IP"
```

## 15. 调试结论记录模板

每次测试建议记录：

```text
日期：
连接方式：ap / sta / rndis
地面材质：
轮子状态：
测试动作：静止 / 前进 / 后退 / 原地旋转
速度参数：

静止 position 漂移：
静止 yaw 漂移：
前进 1m 的 position.x：
前进 1m 的 position.y：
前进时 vbx：
前进时 vby：
前进时 slip_flag：
原地旋转时 position.x/y 是否跳：

结论：
下一步：
```

