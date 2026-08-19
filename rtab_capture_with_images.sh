#!/bin/bash
# ============================================================================
# RTAB CAPTURE + IMAGES (Option B, real-world capture)  —  NOT YET RIG-TESTED
# ============================================================================
# Saves camera IMAGES into the rtabmap database alongside the LiDAR geometry,
# so the capture is a self-contained textureable asset (geometry + images + poses).
# This is what the per-shot texturing tool needs, and what the 270-pan requires.
#
# PIECES it starts (in order):
#   1. camera_info_publisher.py   (publishes vetted intrinsics on /camera/camera_info)
#   2. static TF unilidar_lidar -> camera_link  (from the extrinsic)
#   3. rgb_sync node   (combines /image_raw + /camera/camera_info -> /rgbd_image)
#   4. rtabmap launch  (lidar geometry + rgbd_image appearance)
#
# PREREQ: the rig (rig_start.sh) must already be running (LiDAR + camera + fusion),
#         so /image_raw and /fusion/colorized_cloud are live.
# ============================================================================
set -m
CAMFRAME="camera_link"   # must match /image_raw header.frame_id (see PRE-CHECK)

echo "=== RTAB CAPTURE + IMAGES ==="

# ---- PRE-CHECK 0: does rgb_sync exist on this RTAB? (fallback noted if not) ----
echo "[0] checking rtabmap_sync for rgb_sync ..."
if ros2 pkg executables rtabmap_sync 2>/dev/null | grep -q "rgb_sync"; then
  echo "    rgb_sync: FOUND"
else
  echo "    !! rgb_sync NOT found. STOP - use fallback (subscribe_rgb directly). Tell Claude."
  exit 1
fi

# ---- PRE-CHECK 1: is the camera frame_id what we expect? ----
echo "[1] /image_raw frame_id (must match child frame of TF = $CAMFRAME):"
timeout 3 ros2 topic echo /image_raw --field header.frame_id --once 2>/dev/null || echo "   (couldn't read; ensure rig is up)"
echo "    ^ if this is NOT '$CAMFRAME', edit CAMFRAME at top of this script to match."

# ---- clear stale instances ----
echo "[2] clearing stale rtabmap/sync nodes ..."
pkill -f rtabmap; pkill -f icp_odometry; pkill -f rgb_sync; pkill -f camera_info_publisher
sleep 2

# ---- 1. camera_info publisher ----
echo "[3] starting camera_info_publisher.py ..."
python3 ~/camera_info_publisher.py > /tmp/caminfo.log 2>&1 &
sleep 2

# ---- 2. static TF (from the extrinsic, verified) ----
echo "[4] publishing static TF unilidar_lidar -> $CAMFRAME ..."
ros2 run tf2_ros static_transform_publisher \
  --x -0.032192 --y -0.004570 --z 0.166238 \
  --qx 0.026326 --qy 0.070258 --qz 0.674869 --qw 0.734114 \
  --frame-id unilidar_lidar --child-frame-id $CAMFRAME > /tmp/statictf.log 2>&1 &
sleep 2

# ---- 3. rgb_sync (image + camera_info -> rgbd_image) ----
echo "[5] starting rgb_sync ..."
ros2 run rtabmap_sync rgb_sync --ros-args \
  -r rgb/image:=/image_raw \
  -r rgb/camera_info:=/camera/camera_info \
  -r rgbd_image:=/rgbd_image \
  -p approx_sync:=true > /tmp/rgbsync.log 2>&1 &
sleep 3

# ---- verify rgbd_image is publishing before launching rtabmap ----
echo "[6] verifying /rgbd_image publishes (image sync working) ..."
if timeout 6 ros2 topic hz /rgbd_image 2>/dev/null | grep -q average; then
  echo "    /rgbd_image: PUBLISHING (good)"
else
  echo "    !! /rgbd_image NOT publishing. Check /tmp/rgbsync.log + /tmp/caminfo.log. Tell Claude."
  echo "    (common cause: camera_info not publishing, or approx_sync interval too tight)"
fi

# ---- 4. rtabmap launch: LiDAR geometry + rgbd_image appearance ----
echo "[7] launching rtabmap (scan_cloud + rgbd_image) ..."
echo "    Ctrl+C to stop. DB -> ~/.ros/rtabmap.db"
ros2 launch rtabmap_examples lidar3d.launch.py \
  lidar_topic:=/fusion/colorized_cloud \
  frame_id:=unilidar_lidar \
  rgbd_image_topic:=/rgbd_image

# ---- cleanup on Ctrl+C ----
echo ""
echo "=== stopped. cleaning up helper nodes ==="
pkill -f rgb_sync; pkill -f camera_info_publisher; pkill -f static_transform_publisher
echo "DB at ~/.ros/rtabmap.db"
echo "preserve: cp ~/.ros/rtabmap.db ~/Desktop/capture_img_$(date +%Y%m%d_%H%M%S).db"
