#!/bin/bash
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
    "static_transform_publisher"
    "topic_tools"
    "rtabmap_image_resize_node.py"
    "rgb_sync"
    "icp_odometry"
    "rtabmap_viz"
    "rtabmap "
    "foxglove_bridge"
    "lidar_camera_fusion_node.py"
    "colorized_fusion_node.py"
    "overlay_check_node.py"
    "gscam"
)
for pattern in "${PATTERNS[@]}"; do
    pkill -9 -f "$pattern" 2>/dev/null
done
echo "=== Resetting ROS2 daemon ==="
ros2 daemon stop
ros2 daemon start
sleep 2
echo "=== Confirming wired Ethernet is configured for L2 (192.168.1.2) ==="
# Static IP is now handled automatically by the "L2-static" NetworkManager
# profile (configured once, persists across reboots) -- no sudo needed here.
echo "=== Waiting for L2 link (connect Ethernet cable and power now if not already) ==="
for i in $(seq 1 30); do
    if ip link show enP8p1s0 | grep -q "LOWER_UP"; then
        echo "Ethernet link detected after ${i}s."
        break
    fi
    sleep 1
done
if ! ip link show enP8p1s0 | grep -q "LOWER_UP"; then
    echo "WARNING: No Ethernet link detected on enP8p1s0. Check cable connection."
fi
echo "=== Waiting for L2 to respond on the network ==="
for i in $(seq 1 15); do
    if ping -c 1 -W 1 192.168.1.62 > /dev/null 2>&1; then
        echo "L2 responding after ${i}s."
        break
    fi
    sleep 1
done
if ! ping -c 1 -W 1 192.168.1.62 > /dev/null 2>&1; then
    echo "WARNING: L2 not responding at 192.168.1.62. Check power/cable."
fi
echo "=== Starting LiDAR ==="
ros2 launch unitree_lidar_ros2 launch.py > "$LOGDIR/lidar.log" 2>&1 &
echo "=== Starting camera (1920x1200, hardware-accelerated decode) ==="
export GSCAM_CONFIG="v4l2src device=/dev/video0 do-timestamp=true ! image/jpeg,width=1920,height=1200,framerate=30/1 ! jpegparse ! nvv4l2decoder mjpeg=1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert"
ros2 run gscam gscam_node --ros-args -r /camera/image_raw:=/image_raw -r /camera/camera_info:=/camera_info > "$LOGDIR/camera.log" 2>&1 &
echo "=== Waiting 5s for both to initialize ==="
sleep 5
echo "=== Starting debug overlay fusion node ==="
python3 ~/overlay_check_node.py > "$LOGDIR/overlay.log" 2>&1 &
echo "=== Starting colorized point cloud fusion node ==="
python3 ~/colorized_fusion_node.py > "$LOGDIR/colorized.log" 2>&1 &
echo "=== Verifying LiDAR is actually publishing (not just launched) ==="
timeout 5 ros2 topic hz /unilidar/cloud > "$LOGDIR/lidar_check.log" 2>&1
if [ -s "$LOGDIR/lidar_check.log" ]; then
    echo "LiDAR data confirmed flowing."
else
    echo "!!! WARNING: LiDAR launched but no data detected. Check lidar.log and hardware connection. !!!"
fi
echo ""
echo "=== ALL SYSTEMS STARTED ==="
echo "Use the 'Stop Rig' icon to stop everything."
echo ""
echo "This window is keeping everything running."
rmdir "$LOCKDIR" 2>/dev/null
wait
