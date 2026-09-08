#!/bin/bash
# reset_odom.sh — SAFE STUB (2026-09-08). Fired by the kiosk RESET ODOM button (/action?do=reset_odom).
# HONEST STATUS: the full re-anchor-and-continue (restart Point-LIO in place + stitch at processing
# time using the coverage-map overlap) is NOT built/proven yet. This stub does the SAFE minimum:
#   - records the reset request + a timestamp marker (for a future processing-time stitch)
#   - does NOT kill/restart Point-LIO (a blind mid-capture restart would create an unstitchable
#     two-frame bag; that belongs to the proven re-anchor work, not here)
# So today the button is HONEST: it logs intent and marks the bag, it does not fake a recovery.
MARK="$HOME/rig_logs/reset_odom_marks.log"
mkdir -p "$HOME/rig_logs"
echo "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ) RESET_ODOM requested (stub: marker only, no restart)" >> "$MARK"
# emit a ROS marker too if the stack is up, so the bag carries the reset timestamp for post-stitch
if command -v ros2 >/dev/null 2>&1; then
  ( source /opt/ros/humble/setup.bash 2>/dev/null
    timeout 2 ros2 topic pub -1 /rig/reset_marker std_msgs/msg/String "{data: 'reset_odom $(date -u +%s.%N)'}" >/dev/null 2>&1 ) &
fi
echo '{"ok": true, "action": "reset_odom", "mode": "stub-marker-only"}'
