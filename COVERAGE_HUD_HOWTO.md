# HOW TO GET THE COVERAGE HUD (red/green MAP panel) WORKING — EXACT REPEATABLE STEPS
# Confirmed working 2026-09-08 (produced ~14,485 live voxels, capture fusioncap_170751).
# This is the EXACT sequence that worked. Follow it top to bottom. Do not skip Step 0 or the WALK.

################################################################################
# WHY IT WORKS (so you understand what each step is for):
#   The coverage panel renders /map.bin, which the server builds by accumulating
#   /cloud_registered (Point-LIO's world-frame cloud) using map_accumulator.py.
#   For voxels to appear, ALL of these must be true AT THE SAME TIME:
#     1. All 6 kiosk files on the Desktop (esp. map_accumulator.py - the one that gets swept)
#     2. Rig up (lean start) so LiDAR flows
#     3. Kiosk server launched AFTER the rig (so it discovers the topics)
#     4. A CAPTURE running (Point-LIO) - /cloud_registered ONLY exists during a capture
#     5. You WALK during the capture - static = no tracking = no cloud = empty map
#     6. Panel on the MAP tab
#   The whole prior failure was #1 (map_accumulator.py missing -> silent ModuleNotFoundError).
################################################################################

═══════════════════════════════════════════════════════════════════════════════
STEP 0 — RESTORE THE KIOSK STACK (COLD, before powering the L2). *** DO NOT SKIP ***
═══════════════════════════════════════════════════════════════════════════════
# The daily cleanup sweeps required files off the Desktop. Restore all 6 first.
# (adjust "ALL FILES Sept 7" to the NEWEST dated folder on the Desktop)
~/restore_kiosk.sh "$HOME/Desktop/ALL FILES Sept 7"
# MUST print "kiosk stack COMPLETE - safe to launch" with all 6 present:
#   rig_kiosk_server.py, rig_kiosk.html, cloud.html, launch.html, three.min.js, map_accumulator.py
# Verify the server is the REGDIAG/throttled one:
md5sum ~/Desktop/rig_kiosk_server.py            # expect 6a901f2c
# Verify the capture script is daemon-safe + records /cloud_registered:
md5sum ~/point_lio_capture.sh                   # expect b34ca627
grep -c "ros2 daemon stop" ~/point_lio_capture.sh   # expect 0

═══════════════════════════════════════════════════════════════════════════════
STEP 1 — POWER THE L2. Wait ~15 seconds for it to spin up.
═══════════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════════
STEP 2 — LEAN START (brings up LiDAR + camera; NO fusion nodes so camera survives).
═══════════════════════════════════════════════════════════════════════════════
~/rig_start_lean.sh
# Wait for "ALL SYSTEMS STARTED" and "LiDAR data confirmed flowing".
# LEAVE THIS TERMINAL RUNNING (it holds the rig up).

═══════════════════════════════════════════════════════════════════════════════
STEP 3 — LAUNCH THE KIOSK FRESH (in a NEW terminal). Must be AFTER lean start.
═══════════════════════════════════════════════════════════════════════════════
pkill -9 -f rig_kiosk_server.py; sleep 2       # kill any stale/deaf server first
~/rig_kiosk_launch.sh
sleep 6                                          # give ROS discovery time to settle
curl -s -m3 localhost:8080/data | head -c 100
#   WANT: lidar hz ~12, state "ok".  If it shows 0 -> wait and re-check:
#   sleep 3; curl -s -m3 localhost:8080/data | head -c 100   (discovery is racy, ~6-9s)
# In the browser, load the kiosk face DIRECTLY (bypasses a cached-launcher trap):
#     http://localhost:8080/kiosk
# CLICK THE "MAP" TAB in the coverage panel (SCAN/MAP/MESH buttons, top-left of the 3D view).

═══════════════════════════════════════════════════════════════════════════════
STEP 4 — START A CAPTURE (in a NEW terminal). This starts Point-LIO = the map's data source.
═══════════════════════════════════════════════════════════════════════════════
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
~/point_lio_capture.sh
# Wait for "CAPTURE NOW".
#   a) HOLD THE RIG DEAD STILL for ~5 seconds (IMU init - you'll see "IMU Initializing 100%").
#   b) THEN WALK. *** THIS IS ESSENTIAL *** Translate through the space continuously for
#      30-60 seconds: step forward, turn WHILE moving, cover the room. Point-LIO only tracks
#      (and only publishes /cloud_registered) when you TRANSLATE. Standing still = empty map.
#   c) WATCH THE MAP PANEL: voxels appear and fill in as you walk = THE COVERAGE HUD WORKING.

═══════════════════════════════════════════════════════════════════════════════
STEP 5 — CONFIRM (optional; the voxels on the panel already prove it).
═══════════════════════════════════════════════════════════════════════════════
# In another terminal, while capturing:
curl -s localhost:8080/regdiag; echo; curl -s localhost:8080/map.json
#   WANT: /regdiag  {"msgs": >0, "added": >0, "err": ""}   <- added>0 & no err = accumulating
#         /map.json {"voxels": >0 ...}                      <- climbing as you walk
#   (If you see voxels rendering in the panel, you don't NEED this - the render IS the proof.)

═══════════════════════════════════════════════════════════════════════════════
STEP 6 — STOP. One Ctrl-C in the capture terminal (NEVER twice). Wait for "STOP 4/4: SUCCESS".
         Then power down the L2.
═══════════════════════════════════════════════════════════════════════════════
# A good run saves: BAG [ok] + PCD [ok] (a few MB = real tracking). That capture is usable.

################################################################################
# TROUBLESHOOTING (what each symptom means):
#   Panel blank, "voxels 0", gauges live      -> no capture running, OR you're not moving,
#                                                 OR map_accumulator.py missing (check /regdiag err)
#   /regdiag err = ModuleNotFoundError         -> map_accumulator.py not on Desktop -> run restore_kiosk.sh
#   /regdiag msgs=0                            -> server not receiving /cloud_registered:
#                                                 no capture running, or relaunch kiosk AFTER capture starts
#   Gauges all 0 / "dropped" but rig is up     -> kiosk server started before discovery settled ->
#                                                 pkill -9 -f rig_kiosk_server.py; ~/rig_kiosk_launch.sh; wait 6s
#   Panel shows "no server"                    -> server not running on :8080 -> relaunch kiosk
#   Camera 0 / nvmap error 12 spam             -> hardware-decoder exhausted. REBOOT clears it.
#                                                 Does NOT affect coverage (that's the LiDAR path).
#   Coverage mostly yellow, not red/green      -> normal for uniform coverage (yellow = mid-ramp).
#                                                 Dwell in spots vs rush past others to see red->green.
#   Odom dies ~15s / few poses                 -> you went static or panned in place. WALK (translate).
#
# KEY FILE md5s: server 6a901f2c | capture b34ca627
# THE 6 DESKTOP FILES: rig_kiosk_server.py, rig_kiosk.html, cloud.html, launch.html,
#                      three.min.js, map_accumulator.py   (restore_kiosk.sh handles all 6)
################################################################################
