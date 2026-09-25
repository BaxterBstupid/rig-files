<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.69, 2026-09-24) ***** -->
<!-- *** THE CLEAN COMPRESSED CAPTURE HAPPENED — AND PASSED THE VISUAL GATE.        -->
<!-- ***   Capture 114136 (2026-09-24) produced the first full-ring 360 FUSED        -->
<!-- ***   PANORAMA: real photo colour on LiDAR geometry, all the way around the      -->
<!-- ***   room (77.7% coloured, 306° heading, 35 frames, ONE clean bag). The image   -->
<!-- ***   reads as the real room in real colour and the colour LANDS on the          -->
<!-- ***   geometry. Every blocker the Master 20.13.68 header named is now cleared.    -->
<!-- -->
<!-- *** WHAT THIS CERTIFIES (new): (a) compressed capture + a MOVING odom work end    -->
<!-- ***   to end on hardware — dense odom, no hole, 309° pan with 60×87 cm parallax,  -->
<!-- ***   95% poseable; (b) the EXTRINSIC is real-world CORRECT — colour registers    -->
<!-- ***   on geometry across 306°, not just a checkerboard wedge (closes the          -->
<!-- ***   long-open "extrinsic code-verified, real-world UNCERTIFIED" item).          -->
<!-- -->
<!-- *** THE RATIFIED REPEATABLE PROCESS is its own doc: GOLDEN_360_FUSED_RECIPE.md   -->
<!-- ***   (every step, every tool md5, the reproduction targets, the visual gate).    -->
<!-- ***   NEXT STEP: RE-RUN THE EXACT SAME PAN (rig has not moved) FOLLOWING THAT     -->
<!-- ***   RECIPE AND CONFIRM THE IMAGE REPRODUCES. Then move on (geometry branch →    -->
<!-- ***   Unreal walkable; optional exposure-equalization pass for the 360 seams).    -->
<!-- -->
<!-- *** FULL PRIOR LINEAGE (ADR-001, ADR-002, the 20.13.68→20.13.33 session layers,  -->
<!-- ***   and the STAGE 1–7 RealityScan→UE5 recipe) IS PRESERVED VERBATIM in          -->
<!-- ***   MASTER_REFERENCE_20_13_68_.md — read it for the ADRs and history. This      -->
<!-- ***   20.13.69 layer folds ON TOP of it (Stone Clause: additive, nothing lost).  -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ 20.13.69 — THE 360 FUSED PANORAMA PASSED THE VISUAL GATE (capture 114136)  ⭐
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**The image exists.** For the first time the whole chain — capture → geometry → anchor →
photo colour — produced a picture that passes the eye: a full-ring 360 of the room, in
real colour, colour landing on the geometry, all the way around. The rule is honored:
*progress is the image, not the numbers* — and the image is good.

## THE PROVEN RUN (114136, 2026-09-24) — every number, for reproduction

- **Bag:** `plio_texcap_20260924_114136`, 87.4 s.
- **Camera:** `/camera/image_raw/compressed` (compressed fix live), 2047 frames.
- **Odom:** 1,700,640 msgs on `/aft_mapped_to_init` @ ~20 kHz — **dense, NO hole** (the
  raw-recording 127 s hole is dead).
- **Motion:** heading swept **309°**; translation **60 × 87 × 4 cm** — a real pan WITH
  parallax, not single-vantage. (`check_pan_heading.py` → VERDICT: PAN PRESENT.)
- **Anchor:** `make_full_pan_anchor.py` → **95% poseable** (1941/2047), **35** frames
  spread by HEADING (306° coverage), `panbundle.tar.gz` ~10 MB.
- **Cloud:** `scans_20260924_114136.pcd`, 2,038,351 pts (x y z intensity + normals).
- **Fusion:** `fuse_pano.py` → **77.7%** of the cloud coloured → the full-ring 360 PNG
  (`pano_360_fullring_114136.png`). Reproduced byte-for-byte in coverage by the canonical
  tool (only the debug title differs).

## THE RATIFIED PROCESS

The meticulous, step-by-step, md5-locked **repeatable process** lives in
**`GOLDEN_360_FUSED_RECIPE.md`** (banked alongside this file). It is the "do it again"
list: machine division, fixed calibration, the 6 steps (one command each), the
reproduction targets, the known-good blemishes, and the visual acceptance test. Follow it
exactly; the next pan should be a REPEAT, not a re-derivation.

## NEW CANONICAL TOOLS (born on 114136, md5-locked, banked to the project)

- **`make_full_pan_anchor.py`** (`f015c4a746cd2347b7d7ca11192ef1fe`, Jetson) — exports a
  HEADING-spread posed-frame bundle from ONE bag (fixes the old time-spread selection that
  gave a single-heading wedge). Pose math verbatim from `pointlio_pose_matcher.py` v2.
- **`fuse_pano.py`** (`f028ac3d7b2bfcbd18d82f64d64ece8c`, station) — self-contained,
  calibration-embedded full-ring render (occlusion-gated best-camera projection →
  equirectangular). The step that passed the gate. **Never run on the Jetson.**
- **`check_pan_heading.py`** (`20af111e90eff4abf1696aee62143a63`, Jetson) — read-only
  pan-confirm: does the bag's odom actually sweep heading + translate? The pre-export gate.

Prior-session tools still canonical: `rig_start_compressed.sh` (`10b2bb66…`) +
`rig_camera_compressed.py` (`446e6b5a…`) for compressed bringup; `capture_walk.sh`
(`46a4bd7e…`) wrapping the in-place-edited `capture_pointlio_texture.sh` for the hands-off
pan; `pointlio_pose_matcher.py` v2 (`6827341d…`) as the pose-math source of truth.

## WHAT IS NOW CLOSED vs STILL OPEN

- **CLOSED:** compressed capture + moving-odom (proven on hardware); the anchor→colour
  fusion (a real full-ring image); the EXTRINSIC's real-world certification (colour lands
  on geometry across 306°). Master 20.13.68's entire "NEXT STEP: clean capture" premise is
  satisfied.
- **STILL OPEN:** (1) REPRODUCE 114136 from the recipe (the point of this bank — prove it's
  repeatable, not a one-off); (2) the geometry branch to a walkable/relightable Unreal
  asset (`planar_shell` shell + occlusion-gated texture bake on the STATION, then the
  preserved STAGE 1–7 UE recipe in _68); (3) optional: exposure-equalization pass to remove
  the 360's teal auto-exposure seams (cosmetic; a render pass, not a capture problem).

## HONEST BOUNDARIES (do not overclaim)

- This artifact is a **360 FUSED PANORAMA** (colour on the point cloud), the *see-what-we-
  captured* proof — **NOT** yet the walkable Unreal mesh. It certifies the capture is good
  enough to build one; building it is the next arc.
- **Known-good blemishes** (expected, not failures): teal/cyan exposure seams between
  frames; grayscale caps straight up/down (level pan + L2 blind cones). See the recipe §6.

## SESSION LOG LINE
- **2026-09-24:** Confirmed the 114136 bag holds a real 309° pan + parallax (not single-
  vantage). Built + md5-locked `make_full_pan_anchor.py` (heading-spread anchor export) and
  `fuse_pano.py` (self-contained full-ring render); exported 35 heading-spread frames,
  fused onto the 114136 cloud → the first full-ring 360 (77.7% coloured) — PASSED the visual
  gate. Certified the extrinsic in the real world (colour on geometry across 306°). Banked
  the repeatable process as `GOLDEN_360_FUSED_RECIPE.md`. NEXT: reproduce the same pan from
  the recipe, then take the geometry branch to Unreal.

<!-- ============================================================================ -->
<!-- ##  END 20.13.69 LAYER. FULL LINEAGE (ADRs + 20.13.68 → earliest + the        ## -->
<!-- ##  RealityScan→UE5 recipe) IS IN MASTER_REFERENCE_20_13_68_.md, VERBATIM.     ## -->
<!-- ============================================================================ -->

═══════════════════════════════════════════════════════════════════════════
## 11. DRIFT FINDING + RS PIVOT (2026-09-24, capture 141733 repro)
═══════════════════════════════════════════════════════════════════════════
- **Reproduced the golden recipe on a 2nd pan (141733): every tool NUMBER passed, but the
  IMAGE failed the eye** — features REPEAT (one window rendered 3×) and areas are missing.
  Progress is the image (P1): the numbers lied, the picture told the truth.
- **Root cause = Point-LIO HEADING DRIFT on a pan-in-place.** THREE independent signals:
  (a) panorama places the same wall/window at multiple azimuths; (b) top-down floor plan
  shows the room's walls as several ROTATED copies fanning around the camera; (c) wall-
  normal azimuth histogram is nearly FLAT (top-4 bins ~15% vs >55% for a clean rectilinear
  room). A pan = rotation with ~no translation and no loop closure → heading rotates off
  true over the sweep → the LiDAR MAP is built BENT. (141733: 275° sweep, ~1.3 m
  translation, still drifted.) NOTE: "photos out of order" is not a photo-order bug — the
  photos are linear/clean; the panorama places by (drifted) HEADING, so the same direction
  lands twice.
- **OPERATOR RULING (ratified): do NOT solve this by forbidding pans.** Pans are natural in
  any capture; the pipeline must ACCEPT rotation. The cure is a GLOBAL optimizer (loop
  closure / bundle adjustment) that solves all poses jointly — NOT incremental odometry.
  The earlier "traverse must translate" rule (§4/§5) treats the symptom; the disease is
  odometry-only mapping with no global correction. This SUPERSEDES the pan-avoidance framing.
- **RS PIVOT (operator + assistant, as a mutual second opinion):** take photos + LiDAR to
  RealityScan; RS's bundle adjustment is a global camera-pose optimizer, robust to the
  motion that breaks Point-LIO.
  - RESERVATION 1 (load-bearing): **RS refines CAMERA poses; it does NOT de-drift the LiDAR
    MAP.** A single pre-merged drifted cloud is treated as rigid — lock to it and RS
    textures a 3-window mesh. So for THIS bag, let RS build/align from the PHOTOS and use
    LiDAR for SCALE, not as locked geometry (a forced inversion of lock-photos-to-LiDAR).
  - RESERVATION 2: photogrammetry needs parallax; a pure pan gives little — the same
    rotation weakens RS's own triangulation (~1.3 m translation helps, isn't a lot).
  - RESERVATION 3: RS is a black box; its mesh gets the same visual gate ("built a mesh"
    ≠ "built a correct mesh").
- **RS INPUT = rs_export.py (Jetson):** dense OVERLAPPING undistorted keyframes (every
  ~6th, ~324) + intrinsics.txt + cloud.ply (scale). PLAN: align photos FROM SCRATCH first
  (RS BA = the independent second opinion), then bring the cloud in for scale/geometry.
  scp the rs_<time>/ folder Jetson→Shadow (Tailscale).
- **STANDING GAP for the deliverable pipeline:** a mapping backend robust to rotation
  (loop closure / global BA over LiDAR+photos) is the real missing piece. RS tests the
  camera-BA half; the LiDAR-map half (de-drifting from raw per-scan clouds) remains open.

═══════════════════════════════════════════════════════════════════════════
## 12. PAN-DRIFT ROOT-CAUSE AUDIT — IMU IS CLEAN; SUSPECT IS POINT-LIO INIT (2026-09-24)
═══════════════════════════════════════════════════════════════════════════
Full capture->RS audit (/engineering:code-review + /engineering:debug) on 141733.

CLEARED (NOT the cause):
- camera path (separate from Point-LIO); the photos (RS aligned 99%).
- IMU HARDWARE — proven CLEAN by a 30s DEAD-STILL recording (imu_static30): rate 251 Hz,
  no dropouts, monotonic stamps, accel |a|=9.62 m/s^2 (correct units), and INTEGRATED
  GYRO OVER 30s STILL = 0/0/0 deg (noise +/-0.01-0.03 rad/s). NO standing gyro bias.
- Point-LIO config sane (topics, extrinsic ~identity, acc_norm 9.81, imu_time_inte 0.004).

RETRACTED (my error, logged honestly): mid-audit I claimed a ~1.3 deg/s gyro bias from the
pan's 118 deg gyro-integral vs -5 deg odom net-yaw. The dead-still test DISPROVES it — bias
~= 0. The 118 was real hand motion (per-axis integrals of a 3D rotation are not a clean
net-angle). Rule re-logged: confirm the sensor AT REST before blaming it.

STILL THE FACT: a pan makes a fanned/rotated map ("3 windows"). IMU cleared -> the fault is
HOW POINT-LIO USES the good IMU during rotation. Leading suspect:
- MOVING-START INIT. Config start_in_aggressive_motion:false needs a near-static start to
  estimate gravity + initial state. Gravity is on BODY-X here (accel x~8.9), so gravity
  direction MUST be found at rest. capture_walk v4 began motion instantly ("WALK NOW") ->
  gravity/state init corrupted -> tilted world frame -> rotation mistracked -> fan. Directly
  testable and most likely.
- SECONDARY (if static-init doesn't fix it): LiDAR-IMU time-sync (time_lag_imu_to_lidar 0.0
  / per-point stamps) or whether the IMU is actually being fused under fast rotation.

THE FIX UNDER TEST: capture_walk_v5.sh (md5 17fa81edf715525626e28d041533ffdb) ENFORCES a 12s
dead-still init, THEN a stop-and-go pan (rotate ~20deg, STOP ~2s). Validate with the drift
gate (wall-normal azimuth histogram: top-4 bins >55% of wall points = clean rectilinear
room; ~15% = still drifting). Clean => init was the cause. Still fanned => dig into
LiDAR-IMU time-sync / IMU fusion. CEILING: truly arbitrary continuous pans want loop closure.

TOOLS (delivered): imu_audit.py (config dump + IMU rate/units/dropout + integrated-gyro vs
odom-net-yaw; note: its odom cross-check errors on an IMU-only bag — harmless).

═══════════════════════════════════════════════════════════════════════════
## 13. GOVERNING CAPTURE SOP — THE 9-STEP METHOD (ratified 2026-09-24)
═══════════════════════════════════════════════════════════════════════════
Every capture runs through the 9-STEP METHOD (source: rig-files/CAPTURE_METHOD(2).md;
mapped to the compressed pipeline in claude/CAPTURE_METHOD_9STEP_SOP.md). The STEPS +
GATES are invariant; the script in a slot may change. 0 Preconditions (START RIG up,
coverage plan) · 1 Launch · 2 Pre-flight gate (/unilidar/cloud) · 3 Clean slate ·
4 DEAD-STILL IMU init → wait `IMU Initializing: 100.0%` (the gate 141733 dropped) ·
5 Capture (stop-and-go, settled start) · 6 one Ctrl-C · 7 four stops (bag→PLIO→verify→
success) · 8 artifacts · 9 verify + drift gate. NON-NEGOTIABLE gates: STEP 2, STEP 4,
STEP 7. The 141733 drift = running OFF this method (skipped Start Rig; fork dropped the
STEP-4 gate; continuous "WALK NOW"). Assistant presents every future capture AS these
steps, in order, from STEP 0 — never jump to "run the capture."
