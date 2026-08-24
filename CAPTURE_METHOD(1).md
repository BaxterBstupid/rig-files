# THE CAPTURE METHOD — PROVEN 2026-08-24 (WRITTEN IN STONE, UNABRIDGED)
### The complete, exhaustive record of the one-click Point-LIO capture procedure:
### every step, every line of code, every measurement, every guard, and the history
### of why each exists. Reference run: fusioncap_083911 — first try, first success.
### If this method must ever change, change THIS DOCUMENT deliberately. Never drift.

═══════════════════════════════════════════════════════════════════════════
## 0. WHY THIS DOCUMENT EXISTS (the provenance — read this first)
═══════════════════════════════════════════════════════════════════════════
This project stalled at ~25% of deliverable quality for a week and a half. The
diagnosis (2026-08-23, operator-driven) was NOT an engineering failure: it was
LEAKY DATA — settled decisions un-learned between sessions, lost messages, stale
content read as current, wrong file versions confidently used — which forced
racing from one solve to the next, re-fighting battles already won.

The night the record was made consistent (Master 18.1), the first capture run
through this method SUCCEEDED ON THE FIRST TRY and produced a dimensionally true,
visually recognizable cloud ("as close to the real image as can be imagined" —
operator). The method works. This document makes it unlosable.

THE STANDING RULES THIS DOCUMENT SERVES:
1. The operator-controlled Master + this method doc are TRUTH over any session's
   reconstruction or memory.
2. Version is part of the method — a right-named file with wrong contents is a
   trap (this bit us twice in one night: v1-vs-v2, and wget's empty husks).
3. Verify like it matters: every transfer, every save, every version — checked,
   never assumed. End with ls. Trust output, not intention.

═══════════════════════════════════════════════════════════════════════════
## 1. THE INSTRUMENT (complete hardware + calibration context)
═══════════════════════════════════════════════════════════════════════════
THE RIG (handheld):
- COMPUTE: NVIDIA Jetson Orin Nano 8GB (JetPack 6.2, Ubuntu 22.04, ROS2 Humble).
  8GB RAM is a HARD LIMIT with consequences: the deliverable mesher (trimmed
  Poisson depth 9) segfaults on the Jetson; meshing/texturing/Unreal belong on a
  processing station. The Jetson is the CAPTURE FRONT-END. This method is the
  front-end procedure.
- LIDAR: Unitree L2. ~12Hz cloud on /unilidar/cloud, built-in IMU at ~251Hz on
  /unilidar/imu. Range 30m (15m @ 90% reflectivity). Heat-sensitive: prefer
  short capture windows; the sensor should not be left cooking between runs.
  Non-uniform point spacing (~10.9x variation between dense and sparse regions)
  — this is WHY the mesher is trimmed Poisson and not ball-pivoting.
- CAMERA: Arducam B0578 (OG02B10 sensor, 1/2.6", global shutter), 1920x1080 on
  /image_raw via V4L2. USB2 UVC — NO hardware trigger pin, therefore NO hardware
  sync with the LiDAR; time alignment is software (tau ~175ms rough; final value
  measured per-capture from the bag). Fixed focus. Brightness is controlled in
  software (camera_control.py — bright capture matters; a dim room produced the
  murky blue texture of first_fusion).
- MOUNT: camera above LiDAR on the cheese plate, rig geometry LOCKED 2026-08-16.

CALIBRATION (vetted, files on Jetson ~/Desktop):
- INTRINSICS (calib_intrinsics_20260813.yaml, 88% coverage, RMS 0.297,
  fy/fx = 1.0006):
      K = [ 848.759    0      921.002 ]
          [   0      849.231  565.962 ]
          [   0        0        1     ]
      DIST (plumb bob) = [-0.014979, -0.013547, -0.001997, 0.000698, 0.003842]
  GOTCHA carved here: cx = 921.002 is the VETTED value. A stale cx = 1032 from an
  earlier calibration haunted old files — if you ever see cx 1032, it is WRONG.
- EXTRINSIC (extrinsic_20260816.yaml, visually verified):
      R: 85.54 degrees rotation between LiDAR and camera frames
      T = [0.018337, -0.053568, -0.159645] m   (|t| = 0.169 m)
  Projection chain (proven to 1e-16 in the engine): p_cam = R * P_lidar + T,
  then u = fx*x/z + cx, v = fy*y/z + cy.

WHAT THIS METHOD PRODUCES (the two halves of the future fused image):
- GEOMETRY: the Point-LIO map PCD — points-for-truth, dimensionally honest.
- IMAGES+MOTION: the bag — /image_raw frames + /aft_mapped_to_init poses (+ the
  raw /unilidar/cloud and /unilidar/imu). The pose-matcher pairs frames to poses
  BY BAG-RECORD TIME (never header stamps — Point-LIO odom header stamps are
  frozen; header matching yields 0 matches; this cost us a session once).
Downstream (NOT this method): trimmed-Poisson mesh (depth 9, ~5% low-density
trim, >8GB RAM machine) -> per-shot multi-view texture -> delight -> Unreal.

═══════════════════════════════════════════════════════════════════════════
## 2. THE TWO ICONS (do not confuse them)
═══════════════════════════════════════════════════════════════════════════
| Icon file (on ~/Desktop)      | What it does                                  |
|-------------------------------|-----------------------------------------------|
| PointLIO.desktop              | OLD (2026-08-21). Mapping ONLY: launches      |
|                               | run_point_lio.sh -> Point-LIO + RViz. No bag, |
|                               | no guarded shutdown, no PCD verification.     |
| PointLIOCapture.desktop       | THE CAPTURE METHOD (this document). Full      |
|                               | guarded capture: mapping + 4-topic bag +      |
|                               | ordered shutdown + verified, timestamped PCD. |

Use PointLIOCapture for every real capture. PointLIO remains only as a quick
"is the stack alive" viewer.

═══════════════════════════════════════════════════════════════════════════
## 3. THE COMPONENTS — FULL SOURCE, BYTE COUNTS, VERIFICATION
═══════════════════════════════════════════════════════════════════════════
Two files. Their versions are load-bearing. Verify BOTH before trusting a run.

### 3a. ~/point_lio_capture.sh — v2, 5828 bytes
IDENTITY CHECK (run any time; memorize the expected outputs):
    ls -la ~/point_lio_capture.sh
        -> -rwxrwxr-x ... 5828 <date> /home/fasterbybaxter/point_lio_capture.sh
    grep -c "SINGLE-INSTANCE LOCK" ~/point_lio_capture.sh
        -> 2          (v2 signature. If this prints 0 you have v1 — STOP, restore v2.)
    head -1 ~/point_lio_capture.sh
        -> #!/bin/bash
HISTORY: v1 (4714 bytes, built in the lost session of 2026-08-23 afternoon) had
no single-instance lock — a double-clicked icon would launch twice, and the
second instance's clean-slate pkill would KILL THE LIVE CAPTURE mid-run and spawn
a second RViz. v2 (2026-08-23 night) added the lock + icon-terminal pauses.
The v1 file also sat on ~/Desktop and in the repo for a while masquerading as
current — that mix-up is why the grep check above exists.

FULL SOURCE (verbatim, the entire v2 file):

```bash
#!/bin/bash
# point_lio_capture.sh — ONE-WINDOW safe capture for Point-LIO (Unitree L2).
# The Point-LIO equivalent of Start Rig: run it, capture, press Ctrl-C ONCE, done.
#
# PREREQ: LiDAR + camera already up (Start Rig) so /unilidar/cloud, /unilidar/imu,
#         /image_raw are publishing. This does NOT start the driver.
#
# Guarantees (the failure modes we designed out):
#   - Records /unilidar/cloud TOO  -> a failed PCD save is recoverable from the bag.
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
BAG="$HOME/Desktop/fusioncap_${STAMP}"
PCD_DST="$HOME/Desktop/fusioncap_${STAMP}_scans.pcd"
TOPICS=(/aft_mapped_to_init /image_raw /unilidar/imu /unilidar/cloud)

# shellcheck source=/dev/null
set +u  # ROS2 setup files reference unbound vars
source ~/ros2_ws/install/setup.bash
# shellcheck source=/dev/null
source ~/point_lio_ws/install/setup.bash

# --- PRE-FLIGHT: is the sensor actually publishing? (prevents capturing an empty bag) ---
echo "=== Pre-flight: checking /unilidar/cloud is publishing (Start Rig must be up) ==="
if ! timeout 5 ros2 topic echo --once /unilidar/cloud >/dev/null 2>&1; then
    echo "!!! /unilidar/cloud is NOT publishing. Is Start Rig up? Aborting (nothing captured). !!!"
    read -r -p "Press Enter to close this window..." _
    exit 1
fi
echo "    sensor OK."

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
setsid ros2 launch point_lio mapping_unilidar_l2.launch.py rviz:=true \
    >/tmp/pointlio_capture.log 2>&1 &
PLIO_PID=$!
PLIO_PGID="$(ps -o pgid= -p "$PLIO_PID" | tr -d ' ')"

sleep 10   # let IMU init complete

# show the init lines so the user sees it actually initialized before we record
echo "--- Point-LIO init (from log) ---"
grep -m1 "Initializing: 100" /tmp/pointlio_capture.log || echo "  (init line not seen yet; log at /tmp/pointlio_capture.log)"
echo "---------------------------------"

echo "=== Recording all 4 topics (incl. /unilidar/cloud) -> $BAG ==="
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
```

LINE-BY-LINE ANATOMY OF THE SCRIPT (what each block does and why):
- set -u / set +u: strict unbound-variable safety for OUR code, relaxed only
  around ROS2 setup sourcing (Humble's setup.bash references unbound vars).
- SINGLE-INSTANCE LOCK: mkdir /tmp/point_lio_capture.lock is ATOMIC — two
  simultaneous launches cannot both succeed. Second launch prints a loud refusal
  and waits for Enter. trap 'rmdir ...' EXIT releases the lock on EVERY exit
  path. Stale lock after a hard crash/reboot: rmdir /tmp/point_lio_capture.lock
- PATHS BLOCK: PCD_SRC is Point-LIO's FIXED-NAME output
  (~/point_lio_ws/src/point_lio_ros2/PCD/scans.pcd — every run OVERWRITES it;
  Unitree's own repo confirms this fixed-name behavior). STAMP=$(date +%H%M%S)
  names the run; BAG and PCD_DST land on ~/Desktop timestamped so runs never
  overwrite each other.
- TOPICS array: /aft_mapped_to_init (Point-LIO odometry poses — the texture
  bridge needs these), /image_raw (camera frames), /unilidar/imu (raw IMU),
  /unilidar/cloud (RAW LIDAR — the recovery insurance; see STOP 4 FAIL branch).
- PRE-FLIGHT: timeout 5 ros2 topic echo --once /unilidar/cloud — if the sensor
  isn't publishing within 5s, abort BEFORE creating anything. No empty bags.
- CLEAN SLATE: pkill lingering pointlio_mapping and rviz2 from crashed/orphaned
  prior runs. This runs AFTER the lock, so it can never kill a live capture —
  only true orphans.
- PCD_OLD_MTIME: records the CURRENT mtime of scans.pcd BEFORE the run, so the
  end-of-run check can PROVE the file was freshly written (vs silently reusing
  an old run's map — a failure mode we hit historically).
- setsid + PGID capture: Point-LIO and the bag each start in their OWN process
  group; shutdown signals go to the GROUP (kill -INT -- -PGID), so the actual
  pointlio_mapping node reliably receives SIGINT and runs its PCD-save handler.
  Without this, SIGINT can die at the launch wrapper and the save never happens.
- sleep 10 + init grep: gives the IMU init its window, then surfaces the
  "IMU Initializing: 100.0 %" line from /tmp/pointlio_capture.log so the
  operator SEES a good init before recording starts.
- cleanup() — THE ORDER IS LOAD-BEARING:
    STOP 1/4: SIGINT the BAG group first; wait. (Bag flushes to disk complete.)
    STOP 2/4: SIGINT the Point-LIO group; wait; +2s grace. (PCD save completes.)
    STOP 3/4: stat the PCD mtime again; FRESH means strictly newer than before.
    STOP 4/4: SUCCESS -> copy scans.pcd to the timestamped Desktop name, print
              both artifact paths + size. FAIL -> loud honest failure + the
              recovery path (the bag has /unilidar/cloud; replay to regenerate).
  trap '' INT TERM at cleanup entry: further Ctrl-C during shutdown is IGNORED
  so an impatient second Ctrl-C cannot corrupt the save sequence.
- Foreground wait + trap cleanup INT: the script parks on the bag process; ONE
  Ctrl-C in the terminal triggers the whole ordered shutdown. If the bag dies on
  its own (disk full, error), cleanup still runs.

### 3b. ~/Desktop/PointLIOCapture.desktop — 275 bytes
FULL SOURCE (verbatim, all 8 lines):

```ini
[Desktop Entry]
Type=Application
Name=Point-LIO Capture
Comment=One-window safe Point-LIO capture (bag + PCD, single Ctrl-C shutdown)
Exec=gnome-terminal --title="Point-LIO Capture" -- bash -c "$HOME/point_lio_capture.sh"
Terminal=false
Icon=camera-video
Categories=Utility;
```

ANATOMY: Exec explicitly spawns gnome-terminal (Terminal=false because WE manage
the terminal) so the run always has a visible window that accepts the Ctrl-C the
whole design depends on. Icon must be executable (chmod +x) and, on first click,
GNOME may ask "Trust this launcher?" — allow it (one-time).
IDENTITY CHECK:
    ls -la ~/Desktop/PointLIOCapture.desktop     -> 275 bytes, -rwxrwxr-x
    grep Exec ~/Desktop/PointLIOCapture.desktop  -> the gnome-terminal line above
TRANSFER HISTORY carved here: browsers mangle .desktop files (rename to
.download, strip content) — this file travels through the repo NAMED
PointLIOCapture_desktop.txt and is renamed by wget -O on the Jetson. Also: a
FAILED wget -O leaves a ZERO-BYTE HUSK with the right name (bit us 2026-08-23;
the empty file in gedit). A right-named file proves nothing — check bytes.

═══════════════════════════════════════════════════════════════════════════
## 4. THE METHOD — EVERY STEP WITH ITS EXPECTED OUTPUT
═══════════════════════════════════════════════════════════════════════════
### STEP 0 — PRECONDITIONS (before touching the icon)
- Rig assembled, L2 powered, camera connected.
- START RIG is up: the driver stack publishing /unilidar/cloud (~12Hz),
  /unilidar/imu (~251Hz), /image_raw (1920x1080). The capture tool does NOT
  start the driver — by design, so it can never fight or duplicate it.
- Desk check (optional but cheap):  ros2 topic hz /unilidar/cloud   -> ~12Hz
- Disk: a capture writes ~10-100MB+/min of bag. Desktop must have room.
- Heat: L2 warm-not-hot. Prefer several short captures over one long cook.
- BRIGHTNESS: if this capture feeds texture, run the brightness setup
  (camera_control.py) — dim rooms produce murky blue texture. Lesson of
  first_fusion.
- STILLNESS PLAN: know where the rig will sit DEAD STILL for init (a surface
  beats hands).
- COVERAGE PLAN: single vantage tops out ~66% texture coverage (parallax smears
  edge-on surfaces, unseen areas render black). For deliverable texture use the
  MULTI-VIEW pattern: the 270-degree pan, or A2 out-and-back (proven 2026-08-19:
  out-and-back through the space, ~40-60s, revisit the primary subject from a
  second angle).

### STEP 1 — CLICK THE ICON ONCE
One click. (A double-click is SAFE — the lock refuses the second instance — but
one click is the method.) A terminal titled "Point-LIO Capture" opens.
POSSIBLE FIRST LINE (harmless, expected on this Jetson):
    not found: "/home/fasterbybaxter/ros2_ws/install/fast_calib/share/fast_calib/local_setup.bash"
This is a stale workspace reference (fast_calib never built in ~/ros2_ws). It is
sourcing NOISE, not an error. The proven run printed it and succeeded. Breadcrumb
if calib tooling ever misbehaves; otherwise ignore.

### STEP 2 — PRE-FLIGHT GATE
    === Pre-flight: checking /unilidar/cloud is publishing (Start Rig must be up) ===
        sensor OK.
"sensor OK." -> proceed. OTHERWISE:
    !!! /unilidar/cloud is NOT publishing. Is Start Rig up? Aborting (nothing captured). !!!
    Press Enter to close this window...
THE ABORT IS THE TOOL WORKING — it refused to record an empty bag (cold-tested
2026-08-24: clean abort confirmed). Bring Start Rig up; click again.

### STEP 3 — CLEAN SLATE (automatic)
    === Clean slate: clearing any orphaned rviz2 / pointlio_mapping ===
(If it killed something it says so.) EXPECT EXACTLY ONE RVIZ from this run.
TWO RViz windows = wrong (should be impossible with the lock + clean slate);
stop, investigate, report. Hot run 2026-08-24: ONE RViz confirmed.

### STEP 4 — LAUNCH + DEAD-STILL IMU INIT (the make-or-break step)
    === Launching Point-LIO (with RViz reference view). Hold rig DEAD STILL for IMU init... ===
HOLD THE RIG GENUINELY STILL for the ~10s window — on a surface if possible.
Point-LIO establishes gravity here; motion during init = bad gravity = tilted,
smeared map. This rule predates the tool and is confirmed by both HKU's docs
("stay still >5s") and Unitree's own Point-LIO adaptation notes.
THEN the script surfaces the proof:
    --- Point-LIO init (from log) ---
    [pointlio_mapping-1] [INFO] [<stamp>] [laserMapping]: IMU Initializing: 100.0 %
    ---------------------------------
"100.0 %" is the green light. If instead you see "(init line not seen yet...)",
give it a beat; if it never appears, Ctrl-C, close, check /tmp/pointlio_capture.log.

### STEP 5 — CAPTURE
    === Recording all 4 topics (incl. /unilidar/cloud) -> /home/fasterbybaxter/Desktop/fusioncap_HHMMSS ===
    === CAPTURE NOW. Press Ctrl-C ONCE when done. ===
Now move. Smooth, deliberate motion — no whipping. Cover the space per the plan
(270-pan / out-and-back for texture captures). Watch RViz build the map live.
Keep windows in frame when exterior context matters — glass is NOT a wall to
this instrument (proven: the neighbor's house at 5-8m, correctly placed).
Duration: the proven run was short (11MB); A2-style runs ~40-60s; long captures
raise heat + displaced-cluster odds. Short and intentional beats long and hopeful.

### STEP 6 — ONE CTRL-C. THEN HANDS OFF.
Press Ctrl-C ONCE in the capture terminal. The trap catches it and runs the
entire ordered shutdown. DO NOT press it again, do not close the window, do not
touch RViz — extra signals during shutdown are deliberately ignored, but the
discipline is: one Ctrl-C, then watch.

### STEP 7 — THE FOUR STOPS (must appear IN THIS ORDER)
    === STOP 1/4: stopping the bag (flush to disk) ===
    === STOP 2/4: clean SIGINT to Point-LIO group; WAITING for PCD save ===
    === STOP 3/4: verifying the PCD saved FRESH ===
    === STOP 4/4: SUCCESS ===
       BAG  [ok]  /home/fasterbybaxter/Desktop/fusioncap_HHMMSS
       PCD  [ok]  /home/fasterbybaxter/Desktop/fusioncap_HHMMSS_scans.pcd
             size: <N>M
    Done. Press Enter to close this window...
The ORDER is the design: bag first (data on disk), then Point-LIO (save runs to
completion), then PROOF of freshness, then the copy. Never "fix" the order.

FAILURE BRANCH (honest, recoverable):
    === STOP 4/4: !!! PCD DID NOT SAVE FRESH !!! ===
       Map PCD did not write this run. BUT the bag INCLUDES /unilidar/cloud,
       so it is RECOVERABLE: replay <bag> through Point-LIO to regenerate the PCD.
A FRESH-fail is NOT a lost capture: the raw cloud is in the bag. Recovery sketch
(processing session, not mid-shoot): launch Point-LIO, ros2 bag play the capture,
Ctrl-C after playback -> scans.pcd regenerates; copy it out timestamped.

### STEP 8 — THE ARTIFACTS (what a run leaves behind)
    ~/Desktop/fusioncap_HHMMSS/              ROS2 bag: 4 topics, incl. raw cloud
    ~/Desktop/fusioncap_HHMMSS_scans.pcd     the map, timestamped copy
    ~/point_lio_ws/src/point_lio_ros2/PCD/scans.pcd   fixed-name ORIGINAL —
        the NEXT run will overwrite this one; the timestamped Desktop copy is
        the permanent record. (The overwrite behavior is why the copy exists.)
    /tmp/pointlio_capture.log, /tmp/bag_capture.log   run logs (tmp = volatile)
Matching HHMMSS stamps tie bag to PCD forever. Transfer off-Jetson for
processing; the PCD alone is enough for geometry work, the bag is required for
texture (images + poses).

### STEP 9 — VERIFY LIKE IT MATTERS
The SUCCESS block already verified freshness + printed size. Belt-and-braces:
    ls -lh ~/Desktop/fusioncap_*
Expect the bag directory and a multi-MB PCD. A 0-byte anything = treat the run
as failed, keep the bag, investigate.

═══════════════════════════════════════════════════════════════════════════
## 5. THE REFERENCE RUN — fusioncap_083911, 2026-08-24, COMPLETE RECORD
═══════════════════════════════════════════════════════════════════════════
### 5a. The cold test (safety proven first)
Icon clicked with Start Rig DOWN -> pre-flight printed the abort -> clean exit,
nothing created. The gate works.

### 5b. The hot run — actual terminal transcript (verbatim):
    not found: "/home/fasterbybaxter/ros2_ws/install/fast_calib/share/fast_calib/local_setup.bash"
    === Pre-flight: checking /unilidar/cloud is publishing (Start Rig must be up) ===
        sensor OK.
    === Clean slate: clearing any orphaned rviz2 / pointlio_mapping ===
    === Launching Point-LIO (with RViz reference view). Hold rig DEAD STILL for IMU init... ===
    --- Point-LIO init (from log) ---
    [pointlio_mapping-1] [INFO] [1787578757.270987341] [laserMapping]: IMU Initializing: 100.0 %
    ---------------------------------
    === Recording all 4 topics (incl. /unilidar/cloud) -> /home/fasterbybaxter/Desktop/fusioncap_083911 ===
    === CAPTURE NOW. Press Ctrl-C ONCE when done. ===
    ^C
    === STOP 1/4: stopping the bag (flush to disk) ===
    === STOP 2/4: clean SIGINT to Point-LIO group; WAITING for PCD save ===
    === STOP 3/4: verifying the PCD saved FRESH ===
    === STOP 4/4: SUCCESS ===
       BAG  [ok]  /home/fasterbybaxter/Desktop/fusioncap_083911
       PCD  [ok]  /home/fasterbybaxter/Desktop/fusioncap_083911_scans.pcd
             size: 11M
    Done. Press Enter to close this window...
Observed alongside: EXACTLY ONE RVIZ (operator-confirmed).

### 5c. The cloud — every measurement (sandbox inspection of the PCD):
PCD HEADER (verbatim):
    # .PCD v0.7 - Point Cloud Data file format
    VERSION 0.7
    FIELDS x y z intensity normal_x normal_y normal_z curvature
    SIZE 4 4 4 4 4 4 4 4
    TYPE F F F F F F F F
    COUNT 1 1 1 1 1 1 1 1
    WIDTH 334030
    HEIGHT 1
    VIEWPOINT 0 0 0 1 0 0 0
    POINTS 334030
    DATA binary
MEASUREMENTS:
    Points:            334,030
    File size:         11 MB (binary, 8 float32 fields/point)
    Extent:            X 8.19 m   Y 5.20 m   Z 3.53 m
    Bounding box:      min [-8.07, -2.59, -1.41]   max [+0.12, +2.61, +2.12]
    Dist-from-centroid: median 1.97 m | 95th pct 2.87 m | max 6.06 m
    Far-outlier tail:  6,777 points beyond 95th+2sigma = 2.03% of cloud
INTERPRETATION (verified against reality by the operator):
    - Main room: coherent ~4.5 x 5 x 2.1 m box — straight walls, sharp corners,
      flat ceiling, furniture mass. NO rotation collapse (the old RTAB failure
      signature is absent). Point-LIO tracked truly.
    - The X reach to -8m: REAL GEOMETRY — the NEIGHBOR'S HOUSE, captured THROUGH
      THE WINDOW GLASS at 5-8m and placed correctly in the room's frame. Glass
      is a portal, not a wall, to this instrument. This is the barn shot in
      embryo: interior + true exterior context in one dimensionally-honest
      capture.
    - The 2.03% far tail: MIXED — part real through-glass geometry (KEEP), part
      stray displaced tufts (REMOVE). CARVED CONSEQUENCE: pre-mesh cleanup must
      judge CLUSTER COHERENCE (is it a connected surface?), NEVER plain distance
      — film sets legitimately span 2m-100m, and tonight the "outlier" was the
      establishing shot. (Historical: long captures showed ~7% displaced
      clusters; this short clean capture shows 2% — capture discipline shrinks
      the problem at the source.)
    - Scan-line striping visible in renders = the L2's normal sparse pattern =
      the ~10.9x non-uniform spacing = WHY the mesher is trimmed Poisson.
    - NO RGB IN THIS FILE (fields are geometry+intensity+normals). Color lives
      in the bag (/image_raw + poses) and joins at the TEXTURE step. Expected.

### 5d. Operator verdict (recorded):
    "This is actually a great success. This is as close to the real image as can
    be imagined." — 2026-08-24, on first sight of the rendered views.

═══════════════════════════════════════════════════════════════════════════
## 6. THE GUARDS — WHAT PROTECTS YOU, AND THE SCAR EACH ONE COVERS
═══════════════════════════════════════════════════════════════════════════
Every guard exists because something bled. Do not "simplify" them away.
| Guard | The scar it covers |
|---|---|
| Single-instance lock (atomic mkdir, EXIT-trap release) | Double-clicked icon killed a live capture mid-run + spawned a second RViz (the double-RViz bug). Stale lock: rmdir /tmp/point_lio_capture.lock |
| Pre-flight sensor check (5s timeout) | Empty bags recorded against a dead driver; "captures" with nothing in them. |
| Clean slate (post-lock pkill of orphans) | Orphaned RViz from a crashed run doubling GPU/CPU load on an 8GB Jetson. |
| Process-group SIGINT (setsid + kill -INT -- -PGID) | SIGINT dying at the launch wrapper; pointlio_mapping never ran its save handler; PCD never written. |
| Shutdown ORDER: bag -> Point-LIO -> wait -> verify | Reversed/raced shutdowns losing either the bag tail or the PCD save. The order is load-bearing. |
| Fresh-mtime proof (before/after stat) | Silently "succeeding" by reading a PREVIOUS run's scans.pcd (fixed-name overwrite trap). |
| Timestamped Desktop copy | Point-LIO overwrites PCD/scans.pcd every run; un-copied captures were destroyed by the next run. |
| Bag records /unilidar/cloud | A failed PCD save used to mean a lost capture. Now: replay the bag -> regenerate. A capture is never lost. |
| Ctrl-C ignored during shutdown (trap '' INT TERM) | An impatient second Ctrl-C corrupting the save sequence. |
| "Press Enter to close" pauses | Icon-spawned terminals vanishing before the result could be read. |

═══════════════════════════════════════════════════════════════════════════
## 7. RESTORE FROM ZERO + TRANSFER RULES (version is part of the method)
═══════════════════════════════════════════════════════════════════════════
Both components live in rig-files (github.com/BaxterBstupid/rig-files, branch
main). Full restore on a blank Jetson:
    wget -O ~/point_lio_capture.sh "https://raw.githubusercontent.com/BaxterBstupid/rig-files/main/point_lio_capture.sh"
    chmod +x ~/point_lio_capture.sh
    grep -c "SINGLE-INSTANCE LOCK" ~/point_lio_capture.sh     # MUST print 2
    ls -la ~/point_lio_capture.sh                              # MUST be 5828 bytes
    wget -O ~/Desktop/PointLIOCapture.desktop "https://raw.githubusercontent.com/BaxterBstupid/rig-files/main/PointLIOCapture_desktop.txt"
    chmod +x ~/Desktop/PointLIOCapture.desktop
    ls -la ~/Desktop/PointLIOCapture.desktop                   # MUST be 275 bytes
    cat ~/Desktop/PointLIOCapture.desktop                      # MUST show 8 lines
TRANSFER RULES (each is a scar):
1. NEVER paste multi-line files through remote-desktop clipboards (mangles
   newlines/quotes). Files travel: chat -> download -> repo -> wget. Tiny files
   (the 8-line .desktop) may be typed via cat-heredoc directly on the Jetson.
2. .desktop files travel the repo AS .txt (browsers mangle the extension);
   wget -O renames on arrival.
3. A FAILED wget -O leaves a 0-BYTE FILE with the correct name. After EVERY
   wget: ls -la the target. Never trust a filename.
4. After ANY upload to the repo: confirm the file appears in the repo's web
   file list BEFORE closing the tab, then verify the raw URL answers (a 404 on
   wget means the upload didn't land — happened 2026-08-23).
5. VERSION CHECK ALWAYS: right name + wrong contents is the worst failure mode
   because it looks like success. The grep-count IS the version check.

═══════════════════════════════════════════════════════════════════════════
## 8. WHERE A CAPTURE GOES NEXT (context: the pipeline this feeds)
═══════════════════════════════════════════════════════════════════════════
1. OFF-JETSON: copy fusioncap_HHMMSS/ + _scans.pcd to the processing machine /
   cloud. The Jetson's 8GB cannot run the deliverable mesher.
2. GEOMETRY TRACK (points-for-truth): PCD -> outlier cleanup (COHERENCE-based,
   never distance) -> export ASCII .xyz-RGB or .las (NOT .ply — Unreal's LiDAR
   plugin format table is .xyz/.pts/.txt/.las/.laz/.e57; verified against UE5.8
   docs 2026-08-23) -> Unreal LiDAR Point Cloud plugin -> 1UU = 1cm -> verify a
   tape-measured dimension -> walk the scan.
3. TEXTURE TRACK (mesh-for-light): bag -> pointlio_pose_matcher.py (BAG-TIME
   matching, never header stamps) -> trimmed-Poisson mesh (depth 9, ~5% trim,
   >8GB RAM) -> per-shot multi-view texture (pointlio_to_texture.py) -> delight
   -> PBR -> Unreal relight. Or the RealityScan road: bag frames + cloud into
   RealityScan (2.1+ imports SLAM data), fused mesh via its hybrid pipeline ->
   UE Photogrammetry Importer.
4. THE BAR: sub-deliverable results have ALWAYS traced to a compromised INPUT,
   never the pipeline. This method exists to make the input clean. Bright +
   multi-view + dead-still init + this tool = the preconditions, all at once.

═══════════════════════════════════════════════════════════════════════════
## 9. OPEN THREADS REGISTERED AGAINST THIS METHOD (small, honest, tracked)
═══════════════════════════════════════════════════════════════════════════
- fast_calib sourcing warning at launch: benign noise; clean up the stale
  workspace reference someday or build fast_calib. Breadcrumb kept on purpose.
- Live double-click lock test: design-proven + cold-proven + one-RViz observed
  hot; the deliberate mid-capture double-click has not yet been performed. Do it
  casually during any future run; the second window must refuse.
- Odom-cutoff history (7P): older captures cut odom at ~5.5s (frozen sensor
  timestamps vs Jetson clock, no RTC battery). The reference run initialized and
  captured cleanly; watch any future capture for early odom silence; the
  LiDAR_IMU_Init temporal-offset idea is the banked fix if it returns.
- Heat: L2 is heat-sensitive; this method prefers short windows. No thermal
  instrumentation yet — operator judgment stands in.

═══════════════════════════════════════════════════════════════════════════
## 10. THE STONE CLAUSE
═══════════════════════════════════════════════════════════════════════════
This document is the method. The Master (operator-controlled, currently 18.1)
is the project's memory; this file is the capture procedure's single source of
truth, stored in FOUR independent places: rig-files (repo), the Jetson (~/),
the operator's email, and the chat-delivered original. If practice must diverge
from this document, the DOCUMENT is edited first — deliberately, with the
change dated and reasoned — and re-propagated to all four places. Silent drift
is the disease this project already survived once. Never again.

(End of THE CAPTURE METHOD — unabridged. 2026-08-24.)
