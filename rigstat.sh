#!/bin/bash
# rigstat: ONE-SHOT rig status. Rates come from the kiosk server's own /data (no pipe/timeout
# problems), plus memory and bridge state. Run this at every checkpoint.
echo "=== RIG  (from kiosk /data) ==="
curl -s --max-time 3 http://localhost:8080/data | python3 -c '
import sys, json
raw = sys.stdin.read()
if not raw.strip():
    print("  kiosk server NOT answering on :8080"); sys.exit()
try:
    d = json.loads(raw)
except Exception:
    print("  kiosk /data not valid JSON"); sys.exit()
if not d:
    print("  server up, no data yet (reader still starting)"); sys.exit()
def hz(k):
    s = d.get(k, {}); return "%5.1fHz %-7s" % (s.get("hz", 0) or 0, s.get("state", "?"))
print("  rig_on=%s  capturing=%s" % (d.get("rig_on"), d.get("capturing")))
print("  LiDAR  " + hz("lidar"))
print("  Camera " + hz("camera"))
print("  IMU    " + hz("imu"))
print("  Odom   " + hz("odom"))
j = d.get("jetson", {}); l = d.get("l2", {})
r=lambda v: ("%.0f"%v) if isinstance(v,(int,float)) else "?"
print("  Jetson %sC (%s)   L2 %sC (%s)" % (r(j.get("temp")), j.get("state"), r(l.get("temp")), l.get("state")))
'
echo "=== MEMORY ==="
free -h | awk 'NR<=2{print "  "$0}'
echo "=== BRIDGE ==="
BRIDGE_BIN="/opt/ros/humble/lib/foxglove_bridge/foxglove_bridge"
if pgrep -f "^$BRIDGE_BIN" >/dev/null; then
  if pgrep -af "^$BRIDGE_BIN" | grep -q topic_whitelist; then echo "  bridge RUNNING - whitelisted (safe)"
  else echo "  bridge RUNNING - *** NOT whitelisted *** (can serve /image_raw)"; fi
else echo "  bridge NOT running"; fi
