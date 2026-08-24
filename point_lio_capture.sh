#!/bin/bash
# point_lio_capture.sh — ONE-WINDOW safe capture for Point-LIO (Unitree L2).
# The Point-LIO equivalent of Start Rig: run it, capture, press Ctrl-C ONCE, done.
#
# PREREQ: LiDAR + camera already up (Start Rig) so /unilidar/cloud, /unilidar/imu,
#         /image_raw are publishing. This does NOT start the driver.
#
# Guarantees (the failure modes we designed out):
#   - Records /unilidar/cloud TOO  -> a failed PCD save is recoverable from the bag.
#   - ONE window. One Ctrl-C runs the whole safe shutdown in the right order.
#   - Point-LIO started in its own PROCESS GROUP; SIGINT sent to the GROUP so the
#     pointlio_mapping node reliably receives it and COMPLETES the PCD save.
#   - Bag stops FIRST, THEN Point-LIO, and we WAIT for the save to finish.
#   - Verifies the PCD wrote FRESH (mtime newer), copies it to the Desktop, timestamped.
#   - Ends with a clear BAG / PCD summary, or a LOUD, honest failure.

set -u
# (temporarily relaxed around ROS2 sourcing below)

PCD_SRC="$HOME/point_lio_ws/src/point_lio_ros2/PCD/scans.pcd"
STAMP="$(date +%H%M%S)"
BAG="$HOME/Desktop/fusioncap_${STAMP}"
PCD_DST="$HOME/Desktop/fusioncap_${STAMP}_scans.pcd"
TOPICS=(/aft_mapped_to_init /image_raw /unilidar/imu /unilidar/cloud)

# shellcheck source=/dev/null
set +u  # ROS2 setup files reference unbound vars
source ~/ros2_ws/install/setup.bash
# shellcheck source=/dev/null
source ~/point_lio_ws/install/setup.bash

# --- PRE-FLIGHT: is the sensor actually publishing? (prevents capturing an empty bag) ---
echo "=== Pre-flight: checking /unilidar/cloud is publishing (Start Rig must be up) ==="
if ! timeout 5 ros2 topic echo --once /unilidar/cloud >/dev/null 2>&1; then
    echo "!!! /unilidar/cloud is NOT publishing. Is Start Rig up? Aborting (nothing captured). !!!"
    exit 1
fi
echo "    sensor OK."

# --- CLEAN SLATE: kill any orphaned RViz / pointlio from a previous run ---
# (an orphaned RViz + a fresh one = the double-RViz slowdown; prevent it up front)
echo "=== Clean slate: clearing any orphaned rviz2 / pointlio_mapping ==="
pkill -f "pointlio_mapping" 2>/dev/null && echo "    killed a lingering pointlio_mapping" || true
pkill -x "rviz2" 2>/dev/null && echo "    killed a lingering rviz2" || true
sleep 1

# --- record the PCD's CURRENT mtime so we can PROVE a fresh save happened ---
PCD_OLD_MTIME="$(stat -c %Y "$PCD_SRC" 2>/dev/null || echo 0)"

echo "=== Launching Point-LIO (with RViz reference view). Hold rig DEAD STILL for IMU init... ==="
# setsid -> own process group so we can signal the whole group (reliable SIGINT to the node)
setsid ros2 launch point_lio mapping_unilidar_l2.launch.py rviz:=true \
    >/tmp/pointlio_capture.log 2>&1 &
PLIO_PID=$!
PLIO_PGID="$(ps -o pgid= -p "$PLIO_PID" | tr -d ' ')"

sleep 10   # let IMU init complete

# show the init lines so the user sees it actually initialized before we record
echo "--- Point-LIO init (from log) ---"
grep -m1 "Initializing: 100" /tmp/pointlio_capture.log || echo "  (init line not seen yet; log at /tmp/pointlio_capture.log)"
echo "---------------------------------"

echo "=== Recording all 4 topics (incl. /unilidar/cloud) -> $BAG ==="
echo "=== CAPTURE NOW. Press Ctrl-C ONCE when done. ==="
setsid ros2 bag record -o "$BAG" "${TOPICS[@]}" >/tmp/bag_capture.log 2>&1 &
BAG_PID=$!
BAG_PGID="$(ps -o pgid= -p "$BAG_PID" | tr -d ' ')"

cleanup() {
    trap '' INT TERM   # ignore further signals during shutdown
    echo ""
    echo "=== STOP 1/4: stopping the bag (flush to disk) ==="
    kill -INT -- "-${BAG_PGID}" 2>/dev/null
    wait "$BAG_PID" 2>/dev/null

    echo "=== STOP 2/4: clean SIGINT to Point-LIO group; WAITING for PCD save ==="
    kill -INT -- "-${PLIO_PGID}" 2>/dev/null
    wait "$PLIO_PID" 2>/dev/null
    sleep 2   # small grace for the file to flush to disk

    echo "=== STOP 3/4: verifying the PCD saved FRESH ==="
    PCD_NEW_MTIME="$(stat -c %Y "$PCD_SRC" 2>/dev/null || echo 0)"
    if [ "$PCD_NEW_MTIME" -gt "$PCD_OLD_MTIME" ]; then
        cp "$PCD_SRC" "$PCD_DST"
        echo "=== STOP 4/4: SUCCESS ==="
        echo "   BAG  [ok]  $BAG"
        echo "   PCD  [ok]  $PCD_DST"
        ls -lh "$PCD_DST" | awk '{print "         size: "$5}'
    else
        echo "=== STOP 4/4: !!! PCD DID NOT SAVE FRESH !!! ==="
        echo "   Map PCD did not write this run. BUT the bag INCLUDES /unilidar/cloud,"
        echo "   so it is RECOVERABLE: replay $BAG through Point-LIO to regenerate the PCD."
        echo "   BAG  [ok]  $BAG"
        echo "   PCD  [FAIL - regenerate from bag]"
    fi
    exit 0
}
trap cleanup INT

# foreground wait: the script sits here until you press Ctrl-C
wait "$BAG_PID"
# if the bag process ends on its own (error), still run cleanup
cleanup
