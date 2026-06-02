# EP_navigation_v1.1 - RoboMaster EP ROS 2 Humble 导航工作空间

## 工作空间类型
ROS 2 Humble colcon 工作空间，用于 RoboMaster EP + RPLIDAR A2 建图与导航。

## 包结构与职责

| 包 | 类型 | 说明 |
|---|------|------|
| `robomaster_msgs` | ament_cmake | 消息定义 (ChassisStatus, WheelSpeeds, ArmorHit, Move.action) |
| `robomaster_description` | ament_cmake | EP URDF 模型 + meshes |
| `robomaster_ros` | ament_python | EP 底盘驱动 (chassis/battery/armor 模块) |
| `ep_description` | ament_python | 静态 TF base_link → laser_link |
| `ep_navigation` | ament_python | slam_toolbox + Nav2 参数配置 |
| `ep_bringup` | ament_python | 一键启动 launch 文件 |

## 入口点

| 包 | 入口 | 说明 |
|---|------|------|
| `robomaster_ros` | `robomaster_ros/robomaster_driver.py` | 主驱动节点入口 |
| `robomaster_ros` | `robomaster_ros/client.py` | RoboMasterROS 类（连接 EP + 加载模块） |
| `ep_bringup` | `launch/teleop.launch.py` | 键盘控制模式 |
| `ep_bringup` | `launch/mapping.launch.py` | 建图模式 |
| `ep_bringup` | `launch/navigation.launch.py` | 导航模式 |
| `ep_description` | `launch/static_tf.launch.py` | base_link → laser_link 静态 TF |

## 配置文件

| 文件 | 说明 |
|------|------|
| `ep_navigation/config/mapper_params_online_async.yaml` | slam_toolbox 建图参数 |
| `ep_navigation/config/nav2_params.yaml` | Nav2 完整参数 (AMCL/costmap/planner/controller) |
| `ep_navigation/config/amcl_params.yaml` | AMCL 定位参数 |
| `ep_navigation/config/costmap_common.yaml` | 通用代价地图 |
| `ep_navigation/config/global_costmap.yaml` | 全局代价地图 |
| `ep_navigation/config/local_costmap.yaml` | 局部代价地图 |

## 硬件依赖

- DJI RoboMaster EP（需安装 robomaster SDK，见下方说明）
- RPLIDAR A2 激光雷达（串口 `/dev/ttyUSB0`，波特率 115200）
- EP 连接模式：`sta`(路由器) / `ap`(直连) / `rndis`(USB)

## TF 树结构

```
map ──(slam_toolbox/Nav2)──► odom ──(chassis.py)──► base_link ──(静态 TF)──► laser_link
```

## 依赖安装

```bash
sudo apt install -y \
  ros-humble-desktop \
  ros-humble-rplidar-ros \
  ros-humble-slam-toolbox \
  ros-humble-nav2-bringup \
  ros-humble-teleop-twist-keyboard

pip3 install numpy numpy-quaternion scipy
```

## SDK 安装（重要）

`robomaster` SDK 已从 PyPI 下架，需从 Gitee 源码安装：

```bash
# 下载 SDK 源码
curl -L -o /tmp/robomaster.zip https://gitee.com/robomaster-edu/RoboMaster-SDK/repository/archive/release_en.zip
cd /tmp && unzip robomaster.zip

# 安装主包（跳过 C 扩展，后面单独编译）
pip3 install /tmp/RoboMaster-SDK-release_en --no-deps

# 安装依赖
pip3 install numpy opencv-python netaddr netifaces myqr

# 编译安装 libmedia_codec（C 扩展，需 cmake / g++ / libopus-dev）
sudo apt install -y cmake g++ libopus-dev
pip3 install /tmp/RoboMaster-SDK-release_en/lib/libmedia_codec --no-build-isolation
```

## SDK 修复

SDK `conn.py` 中三处用 `is` 比较字符串，导致 `rndis` 连接模式失效。已修复：

```python
# conn.py:282 / 293 / 310
if conn_type is CONNECTION_WIFI_AP:       # → ==
elif conn_type is CONNECTION_WIFI_STA:    # → ==
elif conn_type is CONNECTION_USB_RNDIS:  # → ==
```

如果重新安装 SDK，需重新应用此修复。

## 串口权限

```bash
sudo usermod -a -G dialout $USER
# 重新登录后生效
```

## 键盘控制键位

```
teleop_twist_keyboard 键位图:
        前进 (i)
  左转(j) 停止(k)  右转(l)
        后退 (,)
   u=前+左  o=前+右  m=后+左  .=后+右
```

## 重要约定

- 所有 Python 节点使用 ROS 2 Humble / Python 3.10
- 构建产物 (build/, install/, log/) 已排除在版本控制外
- 地图文件保存在 `~/R_v1.1/maps/`
- 雷达位置相对车体中心：x=0.10m, y=0.0m, z=0.0m
- 第一版按差速车处理，横移 linear.y 禁用
- 底盘 timeout=0.5s，无指令自动停车
- 最大速度：0.2 m/s（线速度），0.5 rad/s（角速度）
- `robomaster_ros` 源码尽量不改，扩展功能走新包
- 默认连接模式改为 `rndis`（USB）

## 已知问题

**Q: SDK 未安装**
```bash
# 见上方 SDK 安装章节，从 Gitee 下载源码安装
```

**Q: 串口权限不足**
```bash
sudo usermod -a -G dialout $USER
# 重新登录
```

**Q: EP 连接失败**
- 检查 EP 开机状态
- USB 连接默认用 `conn_type:=rndis`
- 路由器模式：`conn_type:=sta`
- 直连热点：`conn_type:=ap`
- 可指定 SN 号：`serial_number:=3JKDH3B001891M`

**Q: 雷达不工作**
```bash
ls /dev/ttyUSB*
# 检查权限
# 检查波特率（默认 115200，A2 某些型号可能需要 256000）
```

**Q: 建图时地图质量差**
- 降低移动速度（0.05~0.15 m/s）
- 避免快速原地旋转
- 沿墙走一圈后再走内部
- 避免玻璃墙

**Q: 导航不走 / 乱走**
- 确认 AMCL 粒子已收敛（2D Pose Estimate 设定初始位姿）
- 检查 TF 树是否完整：`ros2 run tf2_tools view_frames`
- 检查 `/cmd_vel` 是否有数据：`ros2 topic echo /cmd_vel`
- 检查 chassis 是否超时停车（0.5s）

## 参数速查

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `conn_type` | rndis | 连接模式 |
| `chassis.timeout` | 0.5s | 超时停车 |
| `chassis.rate` | 10 Hz | 里程计更新频率 |
| `max_vel_x` | 0.2 m/s | 最大前进速度 |
| `max_vel_theta` | 0.5 rad/s | 最大转向速度 |
| `robot_radius` | 0.22 m | 机器人半径 |
| `inflation_radius` | 0.35 m | 膨胀半径 |
