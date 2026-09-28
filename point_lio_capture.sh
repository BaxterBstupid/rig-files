#!/bin/bash
# point_lio_capture.sh — ONE-WINDOW safe capture for Point-LIO (Unitree L2).
# The Point-LIO equivalent of Start Rig: run it, capture, press Ctrl-C ONCE, done.
#
# PREREQ: LiDAR + camera already up (Start Rig) so /unilidar/cloud, /unilidar/imu,
#         /camera/image_raw/compressed are publishing. This does NOT start the driver.
#
# 2026-09-28 (Master 20.13.72 triad-link): CAMERA GATE added (inline, self-contained —
#   no dependency on an external gate file that could go missing). It refuses to record
#   a bag with 0 camera frames (the fusioncap_183145 failure). Checked TWICE:
#     (a) pre-flight, beside the /unilidar/cloud check -> fail fast before launching Point-LIO;
#     (b) FINAL, right before `ros2 bag record` -> catches an Arducam Mode-2 stall that
#         develops during Point-LIO's ~10 s init window.
#
# Guarantees (the failure modes we designed out):
#   - Records /unilidar/cloud TOO  -> a failed PCD save is recoverable from the bag.
#   - Refuses to record without LIVE camera frames (Mode-2 stall / 0-frame bag).
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
TOPICS=(/aft_mapped_to_init /camera/image_raw/compressed /unilidar/imu /unilidar/cloud /cloud_registered)
CAM_TOPIC="/camera/image_raw/compressed"

# shellcheck source=/dev/null
set +u  # ROS2 setup files reference unbound vars
source ~/ros2_ws/install/setup.bash
# shellcheck source=/dev/null
source ~/point_lio_ws/install/setup.bash

# --- helper: is the compressed camera actually publishing? echoes the Hz, or empty ---
cam_hz() {
    timeout "${1:-6}" ros2 topic hz "$CAM_TOPIC" 2>/dev/null \
        | grep -oE 'average rate: [0-9.]+' | head -1 | grep -oE '[0-9.]+'
}

# --- PRE-FLIGHT: is the sensor actually publishing? (prevents capturing an empty bag) ---
echo "=== Pre-flight: checking /unilidar/cloud is publishing (Start Rig must be up) ==="
ok=""
for try_n in 1 2 3; do
    if timeout 8 ros2 topic echo --once /unilidar/cloud >/dev/null 2>&1; then ok=1; break; fi
    echo "    attempt $try_n: topic not seen yet (DDS discovery can be slow) - waiting, retrying..."
    sleep 2   # PATIENCE ONLY - NO daemon stop/start: it deafens the co-running kiosk server
              # (its discovery-dependent subs go silent). Aug-3-era daemon-cycle default, removed.
done
if [ -z "$ok" ]; then
    echo "!!! /unilidar/cloud is NOT publishing after 3 tries. Is Start Rig up? Aborting (nothing captured). !!!"
    read -r -p "Press Enter to close this window..." _
    exit 1
fi
echo "    sensor OK."

# --- PRE-FLIGHT CAMERA GATE (fail fast, before we launch Point-LIO) ---
echo "=== Pre-flight: checking $CAM_TOPIC is publishing (Arducam) ==="
CAM_RATE="$(cam_hz 6)"
if [ -z "$CAM_RATE" ]; then
    echo "!!! CAMERA GATE FAILED: no frames on $CAM_TOPIC (Arducam Mode-2 stall)."
    echo "!!! Aborting (nothing captured) — refusing a 0-camera bag (the fusioncap_183145 failure)."
    echo "!!! FIX: run cam_preflight_gate.sh / check /dev/arducam, then re-run this capture."
    read -r -p "Press Enter to close this window..." _
    exit 1
fi
echo "    camera OK: ${CAM_RATE} Hz."

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

# --- FINAL CAMERA GATE (authoritative): re-verify RIGHT before we commit to the bag ---
# Catches an Arducam Mode-2 stall that appeared during the ~10 s Point-LIO init window.
echo "=== CAMERA GATE (final, pre-record): re-verifying $CAM_TOPIC before recording ==="
CAM_RATE2="$(cam_hz 5)"
if [ -z "$CAM_RATE2" ]; then
    echo "!!! CAMERA GATE FAILED at record time: camera went silent (Mode-2 stall during init)."
    echo "!!! ABORTING before record — refusing the 0-frame bag (the fusioncap_183145 failure)."
    echo "=== Tearing down Point-LIO ==="
    kill -INT -- "-${PLIO_PGID}" 2>/dev/null
    wait "$PLIO_PID" 2>/dev/null
    echo "!!! FIX: check /dev/arducam (cam_preflight_gate.sh), then re-run this capture."
    read -r -p "Camera dead. Press Enter to close this window..." _
    exit 1
fi
echo "    camera still live at ${CAM_RATE2} Hz — recording."

echo "=== Recording all 5 topics (incl. /unilidar/cloud + compressed cam) -> $BAG ==="
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
