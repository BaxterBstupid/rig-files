#!/bin/bash
source /opt/ros/humble/setup.bash

LOCKDIR=/tmp/rig_stop.lock
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    echo "Stop already in progress. Please wait."
    sleep 3
    exit 1
fi

echo "=== Stopping everything ==="
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
)
for pattern in "${PATTERNS[@]}"; do
    pkill -9 -f "$pattern" 2>/dev/null
done

ros2 daemon stop
ros2 daemon start
sleep 2

REMAINING=$(ps aux | grep -E "unitree_lidar_ros2|gscam_node|static_transform_publisher|topic_tools|rtabmap_image_resize_node|rgb_sync|icp_odometry|rtabmap_viz|rtabmap |foxglove_bridge|lidar_camera_fusion_node|colorized_fusion_node" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo ""
    echo "############################################"
    echo "# STOPPED. All pipeline processes confirmed clean."
    echo "############################################"
else
    echo ""
    echo "############################################"
    echo "# WARNING: some processes survived:"
    echo "$REMAINING"
    echo "############################################"
fi

echo ""
echo "This window will close in 5 seconds..."
sleep 5
rmdir "$LOCKDIR" 2>/dev/null
