# EP 小车 ROS 2 容器与 RViz2 操作手册

本手册适用 Jetson 上的 `rm_ros2_nav` 容器及 EP_navigation_Ros2 的 `hi12-ros2` 分支。Jetson 宿主机是 ROS 1 Noetic；ROS 2 Humble 和本项目运行在容器中。2026-11-25 检查时，容器已安装 RViz2、xauth，使用 host 网络，没有目录挂载。实际状态可能随容器重建而变化。

## 1. 连接小车并进入容器

Windows 与 Jetson 接入同一网络。在 VS Code 安装 Remote - SSH，通过命令面板选择 **Remote-SSH: Connect to Host**，输入：

```text
wlwsys@192.168.123.30
```

IP 是小车当前地址，更换网络后应以 Jetson 的 `hostname -I` 和 Windows 所在网段为准。不要把 EP 的 USB RNDIS 地址当作 Windows 连接 Jetson 的地址。登录凭据由实验室人员线下获取。

在远程 VS Code 选择 **终端 → 新建终端**。这是 Jetson 宿主机终端。先检查容器：

```bash
docker ps -a
```

若 `rm_ros2_nav` 未运行：

```bash
docker start rm_ros2_nav
```

进入正在运行的容器，并加载环境：

```bash
docker exec -it rm_ros2_nav bash
source /opt/ros/humble/setup.bash
source /opt/ep-navigation/install/setup.bash
```

每个新开的容器终端都要加载环境。`exit` 只退出当前终端，不会自动停止容器或其他终端里的任务。ROS 2 是容器内的环境，不需要单独输入一个“启动 ROS 2”的命令。

所有功能开始前检查已有节点，避免同一台底盘被多个驱动连接：

```bash
ros2 node list
ros2 topic list
```

## 2. 键盘控制

将小车放在空旷处，确认可以立即停止。单独测试键盘时：

**容器终端 A：底盘驱动**

```bash
ros2 launch robomaster_ros ep.launch.py conn_type:=rndis
```

等待日志显示 `Connected`，保持终端运行。这表示驱动报告已连接底盘；随后仍需确认里程计和实际控制。

**容器终端 B：键盘节点**

另开一个 VS Code 远程终端，重新执行第 1 节的 `docker exec` 与两条 `source` 命令，然后：

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

选中终端 B：i 前进、逗号后退、j 左转、l 右转、k 停止；速度调节以程序显示说明为准，先低速短按。结束先按 k，再对两个进程分别按 Ctrl+C。


如果按键没有反应，在另外一个已加载环境的容器终端检查：

```bash
ros2 node list
ros2 topic info /cmd_vel -v
ros2 topic echo /odom --once
```

正常连接时应看到底盘驱动节点和 cmd_vel 的订阅者，并能收到里程计；仅有键盘发布者、订阅者为 0 时，先检查底盘驱动是否运行。若驱动没有报告 Connected，则检查供电、RNDIS USB 连接及驱动日志。终端 B 要保持焦点；收到订阅者也不能单凭这一项断言小车一定会移动。
当前项目的 `teleop.launch.py` 使用 xterm 启动键盘，先前容器缺少 xterm 导致键盘窗口启动失败。上述分开启动不依赖 xterm。建图或导航已启动底盘时，不要再运行终端 A 的底盘命令；只启动终端 B 的键盘节点，并避免同时发送导航和键盘速度指令。

## 3. 建图

先停止单独的底盘驱动，以及其他可能连接底盘或雷达的任务。按第 5 节在 Jetson 宿主机终端设置好 DISPLAY，并确认 xeyes 在 Windows 显示，然后从该终端进入容器并加载环境：

```bash
docker exec -it -e DISPLAY="$DISPLAY" rm_ros2_nav bash
source /opt/ros/humble/setup.bash
source /opt/ep-navigation/install/setup.bash
```

容器终端 A 执行：

```bash
ros2 launch ep_bringup mapping.launch.py
```

该入口默认启动底盘、二维雷达、SLAM 和 RViz2；不启动键盘。启动前需按第 5 节在宿主机测试并传入 DISPLAY；无图形环境可加 rviz:=false。雷达默认端口 `/dev/ttyUSB0`，HI12 默认启用，容器端口为 `/dev/hi12_imu`。设备未接入或未映射时启动会报错；仅在需要使用内置反馈时显式设置 `use_hi12:=false`。不要因为看不到窗口而重复启动该命令。

另开容器终端 B，按第 2 节启动键盘。检查终端 A 是否显示底盘连接及雷达健康；在另一个已加载环境的容器终端可查看：

```bash
ros2 topic list
ros2 topic echo /scan --once
ros2 topic echo /odom --once
ros2 topic echo /map --once
```

有消息不代表地图精度已通过验收。RViz2 的打开方法见第 6 节。

### 保存地图

在容器里保存：

```bash
mkdir -p /tmp/ep_maps
ros2 run nav2_map_server map_saver_cli -f /tmp/ep_maps/lab_map
```

会生成 YAML 和 PGM。当前容器没有宿主机目录挂载；容器删除或重建后其中的文件可能丢失。在 Jetson 宿主机终端另行复制：

```bash
mkdir -p ~/ep_maps
docker cp rm_ros2_nav:/tmp/ep_maps/lab_map.yaml ~/ep_maps/
docker cp rm_ros2_nav:/tmp/ep_maps/lab_map.pgm ~/ep_maps/
ls -l ~/ep_maps/
```

## 4. 导航

先结束建图和独立底盘驱动，使用已检查的地图。地图必须对容器可见；以下示例使用上一步容器内的文件：

```bash
ros2 launch ep_bringup navigation.launch.py map:=/tmp/ep_maps/lab_map.yaml autostart:=true
```

默认 `autostart:=false`；只有准备好启动 Nav2 生命周期时才使用上面的 `true`。启动后仍需在 RViz2 设置初始位姿、检查定位和代价地图，再选择导航目标。实车导航和障碍物避让应在空旷环境逐项验收，准备随时停止。不要在导航和建图之间重复启动底盘驱动。

## 5. VS Code 远程终端测试小眼睛

本节采用 **Jetson 直接连接 Windows 的 VcXsrv**：DISPLAY 中填写的是使用者当前 Windows 电脑的 IPv4 地址，不是小车 IP。此前曾看到小眼睛窗口；本手册这套直连方式与容器 RViz2 的完整链路尚待在现场再次验收。

1. Windows 上启动 XLaunch，选择 Multiple windows、Display number 0 和 Start no client。直连需要 VcXsrv 监听 TCP；不同版本界面选项可能不同。优先使用经过授权的受信任网络。
2. 在 Windows PowerShell 执行 `ipconfig`，记录与 Jetson 同网段的无线网卡 IPv4 地址。网络改变后重新查看，不要沿用别人的电脑地址。
3. 在 VS Code 中通过 Remote - SSH 连接小车，打开 **Jetson 宿主机终端**，将以下占位内容替换成第 2 步查到的实际地址：

```bash
export DISPLAY=Windows电脑IP:0.0
echo "$DISPLAY"
xeyes
```

例如 IP 为 `192.0.2.10` 时写 `export DISPLAY=192.0.2.10:0.0`；该地址只是示例。Windows 显示小眼睛后关闭窗口或按 Ctrl+C。新开的 Jetson 终端需要重新设置 DISPLAY。

如果报 `Can't open display`：依次检查 Windows 和 Jetson 网络、XLaunch 是否运行及 TCP 监听、Windows 防火墙是否允许当前网络、VcXsrv 的访问授权；记录报错再排查。手册中的 Disable access control 会取消 X 服务访问控制，只能在受信任网络临时测试，测试后立即退出并恢复访问控制；不要关闭整个防火墙。

## 6. 在 Windows 显示容器中的 RViz2

小眼睛成功只证明宿主机图形连接正常，**不代表容器认证和 RViz2 的 OpenGL 一定正常**。在第 5 节设置好 DISPLAY 的同一个 VS Code 远程终端执行：

```bash
docker exec rm_ros2_nav bash -c 'source /opt/ros/humble/setup.bash; ros2 pkg prefix rviz2; command -v xauth'
```

2026-11-25 检查时两项均已安装，容器使用 host 网络；重建容器后需复查。若 XLaunch 启用认证，容器需要被授予该显示的授权；若小眼睛成功但 RViz2 显示认证失败，应由维护人员核对认证，勿泄露 X11 凭据。若临时关闭访问控制进行受信任网络测试，不需要复制认证数据。

启动独立 RViz2，不重复启动建图：

```bash
docker exec -it -e DISPLAY="$DISPLAY" rm_ros2_nav bash -c \
  'source /opt/ros/humble/setup.bash; source /opt/ep-navigation/install/setup.bash; rviz2 -d "$(ros2 pkg prefix --share ep_bringup)/config/mapping.rviz"'
```

在 RViz2 检查 Fixed Frame、Map 的 /map、LaserScan 的 /scan 和 TF；导航时可改用 navigation.rviz。窗口打开但没有数据，先检查建图节点、话题和 TF；如果有 OpenGL 或显示认证错误，保存报错并排查。命令和配置已核对，完整直连 RViz2 仍需现场验收。


## 7. 查看与停止

后台建图若按既有测试方式写入容器日志，可在 Jetson 宿主机查看：

```bash
docker exec -it rm_ros2_nav tail -f /tmp/ep_mapping.log
```

Ctrl+C 只结束日志查看。自行在前台启动的功能，应在对应的启动终端 Ctrl+C 停止；先停止键盘，再停止建图或导航。不要用停止整个容器代替正常结束任务，除非确认其他工作也可停止。
