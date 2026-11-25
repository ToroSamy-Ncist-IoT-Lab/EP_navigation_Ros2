# EP_navigation_v1.1 — RoboMaster EP 自主导航系统

基于 ROS 2 Humble 的 RoboMaster EP + RPLIDAR A2 建图、定位、导航工作空间。

> **当前状态：** 已制作底盘反馈方向修正版：移除额外 180° 偏置、统一初始位姿，并修正航向变化方向。已通过纯计算检查并同步当前小车容器；操作员反馈本轮方向测试正常。地图质量与保存流程仍需单独验收，历史问题记录见下文。

操作手册：[EP 小车 ROS 2 远程操控与 RViz](docs/usage_guide.md)

## 系统需求

| 项目 | 要求 |
|------|------|
| 系统 | Ubuntu 22.04 |
| ROS | Humble |
| 机器人 | RoboMaster EP / EP Core |
| 雷达 | RPLIDAR A2 / A1 / LD19 |
| Python | 3.10+ |

## 系统架构

```
      键盘 / Nav2
          │ /cmd_vel
          ▼
┌────────────────┐    drive_speed()    ┌──────────────┐
│  robomaster_ros │◄──────────────────►│ RoboMaster EP │
│  (chassis.py)   │     EP SDK         │   (底盘)     │
│  /odom + /tf    │                    │              │
└────────┬───────┘                    └──────────────┘
         │ /odom + /tf                   RPLIDAR A2
         ▼                                    │ /scan
┌─────────────────────┐                       │
│  slam_toolbox / Nav2 │◄──────────────────────┘
│  (建图 / 定位 / 导航) │
└─────────────────────┘
```

## 包结构

| 包 | 构建类型 | 职责 |
|---|---------|------|
| `robomaster_msgs` | ament_cmake | 3 个自定义消息 + 1 个 Action |
| `robomaster_description` | ament_cmake | EP 完整 URDF 模型 + 3D 网格 |
| `robomaster_ros` | ament_python | 底盘驱动：chassis、battery、armor |
| `ep_description` | ament_python | 静态 TF：base_link → laser_link |
| `ep_navigation` | ament_python | slam_toolbox + Nav2 参数配置 |
| `ep_bringup` | ament_python | 一键启动 launch 文件 |

## 参考项目

- [jeguzzi/robomaster_ros](https://github.com/jeguzzi/robomaster_ros)：RoboMaster EP 和 S1 的 ROS 2 驱动项目。
- 本仓库包含用于 EP 底盘的 robomaster_ros 功能包；具体修改和配置以本仓库代码为准。

## TF 坐标系

```
map ──(slam_toolbox / Nav2)──► odom ──(chassis.py)──► base_link ──(静态)──► laser_link
```

## 位姿方向修正与历史排查记录

**现象：** 小车实际向前走时，RViz 中 odom→base_link 箭头向反方向移动；实际逆时针旋转时，图中显示顺时针。建图方向也相反。

**已尝试的修复（均未解决）：**

| 尝试 | 修改位置 | 结果 |
|------|----------|------|
| `yaw = rad(msg[0])`（去原版取反） | `updated_attitude` | 未解决 |
| `yaw = rad(msg[0]) + math.pi` | `updated_attitude` | 位置翻转但朝向未变（π 被 initial_yaw 抵消） |
| `initial_yaw` 存原始值 + `self.yaw` 保留 π | `updated_attitude` + `updated_position` | 仍无效 |

**推断：** 问题可能不在 yaw 数值本身，而在坐标系基础假设（URDF 的 base_link 方向、或 SDK 坐标系与 ROS ENU 的映射关系）。**下一步应通过 `/odom` 回读 + `cmd_vel` 测试来定位。**

**诊断命令：**
```bash
# 启动后读一次 odom
ros2 topic echo /odom --once

# 向前移动 0.1m
ros2 topic pub -1 /cmd_vel geometry_msgs/Twist "{linear: {x: 0.1}}"

# 再读一次 odom，看 position.x 增减
ros2 topic echo /odom --once
```

## Odom 修正说明

基于 SDK 原始数据诊断，chassis.py 已实施 4 处修正。诊断文档可从 Git 历史 `e8cc807:docs/` 追溯。

| 函数 | 行号 | 修改 | 说明 |
|------|------|------|------|
| `updated_position` | 369-375 | 加入 `-yaw0` 坐标旋转 | EP 帧增量旋转到 ROS odom 帧 |
| `updated_velocity` | 398-402 | `linear.y = 0` | 差速模式禁用横移 |
| `updated_imu` | 424 | `gyro_z` 因子 `-1→+1` | 与 yaw 符号一致（逆时针为正） |

**待验证：** yaw 朝向偏差（可能差 90° 或 180°），需实车测试后决定是否加偏置。

## 快速开始

### 1. 安装系统依赖

```bash
sudo apt install -y \
  ros-humble-desktop \
  ros-humble-rplidar-ros \
  ros-humble-slam-toolbox \
  ros-humble-nav2-bringup \
  ros-humble-teleop-twist-keyboard
```

### 2. 安装 RoboMaster SDK

`robomaster` 已从 PyPI 下架，需从 Gitee 源码安装：

```bash
curl -L -o /tmp/robomaster.zip https://gitee.com/robomaster-edu/RoboMaster-SDK/repository/archive/release_en.zip
cd /tmp && unzip robomaster.zip

# 安装主包
pip3 install /tmp/RoboMaster-SDK-release_en --no-deps

# 安装依赖
pip3 install numpy opencv-python netaddr netifaces myqr

# 编译安装 libmedia_codec（C 扩展）
sudo apt install -y cmake g++ libopus-dev
pip3 install /tmp/RoboMaster-SDK-release_en/lib/libmedia_codec --no-build-isolation
```

### 3. 安装 Python 依赖

```bash
pip3 install numpy-quaternion scipy
```

### 4. 串口权限

```bash
sudo usermod -a -G dialout $USER
# 重新登录后生效
```

### 5. 编译

```bash
cd ~/R_v1.1
colcon build
source install/setup.bash
```

### 6. 运行

```bash
# 加载 ROS 环境
source ~/R_v1.1/install/setup.bash
```

| 模式 | 命令 | 说明 |
|------|------|------|
| 键盘控制 | `ros2 launch ep_bringup teleop.launch.py` | USB 连接（默认 rndis） |
| 键盘控制（路由器） | `ros2 launch ep_bringup teleop.launch.py conn_type:=sta` | 局域网连接 |
| 键盘控制（直连） | `ros2 launch ep_bringup teleop.launch.py conn_type:=ap` | Wi-Fi 热点直连 |
| 建图 | `ros2 launch ep_bringup mapping.launch.py` | slam_toolbox 实时建图 |
| 保存地图 | `ros2 run nav2_map_server map_saver -f ~/R_v1.1/maps/xxx` | 建图完成后保存 |
| 导航 | `ros2 launch ep_bringup navigation.launch.py map:=~/R_v1.1/maps/xxx.yaml` | 加载地图后导航 |

## 键盘控制

```
teleop_twist_keyboard 键位图:
        前进 (i)
  左转(j) 停止(k)  右转(l)
        后退 (,)
   u=前+左  o=前+右  m=后+左  .=后+右
```

## 安全参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 雷达安装 | x=0.10m, y=0.0m, z=0.0m | 车体中心前方 10cm |
| 底盘超时 | 0.5s | 无指令自动停车 |
| 最大线速度 | 0.2 m/s | 限速防止失控 |
| 最大角速度 | 0.5 rad/s (~30°/s) | 限速防止失控 |
| 机器人半径 | 0.22m | costmap 足迹 |
| 膨胀半径 | 0.35m | 障碍物安全距离 |

## 连接模式

| 模式 | 参数 | 说明 |
|------|------|------|
| USB (RNDIS) | `conn_type:=rndis` | USB 线连接，默认模式 |
| 路由器 | `conn_type:=sta` | 电脑和 EP 在同一局域网 |
| 直连 | `conn_type:=ap` | 连接 EP 的 Wi-Fi 热点 |

## HI12 外置 IMU 与二维里程计

建图和导航入口共用底盘、二维雷达和里程计配置。默认启用 HI12 和 EKF；设置 `use_hi12:=false` 可改用 EP 内置反馈发布 `/odom` 和 `odom → base_link`。启用 HI12 时，驱动发布 `/odom/raw` 和 `/imu/ep`，HI12 发布 `/imu/hi12`，EKF 输出 `/odom` 并负责 `odom → base_link`。EKF 使用车体坐标系的底盘速度、HI12 的相对航向和 Z 轴角速度。接入前核对 HI12 安装方向，`hi12_yaw` 可设置模块相对车体的安装角，单位为弧度。

在 Jetson 上用 `/dev/serial/by-id/` 核对 HI12 和雷达各自对应的串口，再把两台设备分别映射进容器。`lidar_port`、`lidar_baud`、`hi12_port`、`hi12_baud` 可从 launch 传入。两者解析到同一个串口时，HI12 模式会拒绝启动。

只读检查 HI12 可以单独运行 `ros2 run ep_bringup hi12_imu --ros-args -p port:=/dev/hi12_imu`，再用 `ros2 topic echo /imu/hi12 --once` 查看消息。实车上继续核对直行方向和原地旋转方向，并检查 TF 只有一个 `odom → base_link` 发布者。

## Jetson 容器构建

`Dockerfile.jetson` 以 Jetson 上的 `ros2_robomaster_ep:latest` 镜像为基础，安装 HI12、二维雷达、SLAM Toolbox 和 Nav2 依赖，并在 `/opt/ep-navigation` 编译本仓库。构建后加载 `/opt/ep-navigation/install/setup.bash` 使用已安装的功能包。

```bash
docker build -f Dockerfile.jetson -t ep_navigation_ros2:hi12 .
```

启动入口和部署注意事项：

- `mapping.launch.py` 启动二维 SLAM 和 RViz2；`teleop` 默认关闭。无图形环境可使用 `rviz:=false`。
- `navigation.launch.py` 需要显式传入 `map:=<地图 YAML 路径>`，同时加载地图服务器、AMCL 和 Nav2。生命周期默认不自动激活，配置核对完成后再选择 `autostart:=true`。
- 单机调试先确认现有 EP 驱动的运行状态。每台小车同时由一个驱动进程连接。Foxglove 可用于查看话题和 TF。

## License

MIT
