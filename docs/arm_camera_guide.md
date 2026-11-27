# EP 机械臂、夹爪与摄像头实机验收手册（`feat/arm-camera` 分支）

本手册面向 `feat/arm-camera` 分支，适用于在 Jetson Xavier NX（`192.168.123.30`）上独立编译、启动并分级验收 RoboMaster EP 的机械臂、夹爪与自带前视摄像头。

---

## 1. 在 Jetson 准备独立测试容器（不覆盖现有导航镜像）

提供两种隔离方式，均不影响现有 `ep_navigation_ros2:maps-20261125` 与 `rm_ros2_nav` 容器：

### 方式 A：宿主机目录挂载 + 增量编译（开发调试推荐）

将 `feat/arm-camera` 的 `src/` 同步到 Jetson 宿主机 `~/ep_arm_cam_ws/src`，直接复用既有镜像创建带 `--ipc host` 的调试容器并编译：

```bash
docker run -dit \
  --name rm_ros2_arm_cam \
  --network host \
  --ipc host \
  -v /home/wlwsys/ep_arm_cam_ws:/ws \
  -w /ws \
  ep_navigation_ros2:maps-20261125 \
  sleep infinity

docker exec -it rm_ros2_arm_cam bash -c '
  source /opt/ros/humble/setup.bash
  cd /ws && colcon build --symlink-install
'
```

> 使用 `--symlink-install` 后，修改 Python 文件无需重编，直接重启节点即可生效。

### 方式 B：构建固定 Docker 镜像（定型归档用）

在 Jetson 仓库根目录使用独立标签构建：

```bash
docker build -f Dockerfile.jetson -t ep_navigation_ros2:arm-camera .

docker run -dit \
  --name rm_ros2_arm_cam \
  --network host \
  --ipc host \
  ep_navigation_ros2:arm-camera \
  sleep infinity
```

> 两种方式均务必加上 `--network host --ipc host`，否则与 `rm_foxglove_bridge` 跨容器通信时可能出现 `RTPS_TRANSPORT_SHM Error`（临时补救可执行 `export FASTDDS_BUILTIN_TRANSPORTS=UDPv4`）。

---

## 2. 启动独立驱动（无需雷达与 HI12 串口）

先确认 EP 已通电并通过 USB RNDIS 连好 Jetson（`ping -c 2 192.168.42.2` 通畅），且**没有其他 `robomaster_driver` 正在占用 EP**。

**容器终端 A：启动机械臂 + 夹爪 + 摄像头**

```bash
docker exec -it rm_ros2_arm_cam bash
source /opt/ros/humble/setup.bash
# 方式 A 使用 /ws/install/setup.bash；方式 B 使用 /opt/ep-navigation/install/setup.bash
source /ws/install/setup.bash
ros2 launch ep_bringup arm_camera.launch.py
```

常用可选启动参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `conn_type` | `rndis` | 连接方式：`rndis` / `sta` / `ap` |
| `arm_enabled` | `true` | 启用机械臂（与 `servo` 互斥） |
| `gripper_enabled` | `true` | 启用机械爪 |
| `camera_enabled` | `true` | 启用 EP 前视摄像头 |
| `video_resolution` | `360` | 视频分辨率：`360`（640×360）/ `540` / `720` |
| `video_raw` | `2` | 图像发布模式：`0`=关、`1`=常开、`2`=按需（有订阅者才拉流）、`-1`=禁用 |
| `video_rate` | `-1.0` | 限帧 FPS，`-1.0` 表示不限帧（实测 360p 约 30 FPS） |

---

## 3. 五步分级实机验收（容器终端 B）

另开终端进入同一容器并加载环境：

```bash
docker exec -it rm_ros2_arm_cam bash
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash   # 方式 B 改为 /opt/ep-navigation/install/setup.bash
```

### Step 1：只读遥测检查（零动作风险）

```bash
ros2 run ep_bringup arm_camera_tool status
```

预期输出包含：
- `battery`：电量百分比
- `arm_position`：`arm_base_link` 下的 `(x, z)` 米坐标
- `servos`：左右舵机 `valid=[True, True]` 及原始编码值
- `gripper`：`PAUSE (0)` / `OPEN (1)` / `CLOSE (2)`

### Step 2：摄像头抓帧验证（自动触发按需拉流）

```bash
ros2 run ep_bringup arm_camera_tool snapshot --out /tmp/ep_snapshot.jpg
```

完成后节点会自动退订，驱动随后停止拉流以节省 Jetson CPU 与 RNDIS 带宽。如需在电脑端实时查看画面和 3D 机械臂联动，请直接参见第 4 节 Foxglove 用法。

### Step 3：夹爪低力开合验证

确认夹爪内无异物，先以 `0.5` 力度测试张开与闭合：

```bash
ros2 run ep_bringup arm_camera_tool gripper open --power 0.5
ros2 run ep_bringup arm_camera_tool gripper close --power 0.5
ros2 run ep_bringup arm_camera_tool gripper pause
```

### Step 4：机械臂小步长微动验证（先确认周围净空！）

> **安全提醒**：执行前务必确认机械臂活动范围内**无雷达、线缆或障碍物遮挡**。`arm_camera_tool arm-move` 默认强制单步限幅 `±0.05 m`，防止单位误输。

先用 `--dry-run` 预演参数，再执行 `2~3 cm` 微动并回位：

```bash
# 仅校验参数，不发送动作
ros2 run ep_bringup arm_camera_tool arm-move --dz -0.02 --dry-run

# 实际微动，复查坐标，最后回到原位
ros2 run ep_bringup arm_camera_tool arm-move --dz -0.02
ros2 run ep_bringup arm_camera_tool status
ros2 run ep_bringup arm_camera_tool arm-move --dz 0.02
```

如需绝对坐标移动（内置安全范围 `x ∈ [0.07, 0.22] m`、`z ∈ [-0.07, 0.16] m`）：

```bash
ros2 run ep_bringup arm_camera_tool arm-goto --x 0.166 --z 0.071 --dry-run
```

### Step 5：底盘与机械臂/摄像头共存检查

在终端 A 保持 `arm_camera.launch.py` 运行的前提下，另开终端启动键盘节点 `ros2 run teleop_twist_keyboard teleop_twist_keyboard`，同时开启 Foxglove 订阅 `/camera/image_color`，低速短按测试底盘移动、机械臂微动与视频流共存时 RNDIS 是否稳定无断连。

---

## 4. Foxglove 实时可视化用法（网页版 & 跨容器桥接）

Foxglove 可直接在 Windows 浏览器或桌面端实时查看摄像头画面、3D 机械臂模型、TF 坐标树与话题曲线，无需配置 VcXsrv / `DISPLAY`。

### 4.1 跨容器架构与前置检查

Jetson 采用**两容器解耦架构**：
- `rm_foxglove_bridge`：常驻可视化桥接容器（监听 `8765` 端口，使用 `--network host --ipc host`）
- `rm_ros2_arm_cam`（或其他 ROS 2 业务容器）：运行 EP 驱动

只要两个容器同为 `--network host`、`--ipc host` 且处于同一 `ROS_DOMAIN_ID`（默认 `0`），`rm_foxglove_bridge` 会通过 ROS 2 DDS 自动发现业务容器发布的全部话题，**无需把 Foxglove 装进业务容器，也不影响业务容器重启或重编**。

连接前先在 Jetson 宿主机确认桥接容器在线：

```bash
docker ps --filter "name=rm_foxglove_bridge"
# 如未运行则启动：
docker start rm_foxglove_bridge
```

### 4.2 使用网页版连接小车

1. 用 Chrome / Edge 打开 Foxglove 网页版：`https://app.foxglove.dev`（首次使用需登录账号；若希望免登录，可在 Windows 安装开源桌面客户端 **Lichtblick**）。
2. **放行局域网 `ws://` 连接（网页版必做）**：
   - 因官方网页为 `https://`，而小车桥接为局域网非加密 `ws://`，浏览器默认会阻止连接；
   - 点击浏览器地址栏最左侧的**锁/设置图标** → **网站设置（Site settings）** → 将 **不安全内容（Insecure content）** 设为 **允许（Allow）** → 刷新网页。
3. 点击控制台右上角 **打开连接（Open connection）** → 左侧选 **Foxglove WebSocket** → 地址框填入：

```text
ws://<Jetson IP>:8765
```

> 例如当前实验室网络为 `ws://192.168.123.30:8765`（更换网络后以 Jetson 的 `hostname -I` 为准）。

4. 点击 **打开（Open）** 即可进入实时可视化画布。

### 4.3 推荐面板配置

点击画布顶部 **`+`（添加面板）** 按需组合以下面板：

| 面板类型 | 关键配置 | 用途 |
|---------|---------|------|
| **图像（Image）** | Topic 选 `/camera/image_color` | 实时查看 EP 摄像头画面（订阅后约 1 秒自动触发按需拉流，关闭后自动停流） |
| **3D** | 固定参考系选 `base_link`；开启 **变换（Transforms）** 与 **主题 → `/robot_description`**、`/camera/camera_info` | 查看 EP 3D 模型、机械臂/夹爪实时联动、TF 坐标系与紫色相机视锥体 |
| **绘图（Plot）** | 添加 `/arm_position.point.x`、`/arm_position.point.z`、`/imu.angular_velocity.z`、`/cmd_vel.linear.x` | 实时监控机械臂位置与运动曲线 |
| **原始消息（Raw Messages）** | 选 `/foxglove_bridge/sysinfo` 或 `/gripper` | 查看 Jetson CPU/内存负载与夹爪状态 |

### 4.4 常见问题排查

| 现象 | 可能原因与处理 |
|------|---------------|
| 网页一直连不上 `ws://...:8765` | ① 未放行浏览器的“不安全内容”；② `rm_foxglove_bridge` 未启动；③ Windows 与 Jetson 不在同一网段或 Jetson IP 已变更 |
| 连上了但话题列表里没有 `/camera/image_color` 或 `/arm_position` | 业务容器内的 `arm_camera.launch.py` 未启动，或业务容器未加 `--ipc host` 导致与桥接容器通信异常 |
| Image 面板黑屏或一直转圈 | 检查驱动日志是否显示 `Connected`，确认 EP 电源与 USB RNDIS（`192.168.42.2`）连通 |
| 3D 面板看不到机械臂或机械臂不随实车转动 | 检查 `joint_state_publisher` 和 `robot_state_publisher` 是否在运行，以及 3D 面板里是否勾选了 `/robot_description` 与 `base_link` |

---

## 5. 离线回归测试（无需连接小车）

在开发机仓库根目录即可直接运行纯 Python 离线测试（覆盖工具限幅、接口与标定一致性、`Camera` 停机退出防死锁和 `Arm` 防护逻辑）：

```bash
PYTHONPATH=src/ep_bringup python -m unittest discover -s src/ep_bringup/test -v
python -m unittest discover -s src/robomaster_ros/test -v
```
