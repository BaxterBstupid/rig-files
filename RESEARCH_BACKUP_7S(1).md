# RESEARCH BACKUP — 7S SOURCES (fetched + verified 2026-08-23)
### Companion to MASTER_REFERENCE (7S section). Sources were RE-FETCHED and read in full
### where marked; findings below are banked in our own words so they survive link-rot,
### session loss, and compaction. Store alongside the Master in rig-files.

═══════════════════════════════════════════════════════════════════════════
## 1. CMU ROBOTICS INSTITUTE — Li, Gogia, Kaess, ICRA 2019
## "Dense Surface Reconstruction from Monocular Vision and LiDAR"
═══════════════════════════════════════════════════════════════════════════
URL: https://www.ri.cmu.edu/app/uploads/2019/07/Li19icra.pdf  [FULL PAPER FETCHED + READ]
WHY IT MATTERS TO US: the single most on-point source for our holey-mesh problem.
Their premise is our exact situation: MVS (camera-only) fails on textureless walls and
similar viewing angles; LiDAR-only fails indoors because scans are sparse vs camera pixels
and noisy close-up. Their fix uses BOTH sensors in the GEOMETRY stage, not camera-as-paint.

THEIR RIG (validates ours): Velodyne VLP-16 LiDAR + FLIR Grasshopper3 camera on a moving
rig — same class as our L2 + B0578. Processing machine: i7-7700 + 32GB RAM desktop
(reinforces our processing-station conclusion — nobody meshes on an 8GB edge device).

THE PIPELINE (two stages):
  STAGE 1 — LiDAR-improved densification: project registered LiDAR points into each camera
  frame to INITIALIZE the MVS depth map (instead of random init). Per-pixel priority:
  closest LiDAR point (handles occlusion) < SfM sparse feature (more accurate than LiDAR)
  < triangulated interpolation for pixels with neither. Then standard patch matching /
  propagation / multi-view depth fusion. Result: dense camera point cloud that works even
  on textureless surfaces (their Fig 3: OpenMVS fails on blank wall; theirs doesn't).
  STAGE 2 — fused surface extraction: combine the dense camera cloud with a DOWNSAMPLED
  subset of LiDAR points — inserting a LiDAR point ONLY where no camera depth exists, so
  LiDAR noise never pollutes camera-measured areas. Then 3D Delaunay tetrahedralization +
  graph s-t cut (inside/outside labeling) -> WATERTIGHT surface mesh. They add an Elidar
  smoothing term because close-range LiDAR (±3cm on VLP-16) is noisier than triangulated
  camera points — mixed-vertex tetrahedra are biased toward "outside" so the surface
  follows the cleaner camera points where both exist.

RESULTS (F-score @ 5cm, precision/recall/F): Lift lobby 96.6/88.8/92.5 — Kitchen
  91.9/82.3/86.9 — Hallway 93.1/75.2/83.2. Beat OpenMVS, PMVS2, and LiDAR-only on all
  three. LiDAR-only's failure mode = missing thin structures/small objects + stripe
  artifacts from scan lines (recognizable in our own meshes).

HONEST CAVEATS FOR US: assumes KNOWN camera/LiDAR poses + SfM sparse features + known
  extrinsic (we have poses via Point-LIO and a vetted extrinsic — we'd need the SfM feature
  step or substitute). Built on OpenMVS (open source, C++). This is a research pipeline to
  LEARN FROM (LiDAR-as-MVS-prior; only-fill-where-camera-lacks; graph-cut watertight),
  not necessarily to run verbatim. RealityScan does a commercial version of this hybrid.

═══════════════════════════════════════════════════════════════════════════
## 2. HKU-MARS — LiDAR_IMU_Init (LI-Init), IROS 2022
═══════════════════════════════════════════════════════════════════════════
URL: https://github.com/hku-mars/LiDAR_IMU_Init  [FULL README FETCHED + READ]
WHY IT MATTERS: directly relevant to our odom-cutoff / frozen-timestamp problem (7P).
WHAT IT IS: targetless, real-time initialization for LiDAR-inertial systems — calibrates
  TEMPORAL OFFSET + extrinsic + gravity + IMU bias, no hardware sync needed. Merges into
  FAST-LIO2 as an init module. Supports spinning (Velodyne/Ouster/Hesai) + solid-state LiDARs.

THE TIMESTAMP FINDING (their §6, matches our 7P clock diagnosis): some LiDARs' timestamp
  origin = the moment of POWER-ON, so stamps restart near 0 every power cycle -> temporal
  init is needed each power-up unless the offset proves stable across cycles (run LI-Init
  twice across a power cycle; if offsets agree, bank the value into the config as
  time_diff_lidar_to_imu and skip re-init). This is the same failure family as our
  frozen-Feb-2026 sensor stamps vs Jetson clock.

USEFUL PARAMETERS THEY DOCUMENT (for when/if we run it or port ideas):
  mean_acc_norm 9.805 normal IMU / 1 for Livox built-in; cut_frame_num*orig_odom_freq ≈ 30
  for spinning LiDAR; filter_size_surf 0.05-0.15 indoor; filter_size_map 0.15-0.25 indoor;
  stay STILL >5s after launch to accumulate a dense initial map (matches our dead-still-init
  lesson exactly); angular velocity must be rad/s.

HONEST CAVEAT FOR US: LI-Init is ROS1 (Ubuntu>=18.04, ROS>=Melodic, catkin). We are ROS2
  Humble. Using it directly needs a ros1_bridge / bag conversion / port — OR we use its
  IDEA (measure the offset once across power cycles, write it into Point-LIO's config
  time-offset field) rather than its code.

═══════════════════════════════════════════════════════════════════════════
## 3. HKU-MARS — Point-LIO (our current odometry engine)
═══════════════════════════════════════════════════════════════════════════
URL: https://github.com/hku-mars/Point-LIO  [README read via search 2026-08-23]
CONFIRMS OUR 7P DOSSIER VERBATIM:
  - IMU and LiDAR MUST be synchronized ("that's important" — their words' emphasis).
  - Set satu_acc / satu_gyro / acc_norm per the actual IMU (we verified ours: 0 saturation
    crossings, acc in m/s², acc_norm 9.81 correct).
  - "Failed to find match for field 'time'" = per-point LiDAR timestamps missing from bag.
  - LiDAR-only sidestep: imu_en:false + gravity_init set + use_imu_as_input:0.
  - High-rate odom without downsample: publish_odometry_without_downsample:true (explains
    the ~3000Hz burst we saw in the cutoff autopsy — that rate itself isn't the bug).
Designed for high-bandwidth / fast-motion / severe-vibration cases — tailor-made for a
handheld rig. This page is the authoritative config reference for our engine.

═══════════════════════════════════════════════════════════════════════════
## 4. OXFORD DRS — SiLVR: Scalable Lidar-Visual Reconstruction (NeRF-based)
═══════════════════════════════════════════════════════════════════════════
URL: https://arxiv.org/html/2403.06877.pdf  [abstract + key sections read via search]
WHY IT MATTERS: the closest published system to our WHOLE deliverable — handheld (also
drone/legged) LiDAR + 3 wide-FOV cameras -> dense TEXTURED photoreal reconstruction with
geometry on par with LiDAR. Front end = lidar-inertial odometry + SLAM (like ours).
KEY METHOD POINT: a neural (NeRF-family) volume regularized by LiDAR DEPTH + SURFACE
NORMALS — i.e., again, LiDAR constrains GEOMETRY inside a camera-dense method. Their
camera-only baseline (Nerfacto) fails on uniform-coloured ground; adding LiDAR depth/normal
regularization fixes it; vs lidar-SLAM alone they get MORE COMPLETE surfaces from the
dense visual data. Same through-line as CMU: camera densifies, LiDAR disciplines.
CAVEAT: NeRF pipeline (GPU-heavy, offline) — a processing-station workload by definition;
also a novel-view-synthesis representation, so mesh extraction for relighting is an extra
step. Watch this lab; industrial-inspection focus = accuracy culture like ours.

═══════════════════════════════════════════════════════════════════════════
## 5. UNIVERSITY OF MICHIGAN — PeRL (Perceptual Robotics Laboratory)
═══════════════════════════════════════════════════════════════════════════
URL: https://robots.engin.umich.edu/  [lab page read via search]
Our exact sensor triple at scale: NCLT dataset = Segway with Ladybug3 omnidirectional
camera + Velodyne HDL-32E + IMU/FOG/GPS, 34.9 hours / 147.4 km, indoor+outdoor, 27
sessions over 15 months — co-registered 3D lidar + camera imagery for HD mapping.
USE FOR US: a huge public co-registered LiDAR+camera corpus if we ever need test data
beyond our own captures, and a lab lineage (DARPA Urban Challenge team IVS) to mine for
registration practice. NCLT paper: https://robots.engin.umich.edu/nclt/nclt.pdf

═══════════════════════════════════════════════════════════════════════════
## 6. ZHEN, HU, LIU, SCHERER (CMU) — Joint-Optimization LiDAR-Camera Fusion
═══════════════════════════════════════════════════════════════════════════
URL: https://arxiv.org/pdf/1907.00930  [abstract + intro read via search]
Offline dense-model builder: JOINTLY solves bundle adjustment + cloud registration to
compute camera poses AND the LiDAR-camera extrinsic together. Result: ~2.7mm average
accuracy, ~70 points/cm² density vs survey-scanner ground truth; the joint extrinsic
beats target-based calibration, and is most sensitive along the camera's optical axis.
RELEVANCE: we use a FIXED vetted extrinsic (R 85.54°, |t| 0.169m). For hero captures, a
per-capture joint refinement pass could tighten image-to-geometry registration beyond the
fixed value. Offline method — again a processing-station workload. Not urgent; banked.

═══════════════════════════════════════════════════════════════════════════
## 7. LGFaware-meshing (2025) — the honest state of sparse-LiDAR meshing
═══════════════════════════════════════════════════════════════════════════
URL: https://www.tandfonline.com/doi/full/10.1080/10095020.2025.2502481  [read via search]
An online LiDAR mesh-reconstruction method whose own limitations section concedes that
ALL current methods (theirs included) fail to fully reconstruct mesh in SPARSE point-cloud
regions and at edges. Their named future-work exits: (1) deep-learning DEPTH COMPLETION to
densify, (2) fusing MVS point clouds from images. => Our holey mesh is a recognized
frontier problem, and the two documented exits are both CAMERA-DRIVEN densification.
(Their eval used R3LIVE + KITTI datasets — standard corpora, links in the article.)

═══════════════════════════════════════════════════════════════════════════
## THE THROUGH-LINE (the strategic takeaway, stated once)
═══════════════════════════════════════════════════════════════════════════
Every serious lab fuses the camera into the GEOMETRY, not just the paint:
  - CMU: LiDAR primes MVS depth; camera densifies; graph-cut makes it watertight.
  - SiLVR: LiDAR depth/normals regularize a camera-dense neural volume.
  - LGFaware: names depth-completion / MVS densification as the only exits from sparse holes.
  - Joint-opt: even the EXTRINSIC improves when solved jointly with camera poses.
Our current architecture (LiDAR-only geometry -> trimmed-Poisson -> camera texture) is
sound and proven to 92.5%; the research points to camera-assisted densification as the
NEXT quality tier when/if trimmed Poisson + multi-view capture tops out. FLAGGED for
operator decision (7S) — not adopted. It does not violate the accuracy mission: densification
anchored to measured LiDAR is disciplined interpolation, not photogrammetry guessing.

NOT YET EXPLORED: DARPA SubT reconstruction stacks; MIT; deep depth-completion tooling.

═══════════════════════════════════════════════════════════════════════════
## 8. OPERATOR-SOURCED BLOCK, VETTED (2026-08-23) — sync/projection/colorization notes
═══════════════════════════════════════════════════════════════════════════
A pipeline summary the operator surfaced was vetted against the Master. Verdicts:
- ⚠️ WRONG FOR OUR RIG — "match hardware-synced header stamps": (a) nothing on our rig is
  hardware-synced (B0578 = USB2 UVC, NO trigger pin — that absence is WHY tau exists);
  (b) header-stamp matching is the exact bug already fixed: Point-LIO odom header stamps
  are FROZEN -> 0/423 matches; the matcher matches on BAG-RECORD time (§6 gotcha).
  Do NOT reintroduce header-stamp matching.
- ✓ CORRECT, ALREADY BUILT — projection math (p_c = R·P + T; u = fx·xc/zc + cx, v = fy·yc/zc + cy)
  is exactly our fusion node / compose_world_to_cam, verified to 1e-16 with vetted K + extrinsic.
- △ ALREADY DOWNGRADED — "assign RGB to 3D point -> colored point cloud" = per-point colour
  (Way A): plumbing proven, quality = sparse dots, preview-only. Deliverable = mesh + TEXTURE (7H).
- ✓ ALREADY BANKED — eorua8801/unitree-lidar-slam: config-comparison reference only
  (theirs lidar_type 1 / scan_line 4; ours 5 / 18). Not an engine.
- ★ NEW + VERIFIED (fetched 2026-08-23) — unitreerobotics/point_lio_unilidar: Unitree's
  OFFICIAL Point-LIO adaptation for L1/L2 (v2.0.2, 2025). ROS1 Noetic (we run point_lio_ros2 on
  Humble) -> config reference, not drop-in. Independently confirms: fixed-name PCD/scans.pcd save
  path (our overwrite gotcha) + keep-lidar-stationary-first-seconds (our dead-still-init rule).
  ASSET: OFFICIAL L2 SAMPLE BAGS downloadable (indoor + park) — known-good reference data to
  separate "our capture is bad" from "our code is bad":
    https://oss-global-cdn.unitree.com/static/L2%20Indoor%20Point%20Cloud%20Data.bag
    https://oss-global-cdn.unitree.com/static/L2%20Park%20Point%20Cloud%20Data.bag
  Official docs portal: https://support.unitree.com/home/en/developer
- ? UNVERIFIED — MDPI Symmetry 12(2):324 and arXiv 2606.19675: not yet read; low priority.

═══════════════════════════════════════════════════════════════════════════
## 9. UNREAL ENGINE DEEP DIVE (2026-08-23) — LiDAR specs, camera specs, fusion path
═══════════════════════════════════════════════════════════════════════════
Sources READ: official UE5.8 LiDAR plugin docs (dev.epicgames.com), RealityScan help +
release notes (realityscan.com / rshelp.capturingreality.com), Mandalorian/StageCraft
coverage (unrealengine.com, ILM, frame.io), VP-studio scan workflow (myndworkshop.com).

### LiDAR PLUGIN — THE ACTUAL SPECS (UE5.8 official docs)
- SUPPORTED FORMATS: .xyz/.pts/.txt (ASCII: "X Y Z" in METERS, or "X Y Z R G B"; float or
  scientific notation), .las/.laz (8/12/16-bit; .laz compressed = slower import), .e57.
  *** .PLY IS NOT IN THE TABLE — our 7Q-era note ".ply imports" is WRONG/outdated. ***
  => EXPORT TARGET for our clouds = ASCII .xyz-RGB (Open3D one-liner) or .las (laspy).
  (Forum evidence of import friction even with listed formats on UE5.6 — test a small file first.)
- SCALE: import converts meters -> UU at 1UU=1cm (custom Import Scale in Project Settings);
  export converts back. Dimensional truth survives natively.
- PERFORMANCE: governed by a GLOBAL POINT BUDGET (max points displayed; saves VRAM+fps,
  not total RAM). Streaming: only headers load up front, bulk streams on demand. Epic's own
  benchmark: Montreal city LiDAR ~8.9 BILLION points / 253GB on disk ran 120fps at a 1M-point
  budget in ~3.5GB RAM. Our 3.4M-pt room is trivial at this scale.
- TOOLS: Lidar Clipping Volume actors (<=16/level, clip inside/outside, priority) — clean way
  to hide our displaced-cluster garbage IN-ENGINE without touching source data. Per-cloud
  collision build -> walk the scan like a level. Runtime insert/remove supported (LOD caveats).

### CAMERA SIDE — HOW "CAMERA SPECS" WORK IN UNREAL
- Photos do NOT enter raw; they arrive baked onto the mesh as texture (7F pipeline).
- CineCameraActor = PHYSICAL camera model: filmback (sensor mm) + focal length (mm).
  Our calibration maps directly: B0578 OG02B10 = 1/2.6" (~5.76mm wide @1920px);
  fx 848.76px -> physical focal ~ fx*sensor_w/img_w ~= 2.55mm (consistent with ~2.8mm EFL
  in hardware table). => we can build a virtual camera that SEES LIKE OUR RIG, and later
  virtual cameras matching shoot glass. This is "predictively accurate" in engine terms.

### THE FUSION PATH (resolved): FUSION HAPPENS UPSTREAM; UNREAL RECEIVES THE RESULT
Two tracks = our #3 synthesis exactly:
- MESH-FOR-LIGHT (deliverable): RealityScan is the purpose-built fuser. Docs confirm:
  auto registration/filtering/coloring/texturing/meshing of LiDAR, no scan-count limits,
  mobile LiDAR alignable with photogrammetry; input mixing is native (images + LiDAR +
  depth cams -> internal .lsp, then treated like images). RealityScan 2.1 added SLAM-DATA
  IMPORT (our Point-LIO output IS SLAM data) + classified point clouds; help index lists
  "re-color/texture LiDAR scans using images" and "reconstruct scene parts INVISIBLE to
  LiDAR scanners" (= the camera-densification through-line, shipped commercially).
  Engine-side delivery: optimized meshes + baked maps via the UE Photogrammetry Importer.
- POINTS-FOR-TRUTH (reference): raw Point-LIO cloud via the LiDAR plugin (Epic aims it at
  set designers aggregating 3D models with laser-scanned data).

### INDUSTRY PROOF (known path, not a bet)
- Mandalorian/StageCraft: >50% of S1 shot in UE-driven LED volume; VFX supervisors scan
  sets as STANDARD OPERATING PROCEDURE; scanned environments are relit/manipulated as if
  fully CG. (frame.io interview w/ Zero VFX; unrealengine.com; ILM.)
- VP studios document the exact chain: LiDAR+photogrammetry scan -> mesh -> Unreal ->
  VIRTUAL LIGHTING of the scanned model (myndworkshop's Central Park rock face = our barn
  shot in miniature). Indie-scale proof: music-video teams take raw point clouds into UE
  for real-time rendering (nofilmschool).

### CONCRETE NEXT-SESSION PATH (banked so it isn't re-derived)
1. Export fusioncap cloud as ASCII .xyz-RGB or .las (NOT .ply / NOT .pcd).
2. Cloud-GPU machine (Vagon/Shadow, 7Q) + UE5 + LiDAR plugin -> drag in -> verify 1UU=1cm
   against a tape-measured dimension -> walk the room. = MILESTONE ONE.
3. (Processing station track) capture cloud + posed images -> RealityScan (SLAM import) ->
   fused textured mesh -> UE Photogrammetry Importer -> Lumen/path-tracer relight.
MASTER CORRECTION PENDING: 7Q ".ply" -> ".las/.laz/.e57/.xyz-pts-txt (NO .ply)".
