[MASTER_REFERENCE(13).md](https://github.com/user-attachments/files/31334830/MASTER_REFERENCE.13.md)
[MASTER_REFERENCE(11).md](https://github.com/user-attachments/files/31325639/MASTER_REFERENCE.11.md)
[MASTER_REFERENCE(10).md](https://github.com/user-attachments/files/31324001/MASTER_REFERENCE.10.md)
[MASTER_REFERENCE(9).md](https://github.com/user-attachments/files/31315428/MASTER_REFERENCE.9.md)
[MASTER_REFERENCE(8).md](https://github.com/user-attachments/files/31309833/MASTER_REFERENCE.8.md)
# MASTER REFERENCE — LiDAR-Camera Capture Rig
### THE authoritative lookup. Scan, don't read. Update values IN PLACE at session end.
<!-- Last touched 2026-08-28 (Master 20.13): + FIELD KIOSK built (8O, Plan A) — one full-screen touch app = the field instrument, absorbing rig_monitor's engine. rig_kiosk_server.py (dependency-free Python http.server: serves page + /data live health + /action fires the real Start/Stop/Capture scripts) + rig_kiosk.html (the Waveshare-validated mock, now live-fed). Sandbox-proven end-to-end (mock mode). Temp thresholds recalibrated green<68/yellow68-80/red>80. Both files on the Jetson Desktop. TOMORROW = jumping-off point (likely MASTER 21, field-validation chapter): hot-validate kiosk /data reads + capture-button-lean + L2-temp topic + button safety; then retire terminal rig_monitor. This CLOSES the bench field-readiness arc (8H-8O). <!-- Last touched 2026-08-28 (Master 20.12b): + QUATERNION-ORDER BUG FIXED in the same driver (AUDIT FINDING #1, long-open). The imu_initial->imu TF unpacked the quaternion as [w,x,y,z] but Unitree's own example.h confirms the array is [x,y,z,w]; the IMU message was already correct, only the debug TF was wrong. Fixed lines 205-208, rebuilt clean with the temp mod. Downstream impact: NONE to data (nothing in the pipeline uses that debug TF; Point-LIO uses the correct IMU topic) — it only corrects the RViz TF-tree display. Explains why captures worked despite it. <!-- Last touched 2026-08-28 (Master 20.12): + L2 TEMP DRIVER MOD DONE & BUILT (awaiting hot test). Modified the unilidar ROS2 driver (unitree_lidar_ros2.h) to extract state.apd_temperature and publish it on /unilidar/apd_temperature (Float32). 4 additive edits (include, declare pub, create pub, publish in the point-data block); correct accessor is getLidarPointDataPacket().data.state.apd_temperature (first build failed on wrong nesting — missed the .data layer — fixed, rebuilt CLEAN). Original backed up as unitree_lidar_ros2.h.orig. NOT YET HOT-TESTED — bundled into the next hot session. <!-- Last touched 2026-08-27 (Master 20.11): + L2 THERMAL RESOLVED via manual+SDK (8N). Manual: operating -10..50C (60 is storage), NO documented catastrophic cutoff, recovery is just "restart the L2" — the fear was over-worried. SDK: apd_temperature lives in struct LidarInsideState, EMBEDDED in every point packet, ALREADY reaching the Jetson but DISCARDED by the current ROS2 driver -> the L2 temp bar is achievable via a (moderate, defined) driver mod to extract+publish it. Also gets voltages/dirty_index/packet_lost/imu_temp. Blind spot is now a scoped task, not a mystery. <!-- Last touched 2026-08-27 (Master 20.10): + HOT-RUN FINDINGS (8M) — rig_monitor v3 validated LIVE and it caught a real problem. BIG DISCOVERY: running EVERYTHING at once (Point-LIO + gscam + 2 fusion nodes + RViz) OVERLOADS the Jetson ~3x (load avg 19.7 on ~6 cores) and STARVES the sensors — camera dropped 30->14Hz, IMU 251->168Hz. Sensors weren't broken, they were CPU-starved. Captures done this way were likely SILENTLY DEGRADED. FIX = LEAN CAPTURE MODE: keep essentials (LiDAR/gscam/pointlio/bag-record), CUT the luxuries (RViz via rviz:=false in the point_lio launch; the two fusion nodes overlay_check + colorized_fusion from rig_start). THERMAL BASELINE measured: Jetson idles ~56C, runs 59-63C under load -> the 50/55 temp thresholds are TOO TIGHT (would be permanently red) -> recalibrate (~green<68/yellow68-80/red>80). L2 TEMP is NOT exposed by the driver (only /unilidar/cloud + /unilidar/imu published) — Windows-tool-only. Background-process cleanup = RED HERRING (load is our own foreground stack; real levers = lean-mode + optional headless). Camera calibrated to 30Hz, smart-odom (neutral when not capturing) both proven. Master 20.9 note follows. + LIVE CAPTURE-HEALTH MONITOR designed & built (8L). Founding principle: TIME is the universal marker — expected data rate is a HARDWARE CONSTANT (content- and pipeline-independent); geometry/coverage are NOT valid markers (content-dependent + gated on unknown Unreal tolerance). Rigor must be CONSTANT/LIVE (a heartbeat during capture, alarming in the moment) NOT an end-of-capture autopsy — only a live alarm prevents wasted shoot days. TWO-TIER philosophy: Tier-1 fatal-failures (no tracking/no file/no sensors/flow-gaps) = rigorous NOW, pipeline-independent; Tier-2 quality-thresholds (how-good-is-good-enough) = PENDING Unreal characterization (the checker bar is downstream-defined). Built rig_monitor.py: live terminal bar-graph = per-sensor FLOW heartbeat + CARD fuel gauge (free-space/measured-rate = time-left, closes the card-fill blind spot). Also check_capture.py (v2, three-state GOOD/CAUTION/RESHOOT) as the post-capture confirmation tool. Logic sandbox-proven; NUMBERS (real sensor rates, true data rate — the ~4-5GB/5min eyeball is UNVERIFIED) need a hot calibration run. Master 20.8b note follows. [+8K JETSON-CLOCK distinction: the Jetson already bakes an ARRIVAL-side clock onto the data (harmless metadata, good for pass-ordering) but it CANNOT fix tau — tau needs a CAPTURE-side hardware trigger. FIRST THING NEXT SESSION (Aug 26/27 AM): run the MOTION/translation captures once the rig is freed — the immediate real step.] <!-- Last touched 2026-08-26 (Master 20.8): + TIMECODE/SYNC framing (8K) — operator (film background) reframed tau as a TIMECODE problem: camera & LiDAR are two devices without a shared clock, tau (~175ms) IS their drift = the film "sound/picture out of sync" problem. The clean fix = the film JAM-SYNC equivalent = a HARDWARE TRIGGER (shared clock, kills drift at source), exactly the "hardware-triggered camera kills tau" note. Boundary: timecode solves SYNC (camera<->LiDAR, pass<->pass) but NOT spatial COVERAGE-completeness (a barn hole is missing in SPACE not TIME). Also banked: THREE kinds of "missing footage" (files/poses/coverage) + a numerical FIELD CHECKER concept. Bag-record time already acts as a rough shared clock (matcher uses it). Also parked: whether the Jetson can bake a clock/timecode onto the data (discussion below). Master 20.7 note follows. + FIELD DATA ARCHITECTURE (8J) — the barn/hour-long-capture reality. DATA RATE ~4-6GB/min -> ONE HOUR ~= 250-360GB, which BREAKS the Jetson (162GB free = fills mid-capture). THREE WALLS: (1) storage (fills), (2) processing (~180x our loads = hours), (3) review (cannot scrub an hour of point cloud like video). FIX: capture strategy = DELIBERATE OVERLAPPING PASSES (bounded bags per section), monitored live, offloaded between, then REGISTERED together (ICP, the proven 19.4mm cross-capture alignment) — NOT one continuous roll. This is the Leica/DJI pro method. HARDWARE: 2TB USB drive WIRED to the Jetson as the capture target (removes storage wall, ~6hrs headroom). WIRELESS SPLIT: OUT for recording (5GB/min firehose would drop packets over WiFi = corruption -> record wired), IN for monitoring (light coverage view via Foxglove to a phone) + offload (bag transfer AFTER capture). Portable USB-powered travel router = the field LAN; Jetson joins as client (ethernet stays with L2). Foxglove = leading candidate for the handheld viewing app (untested). Master 20.6 note follows. + FIRST FULL BAKE ran end-to-end (sandbox) + PROCESSING-STATION/UNREAL scouting (8I). BAKE: complete chain proven on 083911 (clean->normals->Poisson d9->per-vertex texture->export). SURPRISE: d9 mesh ran in ~3GB RAM (8.4s) — the ">8GB needs station" assumption may be WRONG, re-test on Jetson. Quality ROUGH (single-vantage lumps, 36% untextured, stringy through-window) — NOT photoreal; fix is MULTI-VIEW capture, pipeline itself is sound. Exports: bake_083911_unreal.xyz (ASCII xyzrgb, plugin-native) + textured_mesh.ply. PROCESSING STATION: budget laptop (Celeron N4120/8GB/UHD600) CANNOT run UE5 (no discrete GPU) — repurpose as Windows utility box (L2 Unilidar software) + Vagon terminal. Cloud-GPU = the path: Vagon hourly (Planet T4 ~$1/hr, Spark A10G ~$1.67/hr; iRender 4090 ~$8/hr for heavy). SaaS render farms CANNOT run UE5 (needs interactive desktop). UE LiDAR Point Cloud plugin is FREE + built-in. VAGON TRIAL: access works (machine, desktop, file-in) but Epic-launcher install BLOCKED by greyed-out "+" (known bug: launcher cant go online on fresh machine). GitHub-source route = AVOID (compiles engine, hours, wrong tool). Backups this session: foundation+desktop tarballs + rig_start pushed to repo. Master 20.5 note follows. + HARDWARE / POWER / THERMAL / FIELD-READINESS banked (new section 8H), from the un-benching prep discussion. Power topology RESOLVED: L2 = 12V DC / 10W / ~1A via a metered YTADNETH trigger off the Ugreen bank (bank confirmed 140W+100W USB-C PD ports, 12V=6A profile — over-spec'd; power RULED OUT as a crash cause). Jetson = straight USB-C PD on the 140W port, NO trigger (PD self-protects). Thermal: L2 two-stage protection = WARNING then stop-running (cover 85C threshold; storage/spec 60C); self-heating mode -10..30C withholds cloud + spikes to 13W; apd_temperature is self-reported. Restart-after-shutdown protocol UNDOCUMENTED -> PREVENTION via monitoring + soft ceiling; bench-induction RULED OUT. Field display: industry (DJI/Leica/XGRIDS) standard = live point-cloud coverage view (= our RViz), NOT camera feed; + status overlay. Touch UI = 4-button front-end to existing scripts. L2 is ETHERNET (192.168.1.62, enP8p1s0, "L2-static"). Master 20.4 note follows. TRANSLATION HYPOTHESIS PROVEN + init reframed. (1) RAW-SENSOR TEST (RViz, no Point-LIO, no recording): the L2 emits detailed healthy geometry in ALL directions -> the SENSOR is perfect; the smear-then-coalesce on pan is just decay-buffer holding un-repositioned frames (no odometry) = cosmetic. So the whole job of Point-LIO is supplying the "where am I" the raw view lacks. (2) TRANSLATION PROVEN: an 8-inch forward-down TIP (fusioncap_121359) took odom span 0.98s->23.61s and match 6%->68% vs the static pan — minimal translation fully restores tracking. Stack now validated bottom-up: sensor perfect / odometry needs translation (proven) / matcher correct. (3) INIT-WOBBLE non-issue: operator felt wobble at init; feared frame tilt; CEILING measured 0.83deg level (floor "3.82/3.22" was a bad-plane-fit artifact from furniture+far-tails, NOT a real tilt — operator caught the logic: a real frame tilt would cant floor AND ceiling together, they did not). Wobble reframed as FIELD-REAL and possibly HELPFUL (wobble = small translation the LIO wants). (4) PARKED for Aug 26: internalize/relax the still-init (gravity_init config path vs measured wobble-tolerance vs LiDAR_IMU_Init) — do after the rig is freed from the bench. Master 20.3 note follows. CUTOFF REDIAGNOSED — it is NOT a Point-LIO bug and NOT a matcher bug. It is CAPTURE PHYSICS: pure STATIC ROTATION starves the LiDAR-inertial odometry (no translation = LIO cannot resolve motion) -> tracking collapses -> short pose span. PROVEN: static ~300deg pan (fusioncap_185910) gave only 4631 poses/~1s span and coverage collapsed to ~180deg (narrow slab, not all-around). The matcher was AUDITED and CLEARED: live file reads monotonic BAG-TIME (not header stamps), all 7 built-in self-tests pass, math exact to 1e-16 -> every span number it reported is TRUE. Earlier "header-stamp misread" theory RETRACTED. §7U revised: the fix is CAPTURE STRATEGY (translation / out-and-back / drift), not code. The two good captures (083911,102338) had natural handheld translation; that is why they worked. Also: 3 stale .bak matchers on Desktop = version-decoy clutter, to be tucked away. Master 20.2 note follows. + ODOM CUTOFF CHARACTERIZED as RATE-COUPLED (7U) — THREE data points now: 16.09s@2637Hz / 4.60s@6903Hz / 7.03s@4462Hz. Span and publish-rate are INVERSELY coupled (higher Hz -> shorter odom life) = a burning-a-fixed-budget-faster mechanism, not random. This is now the CRITICAL-PATH BLOCKER: the pan test (fusioncap_182551) died at 7.03s so the pan's wide angles got NO poses (131/256 matched, all in first 7s) -> multi-view coverage NOT achieved. Debug underway. Master 20.1 note follows. + DENSIFICATION SANDBOX FINDING (7T) — operator reasoned from pixels to a dense-depth representation; sandbox proved it: a single frame's 6.78% sparse LiDAR depth filled to 100% of the 2.3M camera pixels (15x more measured px than raw LiDAR), color-edge-guided, back-projected to a 2,304,000-pt colored 3D cloud. KEY HONEST LIMIT the 3D view exposed: one frame = a SINGLE-SIDED, partly-INTERPOLATED shell (dished, no back walls) — beautiful from camera POV, incomplete as volume. The PAN resolves it (multi-view overlap turns inferred depth back into measured, stacks shells into a solid). Original Master 20 note follows.  RELIABILITY PROVEN — the run-2 repeat test. Two independent captures of the same room agree at ICP fitness 0.994 / inlier RMSE 19.4mm (origins 2.35deg/50mm apart; extents match 2-5cm). THREE fused images all land: run1-native 62.4%, CROSS-CAPTURE (run2 geometry on run1 photo — checkerboard on checkerboard across scans) 62.0%, run2-native 62.3%. CAMERA-HANG ROOT-CAUSED + FIXED: rig_start.sh launches overlay_check_node/gscam/colorized (by design) but its clean-slate list omitted overlay_check_node + gscam -> orphans stacked across rig starts and a stale gscam held /dev/video0 -> fresh camera died; PATTERNS list patched. ODOM CUTOFF now has TWO data points: 16.09s@2637Hz (run1) vs 4.60s@6903Hz (run2) — VARIABLE, not fixed-time; map still complete from 4.6s at one station. NEW PIPELINE STAGE: per-frame RGBD (make_rgbd.py v1.1, debugged: naive back-projection errs 195mm at edges -> undistortPoints 0.004mm; ships rgbd_to_cloud). first_fusion_hq designated the in-house ANTI-REFERENCE. -->
Last updated: 2026-08-21 (session: Point-LIO texturing bridge BUILT + proven cold; odometry-engine fork 7N added)

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

WHY THIS EXISTS — THE MISSION (the gravity everything orbits; read before any technical call):
This rig is a PRE-PRODUCTION INSTRUMENT FOR CINEMATOGRAPHY, not a scanning gadget. It does
something not really done before: a true FUSING of photography and LiDAR into ONE WHOLE IMAGE.
  - THE CAMERA GIVES US PLACE (what the space is, how it reads, the recognizable scene).
  - THE LiDAR GIVES US MINUTE MEASUREMENT (exactly where surfaces are, to the tape measure).
  - Meshed, they are a WHOLE, DELIVERABLE capture - dimensionally TRUE (a tape measure agrees)
    AND photographically TRUE (the eye recognizes the real space), in correct registration. This
    clean accurate fused capture IS the product - the gravity the whole project orbits. NOT rough
    raw material for a rescue pass; if the foreground comes out rough/undeliverable, the project has
    failed at its center no matter what post can patch.
WE CANNOT MEASURE EVERYTHING, AND DON'T NEED TO. Wholeness = the FOREGROUND / PARALLAX ZONE
(the stuff a camera moves past, that catches light, that other departments need dimensions for)
being complete and true. Beyond that - sky, distant mountains - is PLACE-ONLY: the camera shoots it
as a backdrop plate (skybox/dome/matte in Unreal), no LiDAR needed. A single camera has NO depth, so
it cannot extend geometry; reach comes from MOVING the LiDAR. Far content is backdrop, not measurement.
CANONICAL EXAMPLE - the barn shot (script says NIGHT, plate is DAY): We MEASURE the barn, fence,
grass (parallax, physical, other departments need dimensions). Camera takes mountains + sky as PLACE
(backdrop, swapped day->night in Unreal). Because the space is DIMENSIONALLY TRUE, we pre-light the
night in a virtual space we can TRUST: a moonlight on a crane (we mapped BEYOND the frame so crane/
rigging have measured space), seeing exactly where the barn's shadow falls, where edge light catches
the fence; warm lights INSIDE the barn spilling from windows. Because the map is ACCURATE, the virtual
answer IS the real answer: on shoot day we already know where the crane goes, which fixture is on it,
which interior lights go where. The pre-viz is ACTIONABLE (a dept head commits crew + money to it),
not merely illustrative. THAT is the innovation.
WHY ACCURACY IS NON-NEGOTIABLE (Polycam's WORST CASE SCENARIO.PNG is the anti-reference): Polycam
fails on BOTH axes at once - wrong DIMENSIONS (melt/billow/fused objects) AND wrong PLACE (distorted
photo). And those are ONE failure: bad measurement drags place down with it (the photo is projected
onto the mesh). If the barn's dimensions are wrong, the crane clears the roof in Unreal but HITS it on
the day - the plan fails on location, the shoot eats the cost. Relight/backdrop/night is a DOWNSTREAM
second pass that BUILDS ON the accurate capture; it never rescues a rough one.

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

*** UPDATE 2026-08-20/21 — SUPERSEDES the RTAB-centric summary above: ***
POINT-LIO WORKS (7M). The pivot is DONE: point_lio_ros2 built clean on the Jetson (~2min) and
BEAT the rotation bug on the first real L2 pan — 2.87m ceiling vs RTAB's 13m collapse, a
3.38M-point coherent room. Odometry/rotation is SOLVED. The TEXTURING BRIDGE to Point-LIO output
(7M-NEXT #1) is now BUILT + PROVEN COLD (2026-08-21): pointlio_pose_matcher.py (Piece 2, pose
interpolation, self-tested to 5e-16m / 0deg), pointlio_to_texture.py (Piece 3, NEW multi-view
per-face baker), capture_pointlio_texture.sh (Piece 1), and TEXTURE_BRIDGE_RUNBOOK.md. The whole
bridge was run on the real 161k dense cloud + a real image -> 385k-face mesh -> 90.3% photoreal
render (matches the prior probe). Convention locked to per_shot_texture to 7e-16m. ODOMETRY-ENGINE
CHOICE is now a FLAGGED FORK (7N): Point-LIO chosen + PROVEN; FAST-LIVO2 held in reserve (peer-
reviewed, but bakes lit colour -> not relightable). Open3D-on-Jetson = official pip wheel (CPU-only;
isl-org#6885's CUDA build does NOT apply); run cold processing in an isolated ~/tex_env venv (numpy
clash mitigation). NEXT is the first COMBINED camera+Point-LIO hot capture, then run the bridge on
real Point-LIO output (runbook HOT-1/2 + COLD-1/2).

>>> TWO-STAGE MODEL (recorded 2026-08-21): BENCH = build + prove architecture (big monitor,
   Claude real-time, adjustable LiDAR/camera array). RIG = execute the proven pipeline
   UNTETHERED (Jetson on platform, battery, Waveshare 7" only). Rule: drive everything that
   needs a screen / live help / hands on the array to CLOSURE ON THE BENCH. The first combined
   capture is therefore a LATE-BENCH milestone, not early-rig. Capture geometry = 270 pan-in-
   place (isolates rotation + fidelity), NOT hallway-walk. Bench tooling READY: camera_control.py
   (exposure/gain/colour-temp, proven live) for taming exposure before a pan.

>>> NEXT SESSION STARTS HERE (planned Aug 26, rig freed from bench): **INTERNALIZE / RELAX THE STILL-INIT** + first real TRANSLATION captures.
   THE ODOMETRY QUESTION IS SETTLED (Master 20.4): sensor perfect (raw RViz test), odometry needs
   TRANSLATION (proven: 8in tip -> 23.6s span / 68% match vs static pan 0.98s / 6%), matcher correct.
   The "cutoff" was never a bug — it was absent translation. Static-pivot capture is RULED OUT.
   AUG 26 PLAN: (a) offline first — operator frees the rig from the bench so real walking/translation
   is possible; (b) then INIT work: read the Point-LIO L2 config, try gravity_init (hand Point-LIO the
   ~known-upright gravity instead of requiring a dead-still 10s to derive it) so startup becomes "power
   on roughly upright, go" — a FIELD-REAL init, not a bench-still one; fallback = measure the real
   wobble tolerance (this session: felt wobble still gave 0.83deg-level ceiling, so "dead still" is
   already stricter than reality needs) or the heavier LiDAR_IMU_Init (ROS1) online-init route;
   (c) then real translation captures (out-and-back / walk-through) for genuine multi-view coverage,
   feeding the multi-view densification (7T). NOTE: calibration (the days of board work) is DONE and
   permanent (intrinsics+extrinsic) — the still-INIT is a SEPARATE thing (gravity+IMU-bias per power-up);
   do not conflate. A calib board could serve as an in-field dimensional TRUTH-CHECK (known object at
   known rough distance reads true size in the fresh map) but that is verification, not init.
   [Prior next-session text — FULL BAKE + UNREAL EXPORT — still valid, deferred behind the init work below.]
   *** UPDATE (Master 20) — RELIABILITY PROVEN, run-2 repeat test: two independent captures
   agree at 19.4mm RMSE (fitness 0.994); fused image reproduced natively twice + once
   CROSS-CAPTURE; camera-hang root-caused to rig_start.sh orphan-stacking and FIXED;
   odom cutoff measured VARIABLE (16.09s vs 4.60s) — top open defect, LiDAR_IMU_Init
   temporal-offset idea is the live lead. New stage: per-frame RGBD (make_rgbd.py v1.1). ***
   *** UPDATE 2026-08-24 — THE CLEAN CAPTURE IS DONE AND FIRST FUSION IS PROVEN ***
   fusioncap_083911: captured via the stone-tablet method (CAPTURE_METHOD.md), first try.
   Frames extracted (extract_frames.py v3: 192/192, rgb8, 1920x1200 = calib size exactly,
   naming img_{npz-row:05d} = the old bundle convention). SAME-VIEWPOINT FUSION PROVEN on
   the bench: cloud projected through the camera's exact eye (K + R_L2C/T_L2C + matcher
   pose, compose verified) onto the real frame — checkerboard on checkerboard, the
   through-glass neighbor-house points land INSIDE the window frame, 62.4% of cloud in one
   view. Evidence: fusion_triptych_f0.png / fusion_overlay_f0.png. NEXT MOVES: (1) FULL
   BAKE — trimmed-Poisson d9 mesh + all-192-frame multi-view texture (bench/sandbox has
   the RAM; Jetson does not); (2) UNREAL — export cleaned cloud as ASCII .xyz-RGB or .las
   (NOT .ply; UE5.8 LiDAR-plugin formats = xyz/pts/txt/las/laz/e57), cloud-GPU walk,
   1UU=1cm tape-measure check; (3) coherence-based cleanup before meshing (KEEP the
   through-window house — judge cluster coherence, never distance).
   (Prior next-session text below retained — station/Unreal context still applies.)
   [superseded heading: PROCESSING STATION + UNREAL + one CLEAN capture (2026-08-23)]
   THE MESHER IS SOLVED — do NOT re-open it. Trimmed Poisson (depth 9, ~5% low-density trim) is the
   mesher: 92.5% photoreal coverage, decided 2026-08-19 (7H), re-verified 2026-08-23. Ball-pivoting is
   REJECTED (too holey; L2's ~10.9x non-uniform point spacing defeats fixed radii). A 2026-08-22 session
   wrongly concluded "Poisson fatally fails" — that was the 8GB Jetson running OUT OF RAM (depth-9
   segfaults there but runs clean on a bigger machine). See the corrected §6 gotcha. CONSEQUENCE: the
   deliverable mesher (and Unreal) CANNOT run on the Jetson -> Jetson = capture front-end; meshing/
   texture/relight = PROCESSING STATION (workstation or cloud-GPU; validate via Vagon/Shadow first, 7Q).
   OPERATOR'S STATED NEXT MOVES: (1) upload capture data to the cloud + view it in UNREAL (LiDAR Point
   Cloud plugin imports .las/.laz/.e57/.xyz-.pts-.txt — NOT .ply (corrected 2026-08-23 vs UE5.8 docs), 1UU=1cm); (2) connect camera + LiDAR for a fused IMAGE via the proven
   chain (Point-LIO capture -> pointlio_pose_matcher -> trimmed-Poisson mesh [on the big machine] ->
   pointlio_to_texture); (3) continue research per 7S (CMU camera-densification for sparse-LiDAR holes;
   HKU LiDAR_IMU_Init for the odom-cutoff; DARPA/MIT still to explore).
   WHY RESULTS WERE BELOW DELIVERABLE (so it is never re-derived): the pipeline is proven photoreal on
   clean geometry — every sub-deliverable fusion came from a COMPROMISED INPUT (RTAB rotation-collapse,
   then wrong mesher on clean geometry, plus dim room + single-vantage ~66% coverage). The capture that
   gets ALL preconditions right at once — bright (camera_control.py), multi-view (270-pan / A2 out-and-
   back, 7I), dead-still Point-LIO init, correct save-order, meshed with trimmed Poisson on adequate RAM
   — has NEVER been run. That one clean capture + the known-good pipeline is the path from ~25% to
   deliverable.
   OPEN THREADS (real, not blocking): (a) Point-LIO odom cutoff — TWO DATA POINTS, VARIABLE: run2 (fusioncap_102338) odom died at
   4.60s of 29.45s (31,742 msgs @6902.9Hz!) -> 59/253 matched (23%); run1 below. Cutoff time AND
   publish rate vary wildly between runs (2637 vs 6903Hz) -> not fixed-time, possibly load/rate-
   coupled. Mitigation fact: one-station room map completes in ~4.6s anyway (277k pts, 19.4mm
   agreement) — the defect hurts LONG/moving captures most. CONFIRMED STILL ALIVE 2026-08-24 on fusioncap_083911: odom spanned 16.09s of a 32.78s capture (42,419 msgs @2637Hz), with mid-run gaps of 0.85-5.6s before dying; 140/332 images fell outside odom and dropped. NOT self-resolved by the clock fix. Earlier hypothesis was the Jetson-clock vs
   frozen-sensor-timestamp issue (7P, "clock breakthrough" 2026-08-23 log); may already be self-
   resolved; confirm on next hot capture; HKU LiDAR_IMU_Init (7S) is the temporal-init lead if not.
   (b) Displaced-cluster outliers (92% room + 7% clustered garbage on long captures; needs a scale-
   independent fix — film sets span 2m-100m). (c) Repo hygiene: Desktop code fixes (typestore/bagtime
   matcher; engine) still not pushed to rig-files; MASTER naming (the "(1)" copy) still to clean.
   (d) Reference repo eorua8801/unitree-lidar-slam — same stack (same Point-LIO + L2), useful for
   CONFIG COMPARISON (theirs: lidar_type 1 / scan_line 4; ours: 5 / 18). NOT an engine to switch to.

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
>>> [RTAB METHOD — PROJECT HISTORY, superseded by Point-LIO 2026-08-20. See 7C0. Install facts remain true (RTAB is still on the Jetson) but this is NOT the current path — do NOT fire the draft command below. Current odometry = Point-LIO (7M); launch via run_point_lio.sh.] <<<
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
| camera_control.py | touch panel: exposure+gain+colour-temp via v4l2 | on Jetson ~/, PROVEN LIVE 2026-08-21 (326 lines; --selftest passes) |
| CameraControl.desktop | icon launcher for camera_control.py | on Jetson ~/, working (Exec=python3 ~/camera_control.py) |
| run_point_lio.sh | sources ros2_ws + point_lio_ws, launches L2 mapping (does NOT start driver) | on Jetson ~/, PROVEN 2026-08-21 |
| per_shot_texture.py | THE fusion engine (mesh+per-face texture; made sampleB) | ~/Desktop/ (10,492 B) + rig-files; recovered from transcript 2026-08-20-16-31-39, reproduces sampleB EXACTLY (99%/450,304 tris/0.63) |
| inspect_pcd.py | C1 coherence checker (own PCD reader, matplotlib only, no Open3D; auto-verdict vs RTAB 13m) | on Jetson ~/, PROVEN (made pointlio_views.png) |
| PointLIO.desktop | icon launcher -> ~/run_point_lio.sh | on Jetson ~/Desktop |
| loam_livox.rviz | Point-LIO RViz preset | EDITED 2026-08-21: CloudRegistered Style=Points, Decay=5 (was Flat Squares/30); backup .rviz.backup |
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
- **MESHER = TRIMMED POISSON (RESOLVED 2026-08-23; corrects a 2026-08-22 regression)**: The mesher
  is TRIMMED POISSON (depth 9, ~5% low-density trim) - proven 2026-08-19 at 92.5% photoreal coverage
  (see 7H, evidence texture_probe_poisson.png). Ball-pivoting is REJECTED for texture (too holey:
  non-uniform L2 point spacing, ~10.9x variation, defeats fixed-radius ball-pivoting -> speckle/weave).
  *** CORRECTION: a 2026-08-22 session wrongly concluded "Poisson FATALLY FAILS on room-scans, swap to
  ball-pivoting" after Poisson threw "Failed to close loop" / segfaulted on the Jetson. That was a
  REGRESSION - it lost the settled 7H result and cost ~two sessions re-deriving it. The real cause of
  the crash was NOT that Poisson can't mesh rooms: it was the 8GB JETSON RUNNING OUT OF RAM. Verified
  2026-08-23: on a machine with more RAM, Poisson completes cleanly at depth 8/9/10 and produces the
  solid deliverable-grade surface. ***
  CONSEQUENCE (important, drives the architecture): depth-9 Poisson NEEDS MORE RAM THAN THE 8GB JETSON
  HAS. So the deliverable mesher CANNOT run on the Jetson -> meshing/texturing belong on the PROCESSING
  STATION (workstation or cloud-GPU; see 7Q/7F). The Jetson is capture front-end only. This is concrete
  evidence FOR the processing-station pivot. (Honest nuance from 7E: trimmed Poisson interpolates SMALL
  gaps on measured surfaces = fair reconstruction, and the density-trim cuts the far/invented
  extrapolation = stays honest to the accuracy mission. Ball-pivoting's honesty isn't worth its holes.)
- **ROSBAGS 0.11.5 NEEDS A TYPESTORE (2026-08-22)**: AnyReader([Path(bag)]) now raises "Bag contains
  no type definitions." Fix (applied to matcher, BOTH read loops): get_typestore(Stores.ROS2_HUMBLE)
  and pass default_typestore=_ts. Humble bags don't embed type defs.
- **POINT-LIO ODOM HEADER STAMPS ARE FROZEN - MATCH ON BAG TIME (2026-08-22)**: /aft_mapped_to_init
  message HEADER stamps are frozen/identical (all ~1787358243.694) and ~53s BEFORE the recording, so
  matching images (good headers) to poses on header-time gives 0 matches. FIX: match on BAG-RECORD time
  (consistent across topics), not header stamp. Matcher read_bag now appends `bt` (bag time) for both
  odom and images. This is why the first matcher run got 0/423, then 78 after the fix.
- **POINT-LIO ODOM CUTS OUT (~5.5s) (2026-08-22, OPEN)**: in a ~50s recording, odom published only the
  first ~5.5s (17007 msgs @ ~3000Hz, absurdly fast) then went silent while images kept coming ~44s more.
  The clean short capture only HAD 5.5s of tracking - likely WHY it stayed coherent (no time to inject a
  displaced cluster). Root cause unknown; investigate. Record /unilidar/imu on captures to autopsy.
- **"DIVERGENCE" IS DISPLACED-CLUSTER OUTLIERS, NOT ESTIMATOR RUNAWAY (2026-08-22)**: operator's RViz
  insight - both "diverged" and clean captures showed a coherent bounded room in RViz; a true estimate
  runaway would be visible. Tested: the 73MB "13km" cloud is 89.6% within 5m, 91.7% within 10m, only
  7.45% beyond 50m -> a real room + a CLUSTERED ~7% garbage blob dragging the bounding box. SOR (nb=20
  std=2) barely touches it (clustered, not lonely fliers). A distance-crop "fixes" small rooms but is
  UNFIT for film sets (2m cell to 100m hangar - no fixed scale). Need a SCALE-INDEPENDENT fix, ideally
  prevention (why does the cluster get injected?). inspect_pcd.py's extent-based verdict is MISLEADING
  on this (fooled by fliers) and its "RTAB 13m" reference string is stale (we're on Point-LIO).

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
- **AUTO-WB OVERRIDES MANUAL KELVIN**: B0578 `white_balance_temperature` shows
  `flags=inactive` while `white_balance_automatic=1`. The colour-temp slider does NOTHING
  until you UNCHECK "Auto white balance" (camera_control.py handles the order; if driving
  v4l2 by hand, set white_balance_automatic=0 FIRST). Same pattern for exposure: set
  auto_exposure=1 (Manual) before exposure_time_absolute bites. (Learned live 2026-08-21.)
- **B0578 COLOUR-TEMP CEILING = 6500K** (white_balance_temperature max=6500, NOT 10000).
  Cooler than 6500K is a post/grade or camera-upgrade item, not a capture setting.
- **POINT-LIO SAVE ORDER (cost us an hour 2026-08-21)**: scans.pcd is written ONLY on a clean
  SIGINT to Point-LIO. Stop Rig / hard-kill / killing the LiDAR FIRST starves Point-LIO -> NO save,
  and you silently re-read an OLD run's file. RULE: Ctrl-C Point-LIO FIRST -> `stat` the pcd to
  confirm the timestamp is NOW -> THEN kill LiDAR (heat cost of the wait is ~2-4s; use SHORT captures).
  For a throwaway look, kill-LiDAR-first is fine (no save wanted).
- **PCD FIXED-NAME OVERWRITE**: pcd_save writes ONE fixed path (…/PCD/scans.pcd), overwritten every
  run. RESCUE it immediately after a good capture: `cp …/PCD/scans.pcd ~/Desktop/scans_<stamp>.pcd`.
  Running Point-LIO by the bare icon skips the timestamped copy the capture script would do.
- **POINT-LIO DIVERGENCE (open risk, 2026-08-21)**: careless/fast init can make Point-LIO run away —
  the saved cloud becomes a kilometre-long streak (extent ~1300m Z), a trajectory smear not a room.
  A DEAD-STILL init gave a clean room (1.1M pts, ~8x5x3m). Always VERIFY a capture's extent before
  trusting it (Open3D one-liner); RViz can look fine while the save diverged. Run-to-run reliability
  is NOT yet proven — characterise WHEN it diverges before buying hardware to "fix" it (see 7O note).
- **auto_exposure / white_balance = interval:-1 memory note**: pcd_save interval:-1 accumulates the
  WHOLE session into one in-memory pcd (config comment warns of memory crash on long runs). Keep captures short.

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
| RTAB-Map install | [HISTORY — RTAB superseded by Point-LIO, see 7C0] ✅ DONE + healthy |
| RTAB-Map first map | [HISTORY — see 7C0] ✅ DONE 2026-08-18: LiDAR-only SLAM (milestone_map_20260818.db, 387+ nodes, 16mm). RTAB-era; Point-LIO is now the odometry. |
| RTAB-Map IMU odometry | [HISTORY — see 7C0] ⏸ attempted/paused (TF issue). Moot — on Point-LIO now. |
| RTAB-Map colour (Way A) | [HISTORY — see 7C0] ✅ colour survived into RTAB map (sparse dots, preview only). Superseded by per-shot TEXTURE path. See 7D. |
| RTAB-Map colour (Way B) | [HISTORY — see 7C0] ⏸ not pursued; per-shot texture is the colour path now. See 7D/7F. |
| **Point-LIO odometry (CURRENT)** | ✅ PROVEN 2026-08-20 (7M): built on Jetson, beat the rotation bug RTAB couldn't (2.87m ceiling vs RTAB 13m collapse), 3.38M-pt coherent room. THE current SLAM/odometry. |
| **Point-LIO texturing bridge (CURRENT)** | ✅ BUILT+PROVEN (7M): pointlio_pose_matcher.py + pointlio_to_texture.py (multi-view per-face baker). Replaces the RTAB db_to_texture path. |
| **FIRST FUSION on live Point-LIO** | ✅ DONE 2026-08-22: full chain capture->matcher->mesh->texture->image on live data. Quality ~25% at the time (wrong mesher used); see mesher row. |
| **MESHER = trimmed Poisson (RESOLVED)** | ✅ trimmed Poisson depth 9, ~5% trim = 92.5% photoreal (7H). Ball-pivoting REJECTED (too holey). CATCH: depth-9 needs >8GB RAM -> segfaults on Jetson, runs on a workstation -> meshing goes on the PROCESSING STATION. |
| Processing station (mesh/UE/relight) | ⬜ NEXT: stand up (or cloud-GPU validate) - the deliverable mesher + Unreal can't run on the Jetson. See 7Q/7F. |
| **FIRST CLEAN CAPTURE (fusioncap_083911)** | ✅ 2026-08-24 via the stone-tablet method: 334,030 pts, coherent room + THROUGH-GLASS exterior at 5-8m, dimensionally true, first try. Bag+PCD on Jetson Desktop ("Fusioncap scans/"). |
| **Capture method WRITTEN IN STONE** | ✅ CAPTURE_METHOD.md (unabridged: full source, every step/output/measurement, guards+scars, restore-from-zero). Destinations: repo + Jetson + email + chat. |
| **Frame extraction tool** | ✅ extract_frames.py v3 (typestore + ok-mask index extraction + img_{row:05d} naming + ROS yuv422=UYVY fix). Proven: 192/192 from the 083911 bag. |
| **SAME-VIEWPOINT FUSION PROVEN** | ✅ 2026-08-24: cloud through the camera's exact eye onto the real frame — checkerboard on checkerboard, window geometry inside window frame, 62.4% of cloud in view. THE CALIBRATION HOLDS ON LIVE DATA. Next: full bake. |
| **REPEATABILITY PROVEN (run 2)** | ✅ 2026-08-24: fusioncap_102338 captured via the method (one RViz, first try). ICP vs run 1: fitness 0.994, RMSE 19.4mm, origins 2.35°/50mm apart, extents match 2-5cm. THE DATA IS REAL AND RELIABLE. |
| **FUSION REPEATS — 3 for 3** | ✅ run1-native 62.4% / CROSS-CAPTURE (run2 geometry on run1 photo) 62.0% / run2-native 62.3%. Checkerboard lands in all three, through-glass house inside the window in all three. |
| **Start Rig defect FIXED** | ✅ 2026-08-24: rig_start.sh launches gscam+overlay_check+colorized but didn't clean-slate its own children -> orphan stacking held /dev/video0 -> camera hang. PATTERNS += overlay_check_node.py + gscam. (rig_start.sh NOT in repo — hygiene item.) |
| **RGBD pipeline stage (per-frame)** | ✅ make_rgbd.py v1.1: depth_{row:05d}.png uint16-mm beside each img (fill ~6.78%/frame on run1). DEBUGGED: naive pinhole back-projection errs up to 195mm at edges; tool ships rgbd_to_cloud (undistortPoints, 0.004mm). Uses npz R directly. |
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
## 7C0. RTAB METHOD — PROJECT HISTORY (SUPERSEDED by Point-LIO 2026-08-20; NOT current)
═══════════════════════════════════════════════════════════════════════════
COLD READER: RTAB-Map was the project's ORIGINAL odometry/SLAM method (Aug 2018-20 era).
The project PIVOTED to Point-LIO on 2026-08-20 (see 7M: Point-LIO beat the rotation bug that
RTAB could not — 2.87m ceiling vs RTAB's 13m collapse). Everything in the RTAB-METHOD sections
below is retained as HISTORY / REFERENCE, NOT as a present, usable path. Do not run these
commands or treat these statuses as current. The CURRENT odometry is Point-LIO (7M/7N).

RTAB-METHOD sections (all historical, read as project history only):
  - §3 "RTAB-Map — INSTALLED & HEALTHY" table — historical install/first-map facts.
  - 7C. IMU integration into RTAB odometry — attempted, paused (TF issue). RTAB-specific.
  - 7D. Camera colour integration via RTAB (Way A/B) — the colour-in-map plumbing.
  - 7I. Capture experiment B-vs-A — run on RTAB; the sampleB geometry was RTAB-rotation-collapsed.
  - 7J. Odometry under-tracks rotation — the RTAB failure that DROVE the Point-LIO pivot.
  - 7K. Strategic status — "RTAB rotation is the ceiling; Point-LIO is the fix" (the pivot decision).
STILL-POTENTIALLY-RELEVANT (don't lose): 7J's findings (split TF tree; scan-deskew under rotation;
  sparse-L2-cloud + ICP under-constrains rotation) were about the L2 cloud + ICP and MIGHT bear on
  Point-LIO if it ever shows rotation issues. Point-LIO currently handles rotation well (7M), so this
  is reference, not an active concern. Files milestone_map_20260818.db + inspect_pcd.py's "RTAB 13m"
  string are RTAB-era relics (inspect_pcd still works; its RTAB reference string is stale).

═══════════════════════════════════════════════════════════════════════════
## 7C. IMU INTEGRATION — DETAILED STATUS (attempted 2026-08-18, PAUSED, not solved)
>>> [RTAB METHOD — PROJECT HISTORY, superseded by Point-LIO. See 7C0. Not current.] <<<
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
>>> [RTAB METHOD — PROJECT HISTORY, superseded by Point-LIO. See 7C0. Not current.] <<<
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
>>> [RTAB METHOD — PROJECT HISTORY, superseded by Point-LIO. See 7C0. Not current.] <<<
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
>>> [RTAB METHOD — PROJECT HISTORY, superseded by Point-LIO. See 7C0. Not current.] <<<
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
>>> [RTAB METHOD — PROJECT HISTORY, superseded by Point-LIO. See 7C0. Not current.] <<<
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
## 7M. *** POINT-LIO WORKS — ROTATION BUG BEATEN (2026-08-20, first real run) ***
═══════════════════════════════════════════════════════════════════════════
MILESTONE: the pivot delivered on the FIRST real L2 capture. The rotation-under-tracking bug
that made RTAB a dead end is SOLVED by Point-LIO.

BUILD: point_lio_ros2 built clean on the Jetson Orin (2min, no aarch64 drama - livox+Eigen
already present). L2 config shipped correct as-is (verified vs Master). 3 pkgs: livox_ros_driver2,
unitree_lidar_ros2, point_lio - all built + registered.

CAPTURE (first hot run): LiDAR driver (unitree_lidar_ros2 launch.py) + Point-LIO
(mapping_unilidar_l2.launch.py). IMU init 0->100% clean (held still ~5s). ~270 pan. Ctrl+C ->
saved PCD. NOTE: the L2 launch AUTO-STARTS RViz (contradicts our "no rviz on Jetson" note; ran
fine here but consider disabling for long field captures). Gotcha hit + fixed: a DUPLICATE
driver instance ("bind udp port failed" spam) from a stale process - pkill -f
unitree_lidar_ros2_node, relaunch ONE clean driver (port bind success, no spam).

RESULT (inspect_pcd.py on scans.pcd, 104MB):
  3,381,174 points (~21x the RTAB sampleB assembly's 159k).
  DIMENSIONS: full extent 13.53 x 6.31 x 3.18 m ; robust(1-99%) 11.27 x 4.84 x 2.87 m.
  *** Z (height) = 2.87 m = a REAL CEILING. RTAB's collapse was 13.0m tall. THIS IS THE PROOF. ***
VISUAL (pointlio_views.png): front + side (height) views show a clean ~2.8m vertical band -
  flat floor, defined ceiling, coherent walls. NO RTAB smear/tower. Top-down shows a real
  ~13m floorplan (the swept space). Radial streaks = normal single-vantage rotational scan.

VERDICT: geometry is CORRECT. Point-LIO TRACKS ROTATION. The blocker that corrupted every RTAB
  pan (14.5deg yaw for 270 physical, 13m-tall collapse, half-room-missing) is BEATEN. Confirmed
  by numbers (2.87m vs 13m) AND by eye (straight floor/ceiling, real room).

HONEST SCOPE (what this does + does NOT prove):
  PROVES: odometry/rotation is solved; Point-LIO builds + runs on our Jetson; L2 config correct;
    dense correct geometry from a pan.
  DOES NOT YET PROVE: the full DELIVERABLE. This is GEOMETRY ONLY (no colour/texture). The
    texturing/relight bridge to Point-LIO output (.pcd + odometry, NOT an RTAB .db) is the NEXT
    build. per_shot_texture.py engine survives; a new bridge replaces db_to_texture.py.
  Also: single-vantage pan -> radial/uneven density; a walked multi-position capture fills better.

NEXT (post-milestone):
  1. Build the texturing bridge: Point-LIO cloud/odometry + timestamp-matched camera images ->
     per_shot_texture. (The genuinely new work; RTAB .db was the old input.)
     *** DONE 2026-08-21 — bridge BUILT + PROVEN COLD. Piece 2 pointlio_pose_matcher.py (pose
     interp, self-tested), Piece 3 pointlio_to_texture.py (multi-view per-face baker), Piece 1
     capture_pointlio_texture.sh, TEXTURE_BRIDGE_RUNBOOK.md. Proven photoreal on real data
     (161k cloud -> 385k mesh -> 90.3% render). Remaining: first COMBINED hot capture. See 7N. ***
  2. Consider disabling RViz in the L2 launch for lean field capture.
  3. Desktop launcher (run_point_lio.sh + PointLIO.desktop already drafted) - prove manually
     first (done), then the icon.
  4. Multi-position / walked capture for fuller density once texturing works.

═══════════════════════════════════════════════════════════════════════════
## 7N. ⚠️ DECISION FORK — POINT-LIO (chosen + PROVEN) vs FAST-LIVO2 (reserve) ⚠️
═══════════════════════════════════════════════════════════════════════════
COLD READER: returnable decision point, like 7G. We chose Point-LIO for odometry and it is now
PROVEN working (7M). If it ever needs replacing, DON'T re-derive — return HERE; FAST-LIVO2 is the
documented, peer-reviewed fallback, with its cost stated.

### THE FORK (decided 2026-08-21)
Two LiDAR-inertial(-visual) odometry paths for the L2:
  - POINT-LIO (CHOSEN + PROVEN): LiDAR-inertial. Algorithm is Unitree's OWN, tailor-made and tuned
    for the L-series — ships a real L2 config (lidar_type 5, scan_line 18, satu/extrinsic values).
    We build the ROS2 PORT dfloreaa/point_lio_ros2 (community packaging of that L2-tuned algorithm).
    Geometry + camera texture stay SEPARABLE. Built ~2min + beat the rotation bug on the first pan (7M).
  - FAST-LIVO2 (RESERVE, NOT chosen): LiDAR-inertial-VISUAL. Peer-reviewed, proven real-time on
    low-power ARM for large outdoor structure capture (Jiang et al., Buildings 2025, 15, 1458 — a
    140m arch bridge; same low-cost non-repetitive-LiDAR + camera + IMU class on an ARM board).

### WHY POINT-LIO (the reasoning to re-examine if backtracking)
  1. TAILOR-MADE FOR OUR EXACT SENSOR. Manufacturer-authored algorithm + L2-tuned config = fewer
     unknowns for the L2's non-repetitive rosette + IMU than a general LIVO stack tuned from scratch.
  2. KEEPS TEXTURE SEPARABLE = RELIGHTABLE. FAST-LIVO2 / R3LIVE-class systems BAKE lit colour into
     the map at capture time (their VIO reconstructs radiance under the CAPTURE lighting). That is the
     WRONG artifact for day->night relight — you cannot cleanly delight a pre-fused map. Point-LIO
     gives clean geometry; our bridge drapes texture SEPARATELY + deliberately. Relight is the rig's
     differentiator (7K) -> DECISIVE.
  3. NOW PROVEN ON OUR RIG (7M): not a gamble. Rotation solved, 2.87m ceiling vs 13m collapse.

### HONEST CAVEATS (don't overstate the claim)
  - "Written for the L2" = the ALGORITHM + TUNING are Unitree's and L2-specific; the ROS2 PORT
    (dfloreaa) is third-party packaging. FAST-LIVO2 also supports Livox/Unitree-class sensors — the
    edge is TAILORING, not exclusivity.
  - Unitree's code quality is below par (audit: scrambled-quaternion TF in the driver, 7C; known-weak
    SDK IMU handling). We ACCEPT the tailoring and VERIFY the feed rather than trust it. Tailoring >
    polish — but ONLY because we audit.

### FAST-LIVO2 (RESERVE) — EVIDENCE + REALISTIC YARDSTICK (from the Buildings 2025 paper)
  - They chose FAST-LIVO for real-time ARM performance on the same sensor class -> the reserve path
    is demonstrably viable on hardware like ours.
  - Their camera-LiDAR reprojection error = 2.48px; OUR calibration = 0.297px (we BEAT the published
    baseline — external confirmation our foundation is sound).
  - Moving-capture accuracy vs survey-grade TLS = 8.3cm (their stated hardware-class ceiling). USE
    THIS as the realistic yardstick for our L2 on a MOVING pan — NOT the 16mm STATIC number. Judge
    HOT-2 "coherent room" by SHAPE, not mm fidelity.
  - Sync: they used HARDWARE triggering (Livox PPS + triggerable HIKROBOT cam, STM32, ~10ms). We
    cannot (L2 has no sync GPIO, B0578 no trigger — 7B). They also state software sync DRIFTS over
    long captures but is ADEQUATE for SHORT ones -> independently validates our stop-and-go / short-
    capture mitigation (runbook C2).
  - DISQUALIFIER for us: bakes lit colour -> not cleanly relightable.

### CIRCUMSTANCES AT THE FORK (judge if changed on return)
  Goal = client-facing photoreal RELIGHTABLE stills (7E). Point-LIO already works (7M). Texturing
  bridge built + proven cold (2026-08-21). Jetson = Orin Nano 8GB, one-roof.

### WHAT TRIGGERS BACKTRACKING TO FAST-LIVO2 (define it now)
  Return here + switch if:
  - the project decides GEOMETRY-MEASUREMENT (not relight) is the deliverable -> FAST-LIVO2's baked
    colour stops being a disqualifier and its peer-reviewed ARM real-time performance wins; OR
  - the Point-LIO -> texture -> relight path proves unworkable in a way FAST-LIVO2's fused approach
    would avoid (UNLIKELY — the bridge is already built + proven cold).
  On return: accept that FAST-LIVO2 BAKES lit colour -> relighting is traded away or moved to a
  separate delight pass.

═══════════════════════════════════════════════════════════════════════════
## 7L. POINT-LIO PIVOT — STEP PLAN (decided 2026-08-20, next session)
═══════════════════════════════════════════════════════════════════════════
DECISION: pivot odometry from RTAB to Point-LIO. Rationale in 7K (RTAB rotation unfixable in
practice; Point-LIO is the manufacturer-demonstrated fix for L2 rotation tracking).
NOTE (2026-08-21): this pivot is DONE + PROVEN (7M). Odometry-engine choice is now a FLAGGED
RETURNABLE FORK — see 7N (Point-LIO chosen + proven; FAST-LIVO2 reserve). Steps below are the
historical build plan (kept for provenance; the build succeeded in ~2min per 7M).

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
═══════════════════════════════════════════════════════════════════════════
## 7O. FIRST FUSION — STEP SCHEDULE (small doable steps to a manipulable fused artifact)
═══════════════════════════════════════════════════════════════════════════
GOAL: a textured 3D artifact (LiDAR geometry + camera imagery) from a LIVE combined capture,
that OPENS and can be ORBITED. QUALITY DOES NOT MATTER — existence + manipulability is the bar.
[COLD]=no rig/no heat. [HOT]=L2 on, move with purpose. Do in order; don't start a step until
the prior one PASSES. (Full standalone copy: FIRST_FUSION_STEPS.md.)

START STATE (true as of 2026-08-21 eve, post-inventory): coexistence proven; save-order fix known;
one clean verified capture (1.1M pts, room-sized); Open3D installed+verified on Jetson; bridge
(matcher+baker) proven cold on the OLD dense cloud. INVENTORY RESULT: the texturing ENGINE
per_shot_texture.py is FOUND + SECURED — recovered VERBATIM from transcript 2026-08-20-16-31-39
(the three multi-view fns compose_world_to_cam/face_normals/best_image_per_face that the B1 bug had
dropped), and VERIFIED to reproduce sampleB_render.png EXACTLY (99% coverage / 450,304 tris /
mean 0.63 on the real sampleB db). It now lives in THREE places: ~/Desktop/per_shot_texture.py
(10,492 B), rig-files repo, and pasteable. Ground-truth source of record = that transcript.
inspect_pcd.py (on Jetson) is the C1 coherence checker (own PCD reader, matplotlib only, no Open3D;
auto-verdict vs the RTAB 13m collapse signature). analyze_l2_imu.py (on Jetson) = divergence diagnostic.

### PHASE A — COLD PREP (ready everything before any heat)
- A1 [COLD] Place the TWO bridge scripts next to the engine on the Jetson (engine per_shot_texture.py
  is ALREADY on ~/Desktop — verified). Put pointlio_pose_matcher.py + pointlio_to_texture.py in the
  SAME folder as per_shot_texture.py (Piece 3 imports per_shot_texture, so co-locate them).
  DONE: both --selftest print ALL PASS.
- A2 [COLD] `python3 -m venv ~/tex_env`; in it `pip install open3d rosbags opencv-python numpy`.
  DONE: import of all four prints ok. (Isolates numpy from system ROS2 — the clash guard.)
- A3 [COLD] Confirm per_shot_texture's hardcoded R_L2C/T_L2C == ~/Desktop/extrinsic_20260816.yaml.
  DONE: match (this is what aligns colour to geometry).
- A4 [COLD] Pre-write the record line (don't improvise hot):
  `ros2 bag record -o ~/Desktop/fusioncap_$(date +%H%M%S) /aft_mapped_to_init /image_raw`.

### PHASE B — HOT WINDOW (short, gated; the only heat). STILL init; SHORT; Point-LIO stop FIRST.
- B1 [HOT] LiDAR ON -> Start Rig -> wait ~15s. DONE: hz on /unilidar/cloud, /unilidar/imu, /image_raw.
- B2 [HOT] Point-LIO icon; hold DEAD STILL through IMU 1->100%. DONE: RViz shows a room, not a streak.
- B3 [HOT] paste A4 record line (new terminal); hold still ~20-30s; Ctrl-C the BAG. DONE: bag folder written.
- B4 [HOT] Ctrl-C POINT-LIO first; `stat` the pcd -> timestamp is NOW. DONE, then kill LiDAR/Stop Rig.
- B5 [HOT->COLD] rescue: `cp …/PCD/scans.pcd ~/Desktop/fusioncap_<stamp>_scans.pcd`. L2 now fully OFF.

### PHASE C — COLD PROCESSING (rig off; in ~/tex_env)
- C1 [COLD] verify coherence with the existing tool: `python3 ~/inspect_pcd.py <rescued.pcd>` ->
  room-sized extent + a coherent floorplan in pointlio_views.png, NOT a km smear. Smeared -> redo Phase B.
  (Better than a one-liner: own PCD reader, no Open3D/venv needed, auto-verdict vs RTAB 13m collapse.)
- C2 [COLD] `pointlio_pose_matcher.py <bag> --image-topic /image_raw --dump-frames <bag>/frames`.
  DONE: high match %, frames count == stamp count.
- C3 [COLD] `pointlio_to_texture.py <rescued.pcd> posed_images.npz <bag>/frames --scale 3 --out first_fusion.png`.
  DONE: prints faces + coverage, writes the render. <-- THE FUSION EXISTS.
- C4 [COLD] open the MANIPULABLE artifact — view the textured mesh/cloud in Open3D, orbit it.
  DONE: 3D window rotates the fused geometry. <-- ENDPOINT. (Note: C4 may need a small cold viewer
  tool; the bridge currently outputs a render, not yet a one-command orbitable mesh.)

### IF A STEP FAILS
- B2 streaks -> bad init; redo dead-still. C1 smeared -> diverged run, don't process. C2 low match ->
  odom/image clocks may not overlap (check bag has both + spans overlap). C3 texture OFFSET (not just
  holey) -> pose/time mismatch or extrinsic drift (recheck A3). Holes/black -> meshing limiter, EXPECTED.

### HARDWARE NOTE (considered, not adopted): external IMU (Taobotics TB100, ~$125)
Could improve tracking reliability + bring the microsecond HARDWARE SYNC the L2 lacks (7B). BUT it
does NOT offload Jetson compute, and adopting it is a PROJECT not a drop-in: new IMU->LiDAR extrinsic
calibration, config rework (non-native IMU topic), and time-sync wiring — and Point-LIO's whole value
(7N) is being tailored to the L2's native IMU. VALIDATE that divergence is actually an IMU problem
(vs. init/motion technique) before spending. Filed as an avenue, not a plan.

═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
## 7P. POINT-LIO LAG / SYNC — INVESTIGATION DOSSIER (updated 2026-08-23)

*** LIKELY ROOT CAUSE FOUND (2026-08-23): JETSON SYSTEM CLOCK vs UNITREE FROZEN TIMESTAMPS ***
A user with the SAME symptom on the same hardware class (Jetson + Unitree) reported the mechanism,
and it fits our evidence exactly:
  - Unitree's internal board publishes sensor timestamps FROZEN around a fixed date (their Go2 showed
    ~Sep 2025; our bag showed frozen ~Feb 2026, all-identical stamps). This is inherent to the Unitree,
    NOT our bug.
  - Point-LIO (and the ROS layer) enforce MONOTONICALLY-INCREASING timestamps: a message whose stamp is
    earlier than the previous one is DROPPED. And the incoming sensor stamp must be EARLIER than system
    time or data gets rejected / never processed.
  - JETSONS HAVE NO RTC BATTERY -> on reboot the clock resets (toward 1970) until the network/NTP
    corrects it. So if you capture BEFORE the clock syncs, system time is BEHIND the Unitree's frozen
    future-stamp -> messages get rejected partway -> ODOMETRY CUTS OUT (our 5.5s cutoff) while images
    (different clock path) keep coming. This explains BOTH the frozen stamps AND the 5.5s cutoff.
  - VERIFY diagnostic (from the report): 
    ros2 topic echo --once /unilidar/imu --field header.stamp.sec | head -n1 | xargs -I{} date -d @{}
    -> shows the date the SENSOR is stamping. Compare to `date` (system clock).
THE FIX IS TRIVIAL: ensure the Jetson clock is CORRECT (NTP/network) BEFORE capturing, or set it
manually with `date`. As of 2026-08-23 the Jetson clock reads correctly (Aug 23 2026), AHEAD of the
frozen Feb-2026 sensor stamp = the GOOD state. So the bug may ALREADY be self-resolved via NTP; the
bad captures were likely taken when the clock was wrong at capture time.
CAVEAT: the report was on a Go2 (/utlidar topics) vs our standalone L2 (/unilidar topics) - same
Unitree timestamp behavior, adjacent product. Treat as strong-but-unverified until a fresh hot capture
confirms the cutoff is gone. VALIDATION TEST: confirm `date` is correct -> fresh capture -> check if
odom now publishes the FULL duration (no 5.5s cutoff). If yes, root cause CONFIRMED and captures are
reliable going forward.
IMPLICATION FOR OLD DATA: captures taken with a wrong clock can't have their frozen per-point stamps
retroactively "corrected" into valid sync (the per-point time relationships were never recorded right).
Best existing capture (192455) is still usable AS GEOMETRY (the cloud is coherent) but is not a model
for reliable future capture. Going forward: correct-clock captures should be clean.

--- earlier dossier (superseded root cause, but checklist still useful for other timestamp issues) ---
## 7P-OLD. POINT-LIO LAG / SYNC — INVESTIGATION DOSSIER (2026-08-22, banked for later)
═══════════════════════════════════════════════════════════════════════════
STATUS: characterized, NOT yet fixed. Banked so it doesn't ambush us later (esp. once
feeding Unreal, which needs reliable captures). This is the "5.5s odom cutoff / displaced
cluster / frozen-timestamp" problem, now traced to a ROOT CAUSE with a fix-path AND a sidestep.

### CONFIRMED EVIDENCE (observed, not hypothesis)
- Odom (/aft_mapped_to_init) HEADER timestamps are FROZEN: all identical (~1787358243.694),
  and ~53s BEFORE the recording started. (We work around this by matching on BAG time.)
- Odom published only ~5.5s of a ~50s run, then went silent while images kept coming ~44s more.
  The CLEAN short capture (192455) only HAD ~5.5s of odom - likely WHY it stayed coherent.
- Odom bursts at ~3000 Hz. **This is BENIGN** - see Note E below; it's the documented effect of
  publish_odometry_without_downsample:true, NOT part of the bug. (One fewer thing to chase.)
- The Point-LIO PAPER proves the estimator survives 75 rad/s / 80 m/s2 / IMU saturation on drones.
  We do STATIONARY captures. So the estimator's motion-handling is NOT the problem - it's plumbing.

### ROOT CAUSE (README-confirmed direction): IMU-LiDAR SYNCHRONIZATION
The Point-LIO README's **#1 important note (A)**: "Please make sure the IMU and LiDAR are
Synchronized, that's important." Our frozen-timestamp evidence is exactly a sync failure signature.
COMPOUNDED by running TWO adaptation layers removed from the original:
  - Livox-native algorithm -> Unitree L2 fork (unitreerobotics/point_lio_unilidar, ROS1)
  - -> ROS2 port we actually run (dfloreaa/point_lio_ros2).
Each layer is a place timestamp handling can break. Point-LIO is fundamentally built around the
Livox CustomMsg per-point-timestamp structure ("only livox_lidar_msg.launch produces the timestamp
of each LiDAR point which is very important for Point-LIO").

### FIX-PATH CHECKLIST (when we return to it)
1. Grep Point-LIO logs for **"Failed to find match for field 'time'"** (README Note C). If present,
   the L2 cloud is MISSING per-point timestamps -> Point-LIO can't process correctly. Primary check.
2. **timestamp_unit** in unilidar_l2.yaml (0=sec,1=ms,2=us,3=ns) vs. what the L2 driver ACTUALLY emits.
   A wrong unit = every point's time misread. LEADING single-parameter suspect - REINFORCED by README
   5.3: for Velodyne/Ouster (spinning LiDARs w/ PointCloud2 time field - the L2's CATEGORY, not Livox
   CustomMsg), timestamp_unit is THE documented knob to make per-point timestamps work. The L2 is a
   spinning-style sensor, so this is very likely the exact parameter that's wrong.
3. **time_lag_imu_to_lidar** - the LiDAR/IMU time-offset parameter. If wrong, point-by-point fusion desyncs.
4. **satu_acc / satu_gyro / acc_norm** (README Note B + 5.2 item 6: "norm of IMU's acceleration
   according to UNIT of acceleration messages"). Set to the L2's REAL IMU values + UNITS. Units trap:
   if L2 reports accel in g's, acc_norm ~1; if m/s2, ~9.81 (cf. Livox built-in=1, Pixhawk=9.805). A
   units mismatch misconfigures the whole filter scaling without an obvious crash. (Ours: satu_acc 30,
   satu_gyro 35 - VERIFY these are the L2's actual values + correct acc_norm unit, not Livox defaults.)
5. **DIFF our config against the official unitreerobotics/point_lio_unilidar** (ROS1) as ground-truth
   reference for L2 timestamp handling. Also diff dfloreaa ROS2 port behavior.
6. Search BOTH repos' Issues for "odometry stops", "timestamp", "5 seconds", "Unitree".
CONFIRMED FROM CONFIG (2026-08-23 grep of unilidar_l2.yaml): acc_norm:9.81 CORRECT (L2 reports m/s2,
measured gravity=9.63 confirms). satu_acc:30/satu_gyro:35 fine (IMU measured ~9.8/~0.02, nowhere near).
timestamp_unit:0 (seconds). time_lag_imu_to_lidar:0.0. IMU SATURATION RULED OUT BY DATA (0 crossings on
a stationary capture). These are secondary now that the CLOCK root cause (above) is the likely answer.
CONFIRMED-OK (not the problem): lidar_type:5 + scan_line:18 MATCH the official Unitree L2 config
(DeepWiki). extrinsic_est_en:false is correct per README Note D (extrinsic is given).

### SIDESTEP (README Note F) - possibly FASTER to reliable captures than fixing sync:
Run Point-LIO **LiDAR-ONLY**: set imu_en:false, use_imu_as_input:0, and give a good gravity_init.
This DODGES the IMU-LiDAR sync problem ENTIRELY (no IMU = nothing to sync). Tradeoff: loses the
aggressive-motion/saturation robustness - which we DON'T USE (stationary/gentle captures). Risk:
LiDAR-only can struggle in geometrically degenerate scenes (long blank hallway, featureless wall)
where the IMU normally helps. For a bounded interior with plenty of geometry, likely fine. CHEAP to
test and could make captures reliable WITHOUT solving the sync bug. Worth trying first.


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
## 7U. THE "ODOM CUTOFF" — REDIAGNOSED AS CAPTURE PHYSICS (2026-08-24) — NOT A BUG

*** MAJOR CORRECTION 2026-08-24 (Master 20.3) — READ THIS FIRST, it overturns the rate-
coupling framing below. The "cutoff" is NOT a Point-LIO software bug, NOT a buffer/count
limit, NOT a timestamp bug, and NOT a matcher bug. IT IS CAPTURE PHYSICS: Point-LIO is a
LiDAR-INERTIAL method that needs TRANSLATION (parallax) to resolve motion; a PURE STATIC
ROTATION (pivot in place) starves it -> tracking collapses -> the pose stream goes short.
EVIDENCE (fusioncap_185910, a smooth deliberate ~300deg STATIC pan, 2026-08-24): only 4,631
poses / ~1s real span; the PCD covered only ~180deg (extent 1.81x6.06m = a narrow forward
slab, bbox almost entirely one side of origin) — i.e. once tracking degraded, swept-in angles
did NOT accumulate into the map. Turned 300deg physically; map kept ~the first slice.
MATCHER AUDITED + CLEARED THE SAME DAY: the LIVE matcher (pointlio_pose_matcher.py, 16939
bytes, Aug 22 08:21) reads MONOTONIC BAG-TIME on both streams (line 174 odom_ns.append(bt),
line 181 img), NOT header stamps; its 7 built-in self-tests ALL PASS (interp 5e-16 m, extrinsic
1e-16). So every "span" number it reported is TRUE, not an artifact. The earlier
"matcher misreads header stamps" theory (floated re: 182551) is RETRACTED — reading the code
disproved it. THREE stale .bak matchers on Desktop are version decoys (they can't run unless
named, but they nearly caused a wrong-version debug); tuck them into ~/Desktop/matcher_old/.
WHY THE GOOD CAPTURES WORKED: 083911 and 102338 were small HANDHELD movements with natural
translation -> odometry tracked -> full room + 19.4mm repeatability. The "failures" were the
more static/rotational takes. The variable was always TRANSLATION, not a mysterious cutoff.
THE FIX IS CAPTURE STRATEGY, NOT CODE: use translation — slow out-and-back / arc-walk / drift
(the A2 pattern the mission already specified). Do NOT attempt a static-pivot pan for coverage.
The rate/count data below is kept as HISTORY of the investigation but its "buffer/count-limit"
conclusion is SUPERSEDED by the physics explanation. ***

## 7U-history. earlier rate-coupled framing (SUPERSEDED — kept as investigation history)
═══════════════════════════════════════════════════════════════════════════
THE DEFECT: Point-LIO odometry stops publishing partway through a capture; all images
after the cutoff get no pose and are dropped by the matcher. This is now THE blocker —
it stands between us and multi-view coverage (the pan), the full bake, and real deliverables.

THREE DATA POINTS (all 2026-08-24, same rig/config/room):
  | capture           | odom span | odom rate | image span | matched      |
  | fusioncap_083911  | 16.09s    | 2637 Hz   | 32.78s     | 192/332 (58%)|
  | fusioncap_102338  |  4.60s    | 6903 Hz   | 29.45s     |  59/253 (23%)|
  | fusioncap_182551  |  7.03s    | 4462 Hz   | 25.16s     | 131/256 (51%)| (the pan)
THE PATTERN (the new finding): odom SPAN and PUBLISH RATE are INVERSELY COUPLED —
  2637Hz->16s, 4462Hz->7s, 6903Hz->4.6s. Higher rate = shorter life. This is NOT random
  and NOT purely timestamp-freeze: it looks like a FIXED BUDGET consumed faster at higher
  rate (a bounded buffer / queue / preallocated state that fills in ~N messages regardless
  of wall-clock: 2637*16 ~= 42k, 6903*4.6 ~= 32k, 4462*7 ~= 31k msgs — same ORDER, ~30-42k
  messages before death — STRONG hint it is a MESSAGE-COUNT / buffer limit, not a time limit).
IMPACT ON THE PAN: fusioncap_182551 (the pan) died at 7.03s -> the pan's wide angles (after
  t=7s) have NO poses; 131 matched frames are all clustered in the first ~7s = effectively
  another single-station capture. MULTI-VIEW COVERAGE NOT YET ACHIEVED. The cutoff must be
  fixed before the pan can deliver the multi-view densification (7T) it is meant to.
DEBUG LEADS (in priority order):
  1. MESSAGE-COUNT/BUFFER hypothesis (new, strongest): ~30-42k odom msgs before death across
     all three. Look for a preallocated buffer / max_iteration / point-or-pose queue cap in
     Point-LIO config or code that's sized in COUNT not time. publish_odometry_without_downsample
     :true produces the huge rates (2637-6903Hz burst) — turning it OFF or capping rate may
     extend span dramatically. FIRST THING TO TRY.
  2. Timestamp/clock (7P, prior lead): Jetson-clock vs frozen sensor stamps; HKU LiDAR_IMU_Init
     temporal-offset idea (7S). Less favored now that the count-coupling is visible.
  3. IMU saturation ruled out earlier (0 crossings).
STATUS: characterized, not fixed. Debug session starting 2026-08-24. Do NOT run another pan
  expecting multi-view until the cutoff extends past the full pan duration (~30-45s).

## 7T. DENSIFICATION — DENSE DEPTH PER PIXEL (sandbox finding, 2026-08-24)
═══════════════════════════════════════════════════════════════════════════
ORIGIN: operator's first-principles line of reasoning — "we deal in pixels; pixels are
just points containing information; the LiDAR measures geometry but we are hardly using
all of it; if we convert to pixels and overlap the camera we'd get something we haven't
seen." CORRECTED MECHANISM (banked so it is not re-confused): you do NOT convert the
cloud TO pixels — a flat render THROWS AWAY depth and holds LESS than the cloud. The gain
runs the OTHER way: give every CAMERA pixel a DEPTH. The camera grid (2,304,000 px) is
~15x denser than the LiDAR's coverage of the same view (~156k projected px = 6.78%); so
the dense color grid INHERITS the sparse LiDAR measurement and fills the ~93% of pixels
the laser missed by borrowing depth from neighbors, guided by color edges. This is the
RGBD / depth-completion direction the 7S research (CMU, SiLVR) points to.

WHAT WAS PROVEN IN SANDBOX (on fusioncap_083911 frame img_00000, the verified make_rgbd
depth map):
  - sparse LiDAR depth in-frame: 155,965 px = 6.77%.
  - densified (color-edge-aware flood + edge-preserving smooth): 100% fill = all 2,304,000
    px carry a depth. 15x more MEASURED-OR-INFERRED px than raw LiDAR gave. ~0.5s compute.
  - back-projected (undistortPoints, the CORRECT consumer) -> a 2,304,000-point COLORED 3D
    cloud: one point PER CAMERA PIXEL, not per LiDAR return. Evidence: densify_quad.png
    (rgb | sparse | dense | dense+rgb), dense_3d_views.png (4 angles),
    dense_fused_frame0.ply (+ _light 399k / _ascii fallbacks).

THE HONEST LIMIT (the reason the 3D view was enlightening, not just pretty):
  - Where the LiDAR actually hit = metric truth. The filled 93% is INFERRED (a smart,
    color-guided interpolation) — safe ACROSS a sampled flat surface (filling scan-stripe
    gaps on a wall), riskier across complex/unsampled geometry. For the crane-accurate
    mission this distinction is everything: inferred px are not measured px.
  - Seen in 3D from the SIDE, one frame is a SINGLE-SIDED, DISHED SHELL: only the front
    surfaces the one camera saw, floating at their depths — no back walls, objects hollow
    from behind. Color makes it READ complete; geometry shows it is one viewpoint's sheet.
  - The simple method here (flood+bilateral, 0.5s) is the FLOOR; the research-grade version
    (CMU depth-completion / MVS) genuinely RECONSTRUCTS gap geometry rather than interpolating.

WHY THE PAN IS THE RESOLUTION (ties directly to the next capture):
  Each overlapping frame back-projects its OWN dense sheet from its OWN angle. Stacked in
  the shared map frame, the single-sided shells become a real SOLID (back sides, far walls,
  corners one frame missed), and depth in the OVERLAP regions becomes MEASURED FROM SEVERAL
  ANGLES instead of interpolated from one. So: single-frame densification = the floor;
  multi-view (270-pan / A2 out-and-back) = the same representation raised toward metric
  truth across the whole grid. This is a strong argument FOR the pan, arrived at from first
  principles by the operator.

STATUS: SANDBOX PROOF-OF-CONCEPT, not an adopted pipeline stage or a validated deliverable.
Tooling used: make_rgbd.py v1.1 (the per-frame RGBD stage) + a throwaway densify script.
NOT YET: a hardened densify tool, multi-view accumulation, or metric validation of filled
px against tape. FLAGGED for the operator; the pan capture is the natural next test.

═══════════════════════════════════════════════════════════════════════════
## 8H. HARDWARE / POWER / THERMAL / FIELD-READINESS (un-benching prep, 2026-08-25)
═══════════════════════════════════════════════════════════════════════════
POWER TOPOLOGY (resolved, do not re-derive):
  - Ugreen bank (photo-confirmed): two USB-C ports 140W (IN1/OUT1) + 100W (IN2/OUT2), one
    USB-A (OUT3). Total-output table: 5V7A/9V6A/12V6A/15V6A/20V10A (=200W aggregate).
    Massively over-spec'd for the rig (~35-45W). POWER IS RULED OUT as a crash cause (the
    pan-session stack-death was operator launching Point-LIO with no Start Rig, not brownout).
  - L2 = 12V DC, 10W, ~1A, DC 3.5x1.35mm barrel jack (CONFIRMED direct from Unitree: 12V DC,
    10W@25C, -20..60C, IP54). Derive 12V from the bank via a YTADNETH voltage trigger (0-20V
    adjustable) SET + METERED TO 12V. *** THE TRIGGER IS ADJUSTABLE 0-20V — a wrong/bumped
    setting could put up to 20V into a 12V sensor and DESTROY the L2. RULE: meter it at 12V
    before EVERY L2 connection; mark/lock it. Two triggers owned: one for L2@12V, one spare
    (keep as a pre-set known-good backup). ***
  - Jetson = USB-C PD on the 140W port, NO trigger (PD negotiates its own safe voltage; a
    trigger there would REMOVE that safety). Arducam = USB off the Jetson. 
  - L2 CONNECTION IS ETHERNET: static 192.168.1.62, interface enP8p1s0, NetworkManager profile
    "L2-static" (persists across reboots). rig_start.sh waits for link + pings before launch.

THERMAL (L2), from Unitree manuals (scraped 2026-08-25):
  - TWO-STAGE over-temp protection: (1) over-temperature WARNING issued first, then (2) "stops
    running" only when severely exceeded. Cover-temp threshold 85C; spec/storage 60C. So the
    failure is NOT silent — there is a warning before shutdown.
  - apd_temperature (deg C) is self-reported in the L2 working-status data (also apd_voltage,
    laser_voltage, dirty_index, packet_lost). Jetson also self-reports (jtop/tegrastats).
  - SELF-HEATING MODE: ambient -10..30C -> L2 self-heats and WITHHOLDS point cloud until warm;
    peak power rises to 13W. Expected on cold starts, not a fault; budget the 13W spike.
  - RESTART-AFTER-THERMAL-SHUTDOWN PROTOCOL IS UNDOCUMENTED (searched; a Restart command exists
    in SDK/Windows sw, but post-cutoff recovery behavior is unspecified). The WARNING FORM is
    also unspecified (status field? LED? Windows-only?). 
  - DECISION (standing rule): PREVENTION, not brinkmanship. Monitor apd_temperature, set a SOFT
    CEILING ~50-55C (below the protection point), stop+cool before any warning. *** DO NOT
    bench-induce a thermal cutoff to learn its recovery — the sensor is too valuable and the
    recovery is unknown; ask Unitree support + read the SDK source instead. *** 
  - AUG-26 to-dos: (a) ros2 topic list -> does the driver expose an L2 status/temperature topic?
    (b) if yes, log apd_temperature over a capture + set the soft ceiling; (c) check SDK source
    (github unitreerobotics) for the over-temp field name/form; (d) email Unitree support for the
    warning form + recovery protocol.

FIELD DISPLAY (drone-industry prior art, researched 2026-08-25):
  - Universal standard (DJI Zenmuse L2 "Point Cloud LiveView", Leica BLK2GO GrandSLAM, XGRIDS,
    FARO Orbis): the field screen shows the LIVE POINT CLOUD BUILDING, color-coded FOR COVERAGE
    so gaps are visible mid-capture — NOT the camera feed. This is exactly what RViz already
    does -> RViz IS the professional answer; the camera is fixed to the rig, so framing is not
    the priority. Steal: color points for coverage; small status overlay (tracking / recording /
    battery / L2 temp), like DJI's altitude/speed/battery telemetry.
  - Independent validation of THIS project's findings: pros say overlap + loop closure stabilize
    handheld scans (=our translation/overlap plan); scan quality is operator-steadiness-dependent
    (=our wobble thread); Leica GrandSLAM = LiDAR-SLAM + Visual-SLAM + IMU (=our exact architecture).
    We reinvented, from first principles, the BLK2GO design.

FIELD DISPLAY HARDWARE + TOUCH UI (Waveshare 7"):
  - Waveshare = a standard HDMI/USB touchscreen; currently would show whatever windows open
    (terminal + RViz). For dev: drive big monitor + Waveshare as EXTENDED (not mirrored) displays
    off the Jetson's two outputs — an HDMI splitter only MIRRORS (forces low common res); check
    the carrier board's outputs instead of buying a splitter.
  - RViz is heavy (GPU/RAM/heat) on the 8GB Jetson in MAXN SUPER — watch load; a lighter live
    coverage view may be worth it for field use (refinement, not day-1).
  - TOUCH FIELD-UI concept (Aug-26+): full-screen menu, 4 BIG thumb targets fronting scripts that
    already work — Start Rig / Start Capture / big STOP / status panel. Turns the rig from
    "operate by terminal" into "hand it to a gaffer." Build once Waveshare is plugged in (see real
    target sizes at 7").

STATUS: all of 8H is PREP/RESEARCH for un-benching; nothing here is executed/instrumented yet.
Gates it feeds: the Aug-26 plan (init work + first translation captures + these hardware items).
═══════════════════════════════════════════════════════════════════════════
## 8I. FIRST FULL BAKE + PROCESSING-STATION / UNREAL PATH (2026-08-25)
═══════════════════════════════════════════════════════════════════════════
FIRST FULL BAKE — CHAIN PROVEN END-TO-END (sandbox, on fusioncap_083911):
  Stages all ran, no breaks: (1) clean = statistical outlier removal, 97.4% kept (coherence
  not distance); (2) normals; (3) MESH = Poisson depth-9, 357k verts / 710k tris, TRIMMED 5%
  low-density; (4) TEXTURE = per-vertex best-facing-frame color, 64.3% verts textured from 192
  frames; (5) EXPORT. The "never-executed stretch" is now executed once — the plumbing works.
  *** SURPRISE FINDING: d9 mesh ran in ~3GB RAM in 8.4s. The standing ">8GB, needs processing
  station" assumption for MESHING may be WRONG — RE-TEST meshing on the Jetson; the station may
  only be needed for UNREAL itself, not the bake. ***
  HONEST QUALITY: ROUGH, not photoreal. Poisson inflates the single-vantage cloud into lumps;
  36% untextured shows gray; far through-window geometry went stringy. This is the single-vantage
  problem in mesh form — MULTI-VIEW TRANSLATION CAPTURE is the fix. Pipeline is SOUND; input
  quality is the variable. Do NOT judge the deliverable by this bake.
  EXPORTS (in outputs + on Jetson): bake_083911_textured_mesh.ply (27.5MB, a MESH — open with
  read_triangle_mesh), bake_083911_unreal.xyz (12.3MB ASCII xyzrgb — the Unreal-plugin-native
  format, NOT .ply), bake_083911_render.png. These are 3D — view in a 3D viewer, not the chat.

PROCESSING STATION — SIZING + HARDWARE:
  - The budget laptop (HP 14, Intel Celeron N4120 @1.1GHz, 8GB RAM, Intel UHD 600 512MB, 58GB)
    CANNOT run UE5 — no discrete NVIDIA GPU; Lumen/Nanite need RTX-class. REPURPOSE it as: the
    WINDOWS UTILITY box (the L2 Unilidar 2 software is Windows-only — for apd_temperature + config)
    + a terminal/window into Vagon. Not deadweight, just not the render box.
  - Pipeline steps (clean/mesh/texture): modest — d9 ran in 3GB, maybe stays on the Jetson.
  - UE5 + Lumen (the mission): needs a REAL NVIDIA RTX GPU, 12GB+ VRAM floor (16GB comfortable),
    32GB RAM preferred (16 will pinch). This is the actual requirement, cloud-rentable by the hour.
  - CLOUD-GPU = the path (no workstation purchase): VAGON hourly — Planet (Tesla T4) ~$0.99/hr,
    Spark (RTX A10G) ~$1.67/hr; storage ~$8/mo to persist the install. iRender RTX 4090 ~$8/hr for
    heavy cinematic renders later. *** SaaS render farms (GarageFarm/Rebus/Fox) CANNOT run UE5 —
    it needs an INTERACTIVE desktop session, not batch. Use IaaS interactive desktops (Vagon/iRender). ***
  - UE LiDAR Point Cloud plugin: FREE + BUILT-IN since UE4.25 (Edit>Plugins>enable>restart). Our
    .xyz (xyzrgb) matches its RGB import. No plugin purchase needed.
  - Meshmixer (Autodesk, free): optional geometry-cleanup side tool (hole-fill, trim, decimate).
    *** CAUTION: its smoothing/sculpting/auto-repair MOVE geometry — never let it touch the
    measured surfaces we sell as tape-accurate. Redundant with Open3D anyway. Not a pipeline piece. ***
  - RealityScan (photogrammetry): a LATER, SEPARATE investigation (appearance/texture) — and note
    it builds geometry from PHOTOS, which may COMPETE with (not complement) our LiDAR accuracy.

VAGON TRIAL (2026-08-25) — access PROVEN, Unreal install BLOCKED:
  - PROVEN: can spin up a Vagon machine, reach the Windows desktop, open Epic launcher, sign in,
    and drag the bake file IN (dashboard=outside the rented PC; virtual desktop=inside, where
    Unreal can see files — must land the file on the Windows desktop, not just the web dashboard).
  - BLOCKED: Epic launcher "Install Engine" did nothing + "+" greyed out. This is a KNOWN EPIC BUG
    (not Vagon, not the account): the launcher cant go "online" on a fresh machine, which greys the
    install. Sample-grab trick (grab a free Samples item to force online) DID NOT clear it this time.
  - FIXES FOR NEXT SESSION (do BEFORE burning meter): (a) fully restart the Epic launcher, or better
    RESTART the Windows machine, to force a clean online session — the most common real fix; (b) then
    Samples-grab; (c) BEST: use VAGON'S OWN APP CATALOG (pre-installed Unreal) to skip the Epic
    launcher entirely — confirm this exists on the Vagon dashboard OFF the clock.
  - *** GitHub/EpicGames Signup (source code) = AVOID for us: that route COMPILES the engine from
    source (hours, tens of GB, dev tooling) — it is for engine modders, does NOT fix the launcher
    glitch, and is the wrong tool. We want the BINARY (launcher) build. ***
  - Architecture clarified: you do NOT run Vagon "on" the Jetson — Vagon is a rented remote PC you
    reach through a browser from ANY device. Jetson MEASURES (capture+bake, native), Vagon RENDERS
    (Unreal), linked by a simple file hand-off. Two jobs, move one file.
  - THE OPEN UNREAL TEST (next session, ~$1-4, benched): install/enable UE5 + LiDAR plugin, import
    bake_083911_unreal.xyz, check (a) does it import, (b) does it look right, (c) SCALE — room ~4.5m
    should read ~450 Unreal units (1uu=1cm). That closes the LAST pipeline unknown.

═══════════════════════════════════════════════════════════════════════════
## 8J. FIELD DATA ARCHITECTURE — capture strategy, storage, transmission (2026-08-26)
═══════════════════════════════════════════════════════════════════════════
THE BARN PROBLEM (the scenario that forced this): measure a large detailed space (e.g. a
barn interior), spend ~1 hour capturing. What happens to that much data?

DATA RATE (from real captures): a ~30s bag ran ~2-3GB -> ~4-6GB/MINUTE (cloud+image+IMU+odom).
  => ONE HOUR ~= 250-360GB in a single session.

THREE WALLS a naive continuous hour hits:
  1. STORAGE: Jetson has ~162GB free -> an hour DOES NOT FIT; it fills mid-capture and the
     bag dies/corrupts. This is a HARD STOP we had not confronted.
  2. PROCESSING: an hour ~= 36,000 frames @10Hz vs the ~200 we bake now = ~180x the load.
     The 90s bake becomes HOURS. Untenable on the Jetson for a continuous hour.
  3. REVIEW: you cannot "scrub" an hour of 3D point cloud like video footage. You must
     PROCESS it into a map first (= wall 2), then view the map.

THE FIX — CAPTURE STRATEGY, not just technique:
  Do NOT roll continuously for an hour. Capture the space as a SERIES of DELIBERATE shorter
  PASSES (a corner, the loft, the stalls, the beams), each a bounded bag (tens of sec to a
  couple min), each monitored live and checked, then REGISTER them together into one model.
  - Registration is ALREADY PROVEN: the cross-capture ICP that aligned run1<->run2 at
    fitness 0.994 / 19.4mm RMSE is exactly this. Proven at 2 captures; not yet done at SCALE
    (e.g. 20 passes). Scaling registration is the new pipeline piece this implies.
  - This is the Leica BLK2GO / DJI pro method: overlapping passes, not one continuous stream.
  - Solves all three walls: bounded bags fit storage, each processes in reasonable time, and
    coverage is checked per-section (live + after).

HARDWARE — 2TB USB DRIVE (buy this):
  - Wire a 2TB USB drive to the Jetson and record bags STRAIGHT TO IT (not the SD card).
    ~300GB/hr into 2TB = ~6hrs headroom. Removes the storage wall. Cheap ($60-100), reliable.
  - *** RECORD WIRED, NOT WIRELESS: the 5GB/min live firehose is too much to stream reliably
    over WiFi -> dropped packets = silent corruption. The recording path MUST be wired
    (USB drive on the Jetson). ***
  - Storage fix is an ENABLER, not a strategy: it removes space anxiety but does NOT fix
    walls 2 & 3 -> still capture in deliberate passes.

WIRELESS — SPLIT INTO THREE JOBS (this is the correct architecture):
  - RECORDING: WIRED (USB drive). Wireless is OUT here (corruption risk). 
  - LIVE MONITORING: WIRELESS, IN. Foxglove (leading candidate, untested) on a phone/tablet
    shows a LIGHT coverage view (downsampled cloud + status) over the LAN — a trickle, not
    the firehose, so WiFi handles it fine. This is the Teradek-instinct answer, intact.
  - OFFLOAD: WIRELESS, IN. After a pass, move the bag to laptop/NAS over the LAN — relaxed,
    a dropped packet just retries.
  - So wireless is NOT eliminated — only the recording is wired; monitoring + offload stay wireless.
  - THE FIELD LAN: a portable, USB-powered (runs off the Ugreen bank) travel router creates
    the network bubble on location (no infrastructure needed). Jetson joins as a CLIENT over
    WiFi (its ETHERNET stays occupied by the L2 @192.168.1.62). Phone/tablet joins too.
    Cleaner than making the Jetson itself broadcast a hotspot (no extra load on the capture PC).

FIELD WORKFLOW (assembled): power (Ugreen -> Jetson 140W PD / L2 12V trigger / router USB) ->
  Jetson+phone join router LAN -> rig up -> Foxglove on phone shows live coverage -> WALK
  deliberate passes watching coverage fill, record wired to 2TB -> stop -> offload bag over LAN
  -> pipeline (matcher/extract/fuse/bake) on Jetson or laptop -> export -> Vagon (Unreal relight).

STATUS: all of 8J is PLANNED field-architecture, none built/tested. Buy: 2TB USB drive,
  portable USB-powered travel router (WiFi6, decent throughput). Test: Foxglove over the router
  to a phone; recording to USB drive; scaled multi-pass registration.

═══════════════════════════════════════════════════════════════════════════
## 8K. TIMECODE / SYNC + FIELD CHECKER + "MISSING FOOTAGE" (2026-08-26)
═══════════════════════════════════════════════════════════════════════════
TAU IS A TIMECODE PROBLEM (operator's film-background reframe, valuable):
  - Camera and LiDAR are two devices WITHOUT a shared clock. A camera frame and a LiDAR sweep
    that claim the same timestamp actually differ by ~175ms (tau). That is EXACTLY the film
    "sound and picture out of sync" problem, in a different domain (camera=picture, LiDAR=sound).
  - Film's CLEAN fix isn't measuring drift after the fact — it's JAM-SYNC: lock all devices to
    one timecode generator so there's no drift to correct. The rig's equivalent = a HARDWARE
    TRIGGER: a shared electrical signal that fires the camera and timestamps the LiDAR off ONE
    clock. This is the SAME idea as the Master's "hardware-triggered camera kills tau" plan.
    Operator's film instinct independently arrived at the correct long-term fix. (HKU LIV-Eye
    does exactly this hardware LiDAR-camera time-sync — banked earlier as worth studying.)
  - BOUNDARY (important): timecode/sync solves the SYNC problems (camera<->LiDAR = tau;
    pass<->pass = registration reference). It does NOT solve spatial COVERAGE completeness —
    a barn hole is missing in SPACE, not TIME; no shared clock reveals an unwalked corner.
    Different failures, different tools.
  - Current state: bag-record time already functions as a rough shared clock (the matcher uses
    monotonic bag-time, not header stamps — that's why it's reliable).

JETSON CLOCK — "can we bake a clock onto the data?" (operator Q, 2026-08-26):
  - ALREADY DONE + HARMLESS: the Jetson ALREADY timestamps every message (cloud/image/IMU) as
    it writes the bag — that IS a clock baked onto the data. It's METADATA riding alongside each
    message, NOT mixed into the point coords or pixels -> it does NOTHING to degrade/alter the
    measurements. "What would it do to the data" = nothing; it's a label, not an ingredient.
  - BUT it is an ARRIVAL-SIDE clock ("when the Jetson wrote this"), which CANNOT fix tau. Tau is
    about when the sensors CAPTURED, not when the Jetson recorded. The camera frame arrives late
    (USB buffering, no hw trigger) vs when photons hit the sensor; the Jetson stamps both on
    arrival as if simultaneous. A recording-end clock cannot undo a capture-end drift. THIS is
    why tau persists despite the Jetson already timestamping everything.
  - THE FIX MUST BE CAPTURE-SIDE: a HARDWARE TRIGGER (one signal fires the camera exposure AND
    marks the LiDAR at the same instant) = the clock at the SOURCE = the film jam-sync. A
    software/Jetson clock is arrival-side and fundamentally can't reach tau.
  - USEFUL NUANCE: the Jetson clock IS good for PASS-TO-PASS timecode — a consistent session
    clock so multi-pass barn captures have known order/rough timing for registration. Free (the
    timestamps already exist). So: Jetson clock helps MULTI-PASS organization; it cannot fix
    WITHIN-PASS camera-LiDAR sync (tau). Right principle (shared clock=sync); the subtlety is
    WHERE the clock lives — for tau it must be at the sensor trigger, not the Jetson.

THREE KINDS OF "MISSING FOOTAGE" (how to know a capture is incomplete):
  1. MISSING FILES: a pass didn't record / bag is 0-byte or truncated. Catch: file-integrity +
     ros2 bag info (counts, valid EOF).
  2. MISSING POSES: bag looks full but ODOMETRY DIED mid-pass (our rotation-collapse signature).
     LOOKS complete to a naive check; only the numbers reveal it. Catch: odom-span-vs-duration.
     THIS is why a numerical checker beats an eyeball.
  3. MISSING COVERAGE: every pass healthy but the passes TOGETHER don't cover the whole space
     (an unwalked corner/loft). The DANGEROUS one — invisible per-pass, only visible in the
     UNION. Catch: roughly REGISTER the passes and look for holes in the combined footprint.
     KEY: 3D "missing" is SPATIAL not temporal — you can't scrub to find it; you must build the
     coverage map and look for holes IN SPACE, ON LOCATION, before striking the set (a spatial
     hole is unfillable once the barn is gone). Strongest argument for fast field-registration.

FIELD CAPTURE-HEALTH CHECKER (concept, buildable from existing pieces):
  A fast, light, GPU-free, numeric PASS/FAIL-and-why per capture — for the field "check the
  gate" moment. Assembled from code we already have (matcher's odom-span/match-rate; the
  azimuth-coverage check from the static-pan analysis; ros2 bag info). Measures: odom span vs
  duration (did tracking survive), point count/density, coverage extent + angular spread,
  frame->pose match rate, sensor-health flags (cloud Hz, IMU present, frames landing), and
  pass-to-pass OVERLAP (registration-readiness). Output in CREW language (good take / re-shoot),
  not "odom span 7.03s" — the people handling cards aren't engineers. Verifies capture HEALTH,
  not final quality (quality comes at the workstation). NOT YET BUILT — draft for this afternoon.

═══════════════════════════════════════════════════════════════════════════
## 8L. LIVE CAPTURE-HEALTH MONITOR — the field "check the gate" system (2026-08-27)
═══════════════════════════════════════════════════════════════════════════
FOUNDING PRINCIPLE (operator-reasoned, the bedrock):
  - TIME is the ONLY universal marker. Expected data rate/volume over runtime is a HARDWARE
    CONSTANT (~data/sec per stream), independent of scene, motion (stationary streams still
    flow), or the downstream pipeline. GEOMETRY/COVERAGE are NOT valid markers — content-
    dependent AND gated on the unknown Unreal gap-fill tolerance. So the alarm rests on time:
    "runtime elapsed, expected data didn't arrive -> fault." Operator: "if at the 30s mark the
    info drops to zero and stays there: alarm."
  - RIGOR MUST BE CONSTANT/LIVE, not a surprise at the end. An end-of-capture check is an
    AUTOPSY (tells you what you lost); only a LIVE heartbeat (alarming in the moment) PREVENTS
    the wasted capture. The rigorous protection is a constant monitor DURING Start->Stop.
  - The check is CONTINUITY over the Start-Rig -> Stop-Rig window: even stationary, sensors
    stream continuously, so ANY gap = a fault (no innocent explanation while the rig is on).
    Needs TWO parts (bench-proven): (a) interior-gap scan (dropouts) + (b) flowed-to-Stop check
    (a crash = flow ENDS early; the gap-scan alone misses it — caught in sandbox testing).
  - VISUAL CHECK (operator watching the live cloud) is the STANDING BACKSTOP no automation replaces.

TWO-TIER CHECKER PHILOSOPHY (resolves the "higher bar" vs "unknown Unreal" tension):
  - The checker's real bar is DOWNSTREAM-DEFINED: "good enough" = "good enough for what the
    pipeline/Unreal gap-fill can recover" — UNKNOWN until Unreal is characterized. So:
  - TIER 1 — FATAL failures (no tracking / no file / no sensors / flow-gaps): pipeline-
    INDEPENDENT (nothing downstream can rescue them) -> be RIGOROUS NOW. High bar justified.
  - TIER 2 — QUALITY sufficiency (how much dropout/sparsity/overlap is "enough"): CANNOT be set
    until the Unreal/gap-fill tolerance is measured empirically (feed it progressively worse
    captures, find where it breaks -> that boundary becomes the Tier-2 threshold). Setting it
    now = guessing. DANGER both ways: bar too LOW wastes a shoot day; bar too HIGH re-shoots
    good work / blames the rig for the checker's paranoia. So hold Tier-2 until characterized.

TOOLS BUILT (both in /mnt/user-data/outputs/, delivered):
  - rig_monitor.py (150 lines) — THE LIVE MONITOR (primary). Terminal text-bars (dependency-
    free, renders identically bench<->Waveshare). Subscribes to the 4 streams, counts msgs/sec:
      FLOW HEARTBEAT: per-sensor bar (green >=70% nominal / yellow >=35% / red-DROPPED <35%).
      CARD FUEL GAUGE: measures the record drive's free-space shrink -> REAL bytes/s -> time-left
        (green>300s / yellow>120s / red). Closes the card-fill blind spot (was flying blind).
    Glanceable: green+full = keep rolling; collapsed/red = look now. Merges INTO the field
    monitor (beside the coverage view), on the Waveshare (or phone via router).
  - check_capture.py (v2, 162 lines) — POST-CAPTURE confirmation (secondary/autopsy). Three-
    state GOOD/CAUTION/RESHOOT, never a false green (unverified tracking = CAUTION, not GOOD).
    Tracking three-band: GOOD>75% / CAUTION 40-75% / RESHOOT<40% (083911 tracked 49% and was
    fine -> that's why 40-75% is CAUTION not RESHOOT). Geometry is SECONDARY (only raises
    CAUTION, never RESHOOT — a misplaced PCD is not proof of a bad capture).

SANDBOX-PROVEN (logic), NEEDS HOT CALIBRATION (numbers):
  - PROVEN benched: rate-counting exact (0% err at 12/15/30/250Hz); dropout falls to zero within
    the 2s window -> alarm (note: ~2s lag from the averaging window — shrink WINDOW for faster
    alarm at the cost of jumpier bars); fill-math correct; brief 0.3s blips do NOT false-alarm;
    check_capture three-state verdict correct on all real-capture scenarios (185910 collapse->
    RESHOOT, 121359 87%->GOOD-ish, 083911 49%->CAUTION, 102338 16%->RESHOOT).
  - *** NUMBERS UNVERIFIED — HOT CALIBRATION NEEDED: the nominal sensor rates in rig_monitor.py
    are PART SPEC / PART GUESS (LiDAR 12 & IMU 250 solid; CAMERA 15 is a GUESS — rig_start sets
    gscam framerate=30, so it may be 30Hz; ODOM 100 unverified). And the DATA RATE is UNKNOWN:
    operator's ~4-5GB/5min eyeball vs a placeholder 80MB/s differ ~5x. The monitor MEASURES the
    real rate live (disk-shrink) so it self-corrects, but needs ~1 min of real recording to
    trust the gauge. THRESHOLDS (DROP_FRAC 0.35, green 0.7, WINDOW 2.0s, card 300/120s) are
    reasonable GUESSES pending calibration vs the rig's real jitter. ***

GOING-HOT CALIBRATION CHECKLIST (benched, rig running — the next real step):
  1. ros2 topic hz on all 4 topics -> put the REAL nominal rates into rig_monitor.py config.
  2. Record ~1 min to the actual capture drive -> read the measured data rate; resolve the 5x
     question; confirm the fuel gauge time-left is sane.
  3. Run rig_monitor.py live: confirm rclpy subscriptions connect + bars go green/steady.
  4. DELIBERATE-FAULT TEST: unplug the camera ~1s -> confirm the Camera bar collapses + ALARM
     fires live (the whole point — catches a fault in the moment).
  5. Calibrate DROP_FRAC/WINDOW vs the rig's real jitter (camera known 18-408ms wobble).

═══════════════════════════════════════════════════════════════════════════
## 8M. HOT-RUN FINDINGS — overload, lean capture mode, thermal baseline (2026-08-27)
═══════════════════════════════════════════════════════════════════════════
rig_monitor.py v3 was validated LIVE on the rig (bench, rig running) and immediately earned its
keep by catching a real, previously-INVISIBLE problem. Findings:

*** THE BIG ONE — SYSTEM OVERLOAD STARVES THE SENSORS: ***
  - Running the full stack at once (Point-LIO + gscam camera + the 2 fusion nodes + RViz + the
    bag recorder + the monitor) drove the Jetson to LOAD AVERAGE 19.7 on ~6 cores = ~3x
    oversubscribed. RAM was near-full (83MB free of 7620) and into swap.
  - RESULT: the sensor STREAMS were STARVED — camera fell 30->14.5Hz, IMU 251->168Hz. The
    monitor showed both as "low" (yellow). The sensors are NOT broken — there is no CPU left to
    service them. *** Captures done in the full-stack config were likely SILENTLY DEGRADED
    (thinner camera/IMU than we thought) and we were BLIND to it until the monitor showed it. ***
  - top confirmed the load sources (ps aux gave exact identities):
      pointlio_mapping ~114% (essential, the SLAM) | ros2 bag record ~38% (essential, recorder,
      recording the right 4 topics: aft_mapped_to_init/image_raw/unilidar_imu/unilidar_cloud) |
      gscam ~89% (essential, camera) | 2-3 fusion python nodes ~47-73% each (LUXURY) | rviz2 ~26%
      (LUXURY — and it is spawned BY the point_lio launch via rviz:=true, not separately).

LEAN CAPTURE MODE (the fix — test next hot session):
  - KEEP (essential record chain): LiDAR driver, gscam (camera), pointlio_mapping, ros2 bag record.
  - CUT (preview luxuries, they contend for the CPU the sensors need):
      * RViz -> launch Point-LIO with rviz:=false (it is in the launch cmd; one-arg change).
      * overlay_check_node.py + colorized_fusion_node.py -> do NOT start for capture (these are
        rig_start.sh's BENCH-preview nodes; fusion happens LATER in processing anyway).
  - HONEST CAVEAT: even lean, pointlio+gscam+recorder is still ~2.5 cores of genuine load — lean
    mode fixes the STARVATION (sensors get CPU back), it does NOT make the Jetson idle; temp still
    climbs (hence the temp bar matters). TEST: launch lean, watch the monitor, confirm camera/IMU
    return to green.
  - TENSION to resolve in handheld tests: the "missing footage" work wants SOME live coverage view,
    but preview is exactly what we're cutting. Need the LIGHTEST sufficient preview (see viewer
    ladder below). That's a FIELD-ergonomics decision, not a bench one.

THERMAL BASELINE (measured live, real numbers at last):
  - Jetson idles ~56.6C (rig on, not capturing), climbs to 59-63C under capture load. Well below
    the ~85-95C throttle, so NOT dangerous — but it means the operator-set 50/55 temp thresholds
    are TOO TIGHT (the bar would be permanently red = alarm fatigue). RECALIBRATE to ~green<68 /
    yellow 68-80 / red>80 (still far below throttle). The 50/55 in rig_monitor v3 is known-wrong,
    pending this update.
  - L2 TEMPERATURE IS NOT REACHABLE from ROS2: `ros2 topic list` shows ONLY /unilidar/cloud and
    /unilidar/imu — the driver publishes no status/temperature topic. apd_temperature exists in
    the L2 but is Windows-Unilidar-tool-only (or needs a deeper SDK/driver investigation to
    surface). So the monitor's L2 temp bar stays "not available"; the L2 stub in v3 is dead code
    (remove or mark non-functional). Monitor L2 heat by PREVENTION (§8H: bounded sessions, ambient).

BACKGROUND CLEANUP = RED HERRING:
  - No hidden background hog is stealing capture CPU. The load is our OWN foreground stack. The
    ~20 nvpmodel_indicator.py processes and jtop are ~0.0% CPU (harmless; the nvpmodel swarm is
    oddly numerous — a symptom to understand someday, not urgent). Real levers = LEAN MODE, and
    optionally HEADLESS operation (GNOME Shell was ~16% CPU + 385MB — running captures without the
    desktop frees that, but conflicts with wanting the Waveshare display; a design tradeoff).

VIEWER LADDER (what to show during capture — parked until HANDHELD tests):
  - fused camera+LiDAR live = best info, TOO HEAVY (it's the colorized_fusion node, a CPU hog). Out.
  - RViz point cloud = shows COVERAGE (the useful thing) but moderately heavy. What we're cutting.
  - camera-only feed = tempting but WRONG rung: not clearly lighter (live video render costs), AND
    shows the LESS useful thing (camera is FIXED to the rig -> no coverage sense, just fixed framing).
  - downsampled/voxel coverage cloud = the SWEET SPOT candidate: keeps coverage info, much lighter
    than full RViz. Test an aggressively voxel-downsampled RViz and measure the CPU drop.
  - rig_monitor's bars already give the near-zero-cost "is it flowing" signal.
  - CAN ONLY be settled in HANDHELD tests (field-ergonomics: how light-yet-readable, + practical
    fixes like sunshades/brightness/screen-angle — partly a physical not software problem).

═══════════════════════════════════════════════════════════════════════════
## 8N. L2 THERMAL — MANUAL + SDK FINDINGS (blind spot resolved) (2026-08-27)
═══════════════════════════════════════════════════════════════════════════
Investigated the L2 thermal "blind spot" via the AUTHORITATIVE Unitree sources (official L2
User Manual PDF + unilidar_sdk2 v2.0.4). Result: the fear was LARGER than the documented reality,
and the temperature is RETRIEVABLE. Two big findings:

FROM THE L2 USER MANUAL (recalibrates §8H, which had rougher scraped numbers):
  - OPERATING ambient range is -10°C to 50°C (NOT 60 — 60 is STORAGE). Storage -20 to 60°C.
    Normal room temps sit comfortably mid-range. (apd_temperature is the INTERNAL sensor temp,
    a different number from ambient.)
  - There is NO documented catastrophic "thermal shutdown with unknown recovery." The manual
    describes operating RANGES + a temperature STATUS FIELD + the cold self-heating mode — but
    no dramatic cutoff mechanism. The looming-catastrophe framing was over-worried.
  - RECOVERY from any L2 problem is ROUTINE and documented: troubleshooting repeatedly says
    "try restarting the L2 (and Unilidar 2 software)." So "unknown recovery" -> it's just RESTART.
  - "temperature" is explicitly listed as one of the L2 Working-status data fields.
  => Net: heat is a normal operating-range concern (airflow + bounded sessions still sound), NOT
     a lurking catastrophe. Big calming recalibration, grounded in the authoritative manual.

FROM THE SDK (unilidar_sdk2 v2.0.4) — the temperature is REACHABLE (closes the "can we measure L2 temp" Q):
  - unitree_lidar_sdk/include/unitree_lidar_protocol.h defines struct LidarInsideState {
      sys_rotation_period, com_rotation_period, dirty_index, packet_lost_up, packet_lost_down,
      apd_temperature (°C, THE one we want), apd_voltage, laser_voltage, imu_temperature }.
  - *** CRITICAL: LidarInsideState is EMBEDDED in every Lidar Point Data packet (it's a `state`
    field inside the point-data struct, protocol.h ~line 160). So apd_temperature is ALREADY
    ARRIVING at the Jetson inside every cloud packet — the current ROS2 driver just parses out
    the cloud + IMU and DISCARDS the inside-state. The data isn't missing; it's thrown away
    before it reaches ROS2. ***
  - So the L2 temp bar on rig_monitor IS achievable — it requires MODIFYING the ROS2 driver to
    read state.apd_temperature from each packet and publish it (a topic, or log). Moderate C++
    work, but a DEFINED task (SDK documents the exact struct/field), not reverse-engineering.
  - BONUS health fields available the same way: apd_voltage, laser_voltage, dirty_index,
    packet_lost_up/down, imu_temperature — a whole L2 health channel, currently discarded.
  - SDK also ships `run_without_rviz.launch` (confirms the no-rviz/lean pattern is standard) and
    getVersionOfLidarFirmware/Hardware interfaces (clean API surface to extend).

DRIVER MOD DONE (2026-08-28) — /unilidar/apd_temperature now published (built, awaiting hot test):
  - Modified ~/ros2_ws/src/unilidar_sdk2/unitree_lidar_ros2/.../include/unitree_lidar_ros2.h with
    4 ADDITIVE edits: (1) #include std_msgs/msg/float32.hpp; (2) declare pub_temp_ (Float32);
    (3) create it on topic "/unilidar/apd_temperature"; (4) in the LIDAR_POINT_DATA block, right
    after pub_cloud_->publish, read temp_msg.data = lsdk_->getLidarPointDataPacket().data.state.apd_temperature
    and pub_temp_->publish(temp_msg). std_msgs was already a dependency (no CMake/package.xml change).
  - *** CORRECT ACCESSOR: getLidarPointDataPacket().data.state.apd_temperature — the packet wraps
    LidarPointData `data`, which holds LidarInsideState `state`. First build failed with ".state"
    (missed the .data layer); the compiler caught it; fixed -> built CLEAN. ***
  - ORIGINAL SAVED: unitree_lidar_ros2.h.orig (revert target if anything's off).
  - HOT TEST (next session): source install/setup.bash; start rig; (1) confirm /unilidar/cloud
    still ~12Hz (didn't break existing fn); (2) ros2 topic list | grep apd shows the topic;
    (3) ros2 topic echo /unilidar/apd_temperature shows a REAL °C number. THEN wire rig_monitor's
    L2 bar to this topic (small edit: set L2_TEMP_TOPIC) -> the L2 thermal blind spot closes LIVE.

QUATERNION-ORDER BUG FIXED (2026-08-28, same driver, same build) — AUDIT FINDING #1 resolved:
  - The old audit flagged the driver unpacking imu.quaternion[] in TWO orders. Confirmed REAL and
    still present: the IMU message read [0]=x,[1]=y,[2]=z,[3]=w (CORRECT) but the imu_initial->imu
    TF read [1]=x,[2]=y,[3]=z,[0]=w (WRONG — treated it as [w,x,y,z]).
  - GROUND TRUTH from Unitree's OWN example.h line 72: printf "quaternion (x,y,z,w)" with
    [0],[1],[2],[3] -> the array IS [x,y,z,w]. So the IMU message was right; the TF was wrong.
  - FIXED the TF (lines 205-208) to x=[0],y=[1],z=[2],w=[3]. Rebuilt CLEAN (with the temp mod).
  - DOWNSTREAM IMPACT (sandbox-reasoned): NONE to data. Point-LIO uses the IMU TOPIC (already
    correct) + the STATIC cloud<->imu TF (correct), not this imu_initial->imu debug TF. Bags record
    topics not this TF; fusion uses our own extrinsic; matcher uses bag-time+poses. The fix only
    corrects the TF-tree/RViz debug-frame display (which nobody normally views). This is WHY the
    captures worked despite the bug — it never touched the data path. Correct-is-correct cleanup,
    not a quality fix; don't expect a capture improvement. (Hot-check: glance ros2 topic echo /tf
    to confirm nothing unexpected consumes that frame.)

HOW TO USE THIS (the practical payoff):
  1. IMMEDIATE (no code): stop treating L2 heat as a catastrophe. Operate -10..50°C ambient,
     bounded sessions, good airflow; if the L2 ever stops, RESTART it (documented recovery).
     Watch the JETSON temp bar (which we CAN read) as a proxy for ambient thermal stress.
  2. MEDIUM (the real win): modify the unilidar ROS2 driver to extract state.apd_temperature
     (+ the other health fields) and publish them -> then rig_monitor's L2 temp bar goes LIVE,
     closing the last thermal blind spot with a real measured number. Scoped C++ task.
  3. ALTERNATIVE (no driver hack): the Windows Unilidar 2 tool reads the status incl. temperature
     — use it for spot-checks / characterization (what does the L2 actually run at?), even if not
     live-on-rig. (Caution: that tool can change L2 config/IP — read, don't blindly change.)
  4. The two Unitree sample bags (Indoor + Park) are real SAME-SENSOR data — good pipeline/checker
     test assets (not thermal; keep on the Jetson, they're large).

═══════════════════════════════════════════════════════════════════════════
## 8O. FIELD KIOSK — the functional field UI (Plan A) (2026-08-28)
═══════════════════════════════════════════════════════════════════════════
Built the field kiosk: ONE full-screen touch app that is the field instrument. Absorbs
rig_monitor.py's engine (Plan A) so the terminal monitor can retire once this is hot-proven.

WHY (the problem it solves): the full Jetson desktop on the 7" Waveshare is a "zoo" — tiny
icons, stray touches switch workspaces, accidental everything. A full-screen KIOSK covers the
desktop entirely -> only the field UI shows, nothing to fumble. The MOCK was validated on the
real Waveshare (operator: "looks really good... works really well") — the hard question (usable
at 7"?) is ANSWERED YES.

ARCHITECTURE (rugged = few parts, dependency-free):
  - rig_kiosk_server.py — Python built-in http.server (NO Flask/pip). Three jobs:
      (1) serves rig_kiosk.html; (2) reads LIVE health (rig_monitor's engine, refactored to
      RETURN a dict: ROS2 rates + Jetson thermal-zone temp + card free-space + L2
      apd_temperature from our driver mod) at /data; (3) fires the REAL scripts at /action.
  - rig_kiosk.html — the validated mock, now LIVE: bars polled from /data every 500ms; buttons
      call /action. Full-screen (F11, or chromium --kiosk).
  - USE_MOCK=1 env -> runs with fake data + no-op buttons (PC/sandbox demo). Else ROS2 mode.
  - BUTTONS fire the CONFIRMED existing scripts (from the desktop icons):
      Start Rig -> ~/rig_start.sh | Stop Rig -> ~/rig_stop.sh | Capture -> ~/point_lio_capture.sh
      (each launched in a gnome-terminal, matching the icons, so operator sees output/Ctrl-C).
  - Temp thresholds RECALIBRATED here to the real baseline: green<68 / yellow 68-80 / red>80.

SANDBOX-PROVEN (end-to-end, mock mode): serves the page; /data returns live JSON that CHANGES
over time; button actions fire (correctly found+attempted the script paths, reported honestly
when absent); the whole plumbing works. Delivered: rig_kiosk_server.py + rig_kiosk.html (both
also on the Jetson Desktop as of tonight). rig_kiosk_mock.html kept as the static design ref.

HOT-VALIDATION ITEMS (Jetson, tomorrow — all expected, none blocking the build):
  1. The /data ROS reads need live validation (same as rig_monitor — rclpy only proves on rig).
  2. CAPTURE BUTTON + LEAN MODE: it fires point_lio_capture.sh — CONFIRM that script is lean
     (rviz:=false, no fusion nodes) or make a lean variant (per the 8M overload finding). KEY.
  3. L2 temp bar depends on the driver-mod topic actually publishing (the 20.12 hot test).
  4. Button safety: deliberately test Start/Stop/Capture fire right + Stop is reliable.
  5. Then: the terminal rig_monitor.py can RETIRE (its job now lives inside the kiosk).

LAUNCHER (for one-tap field mode, when ready): a .desktop icon running
  chromium-browser --kiosk http://localhost:8080 (after starting the server) = one-tap kiosk,
  no browser chrome, hides the desktop. (Deferred — the app itself is the win.)

## 7S. RESEARCH — SOLVING THE HOLEY-MESH / DELIVERABLE PROBLEM (web search 2026-08-23)
═══════════════════════════════════════════════════════════════════════════
COLD READER: real sources READ (not recalled) on 2026-08-23, tied to our actual blockers.
THE THROUGH-LINE across every serious lab: they use the CAMERA to DENSIFY THE GEOMETRY, not
just to colour it. Our current pipeline uses camera for TEXTURE only (place) + LiDAR for
geometry only (measurement). The research consensus for a SOLID mesh from SPARSE LiDAR is to
fuse the camera into the GEOMETRY step (depth-completion or multi-view-stereo densification),
THEN texture. This is the most promising direction to move OFF holey meshes. Sources:

- **CMU Robotics Institute — Li et al., ICRA 2019, "Dense Surface Reconstruction from
  Monocular Vision and LiDAR"** (https://www.ri.cmu.edu/app/uploads/2019/07/Li19icra.pdf).
  NEARLY OUR RIG + OUR FAILURE. States LiDAR-only can't reconstruct indoors well because LiDAR
  is sparse vs camera pixels (= our holey mesh). FIX: integrate LiDAR into a multi-view-stereo
  pipeline for point-cloud DENSIFICATION + tetrahedralization, then graph-cut a WATERTIGHT mesh.
  Reports it significantly beats both camera-only and LiDAR-only. THE most directly on-point source.

- **Sparse-LiDAR holes are a KNOWN FRONTIER PROBLEM (nobody fully solves it)** — LGFaware-meshing,
  2025 (tandfonline 10.1080/10095020.2025.2502481): admits ALL methods incl. theirs "fail to
  completely reconstruct edge regions" in sparse areas. Two escape routes named: (1) deep-learning
  DEPTH COMPLETION, (2) MULTI-VIEW-STEREO densification from images. So our holey mesh isn't
  incompetence - it's the frontier; the exits are camera-driven densification.

- **HKU-MARS Point-LIO README** (https://github.com/hku-mars/Point-LIO) — CONFIRMS our 7P sync
  dossier verbatim: IMU-LiDAR sync critical; "Failed to find match for field 'time'" = missing
  per-point stamps; LiDAR-only sidestep = imu_en:false + gravity_init + use_imu_as_input:0.
- **HKU-MARS LiDAR_IMU_Init** (https://github.com/hku-mars/LiDAR_IMU_Init) — NEW LEAD for our
  odom-cutoff / frozen-timestamp bug: notes some LiDARs' timestamp origin = power-on, so power-
  cycling restarts stamps at 0 and temporal init is needed each power-up. Directly relevant to
  the 7P "frozen Feb-2026 sensor stamp" finding. Worth trying as the temporal-init fix.

- **Oxford Dynamic Robot Systems — SiLVR** (https://arxiv.org/html/2403.06877.pdf, updated Jan
  2026) — CLOSEST TO OUR WHOLE DELIVERABLE: handheld LiDAR+camera -> dense textured photoreal
  reconstruction with geometry on-par with LiDAR + photorealistic novel-view synthesis. Uses a
  LiDAR-inertial-odometry+SLAM front end (like ours). Read how they fuse for the back half.

- **Univ. of Michigan PeRL (Perceptual Robotics Lab)** (https://robots.engin.umich.edu/) — our
  exact sensor triple (3D LiDAR + camera + IMU), co-registered LiDAR+camera for HD mapping; NCLT
  dataset. Reference lab for the fusion; browse for methods.

- **Zhen/Hu/Scherer — Joint-Optimization LiDAR-Camera Fusion** (https://arxiv.org/pdf/1907.00930)
  — hit 2.7mm accuracy by JOINTLY solving bundle-adjustment + cloud-registration to compute camera
  poses AND refine the extrinsic per-capture, beating fixed target-based extrinsic. We currently
  use a FIXED vetted extrinsic; per-capture joint refinement could tighten registration.

NOT YET EXPLORED (next research pass): DARPA SubT program reconstruction stacks (surfaced via
  CMU/Michigan lineage but no direct program page read yet); deep depth-completion tooling specifics.
IMPLICATION FOR THE PLAN: the "camera = place only" split in the mission is right for TEXTURE, but
  the research says for a SOLID MESH we may also need the camera to help DENSIFY geometry in sparse
  regions. This does NOT contradict the accuracy mission (densification guided by measured LiDAR is
  not photogrammetry-guessing) - it's the documented pro path off holey meshes. FLAG for operator
  decision, not yet adopted.

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
- 2026-08-21: TEXTURING BRIDGE (Point-LIO -> texture) BUILT + PROVEN COLD; odometry-engine FORK
  (7N) added. Pulled the authoritative Master from the repo at session end and caught that 7M
  already records Point-LIO WORKING (my in-context copy was stale — the republish protocol found it).
  Built Piece 2 pointlio_pose_matcher.py (pose interp LERP+SLERP, self-tested to 5e-16m / 0deg;
  output convention locked to per_shot_texture's compose_world_to_cam to 7e-16m), Piece 3
  pointlio_to_texture.py (NEW multi-view per-face baker — best_image_per_face only SELECTED before),
  Piece 1 capture_pointlio_texture.sh (real point_lio launch / topics / PCD path confirmed from the
  actual repos), and TEXTURE_BRIDGE_RUNBOOK.md. Proved the whole bridge on the REAL 161k dense cloud
  + real image -> 385k-face mesh -> 90.3% photoreal render. Debug/conflict scan: Piece2->3 file
  interface EXACT (count/values/index); numpy clash mitigated by ~/tex_env venv; Open3D on Jetson =
  official CPU pip wheel (isl-org#6885 CUDA build N/A); render_idx guarded. Added 7N fork: Point-LIO
  chosen + PROVEN (tailor-made for L2; keeps texture separable = relightable); FAST-LIVO2 reserve
  (peer-reviewed Buildings 2025, but bakes lit colour). Yardstick from that paper: moving-capture
  ~8.3cm (NOT the 16mm static number); our 0.297px calib beats their 2.48px. All bridge files pushed
  to rig-files. NEXT: first COMBINED camera+Point-LIO hot capture (runbook HOT-1/2 -> COLD-1/2).
- 2026-08-21 (cont): CAMERA CONTROL PANEL built + PROVEN LIVE on the rig. Motivation: a camera-
  only bench look (Start Rig tolerates "LiDAR not publishing" and continues) put /image_raw on the
  monitor at ~22fps and the operator's eye caught the real problem — a blown centre window, crushed
  shadows, wandering blue white balance = auto-exposure/WB hunting on a high-dynamic-range scene.
  Fix = a hand control. Built camera_control.py (tkinter, touch-sized for Waveshare): Exposure
  (auto/manual + slider), GAIN (0-100, always-active, the other half of manual exposure), White
  Balance / Colour Temperature (auto/manual + Kelvin slider). Verified against the REAL B0578
  --list-ctrls-menus: auto_exposure(1=Manual,3=Auto), exposure_time_absolute(1-5000), gain(0-100),
  white_balance_automatic, white_balance_temperature(2800-6500). Colour-temp slider CAPPED at the
  true 6500K (was 10000 = would clamp). Logic self-test (--selftest) 5/5. LIVE ON RIG: exposure +
  gain move the image in real time (watched in rqt_image_view); colour-temp needs Auto WB UNCHECKED
  first (flags=inactive gotcha — now in section 6). Files: camera_control.py + CameraControl.desktop
  (icon), both on Jetson ~/. TRANSFER LESSON (cost several rounds): multi-line terminal paste MANGLES
  (drops lines) on this box, and browser uploads mis-name .desktop -> .download; the RELIABLE route is
  download the file ON THE JETSON (operator is always on the Jetson) and `mv` it into place. Also
  recorded the BENCH vs RIG two-stage model (see NEXT-SESSION block) + that capture is a 270 pan-in-
  place. Panel is a bench-prep asset for the late-bench combined capture; relight downgraded to one
  prong, ACCURATE 3D MODELLING (beat Polycam "WORST CASE SCENARIO.PNG" — melt/holes) is the main focus.
- 2026-08-21 (eve): MILESTONE — COEXISTENCE PROVEN. Camera + Point-LIO ran together live on the rig;
  RViz showed a coherent room (walls/archway/floor/ceiling), the big load-bearing unknown answered.
  Also: first CLEAN VERIFIED capture (1.1M pts, ~8x5x3m room, saved correctly). Open3D installed +
  functionally verified on the Jetson (official aarch64 CPU wheel; numpy 1.26.4 left untouched;
  meshing test passed) — COLD-PREP 0 done. RViz preset saved into loam_livox.rviz (CloudRegistered
  Style=Points, Decay=5). New assets on Jetson: run_point_lio.sh (sources both ws, launches L2
  mapping, does NOT start the driver) + PointLIO icon. HARD LESSONS: (1) SAVE ORDER — scans.pcd saves
  only on a clean Point-LIO SIGINT; Stop Rig / killing LiDAR first = no save, and you silently re-read
  an old run. Fix: Ctrl-C Point-LIO FIRST -> confirm pcd timestamp -> then kill LiDAR. (2) PCD is
  fixed-name, overwritten each run — rescue to a timestamped copy immediately. (3) DIVERGENCE is real:
  careless init made Point-LIO run away into a ~1.3km trajectory smear (verified via extent + shape
  plots); DEAD-STILL init gave the clean room. Always verify extent before trusting a capture — RViz
  can look fine while the save is garbage. Run-to-run reliability NOT yet proven (open risk). Explored
  but did not adopt: external IMU (TB100) for reliability + hardware sync — validate divergence-is-IMU
  first (7O note). Drew up the FIRST FUSION step schedule (7O + FIRST_FUSION_STEPS.md): small gated
  cold/hot steps to a manipulable fused artifact; quality does not matter, existence does. NEXT: 7O
  Phase A cold prep, then a short recorded capture.
- 2026-08-21 (eve/inventory): full desktop+home toolkit inventory (from a desktop screenshot +
  ls/find on the Jetson) to confirm nothing needed is missing before First Fusion. KEY RESULT: the
  texturing ENGINE per_shot_texture.py — the load-bearing file Piece 3 imports, the one that made
  sampleB_render.png — was the B1-bug casualty (working version never saved; outputs copy was missing
  the 3 multi-view fns). Today it was RECOVERED VERBATIM from transcript 2026-08-20-16-31-39 and
  VERIFIED to reproduce sampleB exactly (99% / 450,304 tris / mean 0.63 on the real db) — recovered,
  not reinvented. Now secured in 3 places (~/Desktop, rig-files repo, pasteable); ground-truth source
  = that transcript. Inventory also confirmed: fusion ALREADY proven (sampleB) but only on OLD/RTAB-era
  geometry — cloud.ply is the 12.3m RTAB-collapse relic, real_scene_colored/fused_2d are preview/2D,
  NOT current fused artifacts; so First Fusion (fusion on live POINT-LIO geometry) is genuinely the
  right next milestone, not a redo. Existing on-Jetson tools folded into 7O: inspect_pcd.py = C1
  coherence check (no Open3D needed), analyze_l2_imu.py = divergence diagnostic. 7O corrected: engine
  already present so A1 = place only the 2 bridge scripts next to it; C1 uses inspect_pcd.py. Also
  noted: multi-line terminal paste MANGLES large files on this box (proved again); reliable route =
  download ON the Jetson + mv (operator is always on the Jetson). NEXT: 7O Phase A assembly.
- 2026-08-22 (all-nighter, the big one): **FIRST FUSION ACHIEVED** - the full chain ran end-to-end on
  LIVE Point-LIO data for the first time (capture -> matcher -> ball-pivoting mesh -> per-face texture ->
  first_fusion.png). Mesh 224k verts / 217k faces @ voxel 0.02, 66% faces textured from 78 matched frames,
  ~65% render coverage. HQ re-run (voxel 0.01, scale 1): 654k verts / 548k faces but WORSE image (knitted
  weave). Operator's eye: ~25% deliverable; the old texture_probe.png looks better on detail. VERDICT: the
  MESHER is the quality bottleneck, not the code. Getting here required solving a chain of REAL seams, all
  cold: (a) Poisson fatally fails on open room-scans -> swapped mesh_cloud to ball-pivoting; (b) rosbags
  0.11.5 typestore requirement -> added get_typestore(ROS2_HUMBLE); (c) Point-LIO odom header stamps frozen
  -> match on bag time (0/423 -> 78/423); (d) matcher interp threshold too strict for Jetson numpy (1e-8 ->
  1e-4, real err 2.4e-6 deg). Also this session: the MISSION/design-philosophy written into the header
  (place vs measurement, whole-not-rough, the barn example, Polycam anti-ref); "divergence" reframed as a
  displaced-cluster OUTLIER problem (operator's RViz insight - 92% room + 7% clustered garbage, SOR can't
  clear it, distance-crop UNFIT for variable film-set scale); Point-LIO odom-cutoff-at-5.5s discovered;
  sensor-role clarified (camera=place has no depth/reach, LiDAR=measurement, far field=backdrop plate,
  reach=move the LiDAR); RealSense D435 considered + rejected (dense but SOFT = the melt problem, and
  <10m range < L2's 30m). CAPTURE PROCESS fully proven twice tonight with correct save-order. Debug+conflict
  pass on today's code: all 3 files parse+import+selftest CLEAN - no code conflicts. **KEY RISK: today's
  fixes (ball-pivoting engine, typestore+bagtime matcher) live ONLY on ~/Desktop - NOT pushed to repo; a
  fresh wget would restore BROKEN versions. PUSH per_shot_texture.py + pointlio_pose_matcher.py to rig-files
  before trusting the repo.** Backups on Desktop: per_shot_texture.py.bak_poisson (the ONLY Poisson copy -
  keep for the mesher revisit), matcher .bak/.bak2/.bak3. Dead file to delete: ~/Desktop/patch_mesh.py.
  NEXT: crack meshing quality (Poisson-on-rooms vs tuned ball-pivoting), restore engine voxel from 0.01.
- 2026-08-22 (strategy session): Big-picture reassessment. Operator (LiDAR since Jan, prior tools
  LiDAX/Foxglove, moved to Jetson for compute) flagged we're ~25% to a deliverable and stuck in a
  tooling loop (RTAB -> Point-LIO -> mesher) - optimizing INTERMEDIATE artifacts while blind to the
  END result. DECISION/PIVOT: get to Unreal EARLY - push rough Point-LIO output into Unreal and let
  it (plus real GPU compute) do meshing/cleanup/relight, so we can tweak the WHOLE chain while
  watching the final output instead of polishing blind. HARD FACTS established: (1) Unreal does NOT
  run on Jetson (Vulkan wall, well-documented dead end) nor usefully on the operator's Surfaces/HP
  laptop (no discrete GPU). (2) Unreal has a native, first-party LiDAR Point Cloud plugin - imports
  .las/.laz/.ply/.e57/.pts, meters->UU (1UU=1cm) so dimensions survive, dynamic LOD for big clouds;
  aimed exactly at set designers. Point cloud != relightable mesh though; meshing/relight still a
  step (pros often use Houdini as an intermediate on a powerful box). So Unreal RELOCATES the meshing
  problem to better tools, doesn't erase it - capture quality still matters. (3) PLAN: Jetson stays
  capture+Point-LIO front end; a GPU WORKSTATION (RTX, 12GB+ VRAM min, 16GB sweet spot, 32-64GB RAM;
  ~$1.6-2k Tier-1 desktop e.g. RTX 4070 Ti Super) becomes the ingest/clean/relight/render back end.
  VALIDATE FIRST via CLOUD GPU rental (~$1-3/hr creative workstation, Vagon or Shadow ~$55/mo) -
  ~$20-60 total to prove the rough-capture->Unreal->deliverable path before buying the box. Cloud
  machine = the box that runs Unreal; drive it remotely from the HP laptop (laptop is just a screen).
  Data handoff is trivial (tiny files). Considered+rejected: RealSense D435 (dense but SOFT depth =
  the melt problem, <10m range < L2's 30m). Sensor roles clarified: camera=PLACE (no depth/reach),
  LiDAR=MEASUREMENT, far field (sky/mountains)=backdrop PLATE in Unreal, reach=MOVE the LiDAR. Also
  cracked the Point-LIO lag diagnosis from mystery -> IMU-LiDAR SYNC failure (README note A), full
  dossier in 7P with fix-path + a LiDAR-only sidestep (imu_en:false). TIMELINE (3hr/day avg, honest):
  constrained deliverable (one lit interior) ~6-10 weeks IF we reorder to solve capture coverage +
  registration stability first; barn-class ~4-6 months. NEXT: prep colored .ply export for Unreal
  (cold), then cloud-GPU validation of the whole approach.
- 2026-08-23 (clock breakthrough): IMU saturation check on 192455 bag: 0 crossings (accel max 9.83 vs
  satu 30; gyro max 0.019 vs satu 35) -> saturation DEFINITIVELY not the lag cause; also confirmed L2
  reports accel in m/s2 (gravity=9.63) so acc_norm:9.81 is correct. Config grep confirmed acc_norm/satu
  values fine, timestamp_unit:0, time_lag:0.0. THEN found a matching user report: the lag/frozen-stamp/
  cutoff is a JETSON-CLOCK vs UNITREE-FROZEN-TIMESTAMP problem (Jetsons have no RTC battery, boot with a
  wrong clock until NTP; Point-LIO drops messages whose stamps aren't monotonic / are ahead of system
  time -> odom cuts out). Jetson clock is currently CORRECT (ahead of the frozen Feb-2026 sensor stamp),
  so the bug may already be self-resolved. Full detail + validation test in 7P. This likely closes the
  months-long "divergence/lag" mystery. NEXT: a fresh hot capture with correct clock to confirm the
  cutoff is gone - and to attempt a BETTER full-fusion image than first_fusion.png / _hq.png.
- 2026-08-23 (Master 17 — leak diagnosed + hardened): Session spent mostly finding WHY progress stalled at ~25%. ROOT CAUSE identified by operator: DATA LEAK between sessions - a settled decision (trimmed Poisson = the mesher, per 7H, 92.5% coverage, decided 2026-08-19) got UN-LEARNED and re-opened as a stale gotcha ("Poisson fatally fails, use ball-pivoting"), and the assistant then RE-DERIVED the same trimmed-Poisson answer the hard way (sandbox, depth 9, 10% trim) - work that was already done. Same pattern hit the missing Unreal message, the stale RTAB content, and today's lost hot-capture data. Assistant had been PULLING THE WRONG MASTER (repo MASTER_REFERENCE(1).md, a diverged lossy branch) instead of the true head; operator supplied MASTER_REFERENCE_16_.md as the authoritative source. LESSON (hard): the conversation/compaction/repo layer is NOT durable memory; the operator-controlled Master IS. Assistant to treat the Master + operator testimony as truth over its own reconstructions. This session's edits (Master 17, built on _16_): (1) RTAB consolidated as PROJECT HISTORY (7C0 index + in-place banners, nothing moved/lost); (2) 7S RESEARCH added (real web sources read - CMU dense-surface densification is the most on-point for the holey mesh; HKU LiDAR_IMU_Init a lead for the odom-cutoff; Oxford SiLVR closest to the whole deliverable). UNRESOLVED + FLAGGED (operator to decide, assistant will NOT silently fix): the mesher contradiction inside the Master (7H says trimmed-Poisson-92.5% DONE; the §6 gotcha + old NEXT-SESSION block say "Poisson fails, ball-pivoting" - these contradict; 7H is the correct one). NEXT (operator's stated plan): upload images to cloud + view in Unreal; connect camera+lidar for an image; continue research (DARPA/MIT/Michigan/HKU).
- 2026-08-23 (Master 18 + 18.1 — record made consistent + audited): Completed what 17 left incomplete
  (operator caught it): (1) §7 DASHBOARD updated — 5 RTAB rows tagged [HISTORY — see 7C0] (facts kept),
  Point-LIO rows ADDED (odometry CURRENT/proven, texturing bridge CURRENT, first fusion done, MESHER
  RESOLVED row, processing-station NEXT row); (2) header now reads Master 18; (3) MESHER CONTRADICTION
  RESOLVED — the stale §6 gotcha ("Poisson fatally fails -> ball-pivoting") replaced in place with the
  corrected verdict: trimmed Poisson d9 ~5% trim IS the mesher (7H, 92.5%); the "fails" conclusion was a
  REGRESSION caused by the 8GB Jetson running out of RAM (depth-9 runs clean with more RAM); ball-
  pivoting rejected; meshing belongs on the processing station. AUDIT of 18 (operator-ordered) verified:
  delivery byte-identical; full 16->17->18 lineage preserved (all 13 changed lines = intended
  replacements, zero unintended loss); all claimed edits present. Audit FOUND 2 defects -> fixed in
  18.1: (a) the front NEXT-SESSION block still carried the regressed "Poisson fatally fails / resolve
  the mesher fork" text — REWRITTEN to current reality (mesher solved; next = processing station +
  Unreal + the one clean capture that has never been run); (b) this log entry was missing. Historical
  log entries (e.g. 2026-08-22's "Poisson fatally fails") are LEFT AS-IS — logs record what sessions
  believed; the header/gotchas/dashboard carry current truth. Also this session: operator moved the
  assistant to a newer model for context/retention headroom; standing rule unchanged — the operator-
  controlled Master + operator testimony are truth over the assistant's reconstructions.
- 2026-08-24 (Master 19 — THE CLEAN CAPTURE + FIRST FUSION, both proven): The milestone session. (1) CAPTURE: cold test = clean pre-flight abort (gate works); hot run via the one-click hardened tool = first-try SUCCESS — init 100%, ONE RViz (v2 lock working), one Ctrl-C, 4 stops in order, PCD FRESH, 11MB. fusioncap_083911: 334,030 pts, extent 8.19x5.20x3.53m = coherent ~4.5x5x2.1m room + THE NEIGHBOR'S HOUSE captured THROUGH THE WINDOW GLASS at 5-8m, correctly placed (glass is a portal, not a wall — the barn shot in embryo). Operator: "as close to the real image as can be imagined." CARVED RULE from it: pre-mesh cleanup judges CLUSTER COHERENCE, never distance (the far "outliers" were the establishing shot; ~2% true tufts vs 7% on old long captures). (2) METHOD WRITTEN IN STONE: CAPTURE_METHOD.md (unabridged 584-line version: full source, anatomy, every step+output, guards-as-scars table, restore-from-zero, reference-run record) -> repo + Jetson + email + chat. (3) EXTRACTION: matcher ran on the new bag (quoted-space path gotcha again) -> 192/332 matched; extract_frames.py written, DEBUGGED IN SANDBOX before running (caught 2 real bugs: ROS yuv422=UYVY chroma semantics; naming must be img_{npz-row:05d} to match the proven bundle convention — verified against matched_inputs.zip ground truth), v3 ran 192/192, encoding rgb8, frames 1920x1200 (= calib size EXACTLY; the "1080" assumption was wrong, calib yaml says 1200). JPEG-92 transport recipe: 617MB PNG -> 80MB zip. (4) THE FUSION: same-viewpoint projection on the bench — cloud through the camera's exact eye (K + R_L2C/T_L2C from the vetted engine + matcher pose row 0, p_cam = R_L2C@R_wl^T@(p-t_wl)+T_L2C composition, cv2.projectPoints with DIST) overlaid on the real img_00000: CHECKERBOARD LANDS ON CHECKERBOARD (the board resolves in pure LiDAR geometry AND in the photo — known 63.5mm/10x7 ruler, both sensors agree); the red FAR points (neighbor house) land INSIDE the window frame; arch/walls/doorway edge-on-edge; 62.4% of the whole cloud in this one view (single-vantage coverage made visible). Evidence: fusion_triptych_f0.png, fusion_overlay_f0.png, arducam_contact_sheet.png. Operator verdict: "very successful... our first step to a usable fusion." (5) HONEST NEGATIVES, recorded: ODOM CUTOFF CONFIRMED STILL ALIVE (odom 16.09s vs images 32.78s; gaps 0.85/5.6/0.85/0.57s then dead; 140 images dropped) — clock fix did NOT resolve it; LiDAR_IMU_Init temporal-offset idea is the live lead (7S). Chat-upload ROT observed twice (files unreadable hours after upload; originals safe on Jetson — re-upload works; four-place redundancy is the defense). Paste-into-bash incident (transfer rule 1 vindicated). Browser duplicate-naming trap again ("extract_frames(1).py"). ALSO FOUND: fusioncap_152121 (Aug 23 15:24) in "Fusioncap scans/" — yesterday's "missing" hot-session data likely never lost, only unrecorded; inspect when convenient. NEXT: full bake (d9 mesh + 192-frame texture, bench or station), Unreal export (.xyz-RGB/.las, NOT .ply), coherence cleanup, then the Unreal walk.
- 2026-08-24 pm (Master 20 — RELIABILITY RUN): Operator's call: "same test again so we know our data is real and reliable. Tweak after." Disciplined step-gates (operator corrected the order: sensors FIRST, then instrument). GATE FAILURE became the session's second win: camera hung on rig-up -> root cause hunt found TWO orphaned overlay_check_node.py (one started 08:39 = run 1's own rig-up, one 10:09) -> rig_start.sh line 81 launches overlay_check (75: gscam, 84: colorized) BY DESIGN but its clean-slate PATTERNS list omitted overlay_check_node.py AND gscam -> every rig start stacked orphans; a stale gscam held /dev/video0 so the fresh camera died at birth. FIX: PATTERNS += overlay_check_node.py + gscam (sed, verified). Note: runs 1 and 2 both ran WITH overlay+colorized alive by design = apples-to-apples. rig_start.sh is NOT in the repo (404) — hygiene item. RUN 2 (fusioncap_102338): method to the letter, first try, ONE RViz, PCD fresh 8.5MB / 276,970 pts. REPEATABILITY MEASURED: ICP run2->run1 fitness 0.994, inlier RMSE 19.4mm, origin delta 2.35°/50mm, extents 8.17/8.19 x 5.25/5.20m; through-glass house present in BOTH. Evidence run1_vs_run2_registered.png. ODOM CUTOFF 2nd data point: odom 4.60s of 29.45s @6902.9Hz (run1: 16.09s @2637Hz) -> VARIABLE in time AND rate; 59/253 matched; map nonetheless complete from 4.6s at one station. FUSION 3-for-3: run2-native fused image produced (62.3% in frame; checkerboard + window geometry land; evidence fusion_triptych_run2.png) after CROSS-CAPTURE fusion (run2 geometry on run1 photo via ICP+calib, 62.0%, checkerboard-on-checkerboard ACROSS scans — the strongest single validation to date; evidence cross_fusion_run2geo_run1cam.png) and run1-native 62.4%. Also this session (post-19): the operator's how-do-you-see question -> per-frame RGBD stage adopted (make_rgbd.py, 192 depth maps, fill ~6.78%) -> DEEP DEBUG on operator order found 2 real defects before rig use (naive back-projection 195mm max edge error -> rgbd_to_cloud ships undistortPoints, 0.004mm; rotation now from npz R directly, convention risk deleted; v1.0 vs v1.1 outputs bit-identical). Operator designated first_fusion_hq.png the in-house ANTI-REFERENCE (side-by-side vs run2 overlay: same room, same rig — process is the difference). Operator framing banked: "as the camera moves, the dimensions change in relation to the rig" = the fixed-world/moving-eye principle; stills are the atomic unit, OVERLAPPING images are the deliverable path (bake next).
- 2026-08-24 late (Master 20.1 — densification sandbox finding banked): Post-run-2, the operator pursued a first-principles thread on pixels vs points: RViz renders data to pixels; the final product is always pixels; the LiDAR produces far more information than the 334k-pt map summary uses; "convert to pixels, overlap the camera, and we'd see something new." Corrected the mechanism together (cloud->pixels LOSES depth; the gain is depth-PER-camera-pixel = RGBD/densification) and SANDBOXED it on fusioncap_083911 frame 0: sparse 6.78% LiDAR depth -> 100% fill of all 2,304,000 camera px (15x), back-projected to a 2.3M-pt colored 3D cloud. Operator reaction: "truly amazing" (the 3D views), then correctly noted the PNG is "a little rough." The 3D view was the teacher: it exposed the single-sided, dished, partly-interpolated SHELL — power and limit in one image — and made the case for the pan from first principles (multi-view stacks shells into a solid and turns inferred depth back into measured). Banked as §7T (SANDBOX PROOF-OF-CONCEPT, not adopted/validated). Evidence in outputs: densify_quad.png, dense_3d_views.png, dense_fused_frame0.ply(+_light/_ascii). Also logged: .ply opens fine in Open3D/3dviewer.net but chokes finicky quick-viewers (binary double precision) — same "file fine, previewer picky" lesson as .desktop/.pcd. NEXT unchanged: the hot PAN capture (full bake + the multi-view densification this finding motivates). NOTE: operator flagged that data has gone missing recently — this finding was banked immediately rather than left to reconstruct.
- 2026-08-24 eve (Master 20.2 — odom cutoff characterized, pan test analyzed): Ran the hot PAN test (fusioncap_182551) to build multi-view coverage for densification (7T). Method clean 3rd time (init 100%, PCD fresh 7.5MB, one Ctrl-C, 4 stops). Operator noted "quicker take, awkward pan." Matcher verdict: odom span 7.03s @4462Hz, 131/256 matched — all clustered in the first 7s. THE PAN FAILED ITS PURPOSE: odom died before the pan swept, so the wide angles have no poses -> still effectively single-station, no multi-view volume. BUT it delivered the key finding: with THREE cutoff data points (16.09/4.60/7.03s at 2637/6903/4462Hz) the cutoff is now CHARACTERIZED as RATE-COUPLED, and the message-COUNT view is even tighter: ~30-42k odom messages before death regardless of wall-clock -> smells like a bounded buffer/queue sized in COUNT, not a time or pure-timestamp bug. Banked as §7U and promoted to CRITICAL-PATH BLOCKER (it gates the pan, the bake, multi-view densification, everything downstream). Debug plan: (1) message-count/buffer hypothesis first — publish_odometry_without_downsample:true drives the 2637-6903Hz burst; disabling or rate-capping may extend span; hunt a count-sized cap in Point-LIO config/code; (2) timestamp/LiDAR_IMU_Init path (7P/7S) as secondary. Banked BEFORE debugging per operator (recent data-loss concern). NEXT: debug the cutoff; do not attempt another multi-view pan until odom survives ~30-45s.
- 2026-08-24 night (Master 20.3 — the "cutoff" rediagnosed as capture physics; matcher cleared): After the pan test, dug into the "odom cutoff." SEQUENCE of honest corrections: (1) checked the Point-LIO log at the 182551 cutoff -> NO error, ran clean start to Ctrl-C -> so not a crash. (2) ros2 bag info on 182551 -> 31,368 poses across the FULL 25s -> so odometry did NOT stop; the matcher's short "span" for that one had to be a read issue -> floated "matcher misreads header stamps." (3) Operator threw out 182551 (messy start, jerky pan, operator in frame) and ran a CLEAN deliberate ~300deg STATIC pan (fusioncap_185910): 4,631 poses, ~1s span, and the PCD covered only ~180deg (1.81x6.06m slab) -> a REAL collapse this time, not a read artifact. (4) Operator asked to debug the matcher: READ THE LIVE CODE — it already uses bag-time (odom_ns.append(bt)), NOT header stamps; ran its 7 built-in self-tests -> ALL PASS, math 1e-16. So the matcher is CORRECT and the "header-stamp" theory is RETRACTED (I was pattern-matching to the project's old 7P timestamp wound; reading the code corrected me). CONCLUSION: the "cutoff" is CAPTURE PHYSICS — pure static rotation starves the LiDAR-inertial odometry; the two good captures (083911/102338) worked because of natural handheld TRANSLATION. §7U rewritten to lead with this; rate-coupling framing demoted to history. Found 3 stale .bak matchers on Desktop (version decoys, nearly caused a wrong-version debug) -> recommend ~/Desktop/matcher_old/. Operator note: static pan "is a good thing" — a clean answer (physics, work around it via translation) beats a mystery bug to chase. NEXT: translation-based capture (out-and-back/drift, the A2 pattern) for multi-view coverage; the static pan is ruled out. Banked immediately per operator (leak history). Discarded captures 182551 + 185910 are in Trash.
- 2026-08-25 (Master 20.4 — translation PROVEN, init reframed, Aug-26 plan parked): Rig benched, limited moves only. Sequence of clean experiments, each rooted in real use: (1) Operator's idea: open RViz on raw /unilidar/cloud, NO Point-LIO, NO recording — "see what IT sees." Result: L2 emits detailed healthy geometry in every direction (Fixed Frame unilidar_lidar, Decay 5, Points 3); pan shows smear-then-coalesce = decay buffer holding un-repositioned old frames (no odometry to place them) = COSMETIC. Proves SENSOR IS PERFECT and Point-LIO's whole job is the missing "where am I." (2) Operator's 8-inch forward+down TIP capture (fusioncap_121359, ~19MB/608k pts): odom span 23.61s @2702Hz, matched 210/307 (68%) — vs static pan 185910 (0.98s, 6%). MINIMAL TRANSLATION FULLY RESTORES TRACKING. Hypothesis proven on-rig. Dropped frames were image[0..] at NEGATIVE t (pre-init, correctly dropped). (3) Init-wobble scare RESOLVED by operator's own logic: felt wobble at init -> feared tilt; my first "3.82deg floor tilt = wobble" was WRONG (bad plane-fit over furniture+far-tails). Operator: "if it were a frame tilt it'd ALL be off." Re-measured on dense core: CEILING 0.83deg (level), floor 3.22deg (contaminated) — NOT parallel -> NOT a frame tilt -> init wobble did NOT corrupt the map. I over-fit a tidy narrative to a bad number; operator corrected me with physics. (4) Operator reframe (important, banked): captures will NEVER be rock-steady in the field; wobble is FIELD-REAL and likely HELPFUL (wobble = small translation the LIO wants); the dead-still init is the one moment we remove the motion the system runs on. -> raises the real question: how much init motion is tolerable, and can init be INTERNALIZED. (5) Operator distinguished CALIBRATION (done, permanent: intrinsics+extrinsic, the days of board work) from INIT (gravity+bias per power-up) — do not conflate; a calib board could be an in-field dimensional truth-check, not an init fix. PARKED to Aug 26 (after operator frees rig from bench offline): gravity_init config path to make startup "power on roughly upright, go"; fallback measured-wobble-tolerance or LiDAR_IMU_Init online init; then real translation captures for multi-view. Matcher .bak cleanup still recommended (~/Desktop/matcher_old/). ONE RVIZ observed on 121359. Discarded 182551+185910 in Trash (185910 kept in uploads as the static-collapse evidence).
- 2026-08-25 (Master 20.6 — first full bake + processing-station/Unreal scouting + backups): Two big threads. (1) FIRST FULL BAKE, benched, on 083911 (operator's PCD; his matched-jpg bundle already on hand): ran the ENTIRE deliverable chain end-to-end for the first time — clean(97.4% kept)->normals->Poisson d9(357k verts/710k tris, 8.4s)->per-vertex texture(64.3% from 192 frames)->export(.ply mesh + .xyz xyzrgb). CHAIN PROVEN. Surprise: d9 ran in ~3GB (re-test on Jetson — the station may not be needed for meshing). Quality honestly ROUGH (single-vantage lumps, 36% gray, stringy window) = the single-vantage problem in mesh form; MULTI-VIEW is the fix; pipeline sound. Operator saw it in Open3D, called quality "really bad" — correct; banked as input-not-pipeline. (2) PROCESSING-STATION + UNREAL scouting: operator's budget laptop (Celeron N4120/8GB/UHD600) ruled OUT for UE5 (no discrete GPU) -> repurpose as Windows utility (L2 software) + Vagon terminal. Cloud-GPU (Vagon hourly) is the path; SaaS render farms can't run UE5 (needs interactive desktop); UE LiDAR plugin free+built-in; Meshmixer optional-cleanup-only (never smooth measured geometry); RealityScan = later/separate (photo-based, may compete with LiDAR accuracy). Operator got a Vagon account + ran a trial: ACCESS WORKS (machine/desktop/file-in) but Epic-launcher install BLOCKED by the known greyed-out-"+" bug (launcher can't go online on fresh machine); sample-grab didn't clear it. Shut down cleanly (no harm, ~20min meter). Fixes banked for next session: restart launcher/Windows first, then samples, or best use Vagon's app-catalog pre-installed Unreal; GitHub source route explicitly AVOIDED (compiles engine, wrong tool). Architecture clarified (Jetson measures / Vagon renders / move one file; you don't run Vagon "on" the Jetson). The open Unreal test (import the .xyz, check scale 1uu=1cm) is the last pipeline unknown, ~$1-4 next session. BACKUPS pushed/surfaced to repo this session: rig_start.sh, foundation_backup_20260825.tar.gz (68 files, full calibration+analysis codebase), desktop_backup_20260825.tar.gz (31 files, pipeline + the irreplaceable calib YAMLs), extract_frames.py, make_rgbd.py, and this 20.6. Memory tour verdict: operational pipeline was backed up; the calibration codebase + the calib_intrinsics/extrinsic YAMLs were the big gap, now closed. Downloads folder has 26 Masters (decoy clutter, cleanup-later, not urgent). tau finding confirmed durably in the Master (~175ms, colour-only, blocked-on-clean-capture). NEXT: still Aug-26 un-benching (init + translation captures + thermal), plus the Vagon Unreal import test (restart-first path).
- 2026-08-26 (Master 20.7 — field data architecture from the barn scenario): Operator posed the real-world test: measure a detailed barn interior, capture ~1 hour continuously, then review. Walked through the honest consequences: ~4-6GB/min -> ~300GB/hr -> BREAKS the Jetson (162GB free, fills mid-capture) and chokes processing (~180x) and can't be "reviewed" like video. CONCLUSION: capture strategy must be DELIBERATE OVERLAPPING PASSES + registration (the proven 19.4mm ICP, scaled up), not one continuous roll — the Leica/DJI method. Operator proposed a 2TB drive: correct fix for the STORAGE wall (wire it to the Jetson, record straight to it, ~6hrs headroom) but does NOT fix processing/review -> still pass-based. Operator then thought the drive "eliminates the wireless possibility" — CORRECTED: it only moves RECORDING to wired (the 5GB/min firehose would drop packets/corrupt over WiFi); wireless stays for MONITORING (light Foxglove coverage view to a phone) and OFFLOAD (after capture). So wireless survives for the two jobs that matter, recording goes wired. Field LAN = portable USB-powered travel router (Jetson joins as client, ethernet stays with L2). Banked as §8J with the full assembled field workflow. This whole thread (Teradek Q -> Jetson-as-LAN -> portable router -> Foxglove -> barn data volume -> 2TB drive) resolves the FIELD-READINESS transmission/storage picture. SHOPPING: 2TB USB drive + portable WiFi6 USB-powered router. TESTS (Aug-26+): record-to-USB-drive, Foxglove-over-router-to-phone, scaled multi-pass registration. NOTE: rig ready this afternoon for the first MOTION/translation captures — the immediate next real step, upstream of all this field-kit work.
- 2026-08-26 (Master 20.8 — timecode/sync framing, missing-footage taxonomy, field checker): Operator (film background) drove a rich field-workflow thread. Reframed tau as a TIMECODE/sync problem and correctly identified the hardware-trigger as the film "jam-sync" fix (shared clock, kills drift at source) — matching the existing "hardware-triggered camera kills tau" plan and the HKU LIV-Eye hardware-time-sync design. Established the boundary: timecode fixes sync, not spatial coverage. Worked out the THREE kinds of "missing footage" (files/poses/coverage) — the dangerous one is COVERAGE (spatial holes, invisible per-pass, only catchable by registering passes and looking for holes ON LOCATION before strike). This is the strongest argument yet for fast field-registration + live monitoring. Proposed a numerical FIELD CHECKER (crew-language good-take/re-shoot verdict, built from existing matcher+coverage+bag-info code) — to be drafted this afternoon. Also raised (parked, discussion open): can the Jetson bake a clock/timecode onto the data, and what would it do to the data. Banked as 8K. This continues the field-readiness arc (8H power/thermal, 8I bake/processing, 8J data-architecture, 8K sync/checker). NEXT: rig ready this afternoon -> first MOTION captures (the immediate real step), and optionally draft the field checker.
- 2026-08-26 (Master 20.8b — Jetson-clock distinction added to 8K): Operator asked whether the Jetson can "bake a clock code onto the data" and what it'd do. Answer banked in 8K: it ALREADY does (every message is timestamped on write) and it's HARMLESS (metadata, not mixed into coords/pixels). BUT it's an ARRIVAL-side clock -> cannot fix tau (tau is capture-side drift; camera arrives late vs actual exposure). Only a capture-side HARDWARE TRIGGER (film jam-sync) reaches tau. The Jetson clock IS useful for pass-to-pass session timecode (multi-pass registration order). Right principle, subtlety is WHERE the clock lives. PLAN: run a test tomorrow first thing — the freed-rig MOTION/translation captures are the immediate next real step (first thing next session).
- 2026-08-27 (Master 20.9 — live capture-health monitor designed & built): Operator drove a deep field-checker design thread to a coherent system. Rejected geometry/distance as markers (content- and pipeline-dependent); established TIME/data-rate as the only universal marker (hardware constant). Established rigor must be CONSTANT/LIVE (heartbeat during capture) not an end-of-capture autopsy — "rigor has to be a constant, not a surprise at the end." Reasoned to the two-part continuity check (interior-gap + flowed-to-Stop), the card-fill blind spot (fill-prediction from rate), and the two-bar glanceable interface (flow heartbeat + card fuel gauge). Built rig_monitor.py (live terminal bar monitor) + hardened check_capture.py to v2 (three-state, never-false-green). Bench-tested extensively: caught 3 bugs in check_capture (hidden errors, misplaced-PCD false-fail, dangerous GOOD-when-unverified) and the crash-blindspot in the continuity logic; sandbox-proved the measurement math (rate-counting 0% err, dropout->zero in 2s, fill-math, blip-tolerance). CRITICAL HONESTY established with operator: the LOGIC is proven but the NUMBERS are not — sensor rates are part-guess (camera may be 30 not 15Hz), and the data rate is unknown (4-5GB/5min eyeball vs 80MB/s placeholder = 5x apart); the monitor measures rate live so it self-corrects, but everything needs a HOT CALIBRATION run. Banked the two-tier philosophy (Tier-1 fatal rigorous now / Tier-2 quality pending Unreal characterization) as the resolution to "higher bar vs unknown Unreal." Section 8L holds it all + the going-hot checklist. NEXT: GOING HOT for the calibration run (measure real rates, resolve the data-rate question, fault-test the monitor live). Rig benched but running for this. (Waveshare still awaiting DP-to-HDMI cable for the untethered field display; monitor logic is bench-testable now regardless.)
- 2026-08-27 (Master 20.10 — hot-run findings: overload, lean mode, thermal baseline): Took rig_monitor v3 HOT and it immediately earned its keep. Calibration run first nailed the real rates (LiDAR 12 steady, camera ~30 warmed-up not 15/14, IMU 251, odom only during Point-LIO). Deliberate-fault test PASSED (unplugged camera -> Camera bar collapsed + ALARM live — the whole point proven). Then the BIG discovery: starting a full capture (Point-LIO + all preview nodes + RViz) overloaded the Jetson ~3x (load 19.7) and STARVED the sensors (camera 30->14Hz, IMU 251->168Hz) — captures were likely silently degraded and we were blind to it. ps aux confirmed exact load sources: pointlio/gscam/bag-record essential; RViz (via rviz:=true in the point_lio launch) + the 2 fusion nodes are the cuttable luxuries. Defined LEAN CAPTURE MODE (rviz:=false + skip fusion nodes) as the fix — test next hot. Measured thermal baseline: Jetson 56-63C -> the 50/55 temp thresholds are too tight, recalibrate. Confirmed L2 temp NOT exposed by driver (only cloud+imu topics). Established background cleanup is a red herring (load is our own stack; real levers lean-mode + optional headless). Worked out the viewer ladder (camera-only is the wrong rung; downsampled coverage cloud is the candidate) but PARKED it as a handheld-tests/field-ergonomics decision (partly a sunshade/brightness physical problem, not software). Operator reviewed rig_monitor v3 cold, approved. Banked as 8M. rig_monitor v3 remains in outputs (known-open: temp thresholds too tight, L2 stub is dead code). NEXT: still awaiting DP-to-HDMI cable for Waveshare/untethered captures; next hot session -> test lean capture mode (confirm camera/IMU recover to green) + recalibrate temp thresholds. Taking a break here.
- 2026-08-27 (Master 20.11 — L2 thermal blind spot resolved via authoritative manual + SDK): Operator pursued the L2 thermal unknown through Unitree's official sources. Read the L2 User Manual PDF (18pp): operating ambient -10..50C (the 60 we had was storage), NO documented catastrophic thermal-shutdown-with-unknown-recovery, temperature is a listed working-status field, and recovery from any problem is the routine "restart the L2." Net: the looming-catastrophe framing was over-worried — heat is a normal operating-range concern, not a lurking disaster (airflow + bounded sessions still sound; watch the Jetson temp bar as ambient proxy). Then read the unilidar_sdk2 v2.0.4: found apd_temperature in struct LidarInsideState, which is EMBEDDED in every point-data packet — so the L2 temperature is ALREADY arriving at the Jetson but the current ROS2 driver discards the inside-state (parses only cloud+IMU). This closes the "can we measure L2 temp" question: YES, via a moderate/defined driver modification to extract+publish state.apd_temperature (plus voltages, dirty_index, packet_lost, imu_temperature — a whole health channel). Banked as 8N with the how-to-use ladder (immediate: operate calmly + restart-is-recovery; medium: driver mod for live L2 temp bar; alt: Windows Unilidar 2 for spot-checks; plus the 2 sample bags as pipeline test assets). The L2 thermal blind spot is now a scoped engineering task, not a mystery. NEXT unchanged: lean-mode test + temp-threshold recalibration next hot session; Waveshare online (crowded, needs field-UI); DP-HDMI cable done. Break point.
- 2026-08-28 (Master 20.12 — L2 temp driver mod: done, built, awaiting hot test): Acting on the 8N finding (apd_temperature reachable but discarded by the driver), MODIFIED the unilidar ROS2 driver to publish it. Read the real driver on the Jetson (unitree_lidar_ros2.h — the header holds all logic; the .cpp is a thin main). Confirmed std_msgs already a dependency. Made 4 careful additive sed edits (one at a time, each verified), after backing up the original as .orig. First colcon build FAILED — accessor was ".state" but LidarPointDataPacket wraps LidarPointData `data` which holds `state`, so the correct path is getLidarPointDataPacket().data.state.apd_temperature; compiler caught it, fixed the one layer, rebuilt CLEAN ("Finished"). The temp publisher is now compiled into the driver, publishing /unilidar/apd_temperature (Float32). NOT yet hot-tested — operator wisely bundled the test into the next planned hot session rather than spin up just for this. NEXT HOT SESSION test stack: (1) temp driver — cloud still 12Hz + /unilidar/apd_temperature echoes real °C; (2) lean capture mode (rviz:=false + no fusion nodes -> camera/IMU recover to green); (3) recalibrate temp thresholds with real numbers; (4) wire rig_monitor L2 bar to /unilidar/apd_temperature -> close the thermal blind spot LIVE. This session turned the L2 thermal blind spot from mystery -> understood -> and now a built (pending-test) live-monitoring solution.
- 2026-08-28 (Master 20.12b — quaternion-order bug fixed in the driver): Pre-rig audit of the Master surfaced AUDIT FINDING #1 (long-open) as the one genuinely nagging item — a quaternion unpacked two ways in the driver we'd just modified. Investigated fresh from the actual code (not the summary): confirmed the IMU message uses [x,y,z,w] (correct) but the imu_initial->imu TF used [w,x,y,z] (wrong). Settled the true order from Unitree's OWN example.h line 72 ("quaternion (x,y,z,w)" with [0..3]) — definitively [x,y,z,w]. Fixed the TF (4 lines, one at a time, verified each), rebuilt CLEAN alongside the temp mod. Reasoned the downstream impact carefully: NONE to recorded/processed data — Point-LIO consumes the IMU topic (already correct) + the static cloud<->imu TF (correct), not this debug TF; bags record topics; fusion uses our extrinsic; matcher uses bag-time+poses. The fix only corrects the RViz TF-tree debug frame (rarely viewed) — which is exactly why captures worked despite the bug (it never touched the data path). A survived-a-power-blip file check confirmed both edits intact before the rebuild. So the driver now carries BOTH fixes (temp publish + quaternion) in one clean build, both awaiting the same hot test. Pre-rig audit also catalogued the remaining open items: tau (correctly parked, colour-only, blocked on clean capture), the strategic "rig's real justification vs iPhone" question (needs a good capture), and low-stakes housekeeping (version-decoy clutter, GitHub push pending) — none nagging. NEXT: the hot session (temp driver + quaternion + lean mode + temp-threshold recal + wire L2 bar), then the motion captures. Waveshare online (crowded, wants field-UI). DP-HDMI done.
- 2026-08-28 (Master 20.13 — field kiosk built, Plan A; closes the bench field-readiness arc): After the driver fixes, moved to the field UI. Operator tested the Waveshare on a generic PC (stripped-down = manageable, vs the cluttered Jetson desktop "zoo" at 7"). Built a full-screen kiosk mock (rig_kiosk_mock.html) sized for 1024x600 — big Start/Stop/Capture buttons + status line + flow/card/temp bars — validated on the real Waveshare ("looks really good, works really well"): the usable-at-7-inches question is answered YES. Then chose PLAN A: make the kiosk FUNCTIONAL by absorbing rig_monitor's engine (so the terminal monitor retires). Built rig_kiosk_server.py (dependency-free Python http.server: serves the page, /data = live health from rig_monitor's logic returning a dict, /action = fires the confirmed real scripts rig_start.sh/rig_stop.sh/point_lio_capture.sh). Wired the frontend live (bars poll /data, buttons call /action). Sandbox-proven end-to-end in mock mode (page serves, JSON changes live, buttons fire+report). Recalibrated temp thresholds to the real 59-63C baseline (green<68/yellow68-80/red>80). Both files downloaded to the Jetson Desktop tonight. Discussed the version-decoy-cleanup + folder-reorg (valuable, but tread carefully around live scripts + the ROS2 workspace — data/old files safe to move, scripts/launchers need reference-checking first). This CLOSES the bench field-readiness arc (8H hardware/power/thermal -> 8I bake/processing -> 8J data-architecture -> 8K sync/checker -> 8L monitor -> 8M overload/lean -> 8N L2-thermal/driver -> 8O kiosk). TOMORROW = the jumping-off point, likely MASTER 21 (a new FIELD-VALIDATION chapter): hot-validate the whole built stack (temp driver + quaternion fix + lean mode + kiosk /data + capture-lean + L2 temp + button safety), then the MOTION/translation captures — the real goal everything has been building toward. Shutting down; both kiosk downloads on the Desktop.
- 2026-08-28 (env note — stick to the scripts): Attempted a manual `source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash` and hit a warning: missing "fast_calib/share/fast_calib/local_setup.bash". DIAGNOSIS (harmless): fast_calib is a STALE leftover reference in ~/ros2_ws (a calibration pkg removed/cleaned at some point) — throws a warning but does NOT stop the driver loading. Confirmed `ros2 pkg list | grep unitree_lidar_ros2` -> the modified driver (temp+quaternion) IS available. point_lio did NOT show from that grep because Point-LIO lives in its OWN workspace (~/point_lio_ws), sourced by the launch scripts, not by a plain ~/ros2_ws source — that's why the manual source looked incomplete. LESSON (hard-won, reaffirmed): USE THE PROVEN SCRIPTS (rig_start.sh / point_lio_capture.sh) which source the right workspaces in the right order — do NOT manually source or get creative on the foundation. The only NEW thing the temp-driver test adds is three READ-ONLY checks on top of a normal Start Rig: ros2 topic hz /unilidar/cloud (still 12Hz), ros2 topic list | grep apd (topic exists), ros2 topic echo /unilidar/apd_temperature (real °C). TODO someday (non-urgent): clean the stale fast_calib reference so the warning stops. Rig was stopped at session start over this warning; environment confirmed fine for validation. NEXT SESSION unchanged: Start Rig (the script) -> the 3 temp checks -> lean mode -> kiosk /data -> translation capture.
- 2026-08-28 (hot check — BATTERY POWERS THE L2 RELIABLY, confirmed): Focused power-first session on the semi-benched hybrid setup (Jetson benched, L2+camera on the movable head via Ethernet+USB leads, big monitor not Waveshare). Confirmed the L2 trigger cable is 12V and checked it before connecting (honoring the §8H "meter before connect / destroy-risk if mis-set" caution). Started the rig on BATTERY power: clean bring-up (Ethernet link 1s, L2 responding 1s, "LiDAR data confirmed flowing"). Then the real test — sustained stability: ros2 topic hz /unilidar/cloud held STEADY at ~12.1Hz across the window (12.21->12.11->12.07 converging on nominal 12), tight jitter (std dev ~0.004s, min 0.065/max 0.091s), NO dropouts, NO sag. => PRIMARY CHECK ANSWERED: the battery powers the L2 cleanly AND holds steady under load, not just at startup. The §8H power design (12V trigger, metered, Ugreen bank) is validated in practice. NOTE: this run was FULL-STACK (rig_start brings up the fusion nodes too), not lean — fine for the power check since LiDAR hz is independent of the fusion-node CPU load. Lean-mode test was the secondary "if we get to it" item — DEFERRED (didn't get to it). NEXT SESSION still: the temp-driver 3 checks + lean mode + translation capture (all via the proven Start Rig script, not manual source). Shut down clean.
- 2026-08-28 (*** MILESTONE — L2 TEMP DRIVER VALIDATED LIVE, both driver mods confirmed ***): Ran the temp-driver check via the proven Start Rig script (clean bring-up). CLEAN SWEEP: (1) ros2 topic hz /unilidar/cloud = rock-steady 12.004Hz, std dev ~0.0003s (metronome) -> the driver mod did NOT disturb the cloud, mod is SAFE. (2) ros2 topic list | grep apd -> /unilidar/apd_temperature EXISTS -> the modified driver is running, temp publisher live. (3) *** ros2 topic echo /unilidar/apd_temperature -> REAL LIVE L2 TEMPERATURE: ~40.2C, rock steady (40.09-40.31 range). *** The single biggest blind spot in the entire project is now CLOSED with a measured fact. And the reading is REASSURING: 40C is COOL — huge margin to the -10..50C operating range and nowhere near any limit. The months-long L2 thermal fear was over-worried, now CONFIRMED by real data, not just the manual. The accessor path we fought through (getLidarPointDataPacket().data.state.apd_temperature) is proven correct — real, sensible, stable, live-updating values. (4) ros2 topic echo /tf --once -> printed a valid transform (the static unilidar_imu->unilidar_lidar, w:1, always-correct one); the "message was lost" spam is just echo-tool noise on a high-rate topic, not a rig problem. The quaternion fix is verified by construction (correct [0,1,2,3] order matching the SDK, built clean, TF publishing without error) — live-watching the dynamic frame is unnecessary belt-and-suspenders. NET: BOTH driver mods (temp publish + quaternion fix) validated. The L2 temp bar can now be wired into the kiosk/monitor with a real topic. The terminal rig_monitor L2 stub can retire. HUGE session — turned the project's scariest unknown into a calm measured 40C. NEXT: wire the L2 temp into the kiosk /data (L2_TEMP_TOPIC already set to /unilidar/apd_temperature in the server) + lean mode + translation capture.
- 2026-08-28 (kiosk BETA test — live on the big monitor, semi-benched): Ran the functional kiosk hot (Plan A). Server started in ROS2 mode (real reads), served to localhost:8080, opened in Firefox on the big monitor. RESULT — the architecture WORKS: the kiosk displayed LIVE data. CORRECT + LIVE: L2 temp 40C green (the driver-mod payoff showing in the field UI for the first time!), Jetson 61C green (recalibrated thresholds work — no false red), Card 150.9GB, status RIG ON, Odom "waiting". ONE BUG found (what a beta is for): the FLOW bars (LiDAR/Camera/IMU) read a false ~3Hz red — the server's ros_reader loop was throttling message intake (spin_once + sleep = ~6-7 checks/sec, missing most messages on high-rate topics). FIX applied: split the reader into (1) a dedicated thread spinning rclpy.spin(node) CONTINUOUSLY to catch every message + (2) a display-paced snapshot loop; raised queue depth 10->50. Updated rig_kiosk_server.py delivered + put on the Desktop. NOT YET re-tested (rig went off before the refresh). ARCHITECTURE NOTES banked: (a) runs FULLY INTERNALLY — localhost, no internet, works in a signal-dead barn (operator rightly checked — Firefox is just a local display surface, not web access); refinement = launch via `chromium --kiosk http://localhost:8080` (fullscreen app-feel, no browser chrome) as the eventual one-tap launcher. (b) The server terminal must stay OPEN (holds the running server) — closing it drops the connection ("Unable to connect"). (c) rig_start.sh publish-check can FALSE-ALARM "no data detected" if the L2 is slow to init (this run: Ethernet 4s/L2 2s vs usual 1s/1s) — ros2 topic hz is the real arbiter (confirmed steady 12Hz). OPERATOR RAISED (good discipline): are we adjusting the measure to fit what we want to see? NO — the fix only stops missed messages; the method (count real msgs / window) is unchanged. *** OPEN NEXT SESSION: refresh kiosk, confirm flow bars read true 12/30/251, AND cross-check against an independent `ros2 topic hz` — the kiosk's numbers must MATCH the tool (noisy-but-right = genuine; suspiciously-perfect = faked). Don't trust the flow bars until verified against the independent measure. ***
