#!/bin/bash
# ============================================================================
# COMBINED CAPTURE — Point-LIO + camera, for the texture bridge   (PIECE 1)
# ============================================================================
# Records the two streams the texture bridge needs, with Point-LIO running so
# geometry (scans.pcd) is built live:
#     /aft_mapped_to_init          (nav_msgs/Odometry) = LiDAR-in-map pose stream
#     <camera image topic>         (frames, timestamped) = texture source
# Point-LIO writes PCD/scans.pcd on CLEAN shutdown (the geometry map).
#
# Values below are CONFIRMED from the real repos (not assumed):
#   - launch:  point_lio  mapping_unilidar_l2.launch.py   (rviz:=false on the Jetson)
#   - config:  lid_topic /unilidar/cloud, imu_topic /unilidar/imu, gravity_align:true
#   - odom:    /aft_mapped_to_init (laserMapping.cpp:811), child frame 'aft_mapped'
#   - geometry: <point_lio pkg>/PCD/scans.pcd, BINARY, saved on clean exit (interval -1)
#
# PREREQ: the LiDAR driver + camera are already up (e.g. via a lean rig bringup that
#         publishes /unilidar/cloud, /unilidar/imu, and the camera image topic).
#         Do NOT also run the colorized fusion node — Point-LIO takes the RAW cloud,
#         and the fusion node just burns CPU during the coexistence-critical window.
#
# USAGE:
#   ./capture_pointlio_texture.sh                # records until Ctrl+C
#   FIRST RUN = short STATIONARY coexistence test (~20s). Prove both topics record +
#   PCD saves + no dropped frames BEFORE attempting a pan. (bridge-doc build order #1.)
# ============================================================================
set -m
PLIO_PKG_DIR="${PLIO_PKG_DIR:-$HOME/point_lio_ws/src/point_lio_ros2}"   # for scans.pcd
STAMP=$(date +%Y%m%d_%H%M%S)
BAGDIR="$HOME/Desktop/plio_texcap_$STAMP"

echo "=== COMBINED CAPTURE (Point-LIO + camera) — $STAMP ==="

# ---- 0. Jetson max performance (Point-LIO is CPU-bound point-by-point) ----
echo "[0] setting max performance (nvpmodel -m 0, jetson_clocks) ..."
sudo nvpmodel -m 0 2>/dev/null; sudo jetson_clocks 2>/dev/null || echo "    (skip if not on Jetson)"

# ---- 1. exactly ONE lidar driver (avoid the known duplicate-driver port clash) ----
NDRV=$(pgrep -fc "unitree_lidar_ros2|unilidar" 2>/dev/null || echo 0)
echo "[1] lidar driver instances: $NDRV"
if [ "$NDRV" -gt 1 ]; then echo "    !! more than one lidar driver — kill extras first."; exit 1; fi

# ---- 2. detect the camera image topic (prefer COMPRESSED — SD can't sustain raw) ----
echo "[2] selecting camera image topic ..."
IMG_TOPIC=""
if ros2 topic list 2>/dev/null | grep -qx "/camera/image_raw/compressed"; then
  IMG_TOPIC="/camera/image_raw/compressed"; echo "    using COMPRESSED: $IMG_TOPIC (SD-friendly)"
elif ros2 topic list 2>/dev/null | grep -qx "/image_raw"; then
  IMG_TOPIC="/image_raw"
  echo "    !! only RAW /image_raw available — 1920x1200 raw at ~15fps can OVERRUN the SD"
  echo "       (~100 MB/s vs ~40-90 MB/s sustained) -> expect dropped frames. Prefer compressed."
else
  echo "    !! no camera image topic found. Is the camera up? (ros2 topic hz /image_raw)"; exit 1
fi

# ---- 3. GATE: the input streams must be LIVE before we launch Point-LIO ----
echo "[3] verifying input streams (allow L2 ~15s spin-up before trusting) ..."
for T in /unilidar/cloud /unilidar/imu "$IMG_TOPIC"; do
  if timeout 8 ros2 topic hz "$T" 2>/dev/null | grep -q average; then
    echo "    $T : LIVE"
  else
    echo "    !! $T not publishing. Bring the rig up fully first (wait for L2 spin-up)."; exit 1
  fi
done

# ---- 4. launch Point-LIO (headless; RViz belongs on the HOST, not the Jetson) ----
echo "[4] launching Point-LIO (mapping_unilidar_l2, rviz:=false) ..."
ros2 launch point_lio mapping_unilidar_l2.launch.py rviz:=false > /tmp/pointlio.log 2>&1 &
PLIO_PID=$!
sleep 5

# ---- 5. GATE: odometry must be publishing, else stop (don't record a poseless bag) ----
echo "[5] GATE: verifying /aft_mapped_to_init publishes ..."
if timeout 10 ros2 topic hz /aft_mapped_to_init 2>/dev/null | grep -q average; then
  echo "    /aft_mapped_to_init : PUBLISHING (Point-LIO odometry live)"
else
  echo "    !! /aft_mapped_to_init NOT publishing. Point-LIO not producing poses."
  echo "    ---- /tmp/pointlio.log (tail) ----"; tail -20 /tmp/pointlio.log
  kill -INT $PLIO_PID 2>/dev/null; exit 1
fi

# ---- 6. record the bag (poses + images; +imu/cloud as cheap insurance) ----
echo "[6] recording bag -> $BAGDIR"
echo "    MOTION: hold STATIONARY ~5s (Point-LIO IMU init), THEN slow STOP-AND-GO pan."
echo "    (stop-and-go = zero angular velocity during each hold -> tau irrelevant, pose"
echo "     interpolation trivial. Grab a beat at each stop. Ctrl+C when done.)"
ros2 bag record -o "$BAGDIR" /aft_mapped_to_init "$IMG_TOPIC" /unilidar/imu &
BAG_PID=$!

# ---- 7. wait for Ctrl+C, then CLEAN shutdown (order matters for the PCD) ----
trap 'echo; echo "[7] stopping ..."; \
  kill -INT $BAG_PID 2>/dev/null; sleep 2; \
  echo "    stopping Point-LIO (SIGINT so it SAVES scans.pcd — do NOT SIGKILL) ..."; \
  kill -INT $PLIO_PID 2>/dev/null; sleep 4; \
  PCD="$PLIO_PKG_DIR/PCD/scans.pcd"; \
  if [ -f "$PCD" ]; then cp "$PCD" "$HOME/Desktop/scans_$STAMP.pcd"; \
     echo "    geometry saved: ~/Desktop/scans_$STAMP.pcd ($(du -h "$PCD"|cut -f1))"; \
  else echo "    !! scans.pcd NOT found at $PCD — check pcd_save_en + that exit was clean."; fi; \
  echo "    bag saved: $BAGDIR"; \
  echo; echo "NEXT (cold): pointlio_pose_matcher.py $BAGDIR --image-topic $IMG_TOPIC --dump-frames $BAGDIR/frames"; \
  exit 0' INT
echo "    recording... (Ctrl+C to stop)"
wait $BAG_PID
