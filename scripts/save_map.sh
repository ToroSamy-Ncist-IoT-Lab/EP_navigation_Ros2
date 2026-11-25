#!/usr/bin/env bash
set -euo pipefail
exec docker exec -i rm_ros2_nav bash -c '
  source /opt/ros/humble/setup.bash
  source /opt/ep-navigation/install/setup.bash
  exec ros2 run ep_navigation save_map "$@"
' bash "$@"
