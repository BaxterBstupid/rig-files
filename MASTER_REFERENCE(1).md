# MASTER REFERENCE — LiDAR-Camera Capture Rig
### THE authoritative lookup. Scan, don't read. Update values IN PLACE at session end.
Last updated: 2026-08-17 (session: framework + RTAB scoping)

> This is the TOP document. Narrative history lives in PLAN_NEXT_SESSION.md (archived
> below this in priority). When a value changes, edit it HERE in place — don't append.
> Every entry carries PROVENANCE (vetted? when? where?) so nothing is trusted blindly.

═══════════════════════════════════════════════════════════════════════════
## 0. START HERE — COLD-READER ONBOARDING (read this first every new session)
═══════════════════════════════════════════════════════════════════════════
WHAT THIS PROJECT IS: a handheld capture rig that 3D-maps rooms/spaces for film-set
predictive lighting. Hardware: NVIDIA Jetson Orin Nano (small Linux computer, ROS2
Humble) + Unitree L2 LiDAR (spinning laser scanner, gives 3D point clouds + has a
built-in IMU motion sensor) + an Arducam B0578 camera (for colour, USB). Goal chain:
LiDAR+camera → calibrated fusion → RTAB-Map SLAM (builds a 3D map while you move) →
textured mesh → Unreal Engine relighting. The user assembles/operates the physical rig
and runs ALL machine commands (the assistant has a separate Linux sandbox and CANNOT
touch the Jetson — it reasons, writes code/docs, and analyzes data the user pastes/uploads).

WORKING STYLE (critical, the user insists on this): ONE STEP AT A TIME, proven before
moving on. NO menus of overlapping commands. COLD PREP before any "hot window" (LiDAR on)
because the L2 is heat-sensitive and every rig-minute costs. When the user asks a question,
answer THAT question. Be honest — this project's whole history is about catching CONFIDENT
WRONG ANSWERS, so never fake certainty; say what's proven vs assumed.

FILE TRANSFER TO/FROM JETSON: via GitHub repo github.com/BaxterBstupid/rig-files (public).
Assistant delivers a file → user uploads to repo → on Jetson: wget -O ~/FILE
"https://raw.githubusercontent.com/BaxterBstupid/rig-files/main/FILE". This MASTER_REFERENCE
lives in that repo too; user pastes its raw URL at session start so the assistant can fetch
current state. (Direct chat uploads sometimes come through blank — if so, the file is still
on disk at /mnt/user-data/uploads/ and the assistant can read it with a tool.)

CURRENT STATE IN ONE PARAGRAPH (as of 2026-08-18): Intrinsics ✅, extrinsic ✅ (both
calibrated + vetted), fusion node ✅ (colour lands on geometry when static). RTAB-Map is
installed + healthy and HAS BUILT ITS FIRST 3D MAP (LiDAR-only, high quality, 16mm
precision) — this is the big recent milestone. Temporal calibration (tau, the camera-LiDAR
time offset) is NOT solved but only matters for COLOUR during motion, NOT for LiDAR geometry.
IMU-into-odometry attempted+paused (TF issue, see 7C) — not needed for good maps. CAMERA
COLOUR is in progress (see 7D): two methods (Way A = pre-coloured cloud, Way B = RTAB
colours at export); Way A is one step from working (colour proven to survive into RTAB,
blocked only by a missing 'time' field), Way B is ~90% cold-prepped. MAJOR STRATEGIC RESULT this session: the pipeline ENDPOINT is now decided — a PHOTOREAL
RELIGHTABLE TEXTURED MESH (mesh-for-light + registered points-for-truth, "#3 synthesis"),
produced via the professional VFX pipeline (LiDAR geometry + camera-texture reprojection ->
delight -> PBR -> offline render). See sections 7E (the decision + why) and 7F (the 6-stage
pipeline + concrete SOFTWARE options: RealityScan / Agisoft De-Lighter / Blender). Per-point
colour (Way A/B) is downgraded to preview-only — the FULL PHOTOS are the texture source, not
per-point cloud colour. NEXT: the rig's job is crisp GEOMETRY + registered PHOTOS; downstream
is the mesh/delighting/render pipeline in 7F. Colour Way A fix (7D) remains available but is
no longer the priority. Camera upgrade (to a hardware-triggered model that kills tau) is planned —
see 7B for the if/then branch.

>>> NEXT SESSION STARTS HERE: Item 2 — COLD-PREP CAMERA COLOUR integration.
   Cold research (no rig): how rtabmap_sync's `rgbd_sync` node fuses the mono B0578
   image (/image_raw) + LiDAR cloud into a coloured RGBD input for RTAB-Map; the exact
   additions to lidar3d.launch.py (the `rgbd_image_topic` arg feeds rtabmap; needs
   camera_info with the vetted intrinsics + the extrinsic TF camera↔lidar); then a
   prepped one-shot bench attempt. Goal: COLOURED maps (currently geometry-only).
   Note: colour-on-motion is limited by unsolved tau (fine for slow captures; trigger
   camera fixes it later, see 7B). See also section 7B step 3.

HOW TO READ THIS DOC: sections 1-6 are lookup tables (hardware, calibration values, nodes,
files, data, gotchas). Section 7 = stage dashboard. 7B = camera-branch plan. 7C = IMU
detailed status. 8 = session log. Narrative history is in PLAN_NEXT_SESSION.md.

═══════════════════════════════════════════════════════════════════════════
## 1. HARDWARE FACTS
═══════════════════════════════════════════════════════════════════════════

### LiDAR — Unitree L2
| Fact | Value | Notes |
|---|---|---|
| Interface | UART + Ethernet only | NO GPIO/PPS/sync pin (can't hardware-trigger) |
| IP | 192.168.1.62 (rig at .2) | wired ethernet |
| Cloud topic | `/unilidar/cloud` | ~12 Hz, ~5,392 pts/single-scan |
| IMU topic | `/unilidar/imu` | 251 Hz, stable |
| Cloud frame | `unilidar_lidar` | from launch.py cloud_frame |
| IMU frame | `unilidar_imu` | from launch.py imu_frame |
| Cloud fields | x,y,z,intensity,ring,time | per-point `time` = 0..0.083s within scan |
| Scan period | 83.3 ms (12 Hz) | +/- 1.6ms, textbook-clean stamping |
| Spin-up | ~10-15 s | DON'T check topics before this — false "silent fail" |
| Mount | rotated 90° to level since Aug 10 | baked into all calibration; DO NOT change |
| Heat | HEAT-SENSITIVE | keep OFF except brief hot windows |
| Surface returns | ~73-75% solid | why hole-detection failed; edges/planes OK |
| Optical origin | bottom mounting surface (mechanical) | +5.4cm dome-tip->origin |

### Camera — Arducam B0578 (CURRENT)
| Fact | Value | Notes |
|---|---|---|
| Sensor | OG02B10, 2.3MP global shutter | 1/2.6", 3µm pixels |
| Interface | USB 2.0 UVC, B4B-ZR 4-pin JST | plug-and-play, no driver |
| Image topic | `/image_raw` | 1920x1200, MJPEG; delivered ~11-15fps |
| Compressed | `/camera/image_raw/compressed` | exists; ~10x smaller |
| Framerates @ 1920x1200 | **30 / 60 / 80 only** | NO 5/10/15fps at full res (v4l2 verified) |
| Framerates lower-res | 1280x720@30/60/90, 960x600@100 | option for throwaway tau bag |
| External trigger | **NO** | USB2 board doesn't break out trigger pin |
| FOV | 110°(D) 98°(H) 75°(V) | M12 mount, ~2.8mm EFL |
| Verify before edit | `v4l2-ctl -d /dev/video0 --list-formats-ext` | ALWAYS check mode is supported |

### Compute — Jetson Orin Nano
| Fact | Value | Notes |
|---|---|---|
| OS/ROS | Ubuntu, ROS2 **Humble** | user: fasterbybaxter, host: fasterbybaxter-desktop |
| Storage | 256GB SD card | ~40-90 MB/s sustained write (dropout bottleneck) |
| GPIO | can do PPS/trigger (JP6) | for FUTURE hardware-trigger camera |
| Display (field) | Waveshare 7" HDMI touch 1024x600 | eventual no-keyboard deployment |

### Rig geometry (LOCKED)
- Camera ABOVE LiDAR, close vertical baseline, parallel/forward aim.
- Cheese-plate rigid mount installed. DO NOT move — extrinsic binds to this geometry.
- Extrinsic R~85-90° comes from the L2's 90°-to-level mounting (internal frame rotated),
  NOT the camera pointing away.

═══════════════════════════════════════════════════════════════════════════
## 2. CALIBRATION VALUES (current, with provenance)
═══════════════════════════════════════════════════════════════════════════

### INTRINSICS — VETTED, TRUSTWORTHY
| Param | Value |
|---|---|
| File | `~/Desktop/calib_intrinsics_20260813.yaml` (OpenCV FileStorage) |
| fx, fy | 848.759, 849.231 (fy/fx=1.0006 ✓) |
| cx, cy | 921.00, 565.96 |
| distortion | [-0.014979, -0.013547, -0.001997, 0.000698, 0.003842] Brown-Conrady |
| RMS | 0.297 px |
| Coverage | 88% radial, 9/9 cells, 21 frames |
| Model | Brown confirmed (fisheye rejected at 157px) |
| Provenance | session 6, 2026-08-13. Triple-vet PASS. SOLID. |
| **STALE-K TELL** | good cx=**921**. If a tool shows cx=**1032** → STALE, refuse. |

### EXTRINSIC — VETTED, VISUALLY VERIFIED
| Param | Value |
|---|---|
| File | `~/Desktop/extrinsic_20260816.yaml` (1066 bytes, load-verified) |
| R | 85.54° (4-pose normals-Kabsch) |
| t | [0.018, -0.054, -0.160] m, \|t\|=0.169m |
| Method | plane-NORMAL (rotation) + CENTROID (translation) |
| paired intrinsics | calib_intrinsics_20260813.yaml |
| Provenance | session 8, visual verdict PASS (colour on geometry). SOLID. |
| Note | edge/hole methods SHELVED (normals+centroids wins on our sparse L2) |

### TEMPORAL (tau) — NOT SOLVED (blocked on clean capture)
| Param | Value |
|---|---|
| Best estimate | ~+150-200ms (LiDAR stamp LAGS camera), NOT tightly localized |
| Correction rule | SUBTRACT \|tau\| from LiDAR timestamps (sign nailed) |
| Blocker | recorder DROPOUTS (SD too slow at full-res 30fps → ~40% dropped) |
| Method | velocity cross-correlation (position road + IMU road), textbook |
| Status | method+tools triple-vetted; RESULT pending clean lower-res bag OR trigger camera |
| Key gate | peak width <100ms AND halves agree <30ms AND visual overlay |
| Note | LiDAR ICP odometry means MAP GEOMETRY doesn't need tau; tau only affects COLOUR |

═══════════════════════════════════════════════════════════════════════════
## 3. NODES, TOPICS & LAUNCH
═══════════════════════════════════════════════════════════════════════════

### Rig startup
| Item | Value |
|---|---|
| Start | `~/rig_start.sh` (LiDAR + camera + fusion nodes; supervises via `wait`) |
| Camera line | GSCAM_CONFIG line 74, framerate=30/1 (baseline; .bak_fps backup exists) |
| Stop | 'Stop Rig' icon |
| Gotcha | wait ~15s for L2 spin-up before trusting topic checks |

### Live nodes
| Node | Topic out | Notes |
|---|---|---|
| colorized_fusion_node.py | `/fusion/colorized_cloud` | loads intrinsics+extrinsic YAML, stale-K guard (refuses cx≥960); ~15Hz |
| overlay_check_node.py | `/fusion/overlay_image` | diagnostic; accumulation version (25 scans) for rqt |

### RTAB-Map — INSTALLED & HEALTHY (no install needed)
| Item | Value |
|---|---|
| Version | RTAB-Map 0.23.7, OpenCV 4.5.4 (matches Python cv2 → no conflict) |
| Backend | PCL 1.12.1, g2o, GTSAM, TORO, OctoMap, libpointmatcher all ON |
| Template | `/opt/ros/humble/share/rtabmap_examples/launch/lidar3d.launch.py` |
| Odometry | ICP from L2 cloud (LiDAR-driven; map geometry independent of tau) |
| First-map cmd (draft) | `ros2 launch rtabmap_examples lidar3d.launch.py lidar_topic:=/unilidar/cloud frame_id:=unilidar_lidar imu_topic:=/unilidar/imu` |
| DB output | `~/.ros/rtabmap.db` |
| To settle before firing | voxel_size, deskewing on/off, TF base→lidar exists?, imu needs madgwick? |

═══════════════════════════════════════════════════════════════════════════
## 4. FILES & LOCATIONS
═══════════════════════════════════════════════════════════════════════════

### On the Jetson (~/)
| File | Purpose | Status |
|---|---|---|
| rig_start.sh | rig bringup | working (30fps baseline) |
| colorized_fusion_node.py | live colour fusion | deployed, live-verified |
| overlay_check_node.py | diagnostic overlay | deployed |
| accumulate_scans.py | densify (30 scans) | proven |
| calibrate_intrinsics.py | Stage-1 intrinsics | Jetson-only, re-validate for new cam |
| capture_coverage.py | Stage-1 coverage capture | Jetson-only |
| dump_curves_v4.py | tau extraction (per-point time) | on Jetson |
| ts_check2.py | timestamp-regularity check | on Jetson |
| ~/Desktop/calib_intrinsics_20260813.yaml | VETTED intrinsics | SOLID |
| ~/Desktop/extrinsic_20260816.yaml | VETTED extrinsic | SOLID |

### Sandbox / outputs (delivered)
| File | Purpose |
|---|---|
| MASTER_REFERENCE.md | THIS doc |
| PLAN_NEXT_SESSION.md | narrative history (archived-priority) |
| CALIBRATION_FRAMEWORK.md | triple-vetted 3-stage procedure |
| CAMERA_OPTIONS.md | upgrade options + pre-purchase checklist |
| PREP_COLOR_WAY_A.md | Way A colour steps + session result + fixes |
| PREP_COLOR_WAY_B.md | Way B colour prep (camera_info + TF + open item) |
| camera_info_publisher.py | publishes vetted intrinsics as CameraInfo (Way B), validated |
| extrinsic_pipeline.py, zhou_joint_solve.py, extract_board_edges.py | extrinsic tools (sandbox-validated) |
| dump_curves_v4.py, measure_tau.py, ts_check2.py | tau tools (sandbox-validated) |

### File transfer method (PERMANENT)
GitHub: **github.com/BaxterBstupid/rig-files** (public, user BaxterBstupid, branch main).
Flow: deliver to outputs → drag-drop to repo via github.com → on Jetson:
`wget -O ~/FILE "https://raw.githubusercontent.com/BaxterBstupid/rig-files/main/FILE"`
(429 rate-limit → wait 30s retry. `saved [NNNN]` confirms.)

═══════════════════════════════════════════════════════════════════════════
## 5. SAMPLES & DATA
═══════════════════════════════════════════════════════════════════════════

| Data | Location | Status |
|---|---|---|
| 4 dense extrinsic poses | Jetson ~/Desktop/extrinsic_final/ ; sandbox /home/claude/poses/ | pose_0..3, cloud+image, extrinsic solved+verified against these |
| milestone_map_20260818.db | ~/Desktop/ (5.1M) | FIRST RTAB LiDAR map. Re-export ply: rtabmap <path>. KEEP |
| tau_pan_v3 | ~/Desktop/ (2.8G) | best/freshest tau bag (0.7m, IMU, per-point time). KEEP |
| tau_pan_v2 | ~/Desktop/ (3.7G) | superseded (static-head). deletable |
| tau_curves_v3/v4.csv | extracted | small analysis outputs |
| calib_bigboard_20260813_102030 | Jetson | the 21-frame intrinsic set |
| board geometry | — | 815×1020mm, 4 holes 127mm, checkerboard 7×10 @ 33mm |
| big board | — | 10×7 inner corners @ 63.5mm (intrinsics target) |

═══════════════════════════════════════════════════════════════════════════
## 6. GOTCHAS & LANDMINES
═══════════════════════════════════════════════════════════════════════════
- **STALE K**: cx=1032 (old, bad) vs cx=921 (good). Live nodes guard cx≥960. Old K
  =856.21/926.52 lurks in backups + quarantined pnp scripts. NEVER recal from
  July-29 pnp_calibration images.
- **VERIFY HARDWARE BEFORE EDITING**: 5fps edit was textually correct but the camera
  can't do 5fps@full-res → silent fail, wasted hot window. Always v4l2 --list-formats-ext.
- **L2 SPIN-UP ~15s**: checking topics too early gives false "silent fail"/"no data".
- **RECORDER DROPOUTS**: full-res 30fps raw → SD can't keep up → ~40% dropped, long
  gaps. Fixes: lower-res bag / faster storage / compression (not for production).
- **PER-POINT TIME**: cloud has per-point `time` (0..83ms); using header-only adds
  motion-dependent ±83ms error. Use header + mean(board-point times).
- **PATTERN TRANSPOSITION** (7,10)vs(10,7): silent ~7% depth error. Assert vs tape.
- **TWO BOARDS SAME GRID**: hole-board 33mm vs big-board 63.5mm, both 7×10 → 2x depth
  error if wrong square size. Always pass square size explicitly.
- **NEVER reuse a capture filename** (fixed names silently destroy prior capture).
- **end captures with `ls -lh` on real path** (a "wrote" log ≠ file exists).
- **RViz cosmetic tilt**: room stands vertical because L2 mounted 90° — data is correct.

═══════════════════════════════════════════════════════════════════════════
## 7. STAGE STATUS (the one-glance dashboard)
═══════════════════════════════════════════════════════════════════════════
| Stage | Status |
|---|---|
| Intrinsics | ✅ DONE, vetted (88%, fy/fx 1.0006, RMS 0.297) |
| Rig geometry | ✅ LOCKED (camera above, cheese plate) |
| Extrinsic | ✅ DONE, visually verified (R 85.5°, \|t\|0.169m) |
| Fusion node (static) | ✅ live-verified (colour on geometry) |
| Temporal (tau) | ⏳ BLOCKED on clean capture (rough ~175ms known) |
| RTAB-Map install | ✅ DONE + healthy (surprise) |
| RTAB-Map first map | ✅ DONE 2026-08-18: LiDAR-only SLAM, map built+saved (milestone_map_20260818.db, 5.1MB, 387+ nodes). Quality HIGH (16mm precision). |
| RTAB-Map IMU odometry | ⏸ ATTEMPTED, PAUSED (missing static TF, see 7C). Not needed — LiDAR-only excellent. |
| RTAB-Map colour (Way A) | ⏳ 1 step from working: colour SURVIVES to RTAB, blocked by fusion node stripping 'time' field. Fix: deskewing:=false OR preserve time. See 7D. |
| RTAB-Map colour (Way B) | ⏳ cold prep ~90%: camera_info node + static TF built+validated; 1 open item (store rgb w/o depth). See 7D. NOTE: downgraded to preview — see 7E/7F. |
| PIPELINE ENDPOINT decided | ✅ Photoreal relightable TEXTURED MESH (#3: mesh-for-light + points-for-truth). See 7E. |
| VFX pipeline + software mapped | ✅ 6-stage pro pipeline + tools (RealityScan/Agisoft De-Lighter/Blender). See 7F. |
| Mesh melt fear tested | ✅ Poisson blobs (max 1556mm off) vs ball-pivoting honest (0mm) on our real cloud. Edge-preserving meshing avoids melt. See 7E. |
| Camera upgrade | ⬜ researching (trigger camera → kills tau) |
| Downstream (mesh/UE/relight) | ⬜ after first maps |

═══════════════════════════════════════════════════════════════════════════
## 7B. CAMERA INTEGRATION BRANCH (if/then — the plan forks on the camera)
═══════════════════════════════════════════════════════════════════════════
Color-on-geometry during MOTION needs tau handled. LiDAR geometry does NOT (stands
alone). So the camera plan forks:

### CURRENT STATE — using Arducam B0578 to REFINE THE APPROACH
The B0578 (USB2 UVC, NO hardware trigger) is the bench camera. Use it to build and
prove the COLOUR PIPELINE (rgbd_sync → project image onto cloud → export coloured
map). This plumbing is CAMERA-AGNOSTIC and transfers to any future camera.
  - DO: integrate B0578 for colour at the bench (proves pipeline, colours
    slow/careful captures well).
  - ACCEPT: moving-colour is only APPROXIMATE (software tau ~175ms, unsolved-precise).
  - DON'T: over-invest in perfecting B0578 moving-colour — it's replaced below.
  - Geometry maps (LiDAR-only) are already clean and need none of this.

### IF the new (triggered) camera ARRIVES → THEN switch approach:
Trigger camera (e.g. Arducam IMX900 USB3 or AR0234 MIPI — see CAMERA_OPTIONS.md)
ELIMINATES tau by construction (Jetson GPIO triggers exposure at a known instant).
When it arrives:
  1. VERIFY trigger + framerate coexist for the exact model (email Arducam; trigger
     rate BECOMES framerate; confirm below-free-run works). See CAMERA_OPTIONS.md.
  2. RE-CALIBRATE via CALIBRATION_FRAMEWORK.md: new intrinsics (Stage 1) + new
     extrinsic (Stage 2). Camera-agnostic framework — re-run, don't re-invent.
  3. WIRE Jetson-GPIO trigger → camera trigger pin. tau ≈ 0 by construction.
     (Build+sandbox the trigger PAIRING/verify logic — camera-independent — but
     defer the pulse-generation code until the model's trigger spec is known.)
  4. VERIFY tau≈0 with the existing velocity-xcorr tool (should return ~0) AND the
     motion overlay (colour tracks board through motion).
  5. The COLOUR PIPELINE built with the B0578 CARRIES OVER unchanged — just swap the
     camera + new YAMLs. Now moving-colour is CLEAN (no software tau needed).
  => Net: B0578 work is NOT wasted — it proves the pipeline; the trigger camera
     finishes moving-colour.

### Bench-refinement order (where camera fits):
  1. IMU into odometry (no camera)  2. Density/accumulation (no camera)
  3. B0578 colour integration (proves pipeline)  4. Waveshare touch UI (wraps it)
  5. Mobilize + walk (geometry + approximate colour)  6. Trigger camera → clean colour

═══════════════════════════════════════════════════════════════════════════
## 7C. IMU INTEGRATION — DETAILED STATUS (attempted 2026-08-18, PAUSED, not solved)
═══════════════════════════════════════════════════════════════════════════
FOR A COLD READER: this documents an attempt to add the LiDAR's built-in IMU to the
RTAB-Map odometry, why it failed, and exactly how to fix it next time. Nothing here is
required for basic mapping — LiDAR-ONLY mapping WORKS and is the proven baseline.

### WHY WE WANTED THE IMU
RTAB-Map builds maps two ways at once: (1) ODOMETRY = tracking how the rig moves through
space (via ICP = Iterative Closest Point, matching consecutive LiDAR scans), and (2)
MAPPING = assembling those scans into a map. The IMU (a 251Hz motion sensor inside the
Unitree L2) can help the odometry track better through rotations/fast motion. It is an
ENHANCEMENT, not a requirement.

### WHAT WE CONFIRMED WORKS (cold-checkable facts)
- `ros2 pkg list | grep madgwick` → `imu_filter_madgwick` IS installed (a filter that
  computes orientation from raw IMU rates; turned out we didn't need it — see below).
- The L2 IMU (`/unilidar/imu`, frame `unilidar_imu`, ~249Hz) PUBLISHES REAL ORIENTATION
  directly. Checked via `ros2 topic echo /unilidar/imu --once`: the `orientation`
  quaternion had live values (e.g. x0.704 y-0.024 z-0.707 w0.015) that CHANGED when the
  rig was tilted (tilt test: became x0.697 y-0.135 z-0.695 w-0.096). `orientation_covariance`
  first value was 0.0 (NOT -1), meaning orientation IS provided. So we did NOT need the
  madgwick filter — the IMU gives orientation itself. (This was "Branch A" in the prep.)
- `linear_acceleration x: 9.66` = gravity on the x-axis (makes sense: L2 mounted 90°, so
  gravity lands on x not z). Confirms the accelerometer is live/correct.

### WHAT FAILED, AND THE EXACT ERROR
Command tried (adds IMU to the working LiDAR-only launch):
    ros2 launch rtabmap_examples lidar3d.launch.py \
        lidar_topic:=/unilidar/cloud frame_id:=unilidar_lidar imu_topic:=/unilidar/imu
Result: repeated ERRORS, odometry aborts every update. Two linked errors:
  1. `"guess_from_tf" is true, but guess cannot be computed between frames
     "unilidar_lidar_stabilized" -> "unilidar_lidar". Aborting odometry update...`
  2. `Could not transform IMU msg from frame "unilidar_imu" to frame "unilidar_lidar",
     TF is not available ... (if TF between camera/lidar and the IMU is static, you can
     safely ignore this warning and set always_check_imu_tf to false).`

### ROOT CAUSE (traced through the launch file source — see lidar3d_launch_copy on Jetson)
Two problems, both about missing TF (coordinate-frame transforms):
  (a) NO STATIC TRANSFORM is published between `unilidar_lidar` and `unilidar_imu`. They
      are both inside the L2 unit at a fixed offset, but ROS was never told their spatial
      relationship, so it can't relate IMU data to LiDAR data.
  (b) When an IMU is supplied, the launch AUTO-CREATES a `unilidar_lidar_stabilized` frame
      (a gravity-levelled frame for "deskewing" = correcting motion distortion within a
      scan). It launches an `imu_to_tf` node to generate that frame and a `lidar_deskewing`
      node to use it. These hit a TF timing/extrapolation race at startup.

### WHAT WE TRIED AND LEARNED
- `deskewing:=false` (default is `true`): launched with NO red errors at first (the
  `lidar_deskewing` node is skipped). BUT the `unilidar_lidar_stabilized` frame is STILL
  created regardless of deskewing (code: `if not fixed_frame_id and imu_used: fixed_frame_id
  = frame_id + "_stabilized"`), and odometry still uses it as `guess_frame_id`, so error #1
  returned. deskewing:=false alone is NOT a full fix.
- Also hit: TWO RTAB instances running at once (a prior launch didn't fully die). Symptom:
  topics publishing very fast / doubled. FIX: `pkill -f rtabmap; pkill -f icp_odometry`
  then `ros2 node list | grep -i rtabmap` to confirm clean BEFORE relaunching. ALWAYS
  ensure only one instance.

### THE FIX TO TRY NEXT TIME (cold-prep this properly before rig-on)
Primary fix = publish the missing static transform, in its own terminal, BEFORE launching:
    ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 unilidar_lidar unilidar_imu
  (args: x y z yaw pitch roll parent child. `0 0 0 0 0 0` = treat IMU as co-located with
   LiDAR — a fine approximation for a compact unit; refine with the L2's real IMU→LiDAR
   offset from Unitree docs if available.)
Then relaunch RTAB (single instance) with imu_topic and deskewing:=false.
If error #1 (`_stabilized`) persists, the deeper fix is to set the RTAB parameter
`always_check_imu_tf:=false` (the error message itself suggests this) and/or provide an
explicit `fixed_frame_id`. This needs cold research in the rtabmap_odom docs — it is a
TF-plumbing task deserving its own focused, cold-prepped session, NOT live improvisation.

### HONEST RECOMMENDATION
LiDAR-ONLY maps are already EXCELLENT (16mm precision). The IMU is a nice-to-have for
aggressive motion. DEFER it until (a) mobilization/fast-walking actually needs it, or
(b) a dedicated cold session with the static-TF + always_check_imu_tf fix fully prepped.
Do NOT let it block progress. Working baseline command (NO imu, proven):
    ros2 launch rtabmap_examples lidar3d.launch.py \
        lidar_topic:=/unilidar/cloud frame_id:=unilidar_lidar

═══════════════════════════════════════════════════════════════════════════
## 7D. CAMERA COLOUR INTEGRATION — DETAILED STATUS (in progress, 2026-08-18)
═══════════════════════════════════════════════════════════════════════════
FOR A COLD READER: the LiDAR maps are geometry-only (grey). This is the work to make
them COLOURED (needed downstream for film-set relighting). Two methods are being tried;
we build BOTH and compare by eye. Neither is finished yet. LiDAR-only maps still work
and need none of this.

### THE TWO METHODS
WAY A — feed a PRE-COLOURED cloud to RTAB-Map.
  Your colorized_fusion_node.py (runs in rig_start.sh) projects the camera onto the
  LiDAR cloud and publishes /fusion/colorized_cloud (fields: x,y,z,rgb). Point RTAB-Map
  at THAT instead of raw /unilidar/cloud. If RTAB keeps the colour → coloured map.
WAY B — let RTAB-Map colour it itself at export.
  RTAB records raw LiDAR + camera images during mapping, then its export-dialog "Camera
  projection" paints the assembled cloud from the stored images using the calibration.

### WAY A — TESTED 2026-08-18, ONE STEP FROM WORKING
  RAN it. /fusion/colorized_cloud publishes ~12Hz, rgb field CONFIRMED present.
  Launched: ros2 launch rtabmap_examples lidar3d.launch.py \
      lidar_topic:=/fusion/colorized_cloud frame_id:=unilidar_lidar
  RESULT: odometry ABORTED. Error: "Input cloud doesn't have t/time/stamps/timestamp
  field! Input cloud has these fields: x y z rgb ... Failed to deskew input cloud."
  DIAGNOSIS (key):
    - COLOUR SURVIVES to RTAB's input (error itself shows "x y z rgb"). Good - the
      thing we feared (RTAB dropping colour) did NOT happen at the input stage.
    - Blocker is UNRELATED to colour: RTAB DESKEWING needs a per-point 'time' field.
      Raw /unilidar/cloud HAS x,y,z,intensity,ring,time. But colorized_fusion_node.py
      OUTPUTS ONLY x,y,z,rgb - it STRIPS the 'time' field. So deskew fails, odom aborts.
    - Did not test the fix before rig shutdown.
  TWO FIXES (next session):
    FIX 1 (quick): add deskewing:=false (no IMU = don't need deskew anyway):
      pkill -f rtabmap; pkill -f icp_odometry   # single instance first
      ros2 launch rtabmap_examples lidar3d.launch.py \
        lidar_topic:=/fusion/colorized_cloud frame_id:=unilidar_lidar deskewing:=false
    FIX 2 (better, cold-preppable): edit colorized_fusion_node.py to PRESERVE the
      per-point 'time' field (output x,y,z,rgb,time) → true drop-in, works WITH deskew.
  => Way A is ONE small step from a coloured map. Full detail in PREP_COLOR_WAY_A.md.

### WAY B — COLD PREP ~90% DONE (2 of 3 pieces built + validated)
  Needs, during capture: raw cloud + camera image + a camera_info TOPIC + a camera↔lidar
  TF. Then colour at export via "Camera projection".
  PIECE 1 (DONE): camera_info_publisher.py - loads vetted intrinsics
    (calib_intrinsics_20260813.yaml), publishes sensor_msgs/CameraInfo on
    /camera/camera_info stamped to match /image_raw. Sandbox-validated (cx=921.002,
    valid K/P/R/d, stale-K guard works). Transfer to Jetson ~/, run: python3 ~/camera_info_publisher.py
  PIECE 2 (DONE): static TF unilidar_lidar→camera_link, computed from
    extrinsic_20260816.yaml by INVERTING stored lidar→cam (round-trip verified 1e-16):
      ros2 run tf2_ros static_transform_publisher \
        --x -0.032192 --y -0.004570 --z 0.166238 \
        --qx 0.026326 --qy 0.070258 --qz 0.674869 --qw 0.734114 \
        --frame-id unilidar_lidar --child-frame-id camera_link
      (CHECK cold: ros2 topic echo /image_raw --field header.frame_id --once - the
       image's frame_id must MATCH --child-frame-id; adjust one to agree.)
  PIECE 3 (OPEN): exact rtabmap params to STORE rgb images WITHOUT depth on a scan-cloud
    map (standard launch wants a depth image we don't have). One more cold research step.
  QUALITY CAVEAT (from a Velodyne+camera project that did this): sparse lidar clouds
    colour THINLY ("not enough RGB pixels"). Our single scans ~5,400 pts are sparse →
    Way B colour may need DENSE/accumulated clouds to look good. The by-eye compare shows it.
  Full detail in PREP_COLOR_WAY_B.md.

### COMPARE PLAN: build both, export color_wayA.ply + color_wayB.ply, judge BY EYE
  (+ Claude confirms the rgb field survived in each file). Keep whichever lands colour
  correctly on geometry and looks better.

═══════════════════════════════════════════════════════════════════════════
## 7E. THE PIPELINE ENDPOINT DECISION — PHOTOREAL RELIGHTABLE MESH (session, 2026-08-18)
═══════════════════════════════════════════════════════════════════════════
FOR A COLD READER: this section is the STRATEGIC BACKBONE — it defines what the whole
project is ultimately FOR and what the final deliverable is. Everything else (LiDAR SLAM,
calibration, colour work) is upstream of this. Read this to understand the destination.

### WHAT THE PROJECT ACTUALLY PRODUCES (the goal, stated precisely by the operator)
NOT a personal reference/previs. The deliverable is CLIENT-FACING, PROFESSIONAL images
with the operator's name on them. Requirements, all four mandatory:
  1. PHOTOREAL — indistinguishable from a photograph.
  2. 3D — a real navigable/re-angleable scene, not a flat photo.
  3. MANIPULATABLE — relightable (day->night, place your own lights) + re-cameraable.
  4. PREDICTIVELY ACCURATE — light behaves as it will on the real shoot (this is the
     point: scout/plan a real location's lighting before the shoot).
Operator's answers that pin the architecture: quality target = PHOTOREAL (indistinguishable);
who manipulates = JUST THE OPERATOR, producing STILLS (not real-time, not client-interactive);
effort tolerance = HEAVY art pass per hero shot is FINE.

### THE REFERENCE TOOL: Set.A.Light 3D (what "good" looks like to the operator)
Set.A.Light 3D (elixxier) is a PHYSICS-BASED lighting PRE-VISUALISATION simulator for
photographers/filmmakers. You place lights in a virtual 3D room and it predicts —
physically correctly — every shadow/highlight/reflection, so "it works in reality just
like in the sim." It even has a built-in "Day-for-Night" feature. BUT its rooms are
GENERIC kit-bashed approximations from a library. THE PROJECT'S CORE VALUE = replace the
generic room with a METRICALLY ACCURATE LiDAR SCAN OF THE REAL LOCATION you'll shoot on.
=> "Set.A.Light, but the set is the real scanned location." (Open Q, not yet researched:
   can Set.A.Light import custom meshes? If yes, scanned mesh could feed it directly;
   if no, Unreal/Blender is the destination. Decides the back half.)

### WHY THE ENDPOINT IS A TEXTURED MESH (settled, from first principles + research)
Operator's deciding principle: "Lighting always interacts with surfaces." Physical light
prediction REQUIRES SURFACES. Therefore the captured location MUST become a mesh (surfaces),
not stay a point cloud (points don't interact with light) and not a Gaussian Splat.
Contrast of the three representations, evaluated for THIS use case (relightable, Unreal):
  - POINT CLOUD: imports natively to Unreal (LiDAR Point Cloud plugin; wants XYZ+RGB, 1UU=
    1cm so metres convert clean — our format already fits). GREAT for reference/measurement/
    layout. But points aren't surfaces -> NO true predictive relighting. Reference layer only.
  - GAUSSIAN SPLATTING (3DGS): photoreal + real-time, RISING in film/VP. BUT bakes lighting
    IN — relightable-GS is research-only (Relightable 3DG NeurIPS'23, LumiGauss WACV'25),
    NOT in any commercial DCC as of 2026. Splats also don't participate in Unreal LUMEN GI;
    only shadow-proxy hacks (Volinga). GS is for displaying captured-as-lit scenes, i.e.
    the OPPOSITE of relighting. OFF THE PATH for our goal (revisit in 6-12mo as it matures).
  - TEXTURED MESH: the ONLY one with surfaces light interacts with -> the endpoint.
    Editable, measurable, Unreal/Lumen-native. Inherits the LiDAR's 16mm accuracy.
GS geometric accuracy alone ~8cm (needs LiDAR anchor); mesh inherits LiDAR 16mm. Confirmed
by literature + the operator's physics principle. THE ENDPOINT IS A TEXTURED MESH.

### THE "MELTED MESH" FEAR — REAL BUT SOLVABLE (tested cold on our own data)
Operator's valid worry (from a PolyCam example, IMG-5727): mesh-textured scans often look
MELTED — bloated blobs, rounded edges, surfaces dissolving. WHY: PolyCam uses PHOTOGRAMMETRY
(guesses geometry from photos -> fails on blank surfaces) + POISSON meshing (fills gaps with
smooth invented surface). We TESTED meshing on our REAL milestone cloud (cloud.ply, 181k pts,
Open3D):
  - POISSON depth 8/10: BLOBS. Vertex-to-real-point median 25mm but 95th pct 273mm, MAX
    1556mm = inventing surface 1.5m from any measured point = the melt, on OUR data.
  - BALL-PIVOTING: vertices ARE the real points (max 0mm) = NO blobbing, edge-preserving,
    but leaves holes where LiDAR didn't sample.
Literature CONFIRMS: Poisson smooths/rounds sharp edges + is robust to noise but invents in
gaps; Ball-Pivoting/Alpha-shapes are geometrically precise (stay on real points) but hole-y
and noise-sensitive. => OUR geometry is LiDAR-MEASURED (16mm), not photogrammetry-guessed,
so the melt is AVOIDABLE by choosing EDGE-PRESERVING meshing (ball-pivoting / trimmed-Poisson),
NOT default Poisson. The fear was valid but it's a MESHING-PARAMETER problem, not a dealbreaker.
CRITICAL because predictive lighting: a melted wall predicts light WRONG. Mesh honesty = 
prediction validity. (rendered evidence: outputs/mesh_comparison.png)

### CHOSEN ARCHITECTURE: #3 SYNTHESIS — MESH-FOR-LIGHT + POINTS-FOR-TRUTH
Operator chose: keep BOTH representations registered in the same frame:
  - TEXTURED MESH = the working/lighting model (surfaces light interacts with).
  - RAW LiDAR POINT CLOUD = kept as METRIC GROUND-TRUTH to verify the mesh never lied.
Both derive from the SAME capture -> automatically registered (same origin/coords). The mesh
does the lighting job; the points are the incorruptible geometric record to check it against.
Fits a PREDICTIVE/METRIC tool (must be trustable). Matches pro practice (VFX ships LiDAR
points ALONGSIDE the appearance asset for verification). Cost: two assets to carry (Unreal
handles both natively). The points don't relight — they're truth/reference/measurement.

═══════════════════════════════════════════════════════════════════════════
## 7F. THE PROFESSIONAL VFX PIPELINE + SOFTWARE OPTIONS (research, 2026-08-18)
═══════════════════════════════════════════════════════════════════════════
FOR A COLD READER: this is HOW the pros turn LiDAR+camera into a photoreal relightable
asset, and the concrete software to use. Our exact hybrid (LiDAR geometry + camera texture)
is a DOCUMENTED, SUPPORTED professional workflow — not experimental. We are most of the way
to the INPUT side of it already (our rig + calibration are exactly what it needs).

### THE 6-STAGE PIPELINE (every VFX house doing photoreal relightable capture uses this)
  1. CAPTURE — LiDAR (geometry) + camera photos (appearance). == OUR RIG.
  2. RECONSTRUCT — merge into a textured mesh (LiDAR geometry + photo texture).
  3. RETOPOLOGISE — high-poly scan -> clean lower-poly mesh with good UVs (art pass).
  4. DELIGHT — *** THE KEY STEP *** remove baked-in lighting/shadows from the photos to get
     flat "albedo". THIS is what makes it RELIGHTABLE. A photo has sun/shadow baked in; if
     you relight without removing it, the old + new lighting fight. Delighting strips the
     original so a day->night relight is physically correct. (This was the missing concept.)
  5. AUTHOR PBR MATERIALS — albedo + roughness + normal + metalness maps = surfaces that
     respond correctly to new light. This is where "indistinguishable from a photo" is won.
  6. RELIGHT & RENDER — place lights, render photoreal. OFFLINE renderer for stills (we don't
     need real-time -> can use Blender Cycles / path-tracer = higher photoreal ceiling).

### WHY OUR RIG FITS: camera REPROJECTION (the piece our calibration enables)
Standard photogrammetry guesses geometry AND texture from photos (the melt). OUR approach:
geometry from LiDAR (measured), photos used ONLY for texture, applied by CAMERA REPROJECTION
— because we KNOW each camera's exact pose (our intrinsics+extrinsic calibration!), we project
photos onto the LiDAR mesh from those known positions. OUR CALIBRATION WORK IS EXACTLY THE
INPUT REPROJECTION NEEDS. (Blender does camera projection well; RealityScan does it natively.)

### SOFTWARE OPTIONS — RECONSTRUCTION / TEXTURING
  - RealityScan (formerly RealityCapture, by Epic Games) — *** PRIMARY CANDIDATE ***
    FREE for most users. PURPOSE-BUILT for our hybrid: "seamlessly blends photogrammetry with
    laser-scan (LiDAR) inputs — photoreal textures from photos + precise depth from scans."
    Natively: registers, filters, colours, textures, MESHES LiDAR, and re-textures LiDAR scans
    USING IMAGES. Takes our formats directly (LAS/LAZ, E57, PLY, CSV, XYZ, PTS — our cloud is
    .ply). Unreal-native (Epic). Caveat: default meshing can be Poisson-ish -> WATCH THE MELT,
    trim aggressively / use classes for selective meshing.
  - Agisoft Metashape (Pro, paid) — mature LiDAR+photo hybrid; has a built-in delighter.
  - Blender (manual camera reprojection) — FREE, most control, most labour; our calibration
    drives the projection exactly. Good for the honest-meshing purist path.
  - RTAB-Map export --texture — FREE, we already have it; BUT basic, Poisson-based, no
    delighting, low photoreal ceiling. Preview-grade only, not the endpoint.

### SOFTWARE OPTIONS — DELIGHTING (the relightable-maker; Stage 4)
  - Agisoft De-Lighter — FREE standalone, purpose-built: removes baked-in lighting from
    photogrammetry texture maps, leaving them ready for re-lighting. *** THE obvious tool. ***
  - Unity De-Lighting Tool — free, needs extra maps.
  - Substance Painter (manual) — most control, most work.

### SOFTWARE OPTIONS — FINAL RENDER (photoreal stills)
  - Blender Cycles — FREE, offline, photoreal, full art-pass control. BEST FIT for
    "stills + heavy effort OK". Recommended primary.
  - Unreal (Lumen / Path-Tracer) — Unreal-native; path-tracer gives photoreal stills too;
    real-time-ish. Good if staying in the Epic/RealityScan ecosystem.

### THREE COHERENT ADOPTION OPTIONS (all share the SAME front half = our rig)
  OPTION A — "RealityScan-centric" (RECOMMENDED START): rig -> RealityScan merges LiDAR
    geometry + photo texture into a mesh -> Agisoft De-Lighter strips lighting -> Blender/
    Unreal for PBR + relight + render. Least reinvention, free, Unreal-native, proven path.
    Fastest concept validation. Risk: RealityScan meshing melt (trim hard).
  OPTION B — "Blender-centric, full control": rig -> mesh LiDAR HONESTLY (Open3D ball-
    pivoting/trimmed, already tested on our data) -> Blender camera-projects photos from our
    calibrated poses -> delight -> PBR -> Cycles. Max control, avoids black-box meshing,
    honours the #3 truth principle. Cost: most manual labour. Purist path if A's meshing melts.
  OPTION C — "Hybrid: RealityScan geometry-lock + Blender art pass": RealityScan registers
    photos to LiDAR + initial texture -> export to Blender for the hero-shot art pass (clean
    mesh, delight, PBR, render). Automation + final control. Likely where pros land. 2 tools.

### RECOMMENDATION + THE DECIDING TEST
Start OPTION A (RealityScan): free, purpose-built, Unreal-native, fastest to validate the
whole concept. Graduate to OPTION C (add Blender art pass) for hero shots. OPTION B if
RealityScan's meshing disappoints on our geometry. The DELIGHTING step (Agisoft De-Lighter,
free) is the conceptual key that makes day->night physically correct — put it on the radar.
THE ONE THING THAT DECIDES A vs B/C: does RealityScan's meshing keep our LiDAR's 16mm
crispness or does it blob? Testable next. If crisp -> A/C win on effort; if blobs -> B's
honest meshing (proven on our data) becomes necessary.

### WHAT THIS MEANS FOR THE RIG (important reframe)
The rig's per-point COLOUR quality barely matters now. The FULL-RES PHOTOS are the texture
source (via reprojection in the art pass), NOT the per-point cloud colour. So the sparse
"colour dots" limitation of Way A/B is IRRELEVANT to the endpoint. The rig's real job:
CRISP GEOMETRY (LiDAR) + REGISTERED REFERENCE PHOTOS (calibrated camera). Both of which we
have or have scoped. Per-point colour (Way A/B) is downgraded to a quick preview only.
OPEN QUESTION (not yet answered): does the operator already work in a 3D DCC (Blender/Maya/
C4D)? Decides whether to target "clean data into Blender" specifically or stay tool-agnostic.

═══════════════════════════════════════════════════════════════════════════
## 8. SESSION UPDATE LOG (append one line per session; values above stay current)
═══════════════════════════════════════════════════════════════════════════
- 2026-08-17: Built framework + camera options. Found camera framerate limit (30/60/80
  @full-res), hardware-sync needs new camera (L2+B0578 can't). RTAB-Map found already
  installed+healthy. lidar3d.launch.py template + frames identified. Next: LiDAR-only first map.
- 2026-08-18: RTAB-Map FIRST MAP achieved. LiDAR-only SLAM via lidar3d.launch.py
  (lidar_topic=/unilidar/cloud frame_id=unilidar_lidar, no IMU/camera). Map built live
  (387+ nodes, graph-optimized), saved milestone_map_20260818.db (5.1MB). Stutter=Jetson
  load (harmless). ply export didn't land - re-export cold from .db next session. MILESTONE.
- 2026-08-18 (cont): Analyzed first map (cloud.ply, 181,508 pts, exported from .db).
  QUALITY VERDICT: HIGH. Sees to ~8m (median range 1.67m). ~52% points form clean
  planes (35% walls + 17% floor/ceiling) = structured, not noise. Dominant plane
  thickness 16.3mm 1-sigma = AT SENSOR LIMIT (L2 spec ~1-3cm), NO drift/smear blur.
  LESSON: rig barely translated (1.44m path = pan-in-place). Geometry excellent but
  is ~one-vantage panorama. NEXT MAP: WALK A PATH (traverse space) for full spatial
  map + real loop closures. LiDAR-only geometry needs no tau/camera - stands alone.
- 2026-08-18 (cont): Added section 7B CAMERA INTEGRATION BRANCH (if/then): B0578 now
  refines the colour pipeline; IF trigger camera arrives THEN re-calibrate+wire trigger,
  pipeline carries over, moving-colour becomes clean. Also noted: walking = mobilization
  detour (mount+power+Waveshare touch UI), do bench refinement FIRST.
- 2026-08-18 (cont): IMU-into-odometry PREPPED cold (PREP_IMU_INTEGRATION.md).
  imu_filter_madgwick confirmed INSTALLED. Decision tree ready: echo /unilidar/imu
  orientation_covariance[0] == -1 → Branch B (madgwick filter → /imu/data), else
  Branch A (direct). Fallback = LiDAR-only (proven). Bench roadmap: IMU→density→B0578
  colour→Waveshare UI→mobilize. Mounts (Jetson/battery/Waveshare) fabricating in bg.
- 2026-08-18 (cont): IMU-into-odometry ATTEMPTED at bench, PAUSED (full detail in new
  section 7C). Confirmed L2 IMU publishes REAL live orientation (tilt-tested) → madgwick
  NOT needed. But adding imu_topic FAILS: missing static TF between unilidar_lidar and
  unilidar_imu, plus auto-created unilidar_lidar_stabilized frame causes 'guess_from_tf'
  abort. deskewing:=false alone did NOT fix (stabilized frame still made). Also hit
  double-RTAB-instance (pkill -f rtabmap first). FIX prepped in 7C: publish static_transform
  unilidar_lidar→unilidar_imu (0 0 0 0 0 0), maybe always_check_imu_tf:=false. DEFERRED as
  its own cold task — LiDAR-only maps are excellent and need none of this. User wisely
  stopped when commands got ahead of understanding (rig hot). Clean baseline intact.
- 2026-08-18 (cont): Wrote full handoff detail (section 0 onboarding + 7C IMU detail)
  per user request for cold-reader completeness. NEXT SESSION = Item 2: cold-prep camera
  colour integration (rgbd_sync). Rig shut down clean. LiDAR-only baseline intact.
- 2026-08-18 (cont): CAMERA COLOUR work started (new section 7D). Two methods (Way A
  pre-coloured cloud, Way B RTAB export-projection). WAY A TESTED: colorized cloud
  publishes ~12Hz with rgb; colour SURVIVES into RTAB input (good); but odometry aborts
  because fusion node strips the per-point 'time' field deskewing needs. Fix = deskewing
  :=false OR preserve time in fusion node (both noted, untested - rig shut down). WAY B
  cold prep ~90%: built+validated camera_info_publisher.py (vetted K) and computed+verified
  the static TF from the extrinsic; 1 open item (store rgb w/o depth on scan map). Delivered
  PREP_COLOR_WAY_A.md, PREP_COLOR_WAY_B.md, camera_info_publisher.py. Heat kept low.
- 2026-08-18 (cont): MAJOR STRATEGIC session — decided the PIPELINE ENDPOINT. Established
  the deliverable is CLIENT-FACING PHOTOREAL relightable 3D stills (operator's professional
  name on them), heavy art pass OK, operator-manipulated. Reasoned from "light interacts with
  surfaces" -> endpoint is a TEXTURED MESH (not point cloud, not Gaussian Splatting — GS bakes
  lighting, can't relight, research-only + no Lumen). Chose #3 synthesis: mesh-for-light +
  registered LiDAR points-for-truth. TESTED meshing on real cloud.ply: Poisson BLOBS (vertex
  1556mm off real pts = the PolyCam melt) vs ball-pivoting HONEST (0mm, edge-preserving) —
  melt is a solvable meshing-param choice, our LiDAR geometry is sound. RESEARCHED the pro VFX
  pipeline (6 stages: capture->reconstruct->retopo->DELIGHT->PBR->render) — our LiDAR+camera
  hybrid is a DOCUMENTED supported workflow; RealityScan (free, Epic) is purpose-built for it;
  Agisoft De-Lighter (free) is the relightable-maker; Blender Cycles for photoreal stills.
  Delighting = the key concept (strips baked light so day->night is correct). Wrote sections
  7E (endpoint decision) + 7F (pipeline + software options + 3 adoption paths). Per-point
  colour downgraded to preview — full photos are the texture source. Also researched Set.A.Light
  (the operator's reference tool) + Unreal LiDAR plugin (native point-cloud import, our format
  fits). No rig/heat used — all analysis + research on existing data. Open Q: operator's DCC?
