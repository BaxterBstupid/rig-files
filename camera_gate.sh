#!/bin/bash
# ============================================================================
# camera_gate.sh — LIVE Arducam health gate (Mode-2 stall detector)   2026-09-27
# ============================================================================
# WHY THIS EXISTS: on 2026-09-27 fusioncap_183145 recorded a PERFECT geometry bag
# (2.2M odom, 75MB PCD, 360deg motion) but ZERO camera frames — the Arducam had
# gone into its "Mode-2 stall": the node stays ALIVE but /camera/image_raw/compressed
# stops publishing. Rig Check (md5 only), Pre-Flight (ran before the stall), and the
# Kiosk (shows rate but does not BLOCK) all missed it, and terminal-only meant no eyes
# on the rate. This gate asks the ONE question those miss: is the camera producing
# frames RIGHT NOW? Exit 0 = healthy; exit 1 = stalled/weak (DO NOT CAPTURE).
#
# The stall is TRANSIENT — it can appear AFTER bring-up. So run this in TWO places:
#   (1) at the end of Start Rig (rig_start_compressed.sh) — early catch, and
#   (2) as the LAST check inside point_lio_capture.sh, immediately BEFORE
#       `ros2 bag record` — this is the one that would have caught 183145.
#
# USAGE:   bash camera_gate.sh            # standalone (sources ROS itself)
#   or, inside a script that already sourced ROS:
#          bash ~/camera_gate.sh || { echo "camera dead — aborting capture"; exit 1; }
#
# TUNABLES (env):  CAM_TOPIC (default /camera/image_raw/compressed)
#                  CAM_MIN_HZ (default 10 — healthy is ~19)
#                  CAM_WINDOW (default 4 seconds)
# ============================================================================
source /opt/ros/humble/setup.bash 2>/dev/null
source "$HOME/ros2_ws/install/setup.bash" 2>/dev/null

TOPIC="${CAM_TOPIC:-/camera/image_raw/compressed}"
MIN_HZ="${CAM_MIN_HZ:-10}"
WINDOW="${CAM_WINDOW:-4}"

echo "[cam-gate] checking $TOPIC  (need >= ${MIN_HZ} Hz over ${WINDOW}s) ..."
rate=$(timeout "$WINDOW" ros2 topic hz "$TOPIC" 2>/dev/null \
        | grep -oE 'average rate: [0-9.]+' | head -1 | grep -oE '[0-9.]+')

if [ -z "$rate" ]; then
    echo "[cam-gate] !!! STALL — NO frames on $TOPIC in ${WINDOW}s (rate 0)."
elif awk "BEGIN{exit !($rate < $MIN_HZ)}"; then
    echo "[cam-gate] !!! WEAK — only ${rate} Hz (< ${MIN_HZ}); decoder/USB starving."
else
    echo "[cam-gate] OK — camera live at ${rate} Hz. Safe to capture."
    exit 0
fi

# ---- FAIL path: diagnose the mode + print the fix ----
echo "[cam-gate] --------------------------------------------------------"
if pgrep -f rig_camera_compressed >/dev/null 2>&1; then
    echo "[cam-gate] node is ALIVE but silent  ->  Mode-2 stall (pipeline hung)."
else
    echo "[cam-gate] node is GONE / exits on launch  ->  device wedged (hard Mode-2 stall)."
fi
echo "[cam-gate] FIX:  physically UNPLUG the Arducam USB, wait ~3s, REPLUG it,"
echo "[cam-gate]       then re-run rig_start_compressed.sh, then re-run this gate."
echo "[cam-gate] >>> DO NOT CAPTURE until this gate prints OK — the bag would record"
echo "[cam-gate]     0 camera frames (a geometry-only bag, useless for tau/texture)."
exit 1
