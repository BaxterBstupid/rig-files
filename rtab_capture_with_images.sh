#!/bin/bash
# ============================================================================
# RTAB CAPTURE + IMAGES (Option B, real-world capture)  —  v2 (gated)
# ============================================================================
# Saves camera IMAGES into the rtabmap database alongside the LiDAR geometry,
# so the capture is a self-contained textureable asset (geometry + images + poses).
# This is what the per-shot texturing tool needs, and what the 270-pan requires.
#
# PIECES it starts (in order):
#   1. camera_info_publisher.py   (publishes vetted intrinsics on /camera/camera_info)
#   2. static TF unilidar_lidar -> <camera frame>  (from the extrinsic)
#   3. rgb_sync node   (combines /image_raw + /camera/camera_info -> /rgbd_image)
#   4. rtabmap launch  (lidar geometry + rgbd_image appearance)
#
# v2 FIXES over v1:
#   - checkpoint [6] now GATES: if /rgbd_image is not publishing, the script EXITS
#     instead of launching RTAB into a doomed empty capture.
#   - the camera frame_id is DETECTED from /image_raw (not hardcoded/assumed), so the
#     static TF uses the real frame. Prevents a silent frame mismatch.
#   - rgb_sync uses EXACT sync (approx_sync:=false): our camera_info is stamped to
#     exactly match /image_raw, so exact sync matches immediately.
#
# PREREQ: the rig (rig_start.sh) must already be running (LiDAR + camera + fusion),
#         so /image_raw and /fusion/colorized_cloud are live.
# ============================================================================
set -m

echo "=== RTAB CAPTURE + IMAGES (v2, gated) ==="

# ---- PRE-CHECK 0: does rgb_sync exist on this RTAB? ----
echo "[0] checking rtabmap_sync for rgb_sync ..."
if ros2 pkg executables rtabmap_sync 2>/dev/null | grep -q "rgb_sync"; then
  echo "    rgb_sync: FOUND"
else
  echo "    !! rgb_sync NOT found. STOP - tell Claude (need subscribe_rgb fallback)."
  exit 1
fi

# ---- PRE-CHECK 1: DETECT the camera frame_id from /image_raw (don't assume) ----
echo "[1] detecting /image_raw frame_id ..."
CAMFRAME=$(timeout 4 ros2 topic echo /image_raw --field header.frame_id --once 2>/dev/null | head -1 | tr -d '[:space:]')
if [ -z "$CAMFRAME" ]; then
  echo "    !! could not read /image_raw frame_id. Is the rig up (camera publishing)?"
  echo "       Confirm with: ros2 topic hz /image_raw"
  exit 1
fi
echo "    camera frame_id = '$CAMFRAME'  (static TF will use this)"

# ---- clear stale instances ----
echo "[2] clearing stale rtabmap/sync/helper nodes ..."
pkill -f rtabmap; pkill -f icp_odometry; pkill -f rgb_sync; pkill -f camera_info_publisher; pkill -f static_transform_publisher
sleep 2

# ---- 1. camera_info publisher ----
echo "[3] starting camera_info_publisher.py ..."
python3 ~/camera_info_publisher.py > /tmp/caminfo.log 2>&1 &
sleep 2
if grep -q "Publishing CameraInfo" /tmp/caminfo.log; then
  echo "    camera_info: publishing"
else
  echo "    !! camera_info_publisher did not report publishing. Check /tmp/caminfo.log."
  cat /tmp/caminfo.log
  exit 1
fi

# ---- 2. static TF (unilidar_lidar -> detected camera frame) ----
echo "[4] publishing static TF unilidar_lidar -> $CAMFRAME ..."
ros2 run tf2_ros static_transform_publisher \
  --x -0.032192 --y -0.004570 --z 0.166238 \
  --qx 0.026326 --qy 0.070258 --qz 0.674869 --qw 0.734114 \
  --frame-id unilidar_lidar --child-frame-id "$CAMFRAME" > /tmp/statictf.log 2>&1 &
sleep 2

# ---- 3. rgb_sync (image + camera_info -> rgbd_image), EXACT sync ----
echo "[5] starting rgb_sync (exact sync) ..."
ros2 run rtabmap_sync rgb_sync --ros-args \
  -r rgb/image:=/image_raw \
  -r rgb/camera_info:=/camera/camera_info \
  -r rgbd_image:=/rgbd_image \
  -p approx_sync:=false > /tmp/rgbsync.log 2>&1 &
sleep 3

# ---- GATE: /rgbd_image MUST publish, or we STOP (do not launch RTAB blind) ----
echo "[6] GATE: verifying /rgbd_image publishes ..."
if timeout 6 ros2 topic hz /rgbd_image 2>/dev/null | grep -q average; then
  echo "    /rgbd_image: PUBLISHING (good) - proceeding to RTAB."
else
  echo "    !! /rgbd_image NOT publishing. STOPPING (not launching RTAB)."
  echo "    ---- /tmp/rgbsync.log ----"; tail -15 /tmp/rgbsync.log
  echo "    ---- /tmp/caminfo.log ----"; tail -5 /tmp/caminfo.log
  echo "    Likely causes: QoS mismatch on /image_raw, or sync not matching."
  echo "    Diagnostic to run by hand: ros2 topic info /image_raw --verbose"
  pkill -f rgb_sync; pkill -f camera_info_publisher; pkill -f static_transform_publisher
  exit 1
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
echo "preserve it:  cp ~/.ros/rtabmap.db ~/Desktop/capture_img_$(date +%Y%m%d_%H%M%S).db"
