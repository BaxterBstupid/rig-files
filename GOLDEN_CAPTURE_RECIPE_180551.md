# GOLDEN CAPTURE RECIPE — reproduce the 180551 success (corrected for full camera)
# Source: fusioncap_180551 (2026-09-04) — first REAL translating capture: poses spanned 2.65m,
#   56M PCD, 81s, legible mesh, the milestone. Motion: rig off the stand, tip-down / tip-up / ~1m walk.
# ONE CORRECTION vs the original 180551 run: use rig_start_LEAN.sh (no fusion nodes) so the CAMERA
#   survives the FULL capture. The original 180551 used rig_start.sh (fusion nodes) -> its camera died
#   at ~14s (geometry was great, camera truncated). This recipe keeps the geometry success AND fixes camera.

## WHAT MADE 180551 WORK (the essence to reproduce)
1. Rig OFF the stand, held in hand (odometry needs real translation; a stand = odometry-starved).
2. Motion = tip DOWN, tip UP, then a ~1m WALK. Real translation of the sensor through space (this is
   what made the poses span 2.65m instead of the ~cm of every static/pan capture).
3. Slow, deliberate motion. (Fast motion blurs geometry + breaks tracking — keep it ~0.7 m/s, gentle.)
4. All four sensors verified LIVE at the wire BEFORE capturing.

## EXACT STEPS (beginning to end)

### PRE-FLIGHT (cold, no L2)
    md5sum ~/Desktop/rig_kiosk_server.py ~/point_lio_capture.sh 2>/dev/null   # sanity: files present
    source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
    pgrep -af 'pointlio|ros2 bag|unilidar|gscam|fusion' | grep -v grep || echo "all down OK"
    df -h /mnt/rigdata | tail -1                                             # confirm SSD mounted, has room

### 1. POWER THE L2 (physical). Wait ~15s for it to spin up.

### 2. START RIG *** LEAN *** (this is the key correction — NO fusion nodes -> full-rate camera)
    ~/rig_start_lean.sh
    # wait for "ALL SYSTEMS STARTED". Leave this terminal running (it holds the rig up).

### 3. VERIFY ALL FOUR SENSORS AT THE WIRE (second terminal)
    source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
    echo "LiDAR:";  timeout 8 ros2 topic hz /unilidar/cloud 2>&1 | grep -m1 average   # want ~12
    echo "IMU:";    timeout 6 ros2 topic hz /unilidar/imu   2>&1 | grep -m1 average   # want ~251
    echo "Camera:"; timeout 8 ros2 topic hz /image_raw      2>&1 | grep -m1 average   # want ~27
    # if camera silent: physical USB unplug/replug the camera, then re-check (Mode-2 stall fix).

### 4. CAPTURE (the 180551 motion)
    source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
    ~/point_lio_capture.sh
    # wait for "CAPTURE NOW", then:
    #   a. hold DEAD STILL ~5s (IMU init)
    #   b. TIP the rig DOWN slowly (~5s)
    #   c. TIP the rig UP slowly, back through level (~5s)
    #   d. WALK ~1m through the space, slow & deliberate
    #   e. one Ctrl-C to STOP (never a second time)
    # wait for "STOP 4/4: SUCCESS" + BAG [ok] + PCD [ok].

### 5. VERIFY THE CAPTURE (cold) — confirm camera spanned the FULL duration this time
    BAG=/mnt/rigdata/fusioncap_<STAMP>   # use the stamp the capture printed
    cd ~/anchor_test && python3 -c "
from rosbags.rosbag2 import Reader; import numpy as np
r=Reader('$BAG'); r.open(); it=[]; t0=None; t1=None
for c,t,raw in r.messages():
    t0=t if t0 is None else min(t0,t); t1=max(t1 or t,t)
    if c.topic=='/image_raw': it.append(t)
r.close(); it=np.array(sorted(it)); span=(t1-t0)/1e9
print(f'span {span:.1f}s, camera {len(it)} frames, covers {(it[0]-t0)/1e9:.1f}-{(it[-1]-t0)/1e9:.1f}s')
print('CAMERA FULL' if (it[-1]-t0)/1e9 > span-3 else 'CAMERA DIED at %.1fs (are fusion nodes running? use rig_start_lean.sh)'%((it[-1]-t0)/1e9))
"
    # want: 'CAMERA FULL'. If it died -> a fusion node is running; you used rig_start.sh not _lean.

### 6. POWER DOWN THE L2. Everything after is cold analysis.

## POST-CAPTURE (the proven texture pipeline — per TEXTURE_BRIDGE_RUNBOOK.md)
    cd ~/anchor_test
    python3 pointlio_pose_matcher.py $BAG -o posed_<STAMP>.npz --dump-frames frames_<STAMP>
    # then the baker:  python3 pointlio_to_texture.py <cloud.pcd> posed_<STAMP>.npz frames_<STAMP> --out <render>.png
    # (add --occlusion for a walked/multi-viewpoint capture)

## NOTES
- The 180551 ORIGINAL used rig_start.sh (fusion nodes) -> camera truncated to ~14s. This recipe uses
  rig_start_lean.sh so the camera lives the whole capture. Geometry recipe unchanged; camera fixed.
- For TEXTURE specifically, the runbook prefers capture_pointlio_texture.sh (records COMPRESSED camera
  topic; raw /image_raw can overrun the SD and drop frames). For a straight repeat of 180551's geometry
  success, point_lio_capture.sh is fine; for best texture, prefer the texture capture script.
