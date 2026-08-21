[MASTER_REFERENCE(7).md](https://github.com/user-attachments/files/31285455/MASTER_REFERENCE.7.md)
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
blocked only by a missing 'time' field), Way B is ~90% cold-prepped. 2026-08-19 RESULT: colour pipeline PROVEN end-to-end - v3 fusion node deployed+verified,
RTAB runs clean on the colored cloud (no deskew abort), and colour SURVIVES into the saved
map (confirmed by direct DB inspection: 11 nodes, per-point packed RGB; assembled to 27,405
colored pts). BUT the per-point colour is sparse "dots", FAR from usable - it proves the
plumbing, not image quality. Usable/photoreal must come from TEXTURE (7E/7F), not per-point
colour — PROVEN 2026-08-19 by a texture probe (photoreal where geometry is clean; limiter
is now MESHING quality — trimmed Poisson fixes it, 92.5% coverage photoreal). The full
TEXTURING PIPELINE is now BUILT end-to-end (per_shot_texture.py + db_to_texture.py bridge)
and the IMAGE-SAVING CAPTURE is PROVEN ON THE RIG (rtab_capture_with_images.sh v2: 10/10
nodes with geometry+image+calib). Texturing method = PER-SHOT projection (not global-UV).
The 270-pan is now UNBLOCKED (needed image-saving, which works). See 7H for all of this. NOTE: the mesh-vs-Gaussian-splat choice is a FLAGGED RETURNABLE
FORK (section 7G) — we chose MESH (Plan A); if it fails, 7G holds Plan B (Gaussian Splatting)
ready to resume without re-deriving. Prior-session STRATEGIC RESULT: the pipeline ENDPOINT is decided — a PHOTOREAL
RELIGHTABLE TEXTURED MESH (mesh-for-light + registered points-for-truth, "#3 synthesis"),
produced via the professional VFX pipeline (LiDAR geometry + camera-texture reprojection ->
delight -> PBR -> offline render). See sections 7E (the decision + why) and 7F (the 6-stage
pipeline + concrete SOFTWARE options: RealityScan / Agisoft De-Lighter / Blender). Per-point
colour (Way A/B) is downgraded to preview-only — the FULL PHOTOS are the texture source, not
per-point cloud colour. NEXT: the rig's job is crisp GEOMETRY + registered PHOTOS; downstream
is the mesh/delighting/render pipeline in 7F. Colour Way A fix (7D) remains available but is
no longer the priority. Camera upgrade (to a hardware-triggered model that kills tau) is planned —
see 7B for the if/then branch.

>>> NEXT SESSION STARTS HERE: **PIVOT TO POINT-LIO** (decided 2026-08-20).
   The RTAB rotation bug is not fixed and won't be; the fix is Point-LIO (Unitree
   demonstrates clean L2 rotation-tracked maps). See 7K for full rationale + 7L for the
   step plan. Do the COLD-PREP items in 7L first (build plan, config values, extrinsic
   reformat) BEFORE any rig-on. One step at a time, proven before moving.

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
| RTAB-Map colour (Way A) | ✅ WORKS: v3 deployed+verified, colour survives full pipeline into map (proven via DB). Sparse 'dots' quality only - preview, not usable. See 7D. |
| RTAB-Map colour (Way B) | ⏸ NOT NEEDED for now: Way A proved colour-in-map works. Way B (camera_info+TF) reserved for texture/mesh path. See 7D/7F. |
| PIPELINE ENDPOINT decided | ✅ Photoreal relightable TEXTURED MESH (#3: mesh-for-light + points-for-truth). See 7E. |
| VFX pipeline + software mapped | ✅ 6-stage pro pipeline + tools (RealityScan/Agisoft De-Lighter/Blender). See 7F. |
| ⚠️ FORK: Mesh(A) vs Splat(B) | CHOSE MESH (Plan A). Flagged returnable decision in 7G. If mesh fails -> return to 7G for Plan B (Gaussian Splatting), held in reserve. |
| Texture probe (Plan A test) | ✅ 2026-08-19: texture works, photoreal where geometry clean (69% cov vs 2.6% per-point). Limiter = MESHING. See 7G. |
| Texturing method decided | ✅ PER-SHOT (local projection), not global-UV. Fits stills deliverable, avoids UV artist-hours. See 7H. |
| Per-shot texturing tool | ✅ BUILT+debugged (per_shot_texture.py): mesh + project image from pose + multi-view best-image-per-face. See 7H. |
| DB->texture bridge | ✅ BUILT+tested (db_to_texture.py): capture.db -> mesh -> multi-view texture, end to end. See 7H. |
| IMAGE-SAVING capture | ✅ PROVEN ON RIG 2026-08-19 (v2): 10/10 nodes with scan+image+calib. Full chain real. See 7H. |
| Trimmed Poisson (photoreal) | ✅ 92.5% coverage, photoreal — the mesh for texture. Ball-pivoting too holey. See 7H. |
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
  (a) *** CORRECTED 2026-08-20 (was: "NO static TF exists" — that was WRONG). ***
      The DRIVER DOES publish a lidar<->imu TF: reading the driver source
      (unitree_lidar_ros2.h ~L208) shows it broadcasts imu->cloud INSIDE the IMU callback,
      with the manufacturer transform. So a transform EXISTS — but it is (i) dynamic/
      in-callback rather than a clean static TF, (ii) delivered on an IMU path that is
      HALF-RATE (~250 of 500 Hz) and DROPPING messages (measured 2026-08-20), and (iii) one
      of the driver's sibling TF broadcasts has a SCRAMBLED QUATERNION (order bug, audit
      finding #1). So RTAB intermittently can't get the transform "at IMU msg time" ->
      "TF not available / extrapolation into the future" -> stabilized frame freezes.
      The problem is NOT absence of a TF; it is an UNRELIABLE one.
      *** DO NOT naively add a static TF assuming none exists — it may CONFLICT with the
      driver's existing broadcast (ROS-Answers q366927: a naive static TF BROKE other frames
      on an equivalent Ouster+RTAB setup). SEE THE TREE FIRST (view_frames), then decide. ***
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

### THE FIX TO TRY NEXT TIME (cold-prep this properly before rig-on)  [REVISED 2026-08-20]
The TF EXISTS but is unreliable (see root cause (a)). So the fix order is:
  STEP 0 — SEE THE TREE FIRST: `ros2 run tf2_tools view_frames` then `cat ~/frames.gv`.
    Determine whether lidar<->imu is present-but-stale, or double-published/conflicting.
    This decides which fix is correct and AVOIDS the conflict trap (q366927). Do NOT skip.
  FIX 1 (cheapest, try first) — `always_check_imu_tf:=false` on the launch. The RTAB warning
    itself suggests this; our stamps are valid host-time and the transform is ~static, so
    re-checking it per IMU message is what throws the extrapolation error. One argument.
  FIX 2 (if a static TF is actually needed) — publish it with the CORRECT value, NOT zeros:
    ros2 run tf2_ros static_transform_publisher \
        -0.007698 -0.014655 0.00667 0 0 0 unilidar_lidar unilidar_imu
    (authoritative lidar->imu transform, unilidar_sdk2 README + glim#248; identity rotation.
     *** C2 CORRECTION: the old note said "0 0 0 0 0 0 / co-located, fine approximation" —
     that was WRONG. Use the real offset above. ***)
    BUT only after STEP 0 confirms it won't conflict with the driver's existing broadcast;
    if it would, DISABLE the driver's in-callback TF first (or use FIX 1 instead).
  FIX 3 (fallback) — imu_filter_madgwick republishing a clean /rtabmap/imu at steady rate
    (canonical per RTAB author + depthai#1147); may also dodge the half-rate/timing issue.
Then relaunch RTAB (single instance) with imu_topic. Pass criterion: node-pose yaw spread
matches the physical pan (vs the ~8x under-count). This is a focused cold-prepped task, NOT
live improvisation.

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


### WAY A — RESOLVED + PIPELINE PROVEN END-TO-END (2026-08-19)
v3 fusion node (colorized_fusion_node_v3.py) was DEPLOYED to the Jetson (swapped in as
~/colorized_fusion_node.py; v2 backed up as .bak_v2) and VERIFIED on real data:
  - colored cloud /fusion/colorized_cloud publishes ~12.5Hz with fields x,y,z,rgb,TIME
    (the time field at offset 16 is the fix; last session it was ABSENT -> RTAB aborted).
  - RTAB launched on the colored cloud:
      ros2 launch rtabmap_examples lidar3d.launch.py \
        lidar_topic:=/fusion/colorized_cloud frame_id:=unilidar_lidar
    -> odometry RUNS CLEAN, NO deskew abort (Odom ratio ~0.5-0.75, std dev ~2cm/0.5deg,
    update ~0.02s). rtabmap node maps (local map grows). The deskew blocker is GONE.
  - Stationary ~30-45s capture saved: ~/Desktop/color_stationary_20260819.db (11 nodes).

COLOR SURVIVES THE FULL PIPELINE (proven by direct DB inspection, not just GUI):
  Opened the .db in the sandbox (SQLite). Each of the 11 nodes' scan blob is zlib-
  compressed float32 (N,4) = x,y,z + PACKED RGB. Reinterpreting channel-3 bits as uint32
  gives real per-point colors (e.g. R159 G165 B197 bluish-grey wall; R125 G135 B90 olive
  wood; R245 G247 B248 near-white). => colour flows camera->fusion->odometry->mapping->DB.
  Assembled all 11 scans into world frame via each Node's pose -> 27,405 colored points ->
  color_stationary_assembled.ply + color_map_render.png (in outputs).

GUI EXPORT QUIRK (worked around, important for cold reader): the standalone rtabmap GUI
  export threw "Cloud N not found in cache" and the 3D map view was empty. This is a known
  RTAB scan-cloud quirk (cache not auto-populated; Edit->Download all clouds is supposed to
  fix it but didn't fully here). NOT a data problem - the DB was intact. WORKAROUND that
  WORKS: read the colored scans DIRECTLY from the .db (SQLite -> zlib -> float32 (N,4) ->
  transform by Node.pose) and write the PLY ourselves. So we do NOT depend on the finicky
  GUI export. (Script pattern is in this session's sandbox work; can be re-derived from the
  DB schema: Data.scan blob per node, Node.pose = 12 float32 3x4 matrix.)

HONEST QUALITY VERDICT (operator + assistant agree): the colored cloud is FAR from usable.
  It is sparse "colour dots" (per-point colour samples ~3% of the image), dim, not
  photographic. This test proved the PLUMBING (colour survives the pipeline into a coherent
  map), NOT usable image quality. Per-point colour TOPS OUT short of usable no matter how
  many scans are stacked - density makes it thicker, never photographic. => usable/photoreal
  quality must come from TEXTURE (draping full camera images onto surfaces, all pixels), i.e.
  the mesh+texture path in 7E/7F, NOT from per-point colour. Per-point colour is a
  reference/preview layer only. Stop measuring "usable" against per-point renders.

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
## 7G. ⚠️ DECISION FORK — MESH (Plan A) vs GAUSSIAN SPLATTING (Plan B) ⚠️
═══════════════════════════════════════════════════════════════════════════
COLD READER: THIS IS A FLAGGED, RETURNABLE DECISION POINT. We stood at a fork and
CHOSE MESH (Plan A). If Plan A fails, DO NOT re-derive from scratch — return HERE, to
this exact reasoning and these exact circumstances, and pick up Plan B (Gaussian
Splatting) which is documented and waiting below. This section exists so a failure of
Plan A costs a PIVOT, not a re-investigation.

### THE FORK (what was decided, when, why)
Decided 2026-08-18/19. Two ways to turn the LiDAR+camera capture into a photoreal,
relightable, manipulatable 3D asset:
  PLAN A — TEXTURED MESH (CHOSEN): mesh the LiDAR geometry (edge-preserving, not
    Poisson), drape the camera images as TEXTURE (all pixels), assign PBR materials,
    relight fresh in Unreal/offline renderer. 
  PLAN B — GAUSSIAN SPLATTING (NOT CHOSEN, held in reserve): photoreal real-time
    scene from the same camera+LiDAR capture.

### WHY MESH WAS CHOSEN (the reasoning to re-examine if backtracking)
  1. OPERATOR'S DECIDING PRINCIPLE: "lighting always interacts with surfaces." Physical
     predictive relighting NEEDS surfaces -> mesh. Points/splats aren't surfaces.
  2. GS BAKES LIGHTING IN. Relightable-GS is research-only (Relightable 3DG NeurIPS'23,
     LumiGauss WACV'25), NOT in any commercial DCC as of 2026. GS also doesn't participate
     in Unreal LUMEN GI (only shadow-proxy hacks, Volinga). Our tool's whole job is
     RELIGHTING (day->night), which is exactly GS's weakest area.
  3. Mesh is editable/measurable, inherits LiDAR 16mm accuracy, Unreal-native.
  4. The "melted mesh" fear (PolyCam) was shown to be a SOLVABLE meshing-parameter problem
     (Poisson blobs vs ball-pivoting honest — tested on our data), not a dealbreaker.

### CIRCUMSTANCES AT THE FORK (so you can judge if they've changed on return)
  - Goal: CLIENT-FACING photoreal relightable STILLS (operator's professional name on them),
    heavy art pass OK, operator-manipulated, not real-time.
  - Reference tool: Set.A.Light (physics lighting previz). Precedent: Cine Tracer (Unreal
    cinematography sim) proves lighting-sim-on-Unreal is buildable.
  - As of the fork, GS relighting was immature. **RE-CHECK THIS ON RETURN** — GS relighting
    is moving fast; if commercial relightable-GS exists when you read this, Plan B's main
    disqualifier may be GONE. That single fact could flip the decision.

### WHAT WOULD TRIGGER BACKTRACKING TO PLAN B (define failure of Plan A now)
Flag Plan A as failing and RETURN HERE if:
  - meshing cannot produce clean enough surfaces for photoreal texture DESPITE reasonable
    effort (persistent melt/shred that tuning + density don't fix), OR
  - the mesh+texture+material+relight pipeline proves too labor-heavy per location to be
    viable as a product, OR
  - commercial relightable-GS + Unreal-Lumen-GS integration matures (re-check on return).

### PLAN A PROGRESS (evidence for/against, updated as we climb)
  2026-08-19 TEXTURE PROBE (encouraging FOR Plan A): meshed a real dense cloud (161k pts,
  ball-pivoting) + projected the full camera image as texture. Result: 69% frame coverage
  (vs 2.6% per-point) and WHERE GEOMETRY IS CLEAN IT LOOKS PHOTOREAL (framed painting, wall
  molding, wallpaper, checkerboard all crisp — see outputs/texture_probe.png). CONFIRMS
  texture is the right path for usable quality. LIMITER identified: MESHING quality — black
  "shredded" zones are meshing failures (ball-pivoting struggling), NOT texture failures.
  => Plan A's remaining risk is concentrated in MESHING. If meshing can't be cleaned up,
  that's the trigger to re-examine this fork. So far: promising, not proven.

### IF RETURNING TO PLAN B (Gaussian Splatting) — WHERE TO START
  - The SAME capture (LiDAR + calibrated camera + poses) feeds GS — NOTHING upstream wasted.
  - Research entry points recorded 2026-08-18 (see 7E/7F history): relightable-GS papers,
    Volinga (Unreal GS plugin), THE FUTURE 3D (does LiDAR points + GS hybrid for VP).
  - GS geometric accuracy alone ~8cm -> would still use our LiDAR as the geometry anchor
    (hybrid: GS appearance + LiDAR truth). That hybrid is the likely Plan B shape.
  - First Plan-B action: re-check commercial relightable-GS maturity; if viable, prototype
    a GS scene from one dense pose + images and test relighting in Unreal.

═══════════════════════════════════════════════════════════════════════════
## 7H. TEXTURING PIPELINE — BUILT + IMAGE-SAVING CAPTURE PROVEN (2026-08-19)
═══════════════════════════════════════════════════════════════════════════
COLD READER: this section is the big practical result of the 2026-08-19 session —
the per-shot texturing pipeline is BUILT end-to-end and the image-saving capture is
PROVEN on the rig. This is how the project gets from a capture to a photoreal textured
render. Endpoint context is 7E/7F; the mesh-vs-splat fork is 7G; this is the working
Plan-A texturing machinery.

### THE DECISION: PER-SHOT (LOCAL) TEXTURING, not global-UV texturing
Chosen 2026-08-19. Two ways to texture the mesh:
  - GLOBAL: one clean UV unwrap + bake all images into one texture set. Reusable from any
    angle, but LOTS of skilled-artist UV hours (hand-tuning seams/layout/texel density).
  - PER-SHOT (CHOSEN): project the real photos onto the mesh FROM their known camera
    poses, per hero viewpoint. Little/no manual UV work (the projection defines the
    mapping). Fits the deliverable (operator makes STILLS from chosen viewpoints, heavy
    art pass per shot OK). Downside: not one reusable asset — re-texture per shot.
  UV BRIEF (for the cold reader): "UV" = the map from 2D image pixels onto 3D surface.
  Global texturing's main cost is ARTIST HOURS hand-tuning UV layouts, NOT compute/render.
  Per-shot projection avoids most of that. Unreal/Lumen still needs TEXTURE UVs downstream
  but NOT lightmap UVs (Lumen is dynamic) — see 7F.

### THE TEXTURE PROBE — proved texture (not per-point colour) is the path (real data)
On a real dense cloud (dense_test, 161k pts, 6.9mm spacing, 3.3mm surface thickness):
  - per-point colour samples only ~2.6% of the image -> sparse dots, NOT usable (this is
    why the coloured cloud looked bad — per-point colour tops out short of usable).
  - TEXTURE (project the FULL image onto the meshed surface): 
      ball-pivoting mesh  -> 69% coverage but SHREDDED (holes) — non-uniform point
        spacing (10.9x variation) defeats fixed-radius ball-pivoting.
      TRIMMED POISSON mesh -> 92.5% coverage and PHOTOREAL where geometry is clean
        (framed painting, wall molding, wallpaper, checkerboard all crisp).
  => KEY RESULT: mesh+texture LOOKS PHOTOREAL. The limiter is MESHING quality, not colour.
     Trimmed Poisson (depth 9, trim ~5% low-density) is the mesh for texture (continuous
     surfaces). Ball-pivoting is honest but too holey for texture. Evidence images in
     outputs: texture_probe.png (ball-pivot, shredded), texture_probe_poisson.png (photoreal).
  HONEST LIMIT: single-image texture is photoreal NEAR the capture viewpoint; moving the
  view (parallax) smears surfaces the camera saw edge-on and leaves unseen areas black
  (per_shot_top.png shows this). => need MULTI-VIEW coverage — which the 270-pan provides.

### TOOLS BUILT THIS SESSION (all in outputs/, cold-tested)
  - per_shot_texture.py — the texturing tool: cloud -> trimmed-Poisson mesh (w/ statistical
    outlier removal) -> project image(s) from camera pose -> render from chosen viewpoint.
    Debugged: outlier removal (fixed a pose that meshed sparse from 5 stray far points),
    camera-visibility guard checks X AND Y, empty-cloud guard. Has MULTI-VIEW functions:
    compose_world_to_cam (world pose + extrinsic -> world->cam, math verified to 1e-16),
    best_image_per_face (picks best image per face by head-on angle + visibility).
    KNOWN LIMIT: pure-Python rasteriser is slow (~380k tris); fine for stills, a real
    offscreen renderer would be faster later.
  - db_to_texture.py — THE BRIDGE: reads a capture .db (SQLite) -> poses + scans (always)
    + images (when present) -> assembles world cloud -> mesh -> feeds per_shot_texture's
    multi-view selection. Tested end-to-end on color_stationary db (no-image path) AND
    with injected real images (texture path, 98% faces textured). Handles both cases.
  - camera_info_publisher.py (on Jetson ~/) — publishes vetted intrinsics on
    /camera/camera_info stamped to match /image_raw. Rig-tested, works.
  - rtab_capture.sh — basic PROVEN capture launcher (geometry+colour only, NO images).
  - rtab_capture_with_images.sh v2 — image-saving capture (see below). On Jetson ~/.

### IMAGE-SAVING CAPTURE — *** PROVEN ON THE RIG 2026-08-19 *** (the milestone)
The capture that saves camera IMAGES into the rtabmap db alongside geometry+poses, so the
db is a self-contained textureable asset. This is what per-shot texturing + the pan need.
PIPELINE (one script, rtab_capture_with_images.sh v2, runs from ONE terminal):
  camera_info_publisher + static TF(unilidar_lidar->camera_frame) + rgb_sync
  (/image_raw + /camera/camera_info -> /rgbd_image) + lidar3d.launch w/ rgbd_image_topic.
V1 FAILED (empty db, 0 nodes): rgb_sync never produced /rgbd_image. TWO bugs found:
  1. approx_sync with max_interval=0 didn't match -> FIX: exact sync (approx_sync:=false),
     since camera_info is stamped to EXACTLY match /image_raw.
  2. hardcoded frame_id "camera_link" was WRONG -> the real /image_raw frame is
     'camera_frame'. FIX: v2 DETECTS the frame_id from /image_raw at runtime.
V2 also GATES: if /rgbd_image isn't publishing it EXITS (prints logs) instead of launching
  RTAB into a doomed empty capture (v1's silent-failure trap). camera_info publish is also
  gated. v2 = 110 lines, on Jetson.
V2 RESULT (imgtest2.db, stationary test): 10 nodes, ALL 10 with SCAN + IMAGE (~560KB each,
  full-res) + CALIBRATION. COMPLETE textureable capture. The empty-capture failure is SOLVED.
  => the full chain is now real+proven: rig -> rtab_capture_with_images.sh -> capture.db
     (geometry+images+poses+calib) -> db_to_texture.py -> textured mesh. Every link tested.

### THE 270 PAN (planned, now UNBLOCKED)
Purpose: texturing-COVERAGE capture — every surface photographed near head-on by some frame
(fixes the single-image parallax/smear limit). Plan: ONE smooth continuous ~270 deg sweep
over ~45s (~6 deg/s) — slow favours sharp images (no motion blur), dense LiDAR, easy
odometry; only heat favours fast. Smooth/continuous, no jerks. Erring slower if the live
image shows blur. GATED behind image-saving working — which is now PROVEN, so the pan is
unblocked. NOT yet done (still bench/stationary only). Next real hot window = the pan.
NOTE the earlier stationary pan (color_stationary) saved NO images (basic capture); the pan
must use rtab_capture_with_images.sh (v2) so images+poses are saved for texturing.

═══════════════════════════════════════════════════════════════════════════
## 7I. CAPTURE EXPERIMENT — B (stationary) vs A (moving), PARAMETERS + RESULTS
═══════════════════════════════════════════════════════════════════════════
COLD READER: this section defines a two-arm capture experiment and holds its
results. GOAL: capture the SAME space two ways — stationary (B) and moving (A) —
and COMPARE the textured output, to MEASURE the cost of the motion-timing limit
(the tau-limit, see 7B/7C). "Differing data for better forensics." Both feed the
per-shot texturing pipeline (7H: rtab_capture_with_images.sh v2 -> capture.db ->
db_to_texture.py -> textured mesh).

### WHY THIS EXPERIMENT (the reasoning, so it isn't lost)
The ~1s odometry latency + "image pose will not be synchronized with odometry"
warning (measured this session) are the tau-limit of the UN-TRIGGERED B0578 made
concrete (see 7B: colour-on-motion is tau-limited; fine for slow/stationary; the
trigger-camera fork fixes it later). So:
  - STATIONARY (B): no motion -> pose-lag is harmless -> CLEAN reference. Plays to
    the camera's actual strength. Already PROVEN (imgtest2.db, 10/10 nodes).
  - MOVING (A): inherits ~1s pose-lag -> at rotation speed this = a few degrees of
    image-to-pose misregistration. This is the tau cost we want to SEE/measure.
Comparing B (clean) vs A (motion) MEASURES the tau cost on real texturing output —
evidence for the trigger-camera-fork decision, not just theory.

### SHARED CONSTRAINTS
  - LiDAR uptime budget: 60s USABLE PER SAMPLE (spin-up ~15s is NOT counted).
  - Each capture = its own window, SEPARATE for heat (L2 heat-sensitive).
  - Capture tool: rtab_capture_with_images.sh v2 (gated, exact-sync, frame auto-
    detect, BUG3 cleanup trap). PROVEN on rig this session (stationary).
  - Same space, captures close in time (same scene/lighting; only method differs).
  - Verify db after each: nodes have BOTH pose AND image (the textureable check).

### ARM B — STATIONARY SET (clean reference) — PARAMETERS
  - 14 stop points, ~4s each (brief settle + ~30-scan accumulation per stop).
  - 60s usable total. Keep LiDAR spinning between stops; move briskly; hold still ~4s.
  - Each stop = one accumulate-and-save (posed image + dense cloud).
  - Proven method (stationary image-saving works) -> NO de-risk window needed.
  - EXPECTED: clean posed images, no motion misregistration; multi-view coverage
    from 14 viewpoints.

### ARM A — MOVING PAN (motion comparison) — PARAMETERS
  Staged: A-TEST first (de-risk), THEN A-FULL.
  A-TEST (own small window, ~15s usable): short slow turn (~45-90deg). GATE before
    A-FULL: (1) odometry holds under rotation (ratios sane, no drift/abort in log),
    (2) images SHARP (pull a frame, eyeball blur). If blur -> slow down / abort A.
  A-FULL — two forms; CHOSEN = A2 (out-and-back) for forensics:
    A1 single 270 sweep: 270deg over ~55s = ~4.9deg/s. (coverage-only; NOT chosen)
    A2 OUT-AND-BACK (CHOSEN): 135deg out (~30s) + 135deg back (~30s) = 60s, ~4.5deg/s
       each way. Gives BOTH:
         - tau SIGN-FLIP: motion-timing error shifts along direction of travel, so
           it flips sign out vs back -> confirms it's TIMING (not calibration) and
           brackets the true position.
         - RETURN-TO-START DRIFT: end pose should equal start pose (physically back
           at origin); the difference = accumulated odometry drift, measured directly.
  - EXPECTED: images misregistered by ~(1s x angular rate) = a few degrees; tau
    error visible + opposite-signed on the two legs; some odometry drift.

### RESULTS — B (stationary)   [ CAPTURED 2026-08-19 — TEXTURING PROVEN, but GEOMETRY ROTATION-CORRUPTED ]
  - db file: sampleB_191122.db (28 stops out-and-back, ~4s each; RTAB made 64 keyframes)
  - nodes total: 64 | with pose+image+calibration: 64/64 (ALL textureable)
  - pose spread: small translations (x16cm y38cm z19cm) = rotation-in-place, as expected
  - texturing coverage (db_to_texture.py multi-view): 99% faces (447901/450304),
    mean head-on 0.63. Assembled world cloud 159,439 pts -> mesh 450k tris.
    *** NOTE: 99% is coverage of a ROTATION-COLLAPSED mesh (world extent 13m tall) - i.e.
    faces got images, but the underlying geometry is corrupted. Coverage-of-a-bad-mesh. ***
  - VISUAL verdict: TEXTURING MATH is photoreal WHERE geometry is coherent (chandelier,
    framed portraits on walls, molding, pass-through appliances, patterned chairs, curtained
    window all read correctly - see sampleB_render.png / best_render.png). BUT the full-room
    reconstruction is BROKEN: half the room is missing/warped. NOT a clean deliverable.
    *** CORRECTION: this is NOT "the pipeline endpoint proven". Texturing is proven; GEOMETRY
    is rotation-corrupted. Do not cite sampleB as a clean success. See 7K + mesh_shape_views.png. ***
  - notes: render shown was ONE node's single sparse scan (2506 pts) meshed alone ->
    ragged black border is that single scan's mesh boundary, NOT a texture fault.
  - *** CRITICAL FINDING (user caught it): the MULTI-VIEW ASSEMBLY IS BROKEN. *** User
    panned across a whole side of the room but it's MISSING from the result. Cause:
    ODOMETRY UNDER-TRACKS ROTATION. DB pose yaw spread is only ~14.5deg across all 64
    nodes despite physically panning 90deg+. So the images are real but their POSES
    under-represent rotation ~8x -> far side of room collapses onto near side. The
    single-node render looked photoreal because ONE node is internally consistent; the
    CROSS-NODE assembly is wrong. So B (done as a stop-and-go PAN = rotation) is NOT a
    clean stationary capture — it hit the rotation-tracking failure. 99% "coverage" was
    misleading (images assigned, but to wrong poses). A truly stationary capture (hold
    still, physically relocate, hold still — minimal rotation-while-tracking) would be
    the real clean B. See 7J for the rotation-tracking diagnosis.

### RESULTS — A-TEST (moving de-risk)   [ TO FILL ]
  - odometry under rotation (ratios / any drift or abort?):
  - image sharpness (blurred? at what speed?):
  - GATE decision (proceed to A-full? / slow down? / abort?):

### RESULTS — A-FULL (out-and-back)   [ TO FILL ]
  - db file / date / actual sweep (deg each way, duration):
  - nodes total / with pose+image:
  - texturing coverage (%):
  - tau sign-flip observed? (error direction out vs back):
  - return-to-start drift (start pose vs end pose delta):
  - VISUAL verdict vs B (how much worse is motion?):
  - notes:

### COMPARISON / CONCLUSION   [ TO FILL after both ]
  - B vs A textured-result difference (the measured tau cost):
  - is A "good enough" for the slow regime, or does motion clearly hurt?:
  - implication for the trigger-camera fork (7B) priority:

═══════════════════════════════════════════════════════════════════════════
## 7J. ⚠️ ODOMETRY UNDER-TRACKS ROTATION — diagnosis (2026-08-19), NEXT: TF/deskew
═══════════════════════════════════════════════════════════════════════════
COLD READER: the moving/panning capture (Sample B done as a stop-and-go pan) revealed
that RTAB's LiDAR odometry SEVERELY UNDER-MEASURES ROTATION. Physical ~90deg+ pan ->
only ~14deg recorded in the node poses. This makes any ROTATING capture (incl. the
planned A pan) produce WRONG poses -> broken multi-view assembly (far side of room
collapses onto near side). MUST be fixed before A (moving) is viable. Stationary-only
captures (no rotation while tracking) are unaffected.

### EVIDENCE (from icp_odometry logs during the pan — multiple samples agree)
  - ratio 0.60-0.68 (HEALTHY — ICP finds good correspondences, not struggling)
  - rotational std dev ~0.007 rad (~0.4deg — ICP is CONFIDENT about its rotation est.)
  - delay ~0.5s (modest; NOT the ~1s of the image-test; not growing)
  - update time ~0.04-0.07s (fast compute)
  - NO "Lost"/reset/registration-failed messages
  => ICP is CONFIDENT but WRONG about rotation magnitude. Confident+wrong-magnitude on
     rotation = a GEOMETRIC/DESKEW problem, NOT compute, NOT matching, NOT latency.

### RULED OUT (important — don't chase these)
  - Fusion-node latency: delay only ~0.5s here + ICP healthy. Vectorizing the fusion
    node (its per-point Python loops ARE slow — benchmarked ~12x speedup available,
    40ms->3.5ms colorize) is a REAL but SEPARATE latency win; it does NOT fix rotation
    under-tracking. (We nearly fixed this wrong thing; the odometry sample redirected us.)
  - ICP registration failure: ratio healthy, confident, no resets. Not this.

### PRIME SUSPECTS (the actual cause — to confirm next session, mostly cold)
  1. SCAN DESKEW failing under rotation. The L2 sweeps points over ~40ms while rotating;
     correct deskew uses per-point 'time' + sensor motion to un-warp the sweep. If deskew
     is off/wrong, a rotating sweep is warped so consecutive scans look TOO SIMILAR ->
     ICP sees LESS rotation than occurred. Matches "confident but small" exactly.
  2. THE SPLIT TF TREE (appears in EVERY capture, likely the root):
     "Could not find a connection between 'icp_odom' and 'unilidar_lidar' ... two or more
     unconnected trees." Deskew needs the TF chain to know how the sensor moved during
     the sweep. Broken tree -> deskew can't compensate -> rotation under-measured.
     Our static TF (unilidar_lidar->camera_frame) is a SEPARATE branch not linked to the
     odom frame. LIKELY the two suspects are the SAME root: split tree breaks deskew.

### NEXT STEPS (next session — investigate BEFORE changing anything)
  1. [needs rig up] capture the TF tree: `ros2 run tf2_tools view_frames` (makes a PDF
     diagram) OR `ros2 topic echo /tf_static --once` + `/tf --once` -> SEE the disconnect.
  2. [cold] read lidar3d.launch: what odom_frame_id / base frame does icp_odometry use vs
     what RTAB expects (frame_id:=unilidar_lidar)? The mismatch is likely the split.
  3. [cold] confirm deskewing is actually ON and has time field + valid TF to work.
  4. Fix the TF tree so icp_odom connects to unilidar_lidar -> deskew works -> re-test a
     small rotation to confirm poses now track the true angle BEFORE re-attempting A.
  DEPTH-IMAGE WARNING ("sensor data doesn't have depth/right image") = COSMETIC
  (rtabmap_viz wants depth we don't have; RGB+scan is correct). Not related. Ignore.

### *** CONTROLLED TEST RESULT (2026-08-19): FUSION NODE RULED OUT ***
User's instinct: run PLAIN RTAB on raw /unilidar/cloud (no fusion node, no camera path,
no our colorized cloud) and pan — does vanilla RTAB track rotation? Result
(plainRTAB_200724.db, 45 nodes, ~90deg+ physical pan):
  yaw spread = 12.7deg  (colorized run was 14.5deg — ESSENTIALLY IDENTICAL)
  Same signature: confident, smooth, out-and-back shape, magnitude compressed ~7-8x.
=> THE FUSION NODE IS NOT THE CAUSE. Ruled out cleanly in one window. The rotation
   under-tracking is in RTAB / ICP-odometry / deskew / the L2 cloud itself — NOT anything
   we built. Big narrowing (eliminates the whole colorized-path branch).

### NARROWED SUSPECTS (post-controlled-test)
  1. L2 SPARSE NON-REPETITIVE CLOUD vs ICP: the L2 is a rosette scanner (~5,400 pts/scan,
     sparse, non-uniform). ICP on sparse non-repetitive scans can fail to CONSTRAIN
     ROTATION while still looking confident — not enough consistent frame-to-frame
     structure to pin the angle. This is a known weak spot of low-density LiDAR + ICP.
  2. RTAB deskew handling of the L2 cloud (time-field units / deskew assumption). Raw
     cloud has its native time field, so if deskew fails it's RTAB's handling, not us.
  3. => STRONGEST LEAD: IMU FUSION. The L2 has an onboard IMU (251Hz, see 7C, currently
     PAUSED/unsolved). ICP is bad at rotation from sparse scans; an IMU measures rotation
     DIRECTLY and well. Fusing IMU into odometry is the CLASSIC fix for exactly this
     symptom. The paused 7C IMU work is likely the real path to fixing the pan. NEXT
     SESSION should probably resume IMU integration with THIS as the concrete motivation.

### *** RE-WEIGHTED DIAGNOSIS (more log evidence, 2026-08-19 late) ***
More log detail changed the priority order. Key new observations:
  1. The split-tree warning fires EVERY cycle AND is tied to a specific failing call:
     "getMovingTransform() ... movement of unilidar_lidar according to fixed icp_odom ...
     not part of the same tree." RTAB is actively TRYING to compute the sensor's motion
     (needed for deskew + pose propagation) and FAILING because the tree is split. This
     is NOT cosmetic.
  2. The split tree appears in the PLAIN-RTAB run TOO (raw cloud, no fusion node, no our
     camera static TF). => the split is in the BASE lidar3d.launch frame config, NOT our
     static TF as previously assumed. CORRECTION to earlier note that blamed our TF.
  3. Loop closures rejected "Not enough features in images (old=0...)" — old node shows
     ZERO features => stored image data not usable for matching in the colorized run;
     consistent with the "image pose will not be synchronized with odometry" warnings.

REVISED SUSPECT ORDER (test the cheap one FIRST):
  A. [NEW TOP SUSPECT] SPLIT TF TREE in the base launch: icp_odom and unilidar_lidar are
     in separate trees, so RTAB can't compute unilidar_lidar's motion vs icp_odom ->
     breaks deskew / motion propagation -> rotation mis-tracked. This is a LAUNCH-CONFIG
     issue (present even in plain RTAB), plausibly fixable WITHOUT the IMU. TEST THIS FIRST:
       - get the TF tree (ros2 run tf2_tools view_frames while running) to SEE the two
         islands and what frame icp_odometry publishes odom against.
       - read lidar3d.launch: does icp_odometry publish odom_frame/base as unilidar_lidar,
         or a different frame that never connects? Fix so the chain is:
         icp_odom -> (odom) -> unilidar_lidar, one connected tree.
       - re-test a small rotation; if yaw now tracks the true angle, THIS was it.
  B. [STILL POSSIBLE] sparse L2 cloud limits ICP rotation -> IMU fusion (7C) needed.
     Only pursue if fixing the TF tree does NOT restore rotation tracking. IMU is the
     heavier fix; try the free TF-config fix first.

### VIZ OBSERVATION TASK (next session, free — no extra heat)
When re-running, SET UP THE VIEW BEFORE panning so you can watch the diagnosis live:
  - ZOOM OUT the rtabmap_viz 3D map panel before starting the pan (this session the
    window was too short to zoom — set it up first next time).
  - THE KEY THING TO WATCH: as you physically pan ~90deg, does the 3D MAP SWING ~90deg
    with you, or does it stay roughly FIXED while you turn? 
      map swings with you   -> rotation IS tracking live (problem only in saved poses)
      map stays put/barely moves -> you're WATCHING the rotation-under-track happen live
    This is the visual version of the pose-yaw-compression bug (7J). Costs no heat.
  - NOTE from this session: user saw LiDAR reacting to movement the whole time (data
    live/responsive, good) and the image/side panels "changed color but never produced
    an image." For the PLAIN-RTAB run that's expected (no camera fed). For a COLORIZED
    run the camera panel SHOULD show the room; "no image" there would corroborate the
    image-not-usable warnings (old=0 features, depth-image warnings). Confirm which panel
    behaviour goes with which run next time.

### *** ROOT CAUSE FOUND (2026-08-20, from the launch file itself) ***
Read lidar3d.launch.py frame/odom config directly. THE LAUNCH IS ARCHITECTED FOR A
LiDAR+IMU RIG, and we run it LiDAR-ONLY. That is the root cause of ALL the symptoms.
Key lines:
  - L90: 'deskewing': not fixed_frame_id and deskewing  # deskew path depends on fixed_frame_id
  - L57-63: fixed_frame_id is created as frame_id+"_stabilized" ONLY when imu_used.
    No IMU -> fixed_frame_id is EMPTY.
  - L91-92: 'odom_frame_id':'icp_odom', 'guess_frame_id': fixed_frame_id
    Empty fixed_frame_id -> guess_frame_id EMPTY -> ICP has NO ROTATION PRIOR (pure
    scan-to-scan, no motion guess) -> under-tracks rotation on the sparse L2 cloud.
  - L102: 'wait_imu_to_init' (IMU-centric init) — the whole design assumes an IMU.
MECHANISM (one cause, every symptom):
  no IMU -> no fixed/_stabilized frame -> (a) ICP gets no rotation guess -> confidently
  under-measures rotation (the ~8x yaw compression), AND (b) the _stabilized frame that
  would connect icp_odom to the unilidar_lidar chain is absent -> SPLIT TF TREE ->
  getMovingTransform() fails -> deskew/motion-propagation broken. The split tree and the
  rotation under-count are the SAME missing-IMU root, not two separate bugs.
=> THE FIX IS THE IMU (7C), and it is NOT a "fallback" — it is the piece THIS LAUNCH IS
   DESIGNED AROUND. The L2 has a 251Hz IMU already. Wiring it in should simultaneously:
   (1) give ICP its rotation prior -> rotation tracks; (2) create the _stabilized fixed
   frame -> TF tree connects -> deskew works -> getMovingTransform() succeeds.
   7C changes from "paused/maybe" to "THE concrete unblock for the pan."

### *** CORROBORATING EVIDENCE: same bug, DIFFERENT SLAM system (2026-08-20) ***
GLIM issue koide3/glim#248 (open, Jul 2025): a user with the SAME hardware — Unitree L2
on Jetson Orin — reports odometry showing ROTATION/MOVEMENT WHILE STATIONARY. Same
sensor, same compute platform, DIFFERENT SLAM stack (GLIM, not RTAB, and GLIM is IMU-
tightly-coupled). Key implications:
  - A DIFFERENT odometry system hits the SAME failure class on the L2 => the root cause
    is very likely UPSTREAM of the SLAM choice — in the L2's data feed (SDK/ROS2/IMU/
    timestamps/frames), NOT in our RTAB launch config. This SUPPORTS the operator's
    instinct that the bug is in the SDK->ROS2->IMU messaging chain, an accumulated-
    irregularity area.
  - The user HAD the IMU configured (GLIM uses it) + set T_lidar_imu, and STILL failed
    => "just wire in the IMU" may NOT be sufficient. Tempers the earlier "IMU fixes it"
    confidence. The problem may be deeper (timing/stamping/transform), which is exactly
    what an audit would surface.
  - "IMU data alone looks stable" per that user => raw IMU values probably OK; the fault
    is in how IMU+cloud are combined/timed/transformed.
  - ISSUE IS OPEN/UNRESOLVED — tells us it's a KNOWN real L2+Jetson problem, not a solved
    one. We may be genuinely in hard, known-difficult territory with this sensor.
  MANUFACTURER T_lidar_imu (from the issue, useful artifact — the lidar<->imu transform):
    T_lidar_imu = [-0.007698, -0.014655, 0.00667,  0, 0, 0, 1]
    (translation ~mm, ZERO rotation, identity quat). This is the unilidar_lidar<->
    unilidar_imu static transform — likely what we need to publish; note the SDK may NOT
    publish it automatically (part of the audit: does the driver emit this TF?).

### *** AUDIT FINDING #1 (2026-08-20): QUATERNION ORDER INCONSISTENCY in the L2 driver ***
Read the L2 driver IMU/TF publish code (unitree_lidar_ros2.h lines ~170-212). Findings:
  GOOD: the driver DOES publish imu->lidar TF (imu_frame -> cloud_frame) with the mfr
    transform (tx0.007698 ty0.014655 tz-0.00667, identity rot). So lidar<->imu ARE linked
    at the source. AND the IMU message carries a FULL ORIENTATION quaternion
    (imu.quaternion[...]) -> NO madgwick needed. (Resolves the earlier open question.)
  *** BUG — quaternion unpacked in TWO DIFFERENT ORDERS from the SAME array: ***
    IMU MESSAGE (lines 177-180):  orientation = (x,y,z,w) = quaternion[0],[1],[2],[3]
    TF BROADCAST (lines 196-199): rotation    = (x,y,z,w) = quaternion[1],[2],[3],[0]
       i.e. TF treats it as (w,x,y,z) with w=quaternion[0].
    THE SAME imu.quaternion[] IS UNPACKED AS [x,y,z,w] FOR THE MESSAGE BUT [w,x,y,z] FOR
    THE TF. They cannot both be right — one is WRONG. A swapped quaternion order is a
    classic driver bug that makes odometry CONFIDENTLY MIS-READ ROTATION — exactly our
    symptom AND exactly glim#248's cross-SLAM symptom. STRONG root-cause candidate.
  SECOND ODDITY: the driver publishes the LIVE IMU ORIENTATION AS A DYNAMIC TF
    (unilidar_imu_initial -> unilidar_imu, updated every msg) + invents an
    'unilidar_imu_initial' frame nothing else references. A live-orientation TF injected
    into the tree can FIGHT a SLAM's own orientation estimate and adds an orphan frame.
  *** RESOLVED (SDK check): the correct order is (x,y,z,w) = quaternion[0,1,2,3]. ***
    Proven by the SDK's OWN example.h (prints "quaternion (x,y,z,w) = [q0,q1,q2,q3]")
    AND README.md/README_CN.md (4 places each, all label it "(x, y, z, w)"). So:
      - IMU MESSAGE unpack (x=q0,y=q1,z=q2,w=q3) = CORRECT. The /unilidar/imu topic is
        fine — its orientation is right. (So a SLAM reading the TOPIC gets good orientation.)
      - TF BROADCAST unpack (x=q1,y=q2,z=q3,w=q0) = WRONG (it assumes w-first). The
        unilidar_imu_initial->unilidar_imu TF is SCRAMBLED — garbage rotation, published
        every IMU msg. Any pipeline consuming that TF branch gets corrupted orientation.
        This matches glim#248 (GLIM tightly uses the IMU TF -> scrambled rotation).
  IMPLICATION: if the IMU MESSAGE order is wrong, ANY SLAM using /unilidar/imu gets
    scrambled rotation (matches glim#248). If the TF order is wrong, the imu_initial->imu
    TF is mis-rotated. Either way this inconsistency is a real irregularity in the exact
    SDK->ROS2->IMU layer the operator suspected. THIS IS THE LEAD.

### TWO DISTINCT PROBLEMS NOW (don't conflate them)
  PROBLEM A (our RTAB runs so far): we ran lidar3d.launch LiDAR-ONLY, no IMU fed -> empty
    guess_frame_id -> ICP has no rotation prior -> under-tracks rotation from sparse L2
    scans. (7J root-cause section.) This is about NOT USING the IMU.
  PROBLEM B (the driver TF bug, found in audit): the driver's imu_initial->imu TF has a
    SCRAMBLED quaternion (wrong component order). This corrupts orientation for ANY pipeline
    that CONSUMES that TF branch (e.g. GLIM/glim#248). It's a LANDMINE for when we DO wire
    the IMU in.
  HONEST: Problem B is a PROVEN driver bug but may not be what broke OUR (IMU-less) runs —
    those are Problem A. The audit's value: we found B BEFORE naively wiring the IMU (which
    would have hit the scrambled TF and been baffling). Both likely need handling to make a
    working IMU-aided pan.
  THE GOOD NEWS: the /unilidar/imu TOPIC orientation is CORRECT (only the driver's TF is
    wrong). So feeding RTAB the IMU via imu_topic (not via that TF) should give a GOOD
    rotation prior. When wiring IMU: use the imu_topic, and DO NOT rely on / actively avoid
    the driver's broken imu_initial->imu TF (or patch the driver's 4 lines to (x,y,z,w)).

### AUDIT CONTEXT: Unitree LiDAR IMU handling is a KNOWN-WEAK AREA (issue survey)
Surveyed unitreerobotics/unilidar_sdk issues (26 open). Pattern strongly supports the
"SDK/IMU messaging is irregular" instinct — this is a recurring, under-maintained area:
  - #34 (Jan 2026, Go2 L1 via unitree_ros2 /utlidar/imu): IMU outputs CORRUPTED values —
    linear_acceleration ~ -2.9e+28 (garbage), orientation degenerate (x,y,z~1e-33, w~-0.998
    = essentially (0,0,0,w)). DIFFERENT lidar (L1) + DIFFERENT stack, so NOT proof our L2
    is corrupted — but shows Unitree LiDAR IMU data can be outright garbage. No Unitree
    reply. Note user also flags timestamp-sync problems using the robot's main IMU instead.
  - #21 (Dec 2024): user asks for the imu<->cloud transform because it's UNDOCUMENTED. No
    answer. (This is the transform we found in the driver with the scrambled-quat TF.)
  - #27 recalibrate IMU, #33 point/cloud time from packet — all open, IMU/timing themes.
  TAKEAWAY: our found quaternion-order inconsistency is one instance of a broader pattern
  of buggy/inconsistent IMU handling across Unitree LiDAR SDKs. Do NOT trust the IMU feed
  by assumption — VERIFY the live values before building on them.

### *** AUDIT FINDING #2 (2026-08-20): OUR IMU IS HEALTHY — verified live ***
Ran `ros2 topic echo /unilidar/imu --once` (rig up, held still + level). Values:
  orientation (x,y,z,w) = (0.7343, -0.0490, -0.6746, -0.0046), norm 0.998 = NORMALIZED,
    valid quaternion, real components (NOT degenerate like #34's ~1e-33 garbage).
  linear_acceleration = (9.650, -0.462, 0.612), magnitude 9.68 m/s^2 = GRAVITY. CLEAN.
    (Contrast #34's ~ -2.9e+28 corruption. We are NOT hit by that bug.)
  angular_velocity = (0.0002, -0.0113, -0.0110), ~0 at rest = correct.
  frame_id = unilidar_imu.
=> OUR /unilidar/imu IS HEALTHY AND USABLE for odometry. The #34 corruption is NOT our
   problem. The IMU feed is good.
BONUS AXIS FINDING: gravity is almost entirely on IMU X (9.65 of 9.68) -> the IMU's "up"
  axis is its X axis, a consequence of the 90deg-mounted L2. Need this when configuring
  the gravity/fixed frame for IMU-aided odometry (the _stabilized frame alignment).

### PATH TO WIRING THE IMU (now de-risked at the source)
  1. Feed RTAB the IMU via the TOPIC /unilidar/imu (orientation is CORRECT there) — do
     NOT use the driver's imu_initial->imu TF (that one has the scrambled quaternion,
     finding #1). i.e. pass imu_topic:=/unilidar/imu to lidar3d.launch (which then builds
     the frame_id+"_stabilized" fixed frame -> gives ICP its rotation prior + connects TF).
  2. Ensure TF unilidar_lidar<->unilidar_imu exists (driver DOES publish imu->cloud with
     mfr transform; verify it's in the tree via view_frames, or add a clean static TF).
  3. Mind the gravity-on-X axis when the fixed/stabilized frame is set up.
  4. Re-test the SAME pan; PASS CRITERION: node-pose yaw spread ~matches the physical pan
     (vs the ~8x under-count). Watch the map swing live (zoom out first).
  4b. CANDIDATE MITIGATION for the "TF not available at IMU msg time" error: set
      always_check_imu_tf:=false (RTAB default is true; confirmed standard param via
      rtabmap_ros#1298). Our lidar<->imu TF is static, so re-checking it per IMU msg is
      unnecessary and is what throws the extrapolation error. Worth trying alongside a
      clean static TF. (NOTE: rtabmap_ros#1298 itself is NOT our case — it's a remote
      multi-machine D435i camera-VO data-transport failure, not LiDAR+IMU TF. Only the
      always_check_imu_tf param transfers.)
  5. If rotation now tracks -> the pan is unblocked. If NOT -> escalate (the driver TF bug,
     or deeper L2+odometry issue per glim#248 which persisted even with IMU).

### EXTERNAL CORROBORATION (2026-08-20 research) — sharpens the fix
1. AUTHORITATIVE lidar<->imu TRANSFORM (unilidar_sdk2 README, matches glim#248):
   T (Lidar -> IMU) = translation (-0.007698, -0.014655, +0.00667), rotation IDENTITY.
   *** CORRECTS earlier sign note: driver code had (0.007698,0.014655,-0.00667) for the
   imu->cloud direction; the DOCUMENTED L->I is (-0.007698,-0.014655,+0.00667). Direction
   & signs matter for a TF. TWO independent sources (SDK README + glim#248) agree on this.
2. RTAB author (matlabbe) on a similar Oak-D case (forum td10761): odometry/drift error
   "may be coming from the camera->imu TF frame" -> the RTAB AUTHOR's first suspect for
   odometry error is the sensor<->imu TF = EXACTLY where we're blocked. Corroborates our
   diagnosis. His canonical IMU launch uses imu_filter_madgwick (raw /imu -> /imu/data) +
   wait_imu_to_init:=true. Ours already has orientation so may skip madgwick, but madgwick
   is the MAINTAINER-BLESSED FALLBACK if direct /unilidar/imu keeps failing. He also notes
   gravity links null out z-error, and loop-closure-on-return corrects drift (validates the
   out-and-back pan design).
3. *** CONFLICT-RISK VALIDATED (ROS Answers q366927, Ouster OS1 + RTAB, hand-held): ***
   Same split we have — "odom frame has two child frames: baselink and os1sensor_STABILIZED."
   User tried adding a STATIC TF (baselink<->stabilized) and it "results in the other LIDAR
   frames not having a transform to odom" i.e. the naive static-TF fix BROKE OTHER FRAMES.
   => do NOT blindly add a static lidar<->imu TF. LOOK AT THE TREE (view_frames) FIRST, then
   apply the correct fix. This is direct evidence for the hesitation already flagged.
   RTAB's own ouster example warns: first cloud may be poorly synced with IMU -> may need an
   odometry reset on first cloud (resonates with our "TF not available at IMU msg time").
4. *** L2 IMU IS FACTORY-DISABLED BY DEFAULT (L2 User Manual): *** factory params = "3D Mode,
   NEGA Mode, IMU Disable, ENET, SELF START, GRAY ON." VERIFY our work_mode actually ENABLES
   the IMU properly (we DO see /unilidar/imu publishing, so likely enabled, but confirm the
   mode bits — a mis-set IMU mode could contribute). L2 IMU spec: 1kHz sample / 500Hz report.

### CORROBORATION: "stock RTAB launch under-utilizes the IMU" is a KNOWN pattern
luxonis/depthai#1147 (title: "Imu has not been utilized in rtabmap.launch.py", labeled
BUG): an OAK-camera user found the stock RTAB launch WASN'T actually using the IMU, wired
it in properly, and reported "such an improvement in speed of odometry calculation and
stability." Independent confirmation of OUR root-cause category (RTAB not using IMU -> poor
odometry; wiring it in -> better). His canonical pipeline (matches the RTAB-author forum
thread — now THREE sources agree):
    imu_filter_madgwick_node: use_mag=False, world_frame='enu', publish_tf=False,
      remap imu/data_raw -> <raw imu>,  /imu/data -> /rtabmap/imu
    rtabmap/odometry: wait_imu_to_init=True, imu remapped to /rtabmap/imu
CAVEATS (does NOT fully map to us): (1) it's a CAMERA (RGBDOdometry), not LiDAR icp_odometry;
(2) his OAK IMU is data_raw ONLY (no orientation) so he NEEDED madgwick — OURS already has
orientation, so this does NOT prove we need it; (3) he didn't hit our lidar<->imu TF blocker
(camera imu<->cam TF is published cleanly; ours is the flaky Unitree driver TF).
NEW IDEA (speculative, cheap to try): run madgwick ANYWAY even though our IMU has
orientation — madgwick republishes a CLEAN /rtabmap/imu at steady rate, which MIGHT sidestep
our "TF not available at IMU msg time" timing error as a side effect. Worth trying if the
direct route + always_check_imu_tf:=false doesn't work. Not a substitute for fixing the TF.

### *** KEY LEAD: L2 TIME BASE runs at ~1/2 real rate (unilidar_sdk2#25) ***
markgol (Jan 2026, HW 2.2.1.1 / FW 2.8.11.1) measured L2 packet timestamps vs host system
time: the L2's internal TIME BASE runs at ~1/2 ACTUAL TIME RATE. Confirmed with IMU packets,
3D packets, and both; 0 lost packets. OPEN, no Unitree reply.
WHY THIS MATTERS TO US (directly on-target): our IMU-integration failure was a TIMING error —
"TF not available at IMU msg time" + "Lookup would require extrapolation into the future
(requested ...482 but latest data ...471, ~10s gap)". A half-rate sensor clock makes L2-
stamped times DIVERGE from host/ROS time -> exactly the class of mismatch that throws
extrapolation/TF-timing errors and freezes the stabilized frame.
HONEST TENSION (do not overclaim): our driver runs use_system_timestamp:True, which stamps
the CLOUD with HOST time and SHOULD sidestep the L2 clock. BUT the failure was in the IMU->TF/
stabilized-frame path, which mixes IMU + cloud + stabilized-frame stamps; if any of those
carries L2-half-rate time while others carry host time, they diverge as observed. So #25 is a
STRONG CANDIDATE CONTRIBUTOR to our IMU-path failure, NOT yet confirmed as our cause.
=> MEASURABLE ON OUR RIG (concrete diagnostic, cheap): compare timestamps to host wall-clock:
   - `ros2 topic echo /unilidar/imu --field header.stamp` a few times + note wall clock; see
     if stamp advances at real rate or half.
   - same for /unilidar/cloud header.stamp.
   - compare /unilidar/imu stamp vs /unilidar/cloud stamp at the same instant — do they agree?
   - check our FW version (vs #25's 2.8.11.1) — the bug may be firmware-specific.
   If our unit shows half-rate on the IMU path, THAT is likely why imu_to_tf/deskew froze, and
   the fix shifts (force host-stamping on the IMU path, or a firmware update, not just a static TF).
   This is the best-targeted lead in the whole survey — same SDK, same hardware, same timing domain.

### STEP-1 (firmware/version check) — partial result (2026-08-20)
- SDK library version = 2.0.9 (unitree_lidar_sdk_config.h, compile-time constant). This is
  the SDK version, NOT the firmware (#25's half-rate unit was FIRMWARE 2.8.11.1).
- FIRMWARE + HARDWARE version are RUNTIME queries: getVersionOfLidarFirmware() /
  getVersionOfLidarHardware() (see unitree_lidar_sdk.h + example.h which prints
  "lidar firmware version = ..."). So it CAN'T be read purely cold — needs the rig; the
  driver likely prints it at startup (capture deliberately next rig-up).
- *** SHARPENS the #25 question: authoritative SDK doc (unitree_lidar_utilities.h L123/229):
  use_system_timestamp=true -> HOST system timestamp; false -> LIDAR HARDWARE timestamp
  (the half-rate clock). Our config = True. So per the SDK, our stamps SHOULD be host-time,
  which would mean #25's half-rate hardware clock does NOT reach our timestamps -> #25 may
  NOT be our cause. OPEN QUESTION to settle on the rig: does use_system_timestamp cover the
  IMU publish path too, or only the cloud? If IMU path is host-stamped as well, #25 is likely
  a red herring for us and our TF-timing failure has a different root (the driver's in-callback
  TF publishing). If the IMU path is NOT host-stamped, divergence could still bite. ***
  NEXT-RIG CHECK (settles it): echo header.stamp of BOTH /unilidar/imu and /unilidar/cloud,
  compare to host wall-clock rate; if both advance at real-time, use_system_timestamp is fully
  applied and #25 is not our problem.

### *** RESOLVED (2026-08-20, via sources): the "half rate" + "message loss" are NOT defects ***
UPDATE that supersedes the alarm below. Two source-based findings (NO code written):
  1. 250 Hz is the INTENDED SLAM rate, not half-broken. Unitree's OWN point_lio_unilidar
     config sets imu_time_inte:0.004 = 250 Hz, and L1+L2 use IDENTICAL config (DeepWiki:
     deepwiki.com/unitreerobotics/point_lio_unilidar). The L1 product spec: IMU "250 Hz output
     FOR STABLE SLAM". The 500 Hz in the L2 manual is the chip's raw reporting ceiling; the
     SLAM-facing rate the manufacturer ships/configures is 250 Hz. Our ~250 Hz = correct.
  2. "A message was lost!!!" from `ros2 topic echo` is a DIAGNOSTIC-TOOL ARTIFACT, not a data-
     path loss. Sensor topics are BEST_EFFORT QoS; echo/mismatched readers report losses a
     properly-QoS'd SLAM subscriber does NOT get. Corroborated: Husarion Panther (echo drops
     but direct SSH reads clean), TurtleBot4 #152, academic ros2probe study (observer loses a
     DIFFERENT set than the subscriber). The drops we saw = the OBSERVER, not the sensor.
CONFIDENCE: strong documentary (Unitree's own config + multiple independent sources); NOT yet
  rig-measured that a sensor-QoS subscriber gets a clean stream. Documentary, not rig-proven.
IMPLICATION: our RTAB failure was NOT bad IMU data - it was RTAB TF-PLUMBING (the _stabilized
  frame / flaky in-callback driver TF / deskew timing). The IMU feed is fine. Point-LIO expects
  250 Hz (its config sets it) so it would ingest our IMU fine. The IMU was never the blocker.
--- (original half-rate alarm, kept for the record; now understood as normal) ---

### *** MEASURED ON OUR RIG (2026-08-20): IMU ARRIVES AT HALF SPEC RATE ***
ros2 topic hz results (rig up, steady):
  /unilidar/imu   = ~250 Hz  (L2 manual spec = 500 Hz report rate) -> EXACTLY HALF.
  /unilidar/cloud = ~12 Hz    (steady; this is the rate EVERY working capture used - normal
                               functional cloud rate for us).
=> The IMU is arriving at HALF its documented 500 Hz. Consistent with unilidar_sdk2#25's
   "L2 time base is half real rate" finding, now observed on OUR unit on the IMU path.
   The cloud at 12 Hz appears functionally normal (all working captures used it), so this may
   be IMU-path-specific rather than a uniform whole-clock halving - but we do NOT have a solid
   "cloud should be X Hz" reference to be sure. NOT over-claiming which.
NOT YET DISTINGUISHED (the stamp-vs-wallclock test was attempted but the procedure was botched
   by the assistant bundling steps; deferred): whether the ~250 Hz is a half-rate CLOCK (stamp
   values advance at half real-time, the #25 claim) vs half-rate DELIVERY (msgs arrive at 250 Hz
   but stamps are correct). use_system_timestamp:True should give correct stamp VALUES either
   way, but half the SAMPLE COUNT reaches imu_to_tf regardless -> plausibly contributes to the
   stabilized-frame/deskew timing failure ("TF not available at IMU msg time").
   To distinguish later (ONE command, clean): 
     ros2 topic echo /unilidar/imu --field header.stamp --once   (note sec.nsec)
     ...wait a known interval, run again, compare stamp delta to real elapsed. Half = clock bug.
STAMP-VALUE RESULT (2026-08-20): two /unilidar/imu header.stamp reads were
  1787244461.171 and 1787244527.550 - BOTH are correct current UNIX epoch times (decode to
  real present-day wall-clock). A half-rate HARDWARE clock could NOT produce a correct current
  epoch. => use_system_timestamp:True IS stamping with real HOST time; the stamp VALUES are
  fine. So #25's half-rate CLOCK is NOT corrupting our timestamps. (The intended wait-vs-delta
  ratio test was abandoned - assistant failed to tell the operator to time the wait beforehand;
  but the epoch-correctness check answers it without timing.)
  *** CONCLUSION: our problem is NOT timestamp VALUES. It's IMU DELIVERY: ~250 Hz (half of
  500 spec) AND ACTIVE MESSAGE LOSS - `ros2 topic echo /unilidar/imu` reported "A message was
  lost!!!" 8x before one got through. Half throughput + drops on the IMU path -> fewer IMU
  samples reach imu_to_tf -> plausible contributor to the stabilized-frame/deskew timing
  failure. The fix direction shifts to DELIVERY/QoS + TF-STRUCTURE, NOT timestamp correction. ***
  NEW SIGNAL TO INVESTIGATE: IMU message loss (QoS/transport). Could be QoS-profile mismatch,
  Ethernet/UDP packet loss, or the driver. Check QoS on /unilidar/imu; the L2 is ENET/UDP.
FIRMWARE VERSION: still not captured (runtime query; grab at next driver startup).

Surveyed: glim#248 (L2 same symptom, cross-SLAM - KEY), RTAB-author forum td10761 (sensor<->
imu TF is the culprit + madgwick pattern - KEY), ROS-Answers q366927 (Ouster: naive static TF
breaks frames - KEY caution), L2 SDK/manual (authoritative transform + IMU-disabled-default -
KEY), depthai#1147 (stock RTAB under-uses IMU - corroboration). MISSES (different problems,
recorded as non-matches): rtabmap_ros#1298 (remote camera transport), #1174 (wheel+VO fusion).
=> The useful sources converge. EXCEPTION: unilidar_sdk2's OWN issue tracker is on-target
(same hardware). Besides #25 (time base), worth a look if needed: #27 (duplicated walls / Z
oscillation during mapping = odometry failure signature), #24 (SLAM unstable at ~45deg mount
angle - we're at 90deg), #16 ("Do not have TF data"), #20 (point cloud data structure/time
fields). The unblocking action remains the view_frames TF capture + the #25 timestamp
measurement on the rig, both cheap.

### REMAINING AUDIT STEPS (optional / as needed)
  0. [NEW, do FIRST, cheap] VERIFY LIVE /unilidar/imu VALUES (rig up, one command):
       ros2 topic echo /unilidar/imu --once
     Check, holding the rig STILL and roughly level:
       - orientation: a normalized quaternion (norm~1), NOT degenerate like #34's
         (x,y,z ~ 0 with only w) — for a level sensor expect w near +/-1, small x,y,z.
       - linear_acceleration: SANE, ~9.8 m/s^2 total magnitude (gravity), NOT 1e+24+
         garbage like #34. If accel is garbage -> IMU-aided odometry can't work until fixed
         (firmware/SDK update), regardless of the quaternion-order fix.
       - angular_velocity: ~0 when still.
     This one echo tells us if our IMU is USABLE at all. Do it before any IMU integration.

Before wiring/building more, AUDIT the SDK->ROS2->IMU/cloud chain — verify each link
carries what we've assumed, don't build on unverified foundations. Specific checks:
  1. Does the SDK PUBLISH the unilidar_lidar<->unilidar_imu TF? (if not -> that missing
     transform could BE the split TF tree). Manufacturer value above if we must add it.
  2. /unilidar/imu message contents: orientation quaternion present, or raw gyro+accel
     only? (ros2 topic echo /unilidar/imu --once, or read driver source). Decides madgwick.
  3. Are /unilidar/cloud and /unilidar/imu timestamps consistent + sane? (use_system_
     timestamp:True on both — verify they actually agree).
  4. Is the per-point 'time' field in the cloud correct (deskew needs it)?
  5. Check the L2 IMU sign/axis conventions vs ROS REP-103 (a flipped axis would make
     odometry mis-read rotation — a classic "messaging irregularity").
  Given glim#248, keep expectations honest: this may be a known-hard L2 issue; the audit
  is to LOCATE the irregularity, which could be timing, TF, or axis convention.

### CONFIRMED IMU FACTS (from the unilidar SDK launch file, in the record)
From ~/ros2_ws/src/unilidar_sdk2/unitree_lidar_ros2/.../launch/launch.py (seen in the
2026-08-17 tau transcript):
  - IMU topic:  /unilidar/imu   (published by the SAME driver — already live when rig up)
  - IMU frame:  unilidar_imu
  - cloud frame: unilidar_lidar ; cloud topic: unilidar/cloud
  - use_system_timestamp: True (cloud + imu stamped with host time)
So the IMU is ALREADY BEING PUBLISHED whenever the rig runs — we just never fed it to
lidar3d.launch. Good: less to set up than feared.

### OPEN QUESTION TO RESOLVE COLD (before wiring IMU) — SDK not yet checked for this
We have NOT looked in the unilidar SDK for the IMU MESSAGE CONTENTS or example code.
The decisive unknown: does /unilidar/imu publish a full ORIENTATION quaternion, or only
raw angular-velocity + linear-acceleration?
  - if ORIENTATION present -> can feed RTAB/fixed-frame more directly.
  - if RAW only -> must run imu_filter_madgwick (use_mag:=false, publish_tf:=false) to
    COMPUTE orientation first (the lidar3d.launch header explicitly expects this).
CHECK (cold, on Jetson, no rig): the driver source at
  ~/ros2_ws/src/unilidar_sdk2/unitree_lidar_ros2/src/... (the .h/.cpp that builds+publishes
  the sensor_msgs/Imu) — does it set orientation, or leave it 0 with only angular_velocity
  + linear_acceleration? Also check for an IMU README/example in the SDK.
  QUICK RUNTIME CHECK (rig up, cheap): ros2 topic echo /unilidar/imu --once  -> look at the
  'orientation' field: nonzero/normalized quaternion = has orientation; all-zero (w=0 or
  x=y=z=w=0) = raw only -> need madgwick.

### NEXT SESSION — RESUME 7C IMU INTEGRATION (now the critical path)
  Per the launch header (L9-12): needs TF between lidar/base and imu frame, and an IMU
  orientation via imu_filter_madgwick (use_mag:=false publish_tf:=false). Steps:
   1. confirm the L2 IMU topic is publishing (/unilidar/imu per PART? sensor facts) +
      its frame_id + that it has orientation or needs madgwick to compute it.
   2. static TF unilidar_lidar<->unilidar_imu (measure/again from datasheet).
   3. run imu_filter_madgwick (use_mag:=false, publish_tf:=false) -> oriented IMU.
   4. launch lidar3d with imu_topic:=... so fixed_frame_id becomes frame_id+"_stabilized".
   5. re-test the SAME pan; check node-pose yaw spread now ~matches the physical pan
      (vs the ~8x under-count). THAT is the pass criterion.
  Note the RECONSTRUCTION of the broken pan is NOT worth pursuing (poses are missing info;
  no post-hoc scaling recovers true per-scan orientation — confirmed by a failed x8-yaw
  attempt). Fix the CAPTURE (IMU), don't try to salvage the broken one.

### IMPACT ON THE B-vs-A EXPERIMENT (7I)
  - Rotation-tracking must be fixed before A (moving pan) is meaningful — A would inherit
    the same broken rotation.
  - The "clean B" should be re-done as TRUE stationary (relocate between holds, minimal
    rotation-while-tracking) OR after the TF/deskew fix.
  - The photoreal SINGLE-VIEW result (outputs/sampleB_render.png) still stands as proof
    the texturing pipeline endpoint works; it's the multi-view POSE assembly that's blocked.

═══════════════════════════════════════════════════════════════════════════
## 7K. ⚠️ STRATEGIC STATUS (2026-08-20) — RTAB rotation is the ceiling; Point-LIO is the fix ⚠️
═══════════════════════════════════════════════════════════════════════════
COLD-READER SUMMARY OF WHERE THIS PROJECT ACTUALLY STANDS (honest, evidence-based):

THE CORE PROBLEM, PROVEN VISUALLY:
- The sampleB "photoreal success" is NOT a clean reference. It was a ~270 deg pan that hit
  the rotation-under-tracking bug: poses recorded only 14.5 deg yaw for a ~270 deg physical
  sweep (~18x under-count), translations 16-38cm. Assembled world extent = x3.3 y9.5 z13.0m
  -> a room is NOT 13m tall; that's rotation-collapsed geometry (scans from different walls
  placed at wrong orientations). See mesh_shape_views.png (3 ortho views) + best_render.png
  (94% cov single view). The textured patches are photoreal, but the FULL-ROOM reconstruction
  is corrupted. "Missing half the room" = the rotation bug made visible, NOT a coverage/view
  limitation. *** CORRECTION: earlier Master text calling sampleB a "clean stationary
  reference / PHOTOREAL SUCCESS" was WRONG - it's rotation-corrupted. ***

BENCHMARK REALITY CHECK (operator, 2026-08-20):
- Current output is "Polycam with superior equipment" - only moderately better than the free
  iPhone app, which was used as the WORST-CASE baseline to beat. The rig has NOT yet beaten
  Polycam. The premise (superior LiDAR -> superior image) is real in the SENSOR but is being
  thrown away by the rotation bug degrading survey-grade scans back to phone-grade geometry.
- UNRESOLVED HONEST QUESTION: is the rig's justification (a) better geometry [blocked by
  rotation bug], or (b) RELIGHTING [day->night, Unreal light placement] which Polycam CANNOT
  do? If (b), the goal should shift to proving relighting on adequate geometry, not to a
  prettier mesh. Not yet decided.

CAN THE ROTATION BUG BE FIXED? - most honest answer:
- On RTAB: NO PROVEN FIX. Only untested candidates (always_check_imu_tf:=false, clean static
  TF, madgwick). Every RTAB IMU attempt has been blocked UPSTREAM of testing rotation. RTAB's
  LiDAR-inertial path is a fragile bolt-on and a poor fit for this sparse spinning sensor.
- On the L2 in general: YES, DEMONSTRABLY - but via POINT-LIO, not RTAB. Unitree ships
  official L2 Point-LIO demos (videos + downloadable L2 indoor/park bags) at
  github.com/unitreerobotics/point_lio_unilidar showing clean L2 rotation-tracked maps. So
  the rotation problem is NOT a hardware limit; it is an RTAB-specific failure. The IMU feed
  itself is fine (250Hz is the intended SLAM rate; "message lost" was a topic-echo artifact).
- => "Solvable on the L2, demonstrated by the manufacturer; NOT yet solved by US." The fix is
  a PIVOT to Point-LIO for odometry, not more RTAB debugging.

POINT-LIO PIVOT - what it costs and what survives (from earlier analysis):
- SURVIVES a pivot (engine-independent): raw clouds, raw IMU, camera images, calibration
  (reformat extrinsic to "lidar-in-IMU-frame", don't re-measure), the texturing ENGINE
  (per_shot_texture.py takes posed images+mesh, source-agnostic).
- NEEDS REWORK: the db_to_texture bridge (Point-LIO outputs .pcd + odometry, NOT an RTAB .db)
  -> re-plumb to consume Point-LIO poses/cloud + separately-logged posed images.
- WATCH-OUTS: official Unitree repo is ROS1 noetic / Ubuntu 20.04 - WRONG for our ROS2 Humble
  rig. The ROS2 port is dfloreaa/point_lio_ros2 (has explicit L2 support). Build friction on
  Jetson (PCL/Eigen/livox_ros_driver2) likely. IMU config needs satu_acc/satu_gyro/acc_norm
  + extrinsic in Point-LIO's convention. imu_time_inte:0.004 (=250Hz) matches our IMU.
- ZERO-RIG PROOF AVAILABLE: Unitree's L2 indoor bag can be run through Point-LIO to confirm
  clean rotation BEFORE any Jetson build. (Operator has already seen the demos.)

THE DECISION IN FRONT OF THE OPERATOR (not yet made):
  (A) Pivot odometry to Point-LIO ROS2 - the demonstrated fix for rotation, but a real
      re-build + texturing re-plumb.
  (B) Keep fighting RTAB IMU - unproven, fragile, poor-fit; low confidence.
  (C) Use Polycam for scouting-grade geometry NOW; reserve the custom rig as an R&D track for
      the RELIGHTING endgame (the thing Polycam can't do), which is the rig's real
      differentiator if geometry-parity with Polycam is the current ceiling.
  Recommendation leaned: if moving-capture is required, (A) is the demonstrated path; but FIRST
  settle whether the rig's value is geometry or relighting, because that decides if the pivot
  is even worth it.

═══════════════════════════════════════════════════════════════════════════
## 7L-HW. JETSON = ORIN NANO 8GB — most "Jetson Nano" guidance is WRONG for us
═══════════════════════════════════════════════════════════════════════════
CONFIRMED (operator, 2026-08-20): the board is 8GB = Jetson ORIN Nano (2023, Ampere), NOT the
original Jetson Nano (2019, 4GB, Maxwell). These are very different machines. Much online
"Jetson Nano" Point-LIO/SLAM guidance targets the OLD 4GB board and is WRONG for us.

DISCARD (wrong for Orin):
  - "Use Ubuntu 18.04/20.04 + ROS Melodic/Noetic" -> WRONG. We are correctly on Ubuntu 22.04 +
    ROS2 Humble (right for Orin's JetPack). Do NOT downgrade OS/ROS on old-Nano advice.
  - OOM-panic framing (maps trigger crashes, need 8GB MicroSD swap) = 4GB-survival advice.
    With 8GB + Ampere we have real headroom. Not one map from a crash.
KEEP (good on any Jetson):
  - Max performance: `sudo nvpmodel -m 0` + `sudo jetson_clocks` before a run (Point-LIO is
    CPU-bound point-by-point; worth doing on Orin too).
  - Don't run RViz on the Jetson - run it on a HOST over the ROS network. Keeps the capture
    device lean.
  - Map-size/downsample config discipline: the L2 config already sets filter_size_surf/map:0.4,
    blind:0.5 - understand these keep the incremental map manageable (not crash-avoidance for
    us, just good practice).

COMPUTE RISK = CLEARED. Operator ran Point-LIO/L1 -> CLEAN map on a 2017 generic x86 tower.
  If a 2017 tower did it, the Orin Nano (8GB, far stronger than old Nano) runs it comfortably.
  Point-LIO is lightweight. Compute + RAM are OFF the worry list.

CLEAN ARCHITECTURE this hardware enables (methodological lock-in):
  - JETSON runs Point-LIO HEADLESS (lean, no viz).
  - The x86 TOWER (already owns a proven Point-LIO run) runs RViz / visualization over the ROS
    network, and is the FALLBACK odometry machine if the Jetson aarch64 build fights us.
  So we are NOT forced to solve the Jetson build to make progress - the tower is a proven
  Point-LIO host. That de-risks the pivot's biggest remaining item.

REMAINING REAL RISK (unchanged by 8GB):
  - aarch64/ROS2 BUILD friction (compiling PCL/Eigen/livox_ros_driver2 on ARM) - the real
    time-sink, but with the x86 tower as fallback.
  - Point-LIO output -> texturing/relight BRIDGE (the genuinely new work; RTAB was the old input).
METHOD NOTE: when build issues hit, use ORIN Nano + JetPack 5/6 + Humble sources - NOT generic
  "Jetson Nano" tutorials (they point at old OS/ROS and will mislead).

## 7L-DATA. L1 DATASET INSPECTED (2026-08-20) — validates the data format for Point-LIO
═══════════════════════════════════════════════════════════════════════════
Operator provided a real Unitree L1 rosbag (unilidar-2023-09-22, 322MB, ROS1 .bag, 435.7s).
Parsed cold with pure-python `rosbags` lib (no ROS install). VERIFIED (measured, not assumed):
  TOPICS/RATES: /unilidar/imu 249.7 Hz (108813 msgs), /unilidar/cloud 9.9 Hz (4312 msgs).
    -> confirms 250Hz IMU is the L-series NORM (3rd confirmation), cloud ~10Hz.
  CLOUD FIELDS: x,y,z(f32) intensity(f32,off16) ring(u16,off20) TIME(f32,off24), point_step 32.
    *** PER-POINT `time` FIELD PRESENT and VARIES 0->0.0968s within each scan. *** This is THE
    critical Point-LIO requirement (README note C: "Failed to find match for field 'time'" =
    common blocker). Unitree format HAS it. timestamp in SECONDS -> matches config
    timestamp_unit:0. This is the field that makes Point-LIO deskew work (and that RTAB's path
    fought). Confirmed present in Unitree data.
  FRAME IDS: cloud=unilidar_lidar, imu=unilidar_imu -> EXACTLY our rig's frames.
  IMU HEALTH: orientation norm 0.998, accel mag 9.715 (gravity). Same healthy signature as our L2.
  MATCHES the L2 Point-LIO config we captured (lidar_type:5, scan_line:18, timestamp_unit:0,
    x/y/z/intensity/ring/time layout).
HONEST LIMITS: this is L1 (not L2) + ROS1 bag (not ROS2). Format is ~identical (our own L2 field
  inspection also showed x/y/z/intensity/ring/time), so it validates the ALGORITHM+FORMAT path,
  not L2 specifically. Does NOT prove Point-LIO tracks OUR rotation - only that the data format
  is correct. Actual rotation test still needs a run.
USE: this bag can serve as the BENCH-VALIDATION input - run it through Point-LIO on a capable
  machine to confirm a clean map before the Jetson build (validates algorithm+format; L1 not L2).
  (Cannot run in Claude's sandbox - no ROS/build. Operator-run.)

## 7L-CONFIG. POINT-LIO L2 CONFIG — FULL VALUES (from Unitree's config/unilidar_l2.yaml)
═══════════════════════════════════════════════════════════════════════════
*** BIG UNLOCK: the ENTIRE L2 config is published by Unitree. We COPY it, not derive it. ***
Source: deepwiki.com/unitreerobotics/point_lio_unilidar/4.2-unitree-l2-configuration
(= config/unilidar_l2.yaml + launch/mapping_unilidar_l2.launch in the ROS1 official repo).
The ROS2 port (dfloreaa) is a port of exactly this - values should carry over (verify the
ROS2 repo's config/ has the L2 yaml; if not, create it from these values).

COMMON:
  lid_topic: /unilidar/cloud        <- MATCHES our rig exactly
  imu_topic: /unilidar/imu          <- MATCHES our rig exactly
  con_frame: false ; con_frame_num: 1 ; cut_frame: false ; cut_frame_time_interval: 0.1
  time_lag_imu_to_lidar: 0.0
PREPROCESS:
  lidar_type: 5 (UNILIDAR) ; scan_line: 18 ; timestamp_unit: 0 (seconds) ; blind: 0.5
MAPPING - IMU (the values the README warned we'd have to find - ALL PROVIDED for L2):
  imu_en: true ; imu_time_inte: 0.004 (=250Hz, matches our measured IMU rate)
  satu_acc: 30.0 ; satu_gyro: 35 ; acc_norm: 9.81
MAPPING - covariances:
  lidar_meas_cov: 0.01 ; imu_meas_acc_cov: 0.1 ; imu_meas_omg_cov: 0.1
  acc_cov_input: 0.1 ; gyr_cov_input: 0.01
MAPPING - EXTRINSIC (IMU->LiDAR, IMU is base frame):
  extrinsic_T: [0.007698, 0.014655, -0.00667]   *** authoritative: positive-first signs ***
  extrinsic_R: [1,0,0,0,1,0,0,0,1]  (identity - no rotation between IMU & LiDAR frames)
  *** CORRECTION to earlier Master note: I had written the LiDAR->IMU direction
  (-0.007698,-0.014655,+0.00667). Point-LIO wants IMU->LiDAR = [0.007698,0.014655,-0.00667].
  Same physical offset, opposite direction. USE THE POSITIVE-FIRST FORM for Point-LIO. ***
OUTPUT:
  publish_odometry_without_downsample: enable ; path_en: true ; scan_publish_en: true
  pcd_save_en: true ; interval: -1 (all frames -> one PCD)
LAUNCH runtime params:
  filter_size_surf: 0.4 ; filter_size_map: 0.4 (L2's enhanced 0.4m downsample)
  point_filter_num: 1 ; cube_side_length: 1000 ; use_imu_as_input: 0 ; space_down_sample: 1

KEY IMPLICATIONS (honest):
  - IMU tuning is NOT the risk I flagged: satu_acc/satu_gyro/acc_norm are all published for L2.
  - Point-LIO uses the SENSOR-INTERNAL IMU<->LiDAR extrinsic (above), which is INDEPENDENT of
    OUR camera calibration. So we do NOT reformat our camera extrinsic for Point-LIO. The
    camera only re-enters at the TEXTURING stage (per_shot_texture), not in odometry.
  - Topics already match (/unilidar/cloud, /unilidar/imu) - no remapping needed.
  - CAVEAT: values sourced from the ROS1 official L2 config; the ROS2 port SHOULD match (same
    sensor, direct port) but VERIFY the ROS2 repo ships config/unilidar_l2.yaml; if missing,
    create it from these exact values + adapt the launch to ROS2 .launch.py form.

═══════════════════════════════════════════════════════════════════════════
## 7L. POINT-LIO PIVOT — STEP PLAN (decided 2026-08-20, next session)
═══════════════════════════════════════════════════════════════════════════
DECISION: pivot odometry from RTAB to Point-LIO. Rationale in 7K (RTAB rotation unfixable in
practice; Point-LIO is the manufacturer-demonstrated fix for L2 rotation tracking).

WHICH REPO (critical - do NOT use the wrong one):
- Unitree's OFFICIAL repo github.com/unitreerobotics/point_lio_unilidar is ROS1 NOETIC /
  Ubuntu 20.04 -> WRONG for our ROS2 Humble / Ubuntu 22.04 Jetson. Use it only as reference
  (config values, L2 datasets, demo proof).
- USE THE ROS2 PORT: github.com/dfloreaa/point_lio_ros2 (explicit Unitree L1/L2 support,
  ROS2 Humble, Ubuntu 22.04 tested). This is the one to build on the Jetson.

COLD-PREP FIRST (no rig, do before any hot window):
  1. Read dfloreaa/point_lio_ros2 README + config fully. Identify the L2 config file and its
     params: lid_topic, imu_topic, extrinsic_T, extrinsic_R, satu_acc, satu_gyro, acc_norm,
     scan_line (=18 for L2), lidar_type (=5 UNILIDAR), timestamp handling, imu_time_inte
     (=0.004 = 250Hz, matches our IMU).
  2. Confirm build deps vs our Jetson: PCL, Eigen, livox_ros_driver2 (Point-LIO needs it
     sourced even for non-Livox), ros-humble-pcl-ros/pcl-conversions. Flag likely Jetson
     build friction (PCL/Eigen versions) BEFORE building.
  3. Reformat OUR extrinsic to Point-LIO's convention: it wants LiDAR pose IN IMU frame
     (extrinsic_T, extrinsic_R = lidar-in-imu). Our calibration is lidar<->cam and the
     lidar<->imu is the mfr value t=(-0.007698,-0.014655,+0.00667), R=identity. Work out the
     exact numbers to paste into the yaml. (Do NOT re-measure; transform what we have.)
  4. Obtain IMU saturation/norm values for the L2 IMU (satu_acc, satu_gyro, acc_norm) - from
     Unitree's official config (point_lio_unilidar/config) as the reference starting point.

ZERO-RIG VALIDATION (optional but smart, before committing Jetson build time):
  - Download Unitree's L2 indoor bag (oss-global-cdn.unitree.com/static/L2 Indoor Point Cloud
    Data.bag) and run it through Point-LIO on ANY capable machine -> confirm clean rotation-
    tracked map. (Operator has already seen Unitree's demos, so this may be skippable.)

BUILD + FIRST RUN (rig, cold-prepped):
  5. Build point_lio_ros2 + unilidar_sdk2 on the Jetson (colcon). Expect iteration.
  6. First run: keep LiDAR STATIONARY the first few seconds (Point-LIO IMU init requirement),
     then do the SAME ~270 pan that broke RTAB. PASS CRITERION: the saved map (PCD/scans.pcd
     or the ROS2 equiv) is a COHERENT room - walls at right angles, ~2.5-3m tall (NOT 13m),
     full room present (not half). Compare directly against the RTAB rotation-collapsed result.
  7. If PASS -> rotation is solved; move to re-plumbing texturing (step 8). If FAIL -> capture
     the exact errors; do not thrash.

TEXTURING RE-PLUMB (after odometry works):
  8. Point-LIO outputs a point cloud map (.pcd) + odometry poses, NOT an RTAB .db. The
     texturing ENGINE (per_shot_texture.py: mesh + best_image_per_face) is source-agnostic and
     SURVIVES. What needs rework is the BRIDGE: replace db_to_texture.py's RTAB-.db reader with
     one that consumes (a) Point-LIO's cloud/poses and (b) the camera images + their poses
     (logged separately, timestamp-matched to Point-LIO odometry). Keep per_shot_texture.py.
  9. Camera images: Point-LIO won't store them like RTAB did. Need a capture that logs
     /image_raw WITH a timestamp that can be matched to Point-LIO's pose stream (interpolate
     pose at image time). This is the main new plumbing.

WHAT SURVIVES THE PIVOT (do not redo): calibration (intrinsics+extrinsic, reformatted),
raw clouds, raw IMU, camera images, per_shot_texture.py texturing engine, the whole VFX/
relight endpoint plan (7E/7F). WHAT'S REPLACED: RTAB -> Point-LIO (odometry+map), and the
db_to_texture bridge -> a Point-LIO-output bridge.

OPEN STRATEGIC FLAG (from 7K, still unresolved): confirm whether the rig's real justification
is GEOMETRY or RELIGHTING. If relighting, prioritize proving that path once geometry is clean.

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
- 2026-08-19: COLOUR PIPELINE PROVEN END-TO-END (benched). Deployed v3 fusion node (preserves
  per-point time field), verified colored cloud publishes x,y,z,rgb,time @12.5Hz. RTAB runs
  CLEAN on /fusion/colorized_cloud - NO deskew abort (the v3 fix worked). Stationary capture ->
  color_stationary_20260819.db (11 nodes). Proved colour SURVIVES the full pipeline by reading
  the DB directly (SQLite->zlib->float32 N,4 with packed RGB; real colors). Assembled 27,405
  colored pts -> render. GUI export quirk ("cloud not found in cache") worked around by reading
  DB directly - we don't depend on the GUI export. HONEST VERDICT: sparse "colour dots", FAR
  from usable - proves plumbing not quality; usable must come from TEXTURE not per-point colour.
  Big strategic session prior: decided endpoint = photoreal relightable textured mesh (7E),
  mapped pro VFX pipeline + software (7F: RealityScan/Agisoft De-Lighter/Blender), found
  Cine Tracer (Unreal cinematography sim) as precedent, and reframed delighting as capture-
  discipline (cross-pol/flat-light stills) rather than unreliable auto-software. Operator
  re-centered the MOUNTAIN: a clear/dense/colored/coherent 3D capture of a walked space is THE
  goal; everything else (delight/relight/Unreal/handoff) is downstream. Files: colorized_fusion
  _node_v3.py (deployed), color_stationary_assembled.ply, color_map_render.png. No walk yet
  (still benched). Camera colour = preview layer; texture path is where usable quality lives.
- 2026-08-19 (cont): TEXTURING PIPELINE BUILT + IMAGE-SAVING CAPTURE PROVEN ON RIG.
  Decided PER-SHOT (local projection) texturing over global-UV (fits stills deliverable,
  avoids UV artist-hours). Texture probe on real dense data: per-point colour 2.6% (dots,
  unusable) vs TEXTURE 92.5% photoreal (trimmed Poisson mesh; ball-pivoting shreds).
  Limiter = MESHING, not colour. Built per_shot_texture.py (mesh+project+multi-view
  best-image-per-face, debugged: outlier removal, XY guard, empty guard; pose composition
  math verified 1e-16) and db_to_texture.py BRIDGE (capture.db -> mesh -> texture, tested
  end-to-end). Built + PROVED rtab_capture_with_images.sh v2 on the rig: v1 failed (empty
  db) due to (1) approx_sync not matching -> exact sync, (2) hardcoded frame 'camera_link'
  wrong -> real frame 'camera_frame', now auto-detected; v2 also GATES on /rgbd_image so it
  can't silently build an empty map. Result imgtest2.db = 10/10 nodes with scan+image
  (~560KB)+calibration = complete textureable capture. Full chain now real: rig ->
  rtab_capture_with_images.sh -> capture.db -> db_to_texture.py -> textured mesh. The 270
  pan is UNBLOCKED (was gated on image-saving). Files in outputs: per_shot_texture.py,
  db_to_texture.py, rtab_capture_with_images.sh (v2), rtab_capture.sh, texture_probe*.png,
  per_shot_*.png. Also researched Unreal integration (Nanite ingests scan geometry, Lumen
  relights — need TEXTURE UVs not lightmap UVs; middle-pipeline PBR-map tool like Marmoset/
  Substance still required — Lumen consumes maps, doesn't make them). Ruled OUT Stable
  Projectorz (AI-invents texture, wrong for real-capture predictive tool).
- 2026-08-19 (cont): Investigated the ~1s odometry DELAY (icp_odometry delay~0.99s,
  CONSTANT not growing = fixed latency, not queue overflow). Found it's the KNOWN
  tau-limit of the un-triggered B0578 (7B) made concrete: RTAB warned "image pose
  will not be synchronized with odometry" + a split TF tree (icp_odom vs
  unilidar_lidar). BUT imgtest2.db check: all 10 nodes have valid pose+image =
  stationary capture is fine (nothing moved). The delay only hurts MOVING capture
  (pose lags ~1s = a few deg at rotation speed). Connected to prior tau work
  (transcript 2026-08-17): the fusion node already timestamp-pairs (slop 0.04s);
  tau (hardware exposure offset) remains unmeasured + only a trigger camera fixes
  it (7B fork). Referenced Ouster forum thread on hardware phase-locking (LiDAR-
  triggers-camera via GPIO encoder-angle) as the endgame technique — but L2 has NO
  sync GPIO and B0578 has NO trigger (both in 7B), so it's deferred to the trigger-
  camera fork, as already decided. DEFINED the B-vs-A capture experiment (7I) with
  full parameters + result placeholders: B=14 stationary stops (~4s each, 60s,
  clean reference, proven), A=out-and-back moving pan (135deg out+back, ~4.5deg/s,
  60s, gives tau sign-flip + return-to-start drift), A gated behind a ~15s moving
  test. 60s usable uptime PER SAMPLE (spin-up excluded), separate windows for heat.
  Next session: run B, then A-test, then A-full; fill 7I results; compare textured
  output to MEASURE the tau cost. Also: rtab_capture_with_images.sh v2 PROVEN on rig
  (10/10 nodes w/ images) — the empty-capture failure is SOLVED.
- 2026-08-19 (cont): Ran Sample B (stop-and-go pan, 28 stops out-and-back). DB=64 nodes,
  ALL 64 with pose+image+calib; bridge textured 99% faces; SINGLE-node render is PHOTOREAL
  (chandelier, framed portrait on wall, molding, appliances — pipeline endpoint PROVEN on
  real data, outputs/sampleB_render.png). BUT user caught that a whole side of the room is
  MISSING from the multi-view result. Diagnosis (7J): ODOMETRY UNDER-TRACKS ROTATION — 64
  node poses span only ~14.5deg yaw despite a 90deg+ physical pan (~8x under-count). From
  icp_odometry logs: ratio 0.60-0.68 (healthy), std dev ~0.007rad (confident), delay ~0.5s
  (modest), no resets => ICP is CONFIDENT but WRONG about rotation magnitude = a DESKEW/
  geometry problem, NOT latency, NOT ICP failure. RULED OUT fusion-node latency (nearly
  fixed this wrong thing; a vectorized fusion node is a real ~12x latency win but does NOT
  fix rotation). PRIME SUSPECT: the split TF tree (icp_odom vs unilidar_lidar unconnected —
  warned every capture) breaking scan deskew under rotation. NEXT: investigate TF tree
  (view_frames) + launch odom/base frames + deskew config; fix so rotation tracks true
  angle BEFORE re-attempting the A pan. Depth-image warning = cosmetic (viz wants depth we
  don't have). User's odometry-sample instinct is what redirected us from the wrong fix.
