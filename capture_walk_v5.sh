#!/bin/bash
# capture_walk_v5.sh — TIMED, KEYBOARD-FREE capture with ENFORCED IMU INIT   (2026-09-24)
# ============================================================================
# v5 CHANGE (audit §12, Master 20.13.69): v4 announced "WALK NOW" the instant
# recording began and drove a CONTINUOUS pan from a moving start. Point-LIO is
# configured start_in_aggressive_motion:false — it REQUIRES a static start to lock
# gravity + gyro bias — and the L2 gyro carries ~1.3°/s bias. No static lock +
# continuous rotation = the bias smears heading across the sweep = fanned/tripled
# walls. v5 fixes the MOTION, which was the actual bug:
#   (A) ENFORCED STATIC INIT: after recording begins, holds a DEAD-STILL countdown
#       (default 12s) BEFORE signalling GO, so Point-LIO locks gravity+bias. The
#       init frames are recorded at the head of the bag (exactly what Point-LIO wants).
#   (B) STOP-AND-GO banner: instructs rotate~20° / STOP~2s / repeat — never a
#       continuous sweep. Zero angular velocity at each stop re-locks bias and pins
#       each LiDAR frame to a stable heading.
# Everything else is v4 verbatim (proven): ws sourcing, foreground-SIGINT trap so
# the capture script's clean-shutdown saves scans.pcd, gate assessment.
#
# USAGE:   ./capture_walk_v5.sh [PAN_SECONDS] [STATIC_SECONDS]     (default 90, 12)
#   1. Start it AT THE DESK, rig ON ITS STAND / held still. Enter sudo password once.
#   2. On "HOLD DEAD STILL" — DO NOT MOVE THE RIG for the countdown (IMU init).
#   3. On "GO" — slow STOP-AND-GO pan: rotate ~20°, stop ~2s, repeat. Gentle.
#   4. Auto-stops after PAN_SECONDS; saves bag + scans_<stamp>.pcd to ~/Desktop.
#      Total recording = STATIC_SECONDS + PAN_SECONDS. Fails LOUD if a gate stopped it.
#
# PREREQ:  rig_start_compressed.sh already up (LiDAR + compressed camera live).
# ============================================================================
set -u

DURATION="${1:-90}"
STATIC="${2:-12}"
case "$DURATION" in ''|*[!0-9]*) echo "usage: $0 [PAN_SECONDS] [STATIC_SECONDS]"; exit 2;; esac
case "$STATIC"   in ''|*[!0-9]*) echo "usage: $0 [PAN_SECONDS] [STATIC_SECONDS]"; exit 2;; esac

SCRIPT="${CAPTURE_SCRIPT:-$HOME/Downloads/capture_pointlio_texture.sh}"
LOG="/tmp/capture_walk_$$.log"
[ -f "$SCRIPT" ] || { echo "[walk] capture script not found: $SCRIPT"; exit 1; }

# --- (1) environment: humble + lidar/tools ws + Point-LIO's own ws ------------
set +u
source /opt/ros/humble/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
source "$HOME/point_lio_ws/install/setup.bash"
set -u

echo "[walk] sudo needed once for jetson_clocks — enter your password:"
sudo -v || echo "[walk] sudo unavailable; continuing WITHOUT max clocks"

: > "$LOG"

# --- (2)+(3) announcer: wait for recording -> ENFORCE STATIC INIT -> GO (stop-and-go)
#     -> after PAN_SECONDS, SIGINT the foreground capture so its clean trap saves.
(
  for _ in $(seq 1 120); do grep -q "Recording\.\.\." "$LOG" 2>/dev/null && break; sleep 1; done
  if grep -q "Recording\.\.\." "$LOG" 2>/dev/null; then
    echo "[walk] ==================================================="
    echo "[walk] ===   HOLD DEAD STILL — IMU INIT (${STATIC}s)     ==="
    echo "[walk] ===   rig on the stand — DO NOT MOVE IT YET       ==="
    echo "[walk] ==================================================="
    for s in $(seq "$STATIC" -1 1); do echo "[walk]    init... ${s}s (keep still)"; sleep 1; done
    echo "[walk] ==================================================="
    echo "[walk] ======   GO — SLOW STOP-AND-GO PAN for ${DURATION}s   ======"
    echo "[walk] ===   rotate ~20deg, STOP ~2s, repeat.            ==="
    echo "[walk] ===   NEVER a continuous sweep. gentle.           ==="
    echo "[walk] ==================================================="
    sleep "$DURATION"
    echo "[walk] ====== TIME UP — stopping cleanly (bag + scans.pcd) ======"
    pkill -INT -f "$SCRIPT"
  fi
) &
TIMER=$!

echo "[walk] launching capture — ${STATIC}s STATIC INIT then ${DURATION}s stop-and-go pan (auto-stop)."
bash "$SCRIPT" > "$LOG" 2>&1        # FOREGROUND: keeps default SIGINT so its trap works
kill "$TIMER" 2>/dev/null; wait "$TIMER" 2>/dev/null

# --- assess: did we actually record, or did a gate stop it first? -------------
if grep -q "Recording\.\.\." "$LOG"; then
  echo "[walk] ---- capture log (tail) ----"; tail -20 "$LOG"
  echo "[walk] done — bag + scans_<stamp>.pcd are on ~/Desktop (paths above)."
else
  echo "[walk] !! capture EXITED before recording — a gate stopped it. Full log:"
  echo "------------------------------------------------------------"; cat "$LOG"
  exit 1
fi
