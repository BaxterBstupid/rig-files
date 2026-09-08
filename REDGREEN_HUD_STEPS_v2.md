# RED/GREEN HUD — DECISIVE STEP SEQUENCE (v2, 2026-09-08)
# GOAL: coverage voxels render red->green in the kiosk MAP panel.
# ROOT STATUS (cold-verified this session): Point-LIO's CONFIG is correct for publishing
# /cloud_registered — QoS RELIABLE (compatible), scan_publish_en=true (wired to scan_pub_en),
# odom_only=false in mapping_unilidar_l2.launch.py (the launch the capture actually uses; the
# odom_only:True was in a DIFFERENT launch, correct_odom_*, we do NOT use). So config is NOT the
# blocker. The empty map is a RUNTIME question: is /cloud_registered actually reaching the server?
# This sequence DIAGNOSES that at the wire vs the panel instead of guessing.

# NEVER-SKIP: Point-LIO only runs during a CAPTURE (not Start Rig / lean). No capture = no
# /cloud_registered = empty MAP. Every empty-map session so far never had a capture running while looking.

═══════════════════════════════════════════════════════════════════
## STEP 0 — DEPLOY (cold). Restore kiosk stack + the REGDIAG-instrumented server & capture.
═══════════════════════════════════════════════════════════════════
# kiosk 5-file stack (daily-cleanup sweeps these):
cp "$HOME/Desktop/ALL FILES Sept 7/rig_kiosk.html"  ~/Desktop/rig_kiosk.html
cp "$HOME/Desktop/ALL FILES Sept 7/cloud.html"      ~/Desktop/cloud.html
cp "$HOME/Desktop/ALL FILES Sept 7/launch.html"     ~/Desktop/launch.html
cp "$HOME/Desktop/ALL FILES Sept 7/three.min.js"    ~/Desktop/three.min.js
# instrumented server (throttled odom + reg_cb logs errors + /regdiag endpoint):
cp <downloaded>/rig_kiosk_server_REGDIAG.py         ~/Desktop/rig_kiosk_server.py
# daemon-safe capture that ALSO records /cloud_registered:
cp <downloaded>/point_lio_capture_REGDIAG.sh        ~/point_lio_capture.sh
chmod +x ~/point_lio_capture.sh
# VERIFY:
md5sum ~/Desktop/rig_kiosk_server.py   # want 6a901f2c
md5sum ~/point_lio_capture.sh          # want b34ca627
grep -c "ros2 daemon stop" ~/point_lio_capture.sh                 # want 0
grep -c "/cloud_registered" ~/point_lio_capture.sh                # want >=1 (now recorded)
for f in rig_kiosk.html cloud.html launch.html three.min.js; do [ -f ~/Desktop/$f ] && echo OK $f || echo MISSING $f; done

═══════════════════════════════════════════════════════════════════
## STEP 1 — POWER L2, wait ~15s.
## STEP 2 — LEAN START:  ~/rig_start_lean.sh   (wait "ALL SYSTEMS STARTED", leave running)
## STEP 3 — WIRE CHECK (new terminal): LiDAR ~12, Camera ~27
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
echo LiDAR:; timeout 8 ros2 topic hz /unilidar/cloud 2>&1 | grep -m1 average
echo Camera:; timeout 8 ros2 topic hz /image_raw     2>&1 | grep -m1 average
═══════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════
## STEP 4 — LAUNCH KIOSK FRESH (AFTER lean settled the daemon), load /kiosk directly.
═══════════════════════════════════════════════════════════════════
pkill -9 -f rig_kiosk_server.py; sleep 2
~/rig_kiosk_launch.sh
sleep 3
curl -s -m3 localhost:8080/data | head -c 150     # want live Hz, not 0
# browser: http://localhost:8080/kiosk   (bypass the launcher-cache trap). gauges live, odom band, panel.

═══════════════════════════════════════════════════════════════════
## STEP 5 — START POINT-LIO (a capture). THE step that feeds the red/green map. New terminal:
═══════════════════════════════════════════════════════════════════
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
~/point_lio_capture.sh
# wait "CAPTURE NOW". Hold still ~5s (IMU init). Watch kiosk: gauges STAY live (daemon-safe proof),
# odom band advances waiting->INIT->TRACKING.

═══════════════════════════════════════════════════════════════════
## STEP 5.5 — FAST PANEL READ (no terminal): what does the MAP panel STATUS TEXT say?
##   (the panel code shows one of these; it splits the whole problem in one glance)
##   - "no server" (red)        -> server/route problem: /map.bin fetch failed. Server not on :8080,
##                                 or route broken. Go check Step 4 (server up? curl /data works?).
##   - "MAP LIVE" + "voxels 0"  -> server fine, panel fine, but ACCUMULATOR EMPTY:
##                                 /cloud_registered never fed it. This is the likely one. -> Step 6.
##   - renders voxels           -> WORKS. MAP mode + MOVE -> red/green (Step 7).
##   (Make sure the panel is on the MAP tab, and a CAPTURE is running, before reading this.)
═══════════════════════════════════════════════════════════════════
## STEP 6 *** THE DECISIVE DIAGNOSTIC *** — wire vs panel. Run WHILE the capture is live. New terminal:
═══════════════════════════════════════════════════════════════════
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
echo "=== A) is Point-LIO running? ==="
pgrep -af pointlio | grep -v grep || echo "  NOT running (start a capture)"
echo "=== B) is it publishing AT THE WIRE? ==="
timeout 6 ros2 topic hz /aft_mapped_to_init 2>&1 | grep -m1 average || echo "  /aft_mapped_to_init SILENT"
timeout 8 ros2 topic hz /cloud_registered   2>&1 | grep -m1 average || echo "  /cloud_registered SILENT"
echo "=== C) does the SERVER see it? (intake diagnostics) ==="
curl -s localhost:8080/regdiag    # {msgs, added, err, fields}
echo; echo "=== D) map state ==="
curl -s localhost:8080/map.json   # {voxels, ...}

# ---- READ THE RESULT (this NAMES the cause, no guessing): ----
#  B: /cloud_registered SILENT at wire  -> Point-LIO isn't publishing it despite correct config.
#       Runtime issue (feats_down_body empty? publish gated at runtime?). NOT server. Investigate PLIO runtime.
#  B: /cloud_registered LIVE at wire, but C: regdiag msgs=0 -> server NOT receiving a topic that IS
#       on the wire -> discovery/topic-name mismatch (server subscribes REG_TOPIC="/cloud_registered";
#       confirm that's the exact name at the wire). 
#  C: msgs>0 but added=0 + err populated -> server RECEIVES but cloud_to_bin CHOKES on the format ->
#       read regdiag "fields" (the point layout) and fix cloud_to_bin for /cloud_registered's fields.
#  C: added>0 / D: voxels>0 -> IT WORKS. Panel MAP mode + MOVE the rig -> red/green fills.

═══════════════════════════════════════════════════════════════════
## STEP 7 — IF WORKING: MAP mode + MOVE (translate; static kills odom ~15s). Dwell=green, rush=red.
## STEP 8 — STOP: one Ctrl-C. Power down L2.
═══════════════════════════════════════════════════════════════════

## KEY FILES (md5): server 6a901f2c | capture b34ca627
## The decisive fact this sequence gets: WHERE the /cloud_registered chain breaks — wire, discovery,
## format, or nowhere (works). One run, one answer. No more theory-chasing.
