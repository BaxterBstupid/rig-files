# MASTER REFERENCE — LiDAR-Camera Capture Rig
### THE authoritative lookup. Scan, don't read. Update values IN PLACE at session end.
Last updated: 2026-08-17 (session: framework + RTAB scoping)

> This is the TOP document. Narrative history lives in PLAN_NEXT_SESSION.md (archived
> below this in priority). When a value changes, edit it HERE in place — don't append.
> Every entry carries PROVENANCE (vetted? when? where?) so nothing is trusted blindly.

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
| RTAB-Map first map | ✅ DONE 2026-08-18: LiDAR-only SLAM, map built+saved (milestone_map_20260818.db, 5.1MB, 387+ nodes) |
| Camera upgrade | ⬜ researching (trigger camera → kills tau) |
| Downstream (mesh/UE/relight) | ⬜ after first maps |

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
