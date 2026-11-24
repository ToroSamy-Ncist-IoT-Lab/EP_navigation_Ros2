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

## 未解决问题 — yaw 180° 翻转

**现象：** 小车实际前进 → RViz 箭头后退；实际逆时针转 → 图中顺时针。建图方向也反。

**已尝试的修复（均未解决）：**
1. 去掉 `-rad()` 的取反 — 未解决
2. `yaw = rad(msg[0]) + math.pi` — π 被 `initial_yaw` 抵消，朝向没变
3. `initial_yaw` 存原始值（不带 π），`self.yaw` 保留 π — 仍未解决

**推断：** 问题可能不在 yaw 数值，而在 SDK 坐标系 ↔ ROS ENU 的基础映射假设。建议通过读 `/odom` + `cmd_vel` 诊断确定 position.x 增减方向和 yaw 当前值，再决定是取反还是旋转。

**下一步：** 不继续改 chassis.py。如需修复，建议新建 `ep_odom` 包做坐标修正节点，或重新审视 URDF 的 base_link 定义。

## Odom 修正（诊断后改动）

### chassis.py 已修改 4 处

| 函数 | 行号 | 修改 | 原因 |
|------|------|------|------|
| `updated_position` | 369-375 | 加入 `-yaw0` 坐标旋转 | EP 帧增量 → ROS 帧对齐启动朝向 |
| `updated_velocity` | 398-402 | `linear.y = 0` | 差速车禁用横移 |
| `updated_attitude` | 406 | `yaw = rad(msg[0]) + math.pi` + 分开存 `initial_yaw` | 尝试 180° 翻转（未解决） |
| `updated_position` | 369 | `yaw0 = initial_yaw + math.pi` | 位置旋转同步翻转（同一次尝试） |
| `updated_imu` | 424 | `gyro_z` 因子 `-1→+1` | 逆时针旋转时 gyro_z 为正 |

### 未解决：yaw 180° 翻转
- 小车前进 → RViz 箭头反方向移动，逆时针转 → 图中顺时针
- 3 种修复都无效，问题不在 yaw 数值本身，需重新审视坐标系基础假设
- 暂停修改 chassis.py

### 待验证
- 实车启动后 `odom.pose.position` 应归零

### SDK 原始数据结论（Git 历史 e8cc807:docs/ep_sdk_test_result_odom_diagnosis.md）
- `sub_position` 在直行时 y 漂仅 1.8mm/6s，可靠
- 后退时 y 漂由初始 yaw 偏角 +3.3° 导致，不是硬件问题
- `sub_imu` gyro_z 逆时针为正，无符号错误
- 上述结果来自内置 SDK 的旧测试。使用 HI12 可对照外部姿态数据，启用方式见 README。

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

**Q: SD原始数据是否存在严重漂移？**
A: 不存。 Git 历史中的 eec1ee3:tmp/test_odom/test_results.md 记录显示直行 y 漂仅 1.8mm，前进/后退/旋转自洽。诊断见 Git 历史 e8cc807:docs/。

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
