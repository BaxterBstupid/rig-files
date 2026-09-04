#!/bin/bash
# topic_silence_check_9_4.sh
# PURPOSE: Prove the sensor input topics are TRULY silent before a bag replay or
#   Point-LIO re-registration. A live publisher colliding with a replayed bag on the
#   same topic (/unilidar/cloud, /unilidar/imu) silently corrupts the result.
# THREE-LAYER PROOF: (1) ROS node list, (2) publisher processes, (3) actual topic rate.
# All three must show quiet before trusting a replay. Proven 2026-09-04 (caught the
# lingering rig_kiosk_server as a subscriber-only spectator; input topics confirmed silent).
# USAGE: run after 'Stop Rig'. Note: rig_kiosk_server SUBSCRIBES to these topics but does
#   not publish them — it won't corrupt inputs, but stop it (kill its PID) for a fully clean stage.
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
echo "=== 1. ROS nodes alive? (want: empty or just /rig_kiosk if server up) ==="
ros2 node list 2>/dev/null
echo "=== 2. publisher processes? (want: nothing, or only rig_kiosk_server) ==="
pgrep -af 'unilidar|pointlio|gscam|ros2 bag|fusion' | grep -v grep || echo "  none ✓"
echo "=== 3. input topics actually silent? ==="
timeout 5 ros2 topic hz /unilidar/cloud 2>&1 | grep -m1 'average' || echo "  cloud: SILENT ✓"
timeout 4 ros2 topic hz /unilidar/imu   2>&1 | grep -m1 'average' || echo "  imu: SILENT ✓"
timeout 4 ros2 topic hz /aft_mapped_to_init 2>&1 | grep -m1 'average' || echo "  aft_mapped: SILENT ✓"
