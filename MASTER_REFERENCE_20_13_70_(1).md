<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.70, 2026-09-26) *****       -->
<!-- -->
<!-- *** LINEAGE NOTE (why this layer is based on 68, not 69):                        -->
<!-- ***   Master 20.13.69 AND 20.13.69(1) are INCOMPLETE files. This 20.13.70        -->
<!-- ***   layer is therefore folded onto MASTER_REFERENCE_20_13_68_.md (the last     -->
<!-- ***   COMPLETE base — it carries BOTH ADRs and the full STAGE 1–7               -->
<!-- ***   RealityScan→UE5 recipe verbatim). The real, load-bearing content of 69     -->
<!-- ***   (the 114136 visual-gate pass, the GOLDEN_360 recipe + tools, the drift     -->
<!-- ***   finding, the IMU-clean audit, and the 9-STEP METHOD) is FOLDED IN below    -->
<!-- ***   as PART I so nothing depends on the broken 69 files. Stone Clause:         -->
<!-- ***   additive, nothing lost.                                                    -->
<!-- -->
<!-- *** THIS LAYER (20.13.70) DOES THREE THINGS:                                     -->
<!-- ***   (I)   FOLDS IN the complete 20.13.69 content (see PART I).                 -->
<!-- ***   (II)  DOCUMENTS THE OPERATIONAL TRIAD that runs every headless bring-up —  -->
<!-- ***         RIG PRE-FLIGHT, RIG CHECK, RIG KIOSK — the invariant prep the        -->
<!-- ***         operator + assistant step through together (rig has no monitor).     -->
<!-- ***   (III) BANKS THE 2026-09-26 SESSION: the RE-SOLVE-FIRST workflow, the       -->
<!-- ***         live-Point-LIO Jetson FREEZE, the TWO-TAU distinction + the          -->
<!-- ***         post-capture degradation audit, and a new offline re-solve station   -->
<!-- ***         (kiss-icp on Shadow) that checks geometry INDEPENDENTLY of the IMU.  -->
<!-- -->
<!-- *** CURRENT STATE (read before acting):                                          -->
<!-- ***   - THE RIG IS OFF. Always assume the L2 is OFF until a clear command        -->
<!-- ***     powers it on. Nothing is captured until the triad passes.                -->
<!-- ***   - RIG CHECK IS RED (advisory). point_lio_capture.sh compressed-camera      -->
<!-- ***     edit: deployed cbc780c53eff9670b7b9e78b0e3fa2bf vs vault-wanted          -->
<!-- ***     b34ca6275a61335e0b62d792073cb113. INTENTIONAL; the launcher stops on     -->
<!-- ***     any red, so bless it (vault + manifest) when ready. NOTE: the 6 kiosk    -->
<!-- ***     files get SWEPT off the Desktop by daily cleanup — restore from          -->
<!-- ***     ~/rig_originals (restore_kiosk.sh) as the recurring first fix.           -->
<!-- ***   - 15 s DEAD-STILL INIT is now the ratified baseline (see II-G). It fixed   -->
<!-- ***     the moving-start drift: fusioncap_180728 came back LEVEL + undrifted.    -->
<!-- ***   - CORRECTED L2 PHYSICS (measured, II-H): the L2 is 360° AZIMUTH × 90°      -->
<!-- ***     ELEVATION. The internal mirror spins a full circle on its own, so a      -->
<!-- ***     STATIC rig sees the whole horizontal room from one spot. The blind       -->
<!-- ***     region is in ELEVATION, not azimuth. (Retracts the "forward hemisphere / -->
<!-- ***     one-side" mis-read.)                                                      -->
<!-- ***   - RE-SOLVE-FIRST IS PROVEN END TO END: record raw → Tailscale → kiss-icp    -->
<!-- ***     on Shadow (Python 3.12) → judgeable top-down in seconds (II-D).          -->
<!-- ***   - fusioncap_080826 (51.6 s) RE-SOLVED: drift traced to moving/jolted start -->
<!-- ***     + rotation-only technique (IMU intact, no 40 s drop — that was display   -->
<!-- ***     starvation). Not a keeper. See II-G.                                      -->
<!-- ***   - NEXT: a MULTI-POSITION capture. One static spot already gives the full   -->
<!-- ***     360° horizontal wall outline; moving to a few vantages is what fills the  -->
<!-- ***     ELEVATION blind cone + OCCLUSION shadows + gives photo PARALLAX.          -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ 20.13.70 — THE OPERATIONAL TRIAD + THE RE-SOLVE-FIRST WORKFLOW  ⭐
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

Two hard lessons drive this layer. First: a capture is a machine that fails
quietly, so the *prep* — not the walk — is where correctness is won or lost, and
that prep must be run as fixed, gated steps every time. Second: trying to make the
Jetson do everything at once (live Point-LIO + record the raw cloud + serve the
kiosk + camera) hard-locks it. The answer to both is the same discipline:
**a fixed, gated bring-up, then record RAW and solve OFFLINE.**

(PART I below folds in the complete 20.13.69 content — the 114136 visual-gate
pass, the golden recipe and tools, the drift finding, the IMU-clean audit, and the
9-STEP METHOD — since the 69 / 69(1) files are incomplete. PART II is the new
20.13.70 work.)


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART I — FOLDED-IN 20.13.69 CONTENT (preserved here; 69 files incomplete)  ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## I-A. THE 360 FUSED PANORAMA PASSED THE VISUAL GATE (capture 114136, 09-24)
═══════════════════════════════════════════════════════════════════════════
**The image exists.** For the first time the whole chain — capture → geometry →
anchor → photo colour — produced a picture that passes the eye: a full-ring 360 of
the room, in real colour, colour landing on the geometry, all the way around. The
rule is honored: *progress is the image, not the numbers* — and the image was good.

**THE PROVEN RUN (114136, 2026-09-24) — every number, for reproduction:**
- **Bag:** `plio_texcap_20260924_114136`, 87.4 s.
- **Camera:** `/camera/image_raw/compressed` (compressed fix live), 2047 frames.
- **Odom:** 1,700,640 msgs on `/aft_mapped_to_init` @ ~20 kHz — dense, NO hole (the
  raw-recording 127 s hole is dead).
- **Motion:** heading swept **309°**; translation **60 × 87 × 4 cm** — a real pan
  WITH parallax, not single-vantage. (`check_pan_heading.py` → VERDICT: PAN PRESENT.)
- **Anchor:** `make_full_pan_anchor.py` → **95% poseable** (1941/2047), **35** frames
  spread by HEADING (306° coverage), `panbundle.tar.gz` ~10 MB.
- **Cloud:** `scans_20260924_114136.pcd`, 2,038,351 pts (x y z intensity + normals).
- **Fusion:** `fuse_pano.py` → **77.7%** of the cloud coloured → the full-ring 360
  PNG (`pano_360_fullring_114136.png`). PASSED the visual gate.

**WHAT 114136 CERTIFIED:** (a) compressed capture + a MOVING odom work end to end on
hardware; (b) the EXTRINSIC is real-world CORRECT — colour registers on geometry
across 306°, not just a checkerboard wedge (closes the long-open "extrinsic
code-verified, real-world UNCERTIFIED" item).

**HONEST BOUNDARY:** this artifact is a 360 FUSED PANORAMA (colour on the point
cloud), the *see-what-we-captured* proof — NOT yet a walkable Unreal mesh. Known-good
blemishes: teal/cyan exposure seams between frames; grayscale caps straight up/down
(level pan + L2 blind cones).

═══════════════════════════════════════════════════════════════════════════
## I-B. THE RATIFIED 360 PROCESS + THE CANONICAL TOOLS (md5-locked)
═══════════════════════════════════════════════════════════════════════════
The meticulous, md5-locked repeatable process lives in **`GOLDEN_360_FUSED_RECIPE.md`**
(banked in the project): machine division, fixed calibration, the 6 one-command
steps, reproduction targets, known-good blemishes, and the visual acceptance test.
Follow it exactly; a repeat pan should be a REPEAT, not a re-derivation.
*(20.13.70 note: correct this recipe where it conflicts with the header.stamp /
re-solve-first findings in PART II — see II-C and II-F.)*

**Canonical tools born on 114136 (md5-locked, banked):**
- **`make_full_pan_anchor.py`** — `f015c4a746cd2347b7d7ca11192ef1fe` (Jetson) —
  exports a HEADING-spread posed-frame bundle from ONE bag. Pose math verbatim from
  `pointlio_pose_matcher.py` v2.
- **`fuse_pano.py`** — `f028ac3d7b2bfcbd18d82f64d64ece8c` (station) — self-contained,
  calibration-embedded full-ring render (occlusion-gated best-camera projection →
  equirectangular). The step that passed the gate. **NEVER run on the Jetson.**
- **`check_pan_heading.py`** — `20af111e90eff4abf1696aee62143a63` (Jetson) —
  read-only pan-confirm: does the bag's odom sweep heading + translate? Pre-export gate.

Prior-session tools still canonical: `rig_start_compressed.sh` + `rig_camera_compressed.py`
(compressed bringup); `capture_walk.sh` wrapping `capture_pointlio_texture.sh` (hands-off
pan); `pointlio_pose_matcher.py` v2 (pose-math source of truth).

═══════════════════════════════════════════════════════════════════════════
## I-C. DRIFT FINDING + RS PIVOT (09-24, capture 141733 repro)
═══════════════════════════════════════════════════════════════════════════
- **Reproduced the golden recipe on a 2nd pan (141733): every tool NUMBER passed, but
  the IMAGE failed the eye** — features REPEAT (one window rendered 3×) and areas are
  missing. Progress is the image (P1): the numbers lied, the picture told the truth.
- **Root cause = Point-LIO HEADING DRIFT on a pan-in-place.** THREE independent
  signals: (a) panorama places the same wall/window at multiple azimuths; (b) top-down
  floor plan shows the walls as several ROTATED copies fanning around the camera;
  (c) wall-normal azimuth histogram nearly FLAT (top-4 bins ~15% vs >55% for a clean
  room). A pan = rotation with ~no translation and no loop closure → heading rotates
  off true over the sweep → the LiDAR MAP is built BENT. (141733: 275° sweep, ~1.3 m
  translation, still drifted.) NOTE: "photos out of order" is NOT a photo-order bug —
  the photos are linear/clean; the panorama places by (drifted) HEADING, so the same
  direction lands twice.
- **OPERATOR RULING (ratified): do NOT solve this by forbidding pans.** Pans are
  natural; the pipeline must ACCEPT rotation. The cure is a GLOBAL optimizer (loop
  closure / bundle adjustment) that solves all poses jointly — NOT incremental
  odometry. This SUPERSEDES the earlier "traverse must translate" pan-avoidance framing.
- **RS PIVOT (mutual second opinion):** take photos + LiDAR to RealityScan; RS's bundle
  adjustment is a global camera-pose optimizer, robust to the motion that breaks
  Point-LIO. RESERVATIONS: (1) **RS refines CAMERA poses; it does NOT de-drift the
  LiDAR MAP** — a single pre-merged drifted cloud is treated as rigid; so let RS
  build/align from the PHOTOS and use LiDAR for SCALE, not as locked geometry;
  (2) photogrammetry needs parallax; a pure pan gives little; (3) RS is a black box —
  its mesh gets the same visual gate.
- **RS INPUT = rs_export.py (Jetson):** dense OVERLAPPING undistorted keyframes
  (every ~6th, ~324) + intrinsics.txt + cloud.ply (scale). Align photos FROM SCRATCH
  first (RS BA = the independent second opinion), then bring the cloud in for scale.
  scp the rs_<time>/ folder Jetson→Shadow (Tailscale). *(This is the ratified transfer
  method reused in II-D.)*
- **STANDING GAP:** a mapping backend robust to rotation (loop closure / global BA over
  LiDAR+photos) is the real missing piece. RS tests the camera-BA half; the LiDAR-map
  half (de-drifting from raw per-scan clouds) remains open.

═══════════════════════════════════════════════════════════════════════════
## I-D. PAN-DRIFT ROOT-CAUSE AUDIT — IMU IS CLEAN (09-24, on 141733)
═══════════════════════════════════════════════════════════════════════════
CLEARED (NOT the cause):
- camera path (separate from Point-LIO); the photos (RS aligned 99%).
- **IMU HARDWARE — proven CLEAN by a 30 s DEAD-STILL recording (imu_static30):** rate
  251 Hz, no dropouts, monotonic stamps, |a| = 9.62 m/s² (correct units), integrated
  gyro over 30 s still = 0/0/0° (noise ±0.01–0.03 rad/s). NO standing gyro bias.
- Point-LIO config sane (topics, extrinsic ~identity, acc_norm 9.81, imu_time_inte 0.004).

RETRACTED (my error, logged honestly): a mid-audit claim of ~1.3 deg/s gyro bias — the
dead-still test DISPROVES it (bias ≈ 0). The 118° was real hand motion (per-axis
integrals of a 3D rotation are not a clean net-angle). Rule re-logged: confirm the
sensor AT REST before blaming it.

STILL THE FACT: a pan makes a fanned/rotated map. IMU cleared → the fault is HOW
POINT-LIO USES the good IMU during rotation. Leading suspect: **MOVING-START INIT**
(config `start_in_aggressive_motion:false` needs a near-static start to estimate
gravity + initial state; gravity is on BODY-X here, so it must be found at rest;
starting motion instantly corrupts init → tilted world frame → rotation mistracked →
fan). SECONDARY: LiDAR-IMU time-sync (`time_lag_imu_to_lidar`) / per-point stamps.
THE FIX UNDER TEST: `capture_walk_v5.sh` (md5 `17fa81edf715525626e28d041533ffdb`)
enforces a 12 s dead-still init, THEN a stop-and-go pan; validate with the drift gate
(wall-normal azimuth histogram: top-4 bins >55% = clean; ~15% = still drifting).
CEILING: truly arbitrary continuous pans want loop closure. Tool: `imu_audit.py`.

═══════════════════════════════════════════════════════════════════════════
## I-E. GOVERNING CAPTURE SOP — THE 9-STEP METHOD (ratified 09-24)
═══════════════════════════════════════════════════════════════════════════
Every capture runs through the 9-STEP METHOD (source: rig-files/CAPTURE_METHOD(2).md;
mapped to the compressed pipeline in `CAPTURE_METHOD_9STEP_SOP.md`). The STEPS + GATES
are invariant; the script in a slot may change.
  0 Preconditions (START RIG up, coverage plan) · 1 Launch · 2 Pre-flight gate
  (/unilidar/cloud) · 3 Clean slate · 4 DEAD-STILL IMU init → wait
  `IMU Initializing: 100.0%` · 5 Capture (stop-and-go, settled start) · 6 one Ctrl-C ·
  7 four stops (bag→PLIO→verify→success) · 8 artifacts · 9 verify + drift gate.
**NON-NEGOTIABLE gates: STEP 2, STEP 4, STEP 7.** The 141733 drift = running OFF this
method (skipped Start Rig; fork dropped the STEP-4 gate; continuous "WALK NOW").
Present every future capture AS these steps, in order, from STEP 0 — never jump to
"run the capture." *(PART II-A documents the physical bring-up that precedes STEP 0.)*


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART II — NEW 20.13.70 LAYER (2026-09-26)                                  ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## II-A. THE OPERATIONAL TRIAD — how the headless rig comes up
═══════════════════════════════════════════════════════════════════════════
The rig is HEADLESS (no monitor). Operator + assistant bring it up TOGETHER,
confirming each gate before advancing — it is never "just turn the rig on." The PREP
is invariant; the recording MOTION is the deliberate experimental variable. The triad
is what makes STEP 0 → STEP 2 of the 9-STEP METHOD (I-E) real on a screenless rig.

**RATIFIED PREP ORDER:  Pre-Flight → Rig Check → Start Rig → Rig Kiosk.**
Rig Check runs *inside* Pre-Flight; Start Rig only happens once STAGE 1 is green; Rig
Kiosk is the shared "eyes" you watch through for the rest of the session.

### 1. RIG PRE-FLIGHT  (rig_preflight_button.py / RigPreflight.desktop)
- An on-monitor tkinter button ("RIG PRE-FLIGHT", blue, 420×420) restored to the
  desktop so prep launches with one click, no typing.
- It opens a gnome-terminal that runs `rig_launch.sh` and holds the window open
  ("Press Enter to close") so the output can be read and pasted back.
- `rig_launch.sh` is the GATE RUNNER (STAGE 1): it runs RIG CHECK (below) and reports
  kiosk status. If STAGE 1 FAILS, you do NOT capture — you reconcile first.

### 2. RIG CHECK  (rig_check.sh)  — the vault integrity gate
- Computes the md5 of every file in the kiosk/capture stack and compares each to its
  BLESSED original.
- **THE VAULT:** `~/rig_originals/` holds the blessed copies; `originals_manifest.txt`
  holds their md5s. "ALL GREEN" = every deployed file is byte-identical to its vault
  original — the stack you are about to run is exactly the stack that was proven.
- ANY RED = a deployed file drifted from the vault → STAGE 1 FAILED → do not capture
  until reconciled (revert the file, OR — for an intentional change — BLESS the new
  file into the vault and update its manifest md5).
- **CURRENT RED (open):** `point_lio_capture.sh`
  - deployed:    `cbc780c53eff9670b7b9e78b0e3fa2bf`  (compressed-camera edit)
  - vault wants: `b34ca6275a61335e0b62d792073cb113`
  - The edit swapped the recorder's camera topic to `/camera/image_raw/compressed`
    (ADR-002: raw chokes the SD). It is the change we want; it just has NOT been
    blessed. **To close: after a capture from the edited button proves out, copy it
    into `~/rig_originals/` and update its md5 in `originals_manifest.txt` → Rig Check
    returns GREEN.** Do NOT bless a tool that has not proven a good capture.

### 3. RIG KIOSK  (rig_kiosk_server.py, port :8080, viewed on the Waveshare)
- The browser status dashboard — the shared eyes on the headless rig, watched on the
  Waveshare display and reachable from the PC at `http://<jetson>:8080/kiosk`.
- Live per-topic health. Expected healthy rates:
    LiDAR `/unilidar/cloud` ≈ 12 Hz · Camera ≈ 30 Hz · IMU `/unilidar/imu` ≈ 251 Hz ·
    odom `/aft_mapped_to_init` = "waiting" until Point-LIO has initialized.
- Carries the **CAPTURE button** — THE canonical capture trigger. Captures are started
  FROM THE KIOSK, never hand-run from the terminal.
- The CAPTURE button runs `point_lio_capture.sh`, which records to
  `/mnt/rigdata/fusioncap_<stamp>/` using `setsid` + a four-stop cleanup trap
  (bag → Point-LIO → verify → success) and NO `set -m`. That construction is what
  finalizes the bag cleanly on stop; a job-control (`set -m`) recorder gets STOPPED by
  the terminal (STAT `Tl`) and never writes a bag — a bug already paid for; do not
  reintroduce it.

**VAULT DISCIPLINE (the rule behind Rig Check):** the deployed stack is trusted only
when it matches `~/rig_originals` by md5. Intentional edits are made, then BLESSED
(copied to the vault + manifest md5 updated). An edit shows RED until blessed — that is
the system working, not a fault.

═══════════════════════════════════════════════════════════════════════════
## II-B. THE RE-SOLVE-FIRST WORKFLOW — record RAW on the rig, SOLVE OFFLINE
═══════════════════════════════════════════════════════════════════════════
**PROVEN 2026-09-26:** running Point-LIO LIVE on the Jetson while ALSO recording
`/unilidar/cloud` + the camera + serving the kiosk OVERLOADS and FREEZES the machine.
The 51.6 s walk hard-locked it. (What looked on the kiosk like "IMU dropped ~30 s in"
was the DISPLAY starving as the machine choked — the RECORDED IMU was full-rate. What
actually died was Point-LIO, i.e. the odometry, which is what froze the box.)

**Recording the RAW streams ALONE is light and records cleanly regardless.** So the
ratified workflow is:
  1. On the rig: record RAW only — `/unilidar/cloud` + `/unilidar/imu` + compressed
     camera. No live Point-LIO to starve or orphan.
  2. On a STATION: replay the raw cloud+imu through a LiDAR-inertial (or LiDAR-only)
     solver OFFLINE — as many passes as we want, with a corrected config. Geometry
     becomes recoverable after the fact.

- `point_lio_capture.sh` (the kiosk CAPTURE button) DOES record `/unilidar/cloud` →
  every bag it makes is offline-re-solvable. (The OLD raw bags never recorded
  `/unilidar/cloud` → they can never be re-solved — that lineage is dead.)
- `ros2 bag reindex` rebuilds `metadata.yaml` from the `.db3` when a capture is killed
  before finalizing. This is how `fusioncap_080826` was recovered after the freeze.

**THE 51.6 s WALK (fusioncap_080826) — the current specimen:**
  - `/unilidar/cloud`  615 msgs (~11.9 Hz) — full
  - `/unilidar/imu`    12829 msgs (~248.6 Hz) — full
  - `/aft_mapped_to_init` 10, `/cloud_registered` 10 — Point-LIO died live (the freeze)
  - `/camera/image_raw/compressed` 864 (~17 Hz)
  → cloud + imu clean and complete = RE-SOLVABLE. Extracted to `cloudimu_080826`
    (cloud+imu only) via `ros2 bag convert` for transfer.

**HARD RULE (reaffirmed):** do NOT run a full bake / live Point-LIO capture as the
processing step on the Jetson — it hard-locks. Full solves go to a station (ADR
lineage: "the texture bake is a PROCESSING-STATION task, NOT a Jetson task").

═══════════════════════════════════════════════════════════════════════════
## II-C. TWO DISTINCT TIME OFFSETS + THE POST-CAPTURE DEGRADATION AUDIT
═══════════════════════════════════════════════════════════════════════════
**There are TWO taus. Never conflate them.**
- **τ_cam↔lidar** (≈ +180 ms, measured) — affects TEXTURE only (which photo colours
  which point). The repo's tau work is this one.
- **τ_imu↔lidar** (never measured; lives INSIDE Point-LIO) — affects ODOMETRY /
  GEOMETRY. This is the axis that bends the map (the I-C/I-D drift). Not calibrated;
  LI-Init is the tool to measure it (still open).

**HEADLINE DEGRADATION FAULT (post-capture audit, 2026-09-25):** the offline pose
matcher associated photos to poses on BAG RECEIVE TIME, not `header.stamp`. Measured on
real data: **+16 to +42 s** camera offset (growing = delivery backlog), which scrambles
pose↔photo per frame in PROPORTION TO MOTION — the alignment killer. A constant tau
cannot remove a variable spread; only header.stamp association can.
- FIX: `make_full_pan_anchor_hstamp.py` associates on `header.stamp` (with a
  clock-validation guard — epoch/monotonic/overlap). Proven on 141733: texture
  recovered (the lamp renders once, coherent). Before/after panoramas rendered. This is
  a NEW tool this session; it supersedes the bag-time association in the matcher path.
- `ts_probe.py` is the read-only measurement (camera bag-vs-header spread; also checks
  the cloud for a per-point time field for deskew). L2 can be off; it only reads the bag.

**GEOMETRY DRIFT IS SEPARATE from texture and is NOT fixable by re-colouring.**
Odometry-only mapping with no loop closure fans walls into rotated arcs on a
pan-in-place (I-C, proven top-down on 141733). Cure = real TRANSLATION (the Golden
walk) and/or a GLOBAL optimizer (loop closure / bundle adjustment). The header.stamp
fix recovers TEXTURE; it does nothing for GEOMETRY drift — different axis, different fix.

═══════════════════════════════════════════════════════════════════════════
## II-D. kiss-icp — a new OFFLINE RE-SOLVE STATION (2026-09-26)
═══════════════════════════════════════════════════════════════════════════
`kiss-icp` = a pip-installable LiDAR-only odometry that runs in plain Python — NO ROS,
NO WSL. Installed on Shadow under **Python 3.12** (Python 3.14 has NO prebuilt wheel →
it tries to compile and fails on a scikit-build-core version clash; 3.12 pulls a
ready-made wheel, no compile). Command that worked:
`& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pip install kiss-icp rosbags`.

**WHY it is the right tool for the geometry check:** it ignores the IMU entirely, so it
is IMMUNE to the τ_imu↔lidar sync problem (II-C) that drives the drift. That makes it a
clean, INDEPENDENT read on whether a walk's geometry came out straight — it cross-checks
Point-LIO without sharing Point-LIO's failure mode. LiDAR-only means no IMU fusion,
which for a translating walk is a strength here, not a loss.

**TRANSFER METHOD (ratified, reused from I-C):** scp the bag Jetson→Shadow over
Tailscale — the same path used for the `rs_export` folders. (Tailnet:
Jetson = fasterbybaxter-desktop / 100.85.175.10; Shadow = the Windows/RealityScan box.)

**PROVEN END TO END (2026-09-26):** `cloudimu_080826` pulled to Shadow over Tailscale,
solved 615 scans in ~4 s, rendered top-down — the whole re-solve-first loop works. Shadow
can NOT run Point-LIO (Windows/ROS2); the IMU-free kiss-icp is the tool there. Tooling
banked on Shadow: `resolve_walk.py` (kiss-icp solve → top-down + side PNG),
`imu_check.py` (IMU rate/gap + motion profile), `imu_init_converge.py` (init-baseline
measurement, II-G), `cov_min.py` (azimuth coverage + odom motion, II-H). Windows-paste
lesson: deliver scripts as FILES (SendUserFile), not hand-typed base64 — long base64
gets mis-transcribed and fails silently.

═══════════════════════════════════════════════════════════════════════════
## II-E. OPERATOR RULES REAFFIRMED THIS LAYER
═══════════════════════════════════════════════════════════════════════════
- ONE command at a time; the operator pastes the result before the next. More than one
  command per turn gets lost on paste-back — the first is done, the rest ignored.
- The L2 powers OFF when a run ends. ALWAYS assume the rig is OFF until a clear command
  powers it on.
- Progress is the IMAGE, not the numbers. "Don't bank anything until we see an image."
- Do NOT reinvent — check what already exists in github.com/BaxterBstupid/rig-files (and
  this Master lineage) before building. Verify any file by md5 before trusting it.
- Everything downloaded lands on the Desktop; anything banked to the project is ALSO
  delivered as a chat download, every time.

═══════════════════════════════════════════════════════════════════════════
## II-G. FIRST GATED CAPTURE + THE 15 s INIT BASELINE (2026-09-26 PM)
═══════════════════════════════════════════════════════════════════════════
Ran the golden-capture-method gated bring-up end to end with the operator (rig OFF →
Pre-Flight → restore swept kiosk files → Start Rig lean → verify at the wire → kiosk
CAPTURE). Two captures re-solved on Shadow with kiss-icp:

- **fusioncap_080826 (51.6 s):** re-solved → drift/smear. IMU check proved the recording
  was INTACT (250.9 Hz, continuous, NO 40 s drop — that was the kiosk DISPLAY starving as
  the Jetson choked). Root cause = TECHNIQUE: a moving/jolted start (motion from t=+0.06 s,
  no dead-still init) + rotation-dominated with ~0 net translation. Not a keeper.
- **fusioncap_180728 (31.7 s):** captured with a real **15 s dead-still init**. Point-LIO
  ran the FULL time (27,152 odom msgs, NO freeze — clean init + freed RAM changed its
  behaviour) and the compressed camera recorded (719 frames, textureable later). Re-solve
  came back LEVEL + undrifted (Z 0→4 m, floor at 0). Measured static (II-H).

**THE INIT BASELINE — ratified.** The init time "kept changing" because there was no fixed
spec (5 s / 12 s / "until 100%") AND the `IMU Initializing: 100%` event is stillness-gated
(motion during init stalls it). Definition now fixed: **hold dead-still, hands off, ≥ N s
AND until Point-LIO reads `IMU Initializing: 100%`.** N measured by `imu_init_converge.py`:
gravity direction locks in <1 s; **gyro-bias averaging is the pole** (binding constraint),
so N is set by how long the bias takes to settle under ~0.5 mrad/s (≈1.4° heading drift
over a 50 s capture). Synthetic (noise matched to the clean-IMU numbers) → ~11 s converge,
**N = 15 s ratified as the working baseline** (confirm against a real `imu_static30` when
convenient). WHERE IN THE PIPELINE: the init is STEP 4 of the capture (after the kiosk
CAPTURE button launches Point-LIO), NOT in Capture Lean (rig_start_lean just brings the
sensors up). `point_lio_capture.sh` already waits for `Initializing: 100`; the missing
piece is the fixed-time floor + actually holding still through it.

═══════════════════════════════════════════════════════════════════════════
## II-H. CORRECTED L2 PHYSICS — 360° AZIMUTH, STATIC (measured 2026-09-26)
═══════════════════════════════════════════════════════════════════════════
`cov_min.py` on fusioncap_180728 (RAW cloud, sensor frame, NO poses): **azimuth coverage
36/36 bins = 360°, blind wedge 0°**, while Point-LIO reports **net translation 0.02 m,
yaw range 1° = STATIC**. So a completely static rig produced a full 360° horizontal scan.

**THE CORRECTED MODEL (this supersedes the mid-session "forward hemisphere / one-side"
mis-read, which was wrong):** the L2 spec "360° × 90°" is **360° in AZIMUTH × 90° in
ELEVATION**. The internal low-speed motor spins the core a full circle continuously, so
the sensor sweeps the entire horizontal ring ON ITS OWN — a static rig sees all four walls
+ the hallway from one spot. The hemisphere/blind limit is in **ELEVATION**, not azimuth;
the 90°-to-level mount (source of the 85.54° extrinsic) just aims where that elevation
blind band sits. CONSEQUENCE for capture: one static vantage already gives the full
horizontal WALL OUTLINE, clean and undrifted. What a single vantage still lacks —
(1) the ELEVATION blind cone, (2) OCCLUSION shadows (behind furniture / far side of
objects), (3) photo PARALLAX — is filled by moving to a FEW positions, not by sweeping.
So the next capture is multi-position (stop-and-go dwell at 3–4 spots), and "the walk" is
for occlusion-fill + parallax, not for "seeing the room."

METHOD NOTE (banked, operator-driven): today's coverage confusion was resolved by
MEASURING raw sensor coverage, not by argument — assistant flip-flopped twice reasoning
from an armchair model before the data settled it. Rule reaffirmed (P1/P3): measure the
raw artifact; do not rationalize a win.

═══════════════════════════════════════════════════════════════════════════
## II-F. HONEST BOUNDARIES / WHAT IS OPEN
═══════════════════════════════════════════════════════════════════════════
- Rig is OFF. Rig Check is RED until `point_lio_capture.sh` is blessed into the vault
  (do it AFTER a capture from the edited button proves out).
- fusioncap_180728 is a clean STATIC 360°-horizontal scan (one vantage). To make a full
  room: a MULTI-POSITION capture (fill the elevation blind cone + occlusion shadows +
  parallax). fusioncap_080826 is exhausted (moving-start drift).
- CARRIED OPEN: (1) reproduce the golden pan from GOLDEN_360_FUSED_RECIPE; (2) the
  geometry branch to a walkable/relightable Unreal asset (planar_shell + occlusion bake
  on the STATION, then the STAGE 1–7 UE recipe preserved in _68); (3) run LI-Init for
  τ_imu↔lidar; (4) loop-closure / global BA to accept arbitrary pans; (5) correct
  GOLDEN_360_FUSED_RECIPE.md where it conflicts with the header.stamp / re-solve-first
  findings.

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-09-26:** Rebased the active layer onto the COMPLETE Master 68 (folding the
  incomplete 69/69(1) content in as PART I). Ratified + documented the OPERATIONAL
  TRIAD (Pre-Flight → Rig Check → Rig Kiosk) and the VAULT discipline behind Rig Check
  (current RED: point_lio_capture.sh compressed edit unblessed). Proved the
  RE-SOLVE-FIRST workflow: live Point-LIO + cloud record + kiosk FREEZES the Jetson; raw
  cloud+imu records cleanly and is re-solvable offline. Captured a 51.6 s walk
  (fusioncap_080826), survived the freeze, recovered it with `ros2 bag reindex`,
  extracted cloud+imu (cloudimu_080826). Distinguished the two taus and banked the
  header.stamp texture fix (make_full_pan_anchor_hstamp.py). Stood up kiss-icp on Shadow
  (Python 3.12) as an IMU-independent offline LiDAR odometry to check geometry.
- **2026-09-26 (PM):** Proved re-solve-first END TO END (080826 → Shadow → kiss-icp
  top-down in ~4 s). Ran the first fully-gated capture: 080826 drift = moving-start +
  rotation-only technique (IMU intact, no 40 s drop); 15 s dead-still init ratified as the
  baseline (gyro-bias averaging is the pole; init is STEP 4, not Capture Lean). Captured
  fusioncap_180728 with a clean 15 s init → Point-LIO ran the full 31.7 s, no freeze,
  level + undrifted. MEASURED the L2 physics: 360° AZIMUTH × 90° elevation — a STATIC rig
  (0.02 m / 1°) covered a full 360° horizontal ring; corrected the "forward hemisphere /
  one-side" mis-read. Banked Shadow tooling (resolve_walk / imu_check / imu_init_converge
  / cov_min). NEXT: multi-position capture to fill the elevation blind cone + occlusion +
  parallax; bless point_lio_capture.sh once a multi-vantage room proves out.

<!-- ============================================================================ -->
<!-- ##  END 20.13.70 LAYER. FULL COMPLETE LINEAGE — BOTH ADRs, the 20.13.68       ## -->
<!-- ##  SESSION LAYER, and the RealityScan→UE5 STAGE 1–7 recipe + all earlier     ## -->
<!-- ##  history — IS PRESERVED VERBATIM IN MASTER_REFERENCE_20_13_68_.md.          ## -->
<!-- ##  (20.13.69 and 20.13.69(1) are INCOMPLETE; their real content is folded    ## -->
<!-- ##  into PART I above. Stone Clause: additive, nothing lost.)                  ## -->
<!-- ============================================================================ -->
