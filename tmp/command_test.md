```bash

ros2 launch ep_bringup teleop.launch.py conn_type:=rndis
ros2 launch ep_bringup mapping.launch.py conn_type:=rndis
ros2 launch ep_bringup navigation.launch.py conn_type:=rndis
```


## ep_sdk_raw_debug使用
```bash
# 1. 静止 20s
python3 ~/R_v1.1/tmp/ep_sdk_raw_probe.py --test none --duration 20

# 2. 前进 6s
python3 ~/R_v1.1/tmp/ep_sdk_raw_probe.py --test forward --duration 6 --speed 0.15

# 3. 后退 6s
python3 ~/R_v1.1/tmp/ep_sdk_raw_probe.py --test backward --duration 6 --speed 0.15

# 4. 逆时针旋转 5s
python3 ~/R_v1.1/tmp/ep_sdk_raw_probe.py --test rotate_ccw --duration 5 --yaw_speed 20
```