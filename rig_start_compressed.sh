#!/bin/bash
# rig_start_compressed.sh — COMPRESSED-capture bringup (ADR-002/003, 2026-09-24)
# ============================================================================
# A SURGICAL FORK of rig_start.sh. IDENTICAL LiDAR bringup; ONLY the camera changes:
#   OLD (gscam): v4l2 MJPEG -> nvv4l2decoder(NVJPG) -> raw BGRx -> /image_raw
#                -> 40 GiB/3.6min, chokes recorder, drops odom, touches the NVMM scar.
#   NEW (ours) : v4l2 MJPEG -> jpegparse -> /camera/image_raw/compressed (no decode,
#                no re-encode, timestamp-fixed). Bag ~1-5 GB, odom stays dense.
#
# 2026-09-28 (Master 20.13.72 triad-link):
#   - HARD GATES: LiDAR and camera verifies now ABORT the bring-up (and tear down the
#     partial start) if the sensor is not actually publishing — no more "launched but
#     silent" proceeding into a 0-frame / 0-cloud capture. This is the point of the gate.
#   - NEXT STEP corrected to point_lio_capture.sh (full re-solvable set: cloud+odom+imu+
#     compressed). NOT capture_pointlio_texture.sh — that DROPS /unilidar/cloud (audit H2),
#     making bags non-re-solvable.
#   - Camera device is /dev/arducam (udev-pinned symlink; rig_camera_compressed.py default).
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
# NEXT AFTER THIS: run point_lio_capture.sh (Point-LIO + records the FULL re-solvable
#   set). It already prefers /camera/image_raw/compressed, so it auto-selects our topic.
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

# Clean teardown used by the hard gates below (kills what THIS script started).
teardown_partial () {
    echo "=== Tearing down partial bring-up ==="
    pkill -9 -f "rig_camera_compressed" 2>/dev/null
    pkill -9 -f "unitree_lidar_ros2"   2>/dev/null
}

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

echo "=== HARD GATE: LiDAR must be publishing (/unilidar/cloud) ==="
LIDAR_RATE=$(timeout 5 ros2 topic hz /unilidar/cloud 2>/dev/null | grep -oE 'average rate: [0-9.]+' | head -1 | grep -oE '[0-9.]+')
if [ -n "$LIDAR_RATE" ]; then
    echo "LiDAR data confirmed flowing: ${LIDAR_RATE} Hz"
else
    echo "!!! LIDAR GATE FAILED: no data on /unilidar/cloud."
    echo "!!! Check lidar.log / L2 power + cable. Aborting bring-up (do NOT capture)."
    teardown_partial
    exit 1
fi

echo "=== HARD GATE: COMPRESSED camera must be publishing (/camera/image_raw/compressed) ==="
CAM_RATE=$(timeout 5 ros2 topic hz /camera/image_raw/compressed 2>/dev/null | grep -oE 'average rate: [0-9.]+' | head -1 | grep -oE '[0-9.]+')
if [ -n "$CAM_RATE" ]; then
    echo "Compressed camera confirmed flowing: ${CAM_RATE} Hz"
else
    echo "!!! CAMERA GATE FAILED: no frames on /camera/image_raw/compressed (Arducam Mode-2 stall?)."
    echo "!!! A capture now would record 0 camera frames. Aborting bring-up."
    echo "!!! FIX: run cam_preflight_gate.sh to check /dev/arducam; physically replug only if truly wedged."
    teardown_partial
    exit 1
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
echo "=== COMPRESSED BRINGUP DONE (both sensors gated GREEN) ==="
echo "Camera topic : /camera/image_raw/compressed (native JPEG). RAW /image_raw is NOT published."
echo "Camera device: /dev/arducam (udev-pinned)."
echo "Debug nodes  : overlay/colorized fusion are OFF (they need raw /image_raw)."
echo "Next step    : run point_lio_capture.sh  (records cloud + odom + imu + compressed cam)."
echo ""
echo "This window is keeping everything running. Use your Stop Rig icon to stop."
rmdir "$LOCKDIR" 2>/dev/null
wait
