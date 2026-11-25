# EP_navigation_v1.1 — RoboMaster EP 自主导航系统

基于 ROS 2 Humble 的 RoboMaster EP + RPLIDAR A2 建图、定位、导航工作空间。

> **当前状态：** main 已同步 hi12-ros2 中通过操作员方向测试的底盘反馈修正：移除额外 180° 偏置、统一初始位姿和航向方向。本分支使用 EP 内置反馈，不启动外置 HI12 或 EKF；main 的完整部署与建图质量尚待单独验收。

## Jetson 容器构建

Jetson 宿主机使用 Ubuntu 20.04 和 ROS 1 Noetic，ROS 2 Humble 项目在 Ubuntu 22.04 容器中运行。目前小车运行的容器基于 hi12-ros2 部署版本；本地 main 的完整容器构建与部署尚待验收。

操作手册：[EP 小车 ROS 2 使用指南](docs/usage_guide.md)

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

建图默认启动 RViz2、关闭内置键盘窗口；可使用 `rviz:=false` 关闭画面，并在另一个终端运行键盘控制。导航默认 `autostart:=false`，需完成检查后再启用。

## 参考项目

- [jeguzzi/robomaster_ros](https://github.com/jeguzzi/robomaster_ros)：RoboMaster EP 和 S1 的 ROS 2 驱动项目。

## TF 坐标系

```
map ──(slam_toolbox / Nav2)──► odom ──(chassis.py)──► base_link ──(静态)──► laser_link
```

## 里程计方向状态

之前出现过前进及转向方向显示相反。方向修正在 hi12-ros2 的 use_hi12:=false 模式下得到操作员反馈正常，现已同步到本地 main；main 单独部署后的方向、地图质量和保存流程仍需验收。底盘断连和 TF 稳定性也需继续检查。

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
| 保存地图 | `ros2 run ep_navigation save_map [名称]` | 建图完成后保存 |
| 导航 | `ros2 launch ep_bringup navigation.launch.py map:=~/R_v1.1/maps/xxx.yaml` | 加载地图后导航 |

## 地图保存与导航

`maps/` 保存运行数据，不纳入 Git。小车上宿主机目录 `~/EP_navigation_Ros2/maps` 挂载到容器 `/maps`，二维地图保存在 `maps/2d/<地图名>/`。运行前需确保建图运行中且 /map 正常发布。

在 ROS 2 容器内（先加载环境）：

```bash
ros2 run ep_navigation save_map 教室
ros2 run ep_navigation save_map
```

不填名称时按北京时间 `年-月-日-时-分` 命名；同名地图会自动追加中文括号序号（如 教室（1）、教室（2）），原地图不会覆盖。每张地图包含同名 YAML 和 PGM。在 Jetson 宿主机上也可以使用兼容入口：

```bash
bash ~/EP_navigation_Ros2/scripts/save_map.sh 教室
bash ~/EP_navigation_Ros2/scripts/save_map.sh
```

例如地图保存在宿主机 `~/EP_navigation_Ros2/maps/2d/教室/`，则容器中对应 `/maps/2d/教室/`。导航前先停止建图并验证地图及定位：

```bash
ros2 launch ep_bringup navigation.launch.py map:=/maps/2d/教室/教室.yaml autostart:=true
```

切换运行版本或重建容器时，须确保 maps 目录仍挂载；旧地图目录 ~/ep_maps 不会自动迁移。


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

## License

MIT
