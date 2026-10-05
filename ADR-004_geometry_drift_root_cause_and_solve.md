# ADR-004: Geometry drift on pans — root cause ranking and the solve

**Status:** Proposed — becomes Accepted when the two no-rig checks run and ONE re-solvable pan capture passes the eye.
**Date:** 2026-10-01
**Deciders:** operator (eye is the arbiter) · assistant
**Scope:** the LiDAR cloud only. The camera, its shutter and its exposure are not in `scans.pcd` and cannot touch this problem.
**Lineage:** ADR-001 (representation fork), ADR-002 (texture reliability), ADR-003 (RS/UE forward compat), RESEARCH_camera_lidar_IMU_2026-09-25, Master 20.13.70 §I-C/I-D/II-B/II-D/II-G/II-H, 20.13.76.

---

## Context

**What we saw today.** The top-down of `scans_20260924_141733.pcd` is not a floor plan: a wall renders as a curved arc, diagonal smears cross the room, the footprint is 11–13 m and irregular. The operator, sitting in the room, does not recognize it. The floor's dot-grid is coherent; the walls are not.

**What the lineage already knew (read end to end).** This is not a new defect — it is the known one, re-seen:

- 20.13.70 §I-C (09-24): on 141733 "every tool NUMBER passed, but the IMAGE failed the eye — features REPEAT (one window rendered 3×)… top-down floor plan shows the walls as several ROTATED copies fanning around the camera… wall-normal azimuth histogram nearly FLAT." Root cause named then: "Point-LIO HEADING DRIFT on a pan-in-place."
- §I-D: IMU hardware cleared (251 Hz, |a| 9.62, zero gyro bias at rest). Leading suspect: moving-start init. "THE FIX UNDER TEST: capture_walk_v5.sh … 12 s dead-still init, THEN a stop-and-go pan; validate with the drift gate." **That test was never run.** The 09-26 session went to the static/multi-position plan instead, then the Jetson froze 3×.
- §II-G: the 15 s dead-still init produced a "level + undrifted" map on 180728 — **a static capture (0.02 m, 1° yaw)**. So the init fix has only ever been validated on a capture that didn't rotate. Rotation + init has never been tested together.
- §II-B: re-solve-first ratified: "record RAW on the rig, SOLVE OFFLINE." Live Point-LIO + cloud recording + kiosk froze the Jetson. But 141733 is a `plio_texcap_` bag → **no `/unilidar/cloud` → it cannot be re-solved.** Its geometry is the live Jetson result and nothing else.
- §II-H: "a STATIC rig sees the whole horizontal room from one spot." This ADR disputes that (see F5) — it matters because it decides whether pans are optional or mandatory.
- 20.13.76: tau WEAK on 141733 is correct (stand pan is tau-blind); TAU-360 must be handheld. Unchanged.
- GOLDEN_360_FUSED_RECIPE: the 88.5 % / 275° "reproduction" on 141733 was coloured onto a cloud the Master itself had already declared drifted. The pano numbers passed because colour registration doesn't care whether the wall under it is bent.

**Operator ruling in force (09-24):** "do NOT solve this by forbidding pans. Pans are natural; the pipeline must ACCEPT rotation."

---

## Findings from the deep research (primary sources; three parallel sweeps, 2026-10-01)

### F1 — The Unitree ROS2 driver host-stamps everything at parse time, and drops silently under load
- `unilidar_sdk2` ROS2 node: `use_system_timestamp` defaults **true**. With it, the SDK **overwrites** the IMU packet stamp with host `CLOCK_REALTIME` taken when `runParse()` processes that packet; the cloud stamp is `getSystemTimeStamp() - scan_period`. The node runs `create_wall_timer(1 ms)` and parses once per tick. (unitree_lidar_ros2.h; library disassembly, x86_64 and aarch64 identical.)
- A `/unilidar/cloud` frame is 18 packets; **per-point `time` across packets is the host-time difference between packet arrivals**, only the ~2.3 ms inside a packet is sensor time. So host scheduling jitter goes straight into the deskew timeline. Even on Unitree's own PC bag, packet spacing runs 3.67–9.32 ms around a physical 4.63 ms, and IMU spacing p1/p99 is 1.12/2.97 ms around 2.0 ms.
- If the driver's internal byte deque exceeds 5000 bytes it is **cleared and the call returns 0** — silent data loss under backlog (disassembly reading).
- IMU stamps are therefore **arrival times, not sample times**; the sensor's 1 kHz sample clock is never exposed. Point-LIO integrates on these deltas.
- Field reports match: point_lio_unilidar #21 — IMU packets "sent randomly in 2us–100ms intervals. And sometimes 1000x per second instead of 500Hz/2ms intervals."
  Sources: https://github.com/unitreerobotics/unilidar_sdk2 (README, `unitree_lidar_ros2/.../unitree_lidar_ros2.h`, `unitree_lidar_utilities.h`), https://github.com/unitreerobotics/point_lio_unilidar/issues/21

### F2 — Point-LIO drifting/rotating on the L2 at low or no motion is a known, unresolved, L2-specific problem
- point_lio_unilidar **#21 "Severe Drift with Unitree Lidar L2 in Point-LIO"**: "even if I don't move the lidar, the aft_mapped frame keeps rotating and translating around the camera_init frame." Open, no Unitree reply. Another user: "drift of 10m before arrive to the same point of loop closure using L2" vs 10 cm on a Mid-360.
- point_lio_unilidar #22 (ROS2 + drift), #20 "Map tilt" ("No amount of changing parameters has fixed it"), #5 (Unitree staff: "environment degeneration… lower the vibration").
- dfloreaa/point_lio_ros2 **#5** (the port we run), maintainer: "That's a common problem with the PointLIO on the Unilidar 3D LiDARs; **unless a lot of static, close-by points are found during startup of the algorithm, the odometry will start to drift and rotate around.**" Another user there: FAST-LIO on the L2 gives "significantly reduced" drift.
- unilidar_sdk2 #27: "duplicated walls" 5–20 cm apart during mapping; advice: let the sensor "properly synchronize (takes up to 10 sec)", damp the mount.
- koide3/glim #248: L2 on Jetson Orin, odometry shows rotation while stationary.
  Sources: https://github.com/unitreerobotics/point_lio_unilidar/issues/21 /22 /20 /5, https://github.com/dfloreaa/point_lio_ros2/issues/5, https://github.com/unitreerobotics/unilidar_sdk2/issues/27, https://github.com/koide3/glim/issues/248

### F3 — The config we actually run is not the one we think, and parts of it are load-bearing for this symptom
- Our bags carry `/aft_mapped_to_init` at **~20 kHz** (1.7 M msgs in 87 s on 114136). That is `publish_odometry_without_downsample: true` in the dfloreaa L2 yaml → `publish_odometry()` **and a TF broadcast run for every point-time group inside the per-point update loop**. On an Orin Nano that is a large, self-inflicted CPU/DDS load competing with the driver's 1 ms parse timer (F1). The LiDAR subscription is best-effort `SensorDataQoS` → lagging processing **drops clouds**.
- `init_map_size: 10` counts **points**, not frames → the initial map is essentially the first downsampled scan. HKU maintainer on startup drift (#86): "modify `init_map_size` to 1000."
- Gravity init = mean of the first **100 IMU frames = 0.4 s** (`MAX_INI_COUNT`). `mean_gyr` is computed but **not** assigned to the bias state (bias starts at 0, learned via `b_gyr_cov 0.0001`). So "IMU Initializing: 100 %" fires at 0.4 s; our 15 s is the right discipline but Point-LIO itself does almost nothing with it.
- Filter sizes: Unitree v2.0.2 raised L2 `filter_size_surf/map` 0.1 → **0.4 m**; the dfloreaa launch passes **0.1**; code defaults are 0.5. LI-Init's indoor guidance is 0.05–0.15 surf / 0.15–0.25 map. We do not know which value is live. **Action: `ros2 param dump /laserMapping` while mapping.**
- IMU weighting in the output model: `imu_meas_omg_cov 0.1` (gyro trusted to ±0.3 rad/s ≈ ±18 °/s), `gyr_cov_output 1000`. At a 3 °/s pan the gyro contributes little; heading is effectively LiDAR-only, from ~5 k sparse points against a coarse map.
  Sources: https://raw.githubusercontent.com/unitreerobotics/point_lio_unilidar/main/config/unilidar_l2.yaml, `launch/mapping_unilidar_l2.launch`, `VERSION.md`; https://github.com/dfloreaa/point_lio_ros2 (`config/unilidar_l2.yaml`, `launch/mapping_unilidar_l2.launch.py`, `laserMapping.cpp`); https://github.com/hku-mars/Point-LIO (README, `IMU_Processing.hpp`), https://github.com/hku-mars/Point-LIO/issues/86

### F4 — What the sources do NOT support
- **A constant IMU–LiDAR time offset.** Arithmetic: at 3 °/s, 100 ms of offset is 0.3° of yaw. A multi-degree fan needs ~1 s of offset or a clock-*rate* error. And a constant offset would hurt fast walking turns more than a slow pan — our clean walks argue against it. (The ~0.1 s `ros2 topic delay` on the cloud is start-of-frame stamping, not an offset.)
- **An IMU–LiDAR extrinsic rotation.** Manual and SDK: "the three coordinate axes of the IMU coordinate system are parallel to the corresponding coordinate axes of the point cloud coordinate system"; translation 1.7 cm (same number as L1, not independently verified for L2). Our evidence agrees: gravity reads on body X, and Point-LIO's maps come out level with the floor at z≈0 — a rotated extrinsic would tilt the world.
- **LI-Init as the fix.** It is ROS1-only, has no Unitree `lidar_type`, and requires >99 % rotation excitation about **all three** axes — a yaw pan cannot calibrate it.
- **The IMU hardware** (cleared 09-24) — **except** one documented L2 fault to CHECK: unilidar_sdk2 **#9**, bogus stationary acceleration when "Z-axis pointing sideways" (our mount), e.g. [18.75, 0.50, 10.32] (|a|≈21 m/s², below `satu_acc 30`, so `check_satu` would not catch it). It can start "randomly at some point."
- **The camera shutter** — not in the cloud.
- The L2 hardware packet clock running at ~½ real time (sdk2 #25; L2lidarClass measured 0.498) only matters with `use_system_timestamp: false`. We run true.
  Sources: https://github.com/unitreerobotics/unilidar_sdk2/issues/9 /25, https://github.com/hku-mars/LiDAR_IMU_Init (README, `LI_init.cpp`), https://github.com/markgol/L2lidarClass

### F5 — Mount geometry: the L2 on this rig sees the FORWARD half-space, so a static vantage cannot see the room
- Manual: the mirror sweeps 180° vertical, the slow motor turns 360°, "to achieve a 360*90° hemispherical ultra-wide-angle scan, which can measure the three-dimensional space **above** the radar." Density "is larger near the center" (+Z); the only tiny blind spot is "directly above" (+Z).
- Our camera extrinsic (GOLDEN_360 §2): `R_L2C[2][2] = 0.989` and `R_L2C[1][0] = −0.987` → **LiDAR +Z ≈ camera forward; LiDAR +X ≈ up.** Gravity on body X (09-24 audit) confirms it. So the dome faces forward; the hemisphere is the half-space in front of the rig; the hemisphere's rim is the vertical plane through the sensor — **zenith and nadir sit on the rim**, sparse. That is exactly why the panoramas show grayscale caps straight up and down. With Z-up (II-H's model) the zenith would be the densest spot, contradicting the caps.
- II-H's "36/36 azimuth bins = 360° = all four walls" measured azimuth around the **sensor Z** axis. With Z forward that is a vertical ring (floor, ceiling, left, right) — trivially full, and silent about the wall behind the rig.
- Consequence: pans and walks are not optional for coverage — the operator's ruling stands on physics as well as workflow. The decisive check is one command (below): a top-down of the static 180728 cloud shows a "D" (half-room) or a rectangle.

### F6 — Offline solver landscape (verified on PyPI / official docs, 2026-10-01)
- **Shadow cannot run Point-LIO or GLIM.** Shadow's rules: "Shadow PC does not support all virtualization software… Attempting to enable virtualization is considered a modification and is not supported." Docker Desktop and WSL2 both need a VM. (https://support.shadow.tech/hc/en-us/articles/32731830348305)
- **KISS-ICP 1.3.0** has Windows wheels (cp38–313), reads the L2 `time` field, deskews by constant velocity, **default `voxel_size = max_range/100 = 1.0 m`** (coarse indoors; use ~0.25 m / `max_range` 20). Full 6-DoF only. Maintainers: "if the rotation is huge, there is nothing KISS-ICP can do"; struggles with sparse sensors (#12, #240). Already installed on Shadow (II-D).
- **KISS-SLAM 0.0.2**: no Windows wheel, and its loop closure only fires when **translation** passes a threshold → it can never close a pan. Not our tool.
- **GLIM v1.2.x (2026)**: README: "Tested on Ubuntu 22.04 / 24.04 with CUDA 12.2 / 12.6 / 13.1, and NVIDIA Jetson Orin (Jetpack 6.1)"; "Non-repetitive scan LiDAR (e.g., Livox Avia and MID360)" supported; docs describe `glim_rosbag` (reads a rosbag directly) and global mapping on factor graphs with **overlap-based** keyframes (no translation needed for loop factors). L2 behaviour untested. (https://github.com/koide3/glim, https://koide3.github.io/glim/)
- Windows-native building blocks if we ever need a custom pan solver: Open3D 0.20 pose graph (`global_optimization`), small_gicp 1.0.1 (H/b per factor), MapClosures 2.1.0, scipy `Rotation.align_vectors`. No off-the-shelf "rotation-only scan-to-dwell-map" tool exists.

---

## Root-cause ranking (evidence-weighted)

| # | Mechanism | Evidence for | Evidence against | Testable how |
|---|---|---|---|---|
| 1 | **Live Point-LIO on the loaded Jetson corrupts its own inputs** — host-stamped IMU/cloud smeared by load, packets silently dropped, clouds dropped on best-effort QoS, per-point odom/TF at 20 kHz feeding the load. Rotation is where timing error bites (ω·δt); translation isn't. | F1, F3, #21 jitter report, our own 3× freezes and the 10-msg odom on 080826 | None of our bags has been checked for stamp jitter yet | `bag_health.py` on 141733 (today); same pan recorded RAW and solved offline (the capture) |
| 2 | **Point-LIO's L2 setup is weak on rotation at startup** — one-scan initial map, 0.4 s gravity window, no close-by structure, moving start on 141733, coarse voxels, gyro barely weighted at 3 °/s | F2 (maintainer statement), F3, I-D | 180728 was clean (but static) | offline re-solve with `init_map_size 1000`, 0.1–0.2 m filters, 15 s still init with near structure |
| 3 | **Fundamental: no loop closure** — a 300° pan that returns to start has an unexploited constraint; any residual drift stays in the map | I-C ruling, RESEARCH 09-25, #25 ("Point-LIO is purely a LIO front-end") | — | GLIM offline on the Jetson |
| 4 | L2 IMU fault #9 (bogus |a|≈21 with Z sideways) | documented, our mount | our 09-24 static test was clean | `bag_health.py` |a| check on every bag |
| — | Constant time offset, extrinsic rotation, shutter, IMU hardware | — | F4 | closed unless data reopens them |

The honest statement: **the exact mechanism is not yet proven.** The solve below is built so that ONE capture discriminates 1–3 and yields a usable clean geometry whichever it is.

---

## Decision

**D1. The live Point-LIO result is no longer the geometry of record.** Geometry of record = an **offline solve of a RAW bag** (`/unilidar/cloud` + `/unilidar/imu` + compressed camera). During capture the Jetson runs the driver, the camera node and the recorder — nothing else (no live Point-LIO, no browser, kiosk render on Shadow per II-I). This removes mechanism 1 at the source and makes every bag re-solvable as many times as we want.

**D2. The Jetson is the offline Linux solver when it is not capturing** (L2 OFF, camera off, kiosk off): `ros2 bag play --rate 0.5` into Point-LIO with the corrected parameters, then SIGINT → `scans.pcd`. Shadow cannot host ROS (F6); the x86 tower, if it still exists, is the alternative. Shadow keeps everything Windows-native: `bag_health`, `top_down`, KISS-ICP (indoor config) as the IMU-free cross-check, anchor/fusion, archive.

**D3. Offline Point-LIO parameters (first pass):** `publish_odometry_without_downsample: false`; `init_map_size: 1000`; `filter_size_surf 0.1`, `filter_size_map 0.2`; extrinsic unchanged; `extrinsic_est_en: false`. Confirm the effective set with `ros2 param dump /laserMapping`. (Point-LIO at ~12 Hz odometry is plenty for the anchor: at 3 °/s, nearest-pose error < 0.15°.)

**D4. GLIM on the Jetson is the loop-closure candidate** (apt PPA, arm64, JetPack 6.1 supported, `glim_rosbag`). Tried after D3 on the same bag — it answers mechanism 3 without a second capture.

**D5. The first test capture is designed to discriminate:** rig OFF the stand? No — **on the stand** this time (it isolates rotation), 15 s dead-still with close-by structure in the forward view, then a slow stand pan ≥ 300° that **returns past the start heading**, then 5 s still. Recorded RAW. Then four top-downs on Shadow: live-free Point-LIO offline (default params), Point-LIO offline (D3 params), KISS-ICP indoor, GLIM. The eye picks. One crisp outline = solved; that solver becomes the pan solver. All four bent = the raw data itself is bad → F1 driver path (`use_system_timestamp`, packet timing) becomes the next ADR.

---

## Options considered

### Option A: Keep live Point-LIO, tune the config live on the rig
| Dimension | Assessment |
|---|---|
| Complexity | Low per try, but every try is a rig session |
| Cost | A capture per parameter; the Jetson still freezes under the same load |
| Diagnostic power | Low — load and config change together |
**Rejected:** mechanism 1 cannot be separated from 2 while Point-LIO runs live.

### Option B: Record RAW, solve offline on the Jetson (Point-LIO → GLIM) — **chosen**
| Dimension | Assessment |
|---|---|
| Complexity | Medium: a raw-record capture slot + an offline replay script; both are small and testable with the L2 off |
| Cost | One capture answers 1, 2 and 3; re-solves are free |
| Scalability | Every future bag is re-solvable; loop closure available via GLIM |
| Team familiarity | Builds on II-B/II-D already ratified |
**Risk:** replay on the Jetson is slower than real time; acceptable (rate 0.5, nothing else running).

### Option C: Windows-native custom pan solver on Shadow (gyro-seeded rotation-only scan-to-dwell-map + Open3D pose graph)
| Dimension | Assessment |
|---|---|
| Complexity | High — custom build, unproven on real L2 data |
| Cost | Days, before a single real result |
| Upside | Keeps "everything on Shadow" pure; could become the long-term station solver |
**Deferred:** worth building only if B proves the raw data is sound and GLIM is unavailable. Building blocks verified (F6).

---

## Consequences
- Easier: geometry becomes repeatable and auditable; bad captures are re-solvable instead of re-shot; the Jetson stops freezing at capture.
- Harder: a second step after every capture (replay); the "IMU Initializing: 100 %" gate is replaced by a timed 15 s still + `bag_health`'s "DEAD-STILL start" verdict.
- Revisit: II-H's static-coverage claim (after the 180728 top-down); GOLDEN_360_FUSED_RECIPE's reference numbers (built on drifted geometry); the TAU-360 plan (unchanged in motion — handheld, tremor — but now recorded RAW and solved offline).

---

## Action items (gated, one command at a time)

**Today, rig OFF, on Shadow:**
1. [ ] `bag_health.py` on `plio_texcap_20260924_141733` → does the live heading lag the gyro (ratio < 1)? IMU stamp gaps/bursts? any |a| > 12? — this is the direct autopsy of the fan.
2. [ ] `top_down.py` on the static 180728 `scans.pcd` → D-shape (forward half-space, F5 confirmed) or full rectangle (II-H stands).
3. [ ] `bag_health.py` on 180728 → jitter/|a| baseline on a clean run.

**Before the next capture (Jetson, L2 OFF):**
4. [ ] `ros2 param dump /laserMapping` (or read the live launch) → bank the effective parameter set; verify md5 of the launch/yaml against rig-files.
5. [ ] Build + bless `capture_raw.sh` (record `/unilidar/cloud /unilidar/imu /camera/image_raw/compressed`, 4-stop trap, no Point-LIO) in the kiosk CAPTURE slot.
6. [ ] Build `resolve_pointlio.sh` (offline replay, D3 params, saves `scans.pcd`); dry-run it on `fusioncap_080826` (cloud+imu present) — no rig needed.
7. [ ] Install GLIM from the arm64 PPA; dry-run `glim_rosbag` on 080826.

**The capture (D5)** → four top-downs → the eye.

---

## Sources (primary)
- unilidar_sdk2: https://github.com/unitreerobotics/unilidar_sdk2 (README; `unitree_lidar_ros2/src/unitree_lidar_ros2/include/unitree_lidar_ros2.h`; `unitree_lidar_sdk/include/unitree_lidar_utilities.h`); issues #9, #14, #20, #25, #27, #28
- point_lio_unilidar: https://github.com/unitreerobotics/point_lio_unilidar (`config/unilidar_l2.yaml`, `launch/mapping_unilidar_l2.launch`, `VERSION.md`, `src/parameters.cpp`, `src/Estimator.cpp`); issues #5, #20, #21, #22, #25
- dfloreaa/point_lio_ros2: https://github.com/dfloreaa/point_lio_ros2 (`config/unilidar_l2.yaml`, `launch/mapping_unilidar_l2.launch.py`, `laserMapping.cpp`); issues #2, #4, #5
- hku-mars/Point-LIO: https://github.com/hku-mars/Point-LIO (README; `IMU_Processing.hpp`); issues #62, #86, #94, #115, #121; paper https://hub.hku.hk/bitstream/10722/331147/1/content.pdf
- hku-mars/LiDAR_IMU_Init: https://github.com/hku-mars/LiDAR_IMU_Init (README, `include/common_lib.h`, `LI_init.cpp`)
- koide3/glim: https://github.com/koide3/glim · docs https://koide3.github.io/glim/ · issue #248
- Unitree L2 manual v1.1 (project file) · https://www.unitree.com/L2
- KISS-ICP: https://github.com/PRBonn/kiss-icp (`config/config.py`, `config/parser.py`, `Preprocessing.cpp`, `Registration.cpp`); https://pypi.org/project/kiss-icp/ ; issues #12, #240 ; paper https://arxiv.org/html/2209.15397v2
- KISS-SLAM: https://github.com/PRBonn/kiss-slam (`slam.py`, `loop_closer.py`); https://pypi.org/project/kiss-slam/
- Shadow virtualization rule: https://support.shadow.tech/hc/en-us/articles/32731830348305-Rules-and-Restrictions-on-Shadow ; Docker: https://docs.docker.com/desktop/setup/install/windows-install/ ; WSL: https://learn.microsoft.com/en-us/windows/wsl/compare-versions
- Open3D multiway registration: https://www.open3d.org/docs/release/tutorial/pipelines/multiway_registration.html ; small_gicp: https://github.com/koide3/small_gicp ; MapClosures: https://pypi.org/project/map-closures/
- markgol/L2lidarClass (L2 clock-rate note): https://github.com/markgol/L2lidarClass
