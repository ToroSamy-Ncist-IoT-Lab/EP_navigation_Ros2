"""Save a ROS 2 occupancy map to a persistent, per-map directory."""

import datetime
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


def main():
    if len(sys.argv) > 2:
        print("用法: ros2 run ep_navigation save_map [地图名称]", file=sys.stderr)
        return 2

    name = sys.argv[1] if len(sys.argv) == 2 else datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%y-%m-%d-%H-%M")
    if (not name or name in (".", "..") or len(name.encode("utf-8")) > 180
            or any(c in name for c in ("/", "\\"))
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        print("地图名称不合法，请使用不含路径分隔符的名称。", file=sys.stderr)
        return 2

    base = Path(os.environ.get("EP_MAPS_DIR", "/maps/2d"))
    if not base.is_dir():
        print(f"地图目录 {base} 不存在，请先确认宿主机目录已挂载。", file=sys.stderr)
        return 1
    requested_name = name
    suffix = 0
    while True:
        name = requested_name if suffix == 0 else f"{requested_name}（{suffix}）"
        if len(name.encode("utf-8")) > 240:
            print("地图名称过长，无法添加重名后缀。", file=sys.stderr)
            return 2
        target = base / name
        try:
            target.mkdir()
            break
        except FileExistsError:
            suffix += 1
        except OSError as exc:
            print(f"无法创建地图目录：{exc}", file=sys.stderr)
            return 1

    yaml_path = target / (name + ".yaml")
    pgm_path = target / (name + ".pgm")
    try:
        result = subprocess.run([
            "ros2", "run", "nav2_map_server", "map_saver_cli",
            "-f", str(target / name), "--ros-args", "-p", "save_map_timeout:=15.0",
        ], check=False)
        if result.returncode or not yaml_path.is_file() or not pgm_path.is_file():
            print("保存失败：请确认建图运行中且 /map 有数据。", file=sys.stderr)
            return 1
        if not yaml_path.stat().st_size or not pgm_path.stat().st_size:
            print("保存失败：地图文件为空。", file=sys.stderr)
            return 1
        uid = os.environ.get("EP_MAPS_UID")
        gid = os.environ.get("EP_MAPS_GID")
        if uid is not None and gid is not None and os.geteuid() == 0:
            for path in (target, yaml_path, pgm_path):
                os.chown(path, int(uid), int(gid))
        print(f"地图已保存：{target}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"保存或设置地图权限失败：{exc}；请检查目录 {target}", file=sys.stderr)
        return 1
    finally:
        # An empty directory is ours; non-empty partial output is retained for inspection.
        try:
            target.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
