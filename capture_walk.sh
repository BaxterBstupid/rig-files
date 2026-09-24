#!/bin/bash
# capture_walk.sh — TIMED, KEYBOARD-FREE walked capture           (2026-09-24)
# ============================================================================
# A thin WRAPPER around the proven capture_pointlio_texture.sh (Piece 1). It does
# NOT reimplement the capture — it reuses that script wholesale and adds ONLY the
# three things the walked capture needs that the bare script lacks (audit 9-24):
#
#   (1) SOURCES ~/point_lio_ws so `ros2 launch point_lio` is found. The capture
#       script never sources it, so run bare it dies at gate [4]. (blocker #1)
#   (2) AUTO-STOPS after N seconds of RECORDING, so you never touch the keyboard
#       mid-walk (no Ctrl+C). N counts from when recording ACTUALLY begins, so
#       setup/gate time doesn't eat into your walk. (blocker #3)
#   (3) STOPS VIA SIGINT so the capture script's OWN clean-shutdown trap runs ->
#       the bag finalizes AND Point-LIO saves scans.pcd. A SIGKILL loses the
#       geometry; that is the whole reason we signal rather than pkill -9. (blocker #2)
#
# DESIGN NOTE (why the capture runs in the FOREGROUND): bash sets a *backgrounded*
# child's SIGINT to SIG_IGN, and a script cannot install an INT trap for a signal
# ignored on entry — so a backgrounded capture would never run its clean-shutdown
# trap on our signal (verified: it hangs, no PCD). A FOREGROUND child keeps the
# default SIGINT, so its trap installs and fires. A background announcer watches the
# log and delivers the timed SIGINT. No job-control / tty dependency.
#
# USAGE:   ./capture_walk.sh [SECONDS]        (default 90)
#   1. Start it AT THE DESK. Enter your sudo password once (jetson_clocks).
#   2. WAIT for the big "RECORDING — WALK NOW" banner, THEN pick up the rig and walk.
#   3. It stops itself after SECONDS and saves the bag + scans_<stamp>.pcd to
#      ~/Desktop (exact paths printed at the end). It fails LOUD if a gate stopped
#      the capture before recording, so a bad run never looks like a good one.
#
# PREREQ:  rig_start_compressed.sh already up (LiDAR + compressed camera live).
# ============================================================================
set -u

DURATION="${1:-90}"
case "$DURATION" in ''|*[!0-9]*) echo "usage: $0 [SECONDS]  (positive integer)"; exit 2;; esac

# CAPTURE_SCRIPT is overridable so the control logic can be tested against a mock.
SCRIPT="${CAPTURE_SCRIPT:-$HOME/Downloads/capture_pointlio_texture.sh}"
LOG="/tmp/capture_walk_$$.log"
[ -f "$SCRIPT" ] || { echo "[walk] capture script not found: $SCRIPT"; exit 1; }

# --- (1) environment: humble + lidar/tools ws + Point-LIO's own ws ------------
# ROS setup scripts reference optional unset vars (AMENT_TRACE_SETUP_FILES, ...),
# so `set -u` must be OFF while sourcing them, then back ON for our own logic.
set +u
source /opt/ros/humble/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
source "$HOME/point_lio_ws/install/setup.bash"     # FIX #1 — Point-LIO on the path
set -u

# pre-authorize sudo once so the script's `sudo jetson_clocks` cannot block on a
# hidden password prompt (its output is redirected to the log).
echo "[walk] sudo needed once for jetson_clocks — enter your password:"
sudo -v || echo "[walk] sudo unavailable; continuing WITHOUT max clocks"

: > "$LOG"

# --- (2)+(3) background announcer: waits for recording to start, opens the walk
#     window for DURATION, then SIGINTs the foreground capture so its trap saves.
(
  for _ in $(seq 1 120); do grep -q "Recording\.\.\." "$LOG" 2>/dev/null && break; sleep 1; done
  if grep -q "Recording\.\.\." "$LOG" 2>/dev/null; then
    echo "[walk] ==================================================="
    echo "[walk] ======   RECORDING — WALK NOW for ${DURATION}s   ======"
    echo "[walk] ==================================================="
    sleep "$DURATION"
    echo "[walk] ====== TIME UP — stopping cleanly (bag + scans.pcd) ======"
    pkill -INT -f "$SCRIPT"        # -> the capture script's clean-shutdown trap
  fi
) &
TIMER=$!

echo "[walk] launching capture — it will AUTO-STOP ${DURATION}s after recording begins."
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
