#!/bin/bash
# rig_start_compressed.sh — COMPRESSED-capture bringup (ADR-002/003, 2026-09-24)
# ============================================================================
# A SURGICAL FORK of rig_start.sh. IDENTICAL LiDAR bringup; ONLY the camera changes:
#   OLD (gscam): v4l2 MJPEG -> nvv4l2decoder(NVJPG) -> raw BGRx -> /image_raw
#                -> 40 GiB/3.6min, chokes recorder, drops odom, touches the NVMM scar.
#   NEW (ours) : v4l2 MJPEG -> jpegparse -> /camera/image_raw/compressed (no decode,
#                no re-encode, timestamp-fixed). Bag ~1-5 GB, odom stays dense.
#
# TRACED DOWNSTREAM EFFECT (ADR-003 discipline — stated, not silent):
#   overlay_check_node.py and colorized_fusion_node.py subscribe to RAW /image_raw,
#   which this bringup does NOT publish -> they are DROPPED here. They are
#   MONITORING-ONLY (not recorded), so the capture is unaffected. If you want a live
#   overlay during the hero walk, we repoint them at the compressed topic separately.
#   gscam also published /camera_info; our node does not. Intrinsics come from the
#   calibration file downstream, not ROS camera_info, so the recorded capture is fine.
#
# NODE LOCATION: expects ~/rig_camera_compressed.py (move it from ~/Desktop first).
# NEXT AFTER THIS: run capture_pointlio_texture.sh (it runs Point-LIO + records; it
#   already prefers /camera/image_raw/compressed, so it auto-selects our topic).
# ============================================================================
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
LOGDIR=~/rig_logs
mkdir -p "$LOGDIR"
LOCKDIR=/tmp/rig_start.lock
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    echo "Start already in progress. Please wait."
    sleep 3
    exit 1
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

echo "=== Killing any lingering processes first (guaranteed clean slate) ==="
PATTERNS=(
    "unitree_lidar_ros2"
    "gscam_node"
    "gscam"
    "rig_camera_compressed"          # our node — ensures a clean restart
    "static_transform_publisher"
    "topic_tools"
    "overlay_check_node.py"
    "colorized_fusion_node.py"
    "foxglove_bridge"
)
for pattern in "${PATTERNS[@]}"; do
    pkill -9 -f "$pattern" 2>/dev/null
done

echo "=== Resetting ROS2 daemon ==="
ros2 daemon stop
ros2 daemon start
sleep 2

echo "=== Waiting for L2 link (connect Ethernet + power now if not already) ==="
for i in $(seq 1 30); do
    if ip link show enP8p1s0 | grep -q "LOWER_UP"; then
        echo "Ethernet link detected after ${i}s."; break
    fi
    sleep 1
done
if ! ip link show enP8p1s0 | grep -q "LOWER_UP"; then
    echo "WARNING: No Ethernet link on enP8p1s0. Check cable connection."
fi

echo "=== Waiting for L2 to respond on the network (192.168.1.62) ==="
for i in $(seq 1 15); do
    if ping -c 1 -W 1 192.168.1.62 > /dev/null 2>&1; then
        echo "L2 responding after ${i}s."; break
    fi
    sleep 1
done
if ! ping -c 1 -W 1 192.168.1.62 > /dev/null 2>&1; then
    echo "WARNING: L2 not responding at 192.168.1.62. Check power/cable."
fi

echo "=== Starting LiDAR ==="
ros2 launch unitree_lidar_ros2 launch.py > "$LOGDIR/lidar.log" 2>&1 &

echo "=== Starting camera: rig_camera_compressed.py (NATIVE JPEG, no decode, timestamp-fixed) ==="
python3 ~/rig_camera_compressed.py > "$LOGDIR/camera.log" 2>&1 &

echo "=== Waiting 5s for both to initialize ==="
sleep 5

echo "=== Verifying LiDAR is actually publishing (not just launched) ==="
timeout 5 ros2 topic hz /unilidar/cloud > "$LOGDIR/lidar_check.log" 2>&1
if [ -s "$LOGDIR/lidar_check.log" ]; then
    echo "LiDAR data confirmed flowing."
else
    echo "!!! WARNING: LiDAR launched but no data. Check lidar.log / hardware. !!!"
fi

echo "=== Verifying COMPRESSED camera topic is publishing ==="
timeout 5 ros2 topic hz /camera/image_raw/compressed > "$LOGDIR/camera_check.log" 2>&1
if [ -s "$LOGDIR/camera_check.log" ]; then
    echo "Compressed camera confirmed flowing:"
    tail -2 "$LOGDIR/camera_check.log"
else
    echo "!!! WARNING: no compressed frames on /camera/image_raw/compressed. Check camera.log. !!!"
fi

echo "=== Confirming the timestamp fix is LIVE (anchored capture clock) ==="
if grep -q "anchored capture clock" "$LOGDIR/camera.log"; then
    echo "OK: capture-clock anchored — PTS stamping active (tau will be a stable constant)."
else
    echo "NOTE: 'anchored capture clock' not in camera.log yet. If you also see"
    echo "      'pts invalid -> now()', the driver did not give a PTS -> tell Claude"
    echo "      (tau goes jittery on the fallback)."
fi

echo ""
echo "=== COMPRESSED BRINGUP DONE ==="
echo "Camera topic : /camera/image_raw/compressed (native JPEG). RAW /image_raw is NOT published."
echo "Debug nodes  : overlay/colorized fusion are OFF (they need raw /image_raw)."
echo "Next step    : run capture_pointlio_texture.sh for the recorded capture."
echo ""
echo "This window is keeping everything running. Use your Stop Rig icon to stop."
rmdir "$LOCKDIR" 2>/dev/null
wait
