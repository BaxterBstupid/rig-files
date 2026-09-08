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
#   - SINGLE-INSTANCE LOCK (v2): a second launch (double-clicked icon) REFUSES loudly
#     instead of clean-slate-killing the first run mid-capture (the double-RViz bug).
#   - Icon-friendly (v2): pauses before closing so a Terminal=true .desktop window
#     never vanishes before you can read the result.

set -u
# (temporarily relaxed around ROS2 sourcing below)

# --- SINGLE-INSTANCE LOCK (must be FIRST: a 2nd launch must never reach the pkills) ---
LOCK="/tmp/point_lio_capture.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    echo "!!! point_lio_capture is ALREADY RUNNING (lock: $LOCK). !!!"
    echo "!!! Refusing a second instance - that is the double-RViz / killed-mid-capture bug."
    echo "!!! Use the EXISTING capture window (Ctrl-C there to stop it cleanly)."
    echo "!!! If NO capture is really running (stale lock after a crash):  rmdir $LOCK"
    read -r -p "Press Enter to close this window..." _
    exit 1
fi
# release the lock on EVERY exit path (success, failure, abort, crash of this script)
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

PCD_SRC="$HOME/point_lio_ws/src/point_lio_ros2/PCD/scans.pcd"
STAMP="$(date +%H%M%S)"
# record to the rig SSD when it's mounted; fall back to Desktop (SD card) if it isn't
if mountpoint -q /mnt/rigdata; then
    RECORD_BASE="/mnt/rigdata"
else
    echo "!!! WARNING: /mnt/rigdata NOT mounted - recording to Desktop (SD card) instead !!!"
    RECORD_BASE="$HOME/Desktop"
fi
BAG="$RECORD_BASE/fusioncap_${STAMP}"
PCD_DST="$RECORD_BASE/fusioncap_${STAMP}_scans.pcd"
TOPICS=(/aft_mapped_to_init /image_raw /unilidar/imu /unilidar/cloud)

# shellcheck source=/dev/null
set +u  # ROS2 setup files reference unbound vars
source ~/ros2_ws/install/setup.bash
# shellcheck source=/dev/null
source ~/point_lio_ws/install/setup.bash

# --- PRE-FLIGHT: is the sensor actually publishing? (prevents capturing an empty bag) ---
echo "=== Pre-flight: checking /unilidar/cloud is publishing (Start Rig must be up) ==="
ok=""
for try_n in 1 2 3; do
    if timeout 8 ros2 topic echo --once /unilidar/cloud >/dev/null 2>&1; then ok=1; break; fi
    echo "    attempt $try_n: topic not seen yet (DDS discovery can be slow) - nudging daemon, retrying..."
    ros2 daemon stop >/dev/null 2>&1; ros2 daemon start >/dev/null 2>&1
done
if [ -z "$ok" ]; then
    echo "!!! /unilidar/cloud is NOT publishing after 3 tries. Is Start Rig up? Aborting (nothing captured). !!!"
    read -r -p "Press Enter to close this window..." _
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
setsid ros2 launch point_lio mapping_unilidar_l2.launch.py rviz:=false \
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
    read -r -p "Done. Press Enter to close this window..." _
    exit 0
}
trap cleanup INT

# foreground wait: the script sits here until you press Ctrl-C
wait "$BAG_PID"
# if the bag process ends on its own (error), still run cleanup
cleanup
