#!/bin/bash
# ============================================================================
# cam_preflight_gate.sh — DEVICE-LEVEL Arducam gate for PRE-FLIGHT   2026-09-27
# ============================================================================
# ROOT CAUSE it defends against (PROVEN 2026-09-27, no physical action taken):
#   The Arducam silently RE-ENUMERATES on the USB bus. /dev/video0 vanished and
#   the same camera reappeared as /dev/video1. The old pipeline was hard-pinned
#   to /dev/video0, so it opened a device that no longer existed -> 0 frames
#   (node alive-but-silent) and any relaunch exited 1. THIS is the Mode-2 stall.
#
# PERMANENT FIX now in place: a udev rule (99-arducam.rules) pins a stable
#   symlink /dev/arducam to the camera's CAPTURE node by USB id 0c45:0578, and
#   rig_camera_compressed.py now defaults device=/dev/arducam. This gate verifies
#   that the camera is actually reachable and streaming through /dev/arducam
#   BEFORE Start Rig, when the ROS node is not yet up and the device is free.
#   (After bring-up, use camera_gate.sh on the /camera/image_raw/compressed topic.)
#
# EXIT 0 = /dev/arducam streams -> safe to Start Rig.
# EXIT 1 = camera not reachable through the expected path (stall, or symlink stale).
# EXIT 3 = v4l2-ctl missing.
#
# TUNABLES (env): CAM_EXPECT (device the pipeline uses; default /dev/arducam)
#                 CAM_FRAMES (frames to grab; default 5)   CAM_TMO (s; default 4)
# NOTE: run BEFORE Start Rig. If the ROS node already owns the camera, v4l2 grabs
#       return "busy" and this gate can't test it — use camera_gate.sh then.
# ============================================================================
EXPECT="${CAM_EXPECT:-/dev/arducam}"
FRAMES="${CAM_FRAMES:-5}"
TMO="${CAM_TMO:-4}"

command -v v4l2-ctl >/dev/null 2>&1 || { echo "[cam-preflight] v4l2-ctl not installed (sudo apt install v4l-utils)"; exit 3; }

_streams () { timeout "$TMO" v4l2-ctl -d "$1" --stream-mmap --stream-count="$FRAMES" --stream-to=/dev/null >/dev/null 2>&1; }

# --- fast path: does the EXPECTED device stream? (follows the /dev/arducam symlink) ---
if [ -e "$EXPECT" ] && _streams "$EXPECT"; then
    echo "[cam-preflight] OK — Arducam live at $EXPECT -> $(readlink -f "$EXPECT" 2>/dev/null) (${FRAMES} frames). Safe to Start Rig."
    exit 0
fi

# --- EXPECT did not stream: scan every node to diagnose ---
echo "[cam-preflight] $EXPECT did not stream — scanning /dev/video* ..."
live=""
for d in /dev/video*; do
    [ -e "$d" ] || continue
    if _streams "$d"; then echo "[cam-preflight] $d -> STREAMS OK"; [ -z "$live" ] && live="$d"
    else echo "[cam-preflight] $d -> no stream (metadata node, or busy/stalled)"; fi
done

if [ -z "$live" ]; then
    echo "[cam-preflight] !!! NO video node streams — Arducam truly wedged (hard Mode-2)."
    echo "[cam-preflight] FIX: physically UNPLUG the Arducam USB, wait ~3s, REPLUG, re-run this gate."
    echo "[cam-preflight] >>> DO NOT START A CAPTURE — the bag would record 0 camera frames."
    exit 1
fi

echo "CAM_DEV=$live"
echo "[cam-preflight] !!! Camera is live on $live but $EXPECT is missing/stale."
echo "[cam-preflight]     The udev symlink is not pointing at the live node."
echo "[cam-preflight] FIX: sudo udevadm trigger --subsystem-match=video4linux ; ls -l $EXPECT"
echo "[cam-preflight]      (or re-install 99-arducam.rules). Then re-run this gate."
echo "[cam-preflight] >>> DO NOT CAPTURE until $EXPECT streams."
exit 1
