<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.77, 2026-10-05) *****            -->
<!-- Additive layer on 20.13.76 (Stone Clause: nothing lost).                            -->
<!--   20.13.76 holds: moving-bag dry run on Shadow, VII-C time-base RESOLVED, tau bag    -->
<!--     must be handheld, Jetson→Shadow Taildrop path.                                   -->
<!--   20.13.75: Shadow stood up as the Windows/Anaconda station. 20.13.74: profile-load,  -->
<!--     pad self-start, shutter angle/speed. 20.13.70: triad, re-solve-first, kiss-icp,    -->
<!--     the 141733 drift finding (I-C) + IMU-clean audit (I-D). 20.13.68: ADRs + UE recipe.-->
<!-- THIS 20.13.77 LAYER banks the GEOMETRY ROOT-CAUSE work of 2026-10-01 → 10-05:        -->
<!--   the fused pano failed the eye → the top-down showed a BENT cloud → the Masters      -->
<!--   were read end to end → three deep research sweeps → bag_health.py MEASURED the      -->
<!--   fan on 141733 → the golden walk 180551 rendered as a CLEAN FLOOR PLAN = the         -->
<!--   CONTROL IMAGE. The defect is boxed: Point-LIO's handling of ROTATION-IN-PLACE.      -->
<!--   Decision record: ADR-004. Rig state: L2 OFF. Jetson coming up for an OFFLINE        -->
<!--   re-solve only — no capture.                                                         -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  🖼️ THE CONTROL IMAGE — `topdown_walls_180551.png` (on the Project file page, permanent)
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

The top-down of `fusioncap_180551_scans.pcd` (the golden translating walk, 2026-09-04) is a
**floor plan**: straight walls, square corners, single lines, no arcs, no doubling — the
rectangular room with its doorway, the long object along its left wall, two more rooms through
the openings, all at one consistent angle (the ~35° tilt is only the start heading in the map
frame). 12.5 × 13.9 m, z-range −1.94..+1.59 m — a real room's height, no flyers.
Operator: "This is a fantastic step forward."

Beside it, the top-down of `scans_20260924_141733.pcd` (the stand pan, 2026-09-24) is a tangle:
a wall bowed into an arc, diagonal smears, an 11–13 m irregular footprint, z-range −17..+28 m.
Operator, sitting in the room: "It's a stretch to say I recognize anything."

**What the pair proves.** The rig, Point-LIO, and even the live loaded Jetson produce clean
geometry **on a walk**. The only thing 141733 did differently was **rotate in place**. That is
the whole defect, boxed — and `bag_health.py` measured it (IX-C).


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART IX — 2026-10-01 → 10-05 (geometry root cause: method, findings, ADR-004) ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## IX-A. THE METHOD (what led to the image — reuse this sequence)
═══════════════════════════════════════════════════════════════════════════
The sequence that turned "the pano looks wrong" into a measured, boxed defect, in order.
Every step was ONE command, pasted back, before the next. Nothing was argued that could be
measured. Rig OFF throughout.

1. **The eye first.** The fused 360 of 141733 (88.5 % coloured, 275° — every NUMBER passed)
   showed the window twice, the mantel missing, the frame cut off. The operator's verdict:
   "far, far from what we need." The numbers lied; the picture told the truth (P1).
2. **Separate colour from geometry with a render the camera cannot touch.** `top_down.py`
   rasterizes `scans.pcd` only — LiDAR points, no camera pixel in it — so a bent wall there
   is odometry, full stop. The 71 MB pcd was "too large" to upload; the tool runs on Shadow
   and ships a 150 KB PNG. (Shutter/exposure were cleared by construction, not by debate.)
3. **Read the lineage end to end before researching.** 20.13.76/75 in full, then 20.13.70
   §I-C/I-D/II-B/II-D/II-G/II-H, RESEARCH 09-25, the 9-STEP SOP, the golden recipes, the L2
   manual. Found: the 141733 fan was already recorded on 09-24 (I-C); its fix-under-test
   (`capture_walk_v5`) was never run; the 15 s init was only validated static; 141733 is a
   `plio_texcap_` bag with NO `/unilidar/cloud` → not re-solvable.
4. **Deep research, primary sources only, three parallel sweeps.** (a) Point-LIO + Unitree
   fork + ROS2 port: configs, source, issues; (b) the L2 driver — README, ROS2 node source,
   and the closed SDK library DISASSEMBLED (x86_64 + aarch64) to learn how it stamps time;
   (c) offline-solver landscape with Windows/pip status verified on PyPI. Load-bearing
   claims re-verified by hand in the cloned source before being written down.
5. **Autopsy the bag itself: `bag_health.py`.** Reads `/unilidar/imu` + `/aft_mapped_to_init`
   (+ cloud if present): IMU host-stamp jitter, |acc| sanity (the documented L2 #9 fault),
   odom continuity, and — the decisive part — integrates the gyro on SO(3) and compares
   it to Point-LIO's orientation over the whole capture. Validated on synthetic bags first
   (tracked → ratio 1.000; injected 15 % under-rotation → 0.850, 4° tilt caught).
6. **A control image.** Render a cloud the Masters already certified clean (180551, 10–11 mm
   planes, square walls) with the SAME tool. One picture of "clean" next to one of "bent"
   calibrates the eye and boxes the variable (walk vs pan).
7. **Write the decision as an ADR before touching the rig** (ADR-004), with the one capture
   designed to discriminate the remaining mechanisms — and a no-capture experiment first.

═══════════════════════════════════════════════════════════════════════════
## IX-B. TOOLS DELIVERED (md5-locked; all three banked in the project `claude/`)
═══════════════════════════════════════════════════════════════════════════
| Tool | md5 | What it does | Machine |
|---|---|---|---|
| `top_down.py` | `8b9ae4d72784c15ace35fe6b5f0e391a` | log-density floor-plan raster of a `scans.pcd` (wall band + all points); one crisp outline = clean, arcs/doubles = drift | Shadow (rigstation) |
| `bag_health.py` | `817b9a8bcfe267ce0223286a86e73da1` | read-only bag autopsy: topics/re-solvable?, IMU jitter, \|acc\|, cloud timeline, odom continuity, **gyro-vs-odom heading** + PNG | Shadow (rigstation) |
| `ADR-004_geometry_drift_root_cause_and_solve.md` | `cdcb8fdf6e523d1bf0addd52ad27c33e` | the research, ranked root causes with sources, the decision, the gated plan | project + Desktop |

Run forms (Anaconda Prompt, `conda activate rigstation`; scripts land in `Downloads`):
`python C:\Users\Shadow\Downloads\top_down.py <scans.pcd> <OUT_DIR>` ·
`python C:\Users\Shadow\Downloads\bag_health.py <BAG_DIR> <OUT_DIR>` · outputs copied to the
Desktop for upload (house rule).

═══════════════════════════════════════════════════════════════════════════
## IX-C. THE 141733 AUTOPSY — measured (bag_health, 2026-10-01)
═══════════════════════════════════════════════════════════════════════════
- **Not re-solvable:** topics = odom (1,876,395 msgs @ ~20 kHz), compressed camera (1943),
  IMU (22,670). No `/unilidar/cloud`. Only the live Point-LIO result exists.
- **IMU on the live Jetson was CLEAN:** 251.3 Hz; header dt p1/p50/p99 = 2.86/3.98/5.17 ms,
  max 13.4 ms; 4 gaps, ~8 samples missing (0.04 %); |acc| 9.48–9.77, max 10.60 — no #9 fault.
- **Dead-still start:** first 3 s mean |gyro| 0.60 °/s. (Corrects the lineage: 141733 did
  NOT drop the STEP-4 gate.) The pan was stop-and-go: per-10 s mean |gyro| 1.2/7.6/7.0/12.0/
  1.5/4.0/3.1/8.9/2.5/0.4 °/s, p99 35 °/s, max 43 °/s — out-and-back, true range 216°,
  net +126.6°.
- **Point-LIO's heading did not track the rig.** odom/gyro per 10 s: −6/−6 (agree) →
  −110/−68 → +5/−3 → +152/+112 → +84/+101 → **−77/+64** → −41/+63 → +128/+148 → **−4/+127**.
  Divergence up to 157°. The first 10 s agree (frames and conventions validated); then the
  estimate **over-rotates ~40 % on every turn** and runs away — 160° back when the rig turned
  37°. Odom tilt wander 3.4°, z ±6 cm, no silences. Not timing (35 °/s × 10 ms = 0.35°).
- **Retracts the 09-24 retraction:** "118° gyro vs −5° odom" was real. The rig ended ~127°
  from its start heading; Point-LIO thought it was back near 0°.

═══════════════════════════════════════════════════════════════════════════
## IX-D. WHAT THE RESEARCH ESTABLISHED (full citations in ADR-004)
═══════════════════════════════════════════════════════════════════════════
- **The Unitree ROS2 driver host-stamps everything at parse time** (`use_system_timestamp`
  true; IMU stamp = Jetson `CLOCK_REALTIME` when parsed; cloud stamp = now − scan_period;
  1 ms wall timer; per-point `time` across a frame's 18 packets = host arrival differences;
  internal buffer silently cleared over 5000 bytes). On 141733 the IMU path was nonetheless
  clean → this mechanism is DOWNGRADED for the IMU; the cloud path stays unchecked.
- **Point-LIO drifting/rotating on the L2 at low/no motion is a known, OPEN, L2-specific
  problem:** point_lio_unilidar #21 ("even if I don't move the lidar, the aft_mapped frame
  keeps rotating"), #22, #20; dfloreaa/point_lio_ros2 #5 (maintainer: "unless a lot of
  static, close-by points are found during startup… the odometry will start to drift and
  rotate around"; FAST-LIO "significantly reduced" drift on the L2); glim #248; sdk2 #27.
- **The config we run:** `publish_odometry_without_downsample: true` (→ the 20 kHz per-point
  odom + a TF per point group); `init_map_size 10` = points, i.e. the first scan; gravity
  from 100 IMU frames = 0.4 s; gyro bias not seeded; `imu_meas_omg_cov 0.1` (gyro trusted to
  ±18 °/s), `gyr_cov_output 1000`; filter sizes 0.1 (dfloreaa launch) vs 0.4 (Unitree v2.0.2)
  — effective values unknown until `ros2 param dump /laserMapping`.
- **Sharpened root cause:** the IMU is good and the live solver barely used it; rotation was
  decided by matching ~5 k sparse hemispherical points against a map already holding the
  previous mis-rotated scans — and it snowballed. First-pass fix to TEST: `use_imu_as_input: 1`
  (Unitree's own launch comment), FAST-LIO2 and GLIM as second/third opinions.
- **Closed by sources/data:** constant IMU–LiDAR offset (3 °/s × 100 ms = 0.3°), extrinsic
  rotation (manual: axes parallel; our level maps + gravity on X agree), LI-Init (ROS1-only,
  no Unitree type, needs 3-axis excitation), the shutter, the IMU hardware.
- **Mount geometry (disputes II-H):** the L2 hemisphere is "above the radar" (+Z); our camera
  extrinsic puts LiDAR +Z ≈ camera forward (`R_L2C[2][2] = 0.989`), +X up. The L2 sees the
  FORWARD half-space; zenith/nadir sit on the rim (hence the grayscale pano caps). A static
  vantage cannot see behind the rig → pans/walks are mandatory for coverage.
- **Station limits:** Shadow forbids virtualization (no Docker/WSL2 → no Point-LIO/GLIM on
  Shadow). KISS-ICP 1.3.0 is native (default voxel 1.0 m is wrong indoors → 0.25 m / 20 m).
  KISS-SLAM: no Windows wheel and its loop closure fires on TRANSLATION only — useless for
  pans. GLIM: Jetson Orin / JetPack 6.1 supported natively, `glim_rosbag` offline,
  overlap-based keyframes (no translation needed).

═══════════════════════════════════════════════════════════════════════════
## IX-E. ADR-004 — THE DECISION (Proposed; Accepted on the eye)
═══════════════════════════════════════════════════════════════════════════
- **D1.** The live Point-LIO result is no longer the geometry of record. Geometry of record =
  an **offline solve of a RAW bag** (cloud + imu + compressed camera). At capture the Jetson
  runs driver + camera + recorder only — no live Point-LIO, no browser, kiosk render on Shadow.
- **D2.** The Jetson is the offline Linux solver when it is not capturing (L2 OFF, nothing
  else running): `ros2 bag play --rate 0.5` into Point-LIO, SIGINT → `scans.pcd`. Shadow
  keeps everything Windows-native (`bag_health`, `top_down`, KISS-ICP cross-check, anchor,
  fusion, archive).
- **D3.** Offline Point-LIO first-pass params: `use_imu_as_input: 1`;
  `publish_odometry_without_downsample: false`; `init_map_size: 1000`; `filter_size_surf 0.1`
  / `map 0.2`; extrinsic unchanged; `extrinsic_est_en: false`. Confirm with `ros2 param dump`.
- **D4.** GLIM on the Jetson = the loop-closure candidate, tried on the same bag.
- **D5.** The first test capture (LATER): on the stand, 15 s dead-still with close-by
  structure in view, slow pan ≥ 300° returning past the start, 5 s still, recorded RAW.
  Four top-downs (Point-LIO default / D3 / KISS-ICP indoor / GLIM) beside the control image.
  The eye picks. All four bent → the raw data itself → next ADR on the driver time path.
- Operator ruling in force: pans are accepted; the pipeline must take rotation.

═══════════════════════════════════════════════════════════════════════════
## IX-F. LINEAGE CORRECTIONS (banked)
═══════════════════════════════════════════════════════════════════════════
1. 141733 had a dead-still start — the "dropped STEP-4 / WALK NOW" explanation is wrong for it.
2. The 09-24 "118° vs −5°" retraction was itself wrong; the discrepancy was real (IX-C).
3. II-H "a static rig sees all four walls" is most likely a misread of sensor-frame azimuth
   with the dome facing forward (IX-D). Decisive check still owed: a top-down of the static
   180728 cloud (its pcd is NOT on Shadow — only `fusioncap_180551_scans.pcd` in
   `Downloads\shadow_bundle\` and `scans_20260924_141733.pcd` in `C:\rig\fusioncaps\`).
4. The GOLDEN_360 "reproduction" (88.5 % / 275° on 141733) was coloured onto a cloud the
   Master had already declared drifted; colour registration does not test geometry.
5. `capture_walk_v5` (the 09-24 fix-under-test) was never run; the 15 s init was validated
   only on a static capture. Rotation + init has never been tested together.

═══════════════════════════════════════════════════════════════════════════
## IX-G. HOUSE RULES REAFFIRMED THIS LAYER
═══════════════════════════════════════════════════════════════════════════
- Images and scripts land on the **Desktop** (chat downloads and Taildrop actually arrive in
  `C:\Users\Shadow\Downloads\` — copy to the Desktop for upload). Anything banked to the
  project is also delivered as a chat download.
- One command per turn; the operator pastes the result before the next.
- Shadow work in the Anaconda Prompt with `rigstation` active (not `base`, not PowerShell).
- The L2 is OFF until a clear command. "Turning on the Jetson" ≠ powering the L2.

═══════════════════════════════════════════════════════════════════════════
## NEXT (carried, in order)
═══════════════════════════════════════════════════════════════════════════
1. **No-capture experiment on the Jetson (L2 OFF):** confirm `fusioncap_080826` (cloud+imu
   complete) and the `point_lio` launch/config exist; re-solve it twice — deployed config vs
   `use_imu_as_input: 1` (+ D3) — two `scans.pcd` → Taildrop → `top_down` on Shadow → beside
   the control image. The eye decides whether the gyro-weighting hypothesis holds.
2. `ros2 param dump /laserMapping` → bank the effective live parameter set.
3. Build + bless `capture_raw.sh` (raw record, no live Point-LIO) for the kiosk CAPTURE slot;
   build `resolve_pointlio.sh` (offline replay). Install GLIM (arm64 PPA); dry-run on 080826.
4. The D5 discriminating pan capture → four top-downs → ADR-004 Accepted.
5. Carried: 180728 static top-down (hemisphere check); TAU-360 handheld (now recorded RAW);
   push the offline toolset to `rig-files`; archive migration; Waveshare; external trigger.

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-10-01:** The 141733 pano failed the eye; the top-down (LiDAR only) showed a bent
  cloud. Read 20.13.76/75 + lineage end to end; three primary-source research sweeps (Point-LIO
  fork/port, the L2 driver incl. SDK disassembly, Windows-native solvers). Built + validated
  `bag_health.py`; on 141733 it showed a CLEAN IMU and a Point-LIO heading that over-rotated
  ~40 % per turn, up to 157° off the gyro — the fan, measured. Wrote ADR-004 (record RAW,
  solve offline on the Jetson; test `use_imu_as_input: 1`; GLIM for loop closure).
- **2026-10-05:** Rendered the golden walk 180551 with the same tool → a clean floor plan =
  THE CONTROL IMAGE (on the Project file page). Defect boxed to rotation-in-place. Operator:
  "a fantastic step forward." Master 20.13.77 written. Jetson coming up for the OFFLINE
  re-solve of 080826 — L2 stays OFF.

<!-- ============================================================================ -->
<!-- ##  END 20.13.77 LAYER. Additive on 20.13.76. Decision record: ADR-004.          ## -->
<!-- ##  Tools: top_down.py 8b9ae4d7… · bag_health.py 817b9a8b… · ADR-004 cdcb8fdf…  ## -->
<!-- ##  Deep lineage (ADRs + STAGE 1-7 UE) in 20.13.68. Stone Clause: nothing lost.  ## -->
<!-- ============================================================================ -->
