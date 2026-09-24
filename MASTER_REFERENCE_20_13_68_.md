<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.68, 2026-09-23) ***** -->
<!-- *** NEXT STEP: CLEAN CAPTURE WITH FIXED ODOMETRY AND COMPRESSED FRAMES.       -->
<!-- ***   Everything off-rig is built + validated. The one thing standing between  -->
<!-- ***   us and the first walkable, relightable room is a single clean capture:   -->
<!-- ***   an odom that actually MOVES (positions span real metres) recorded with    -->
<!-- ***   COMPRESSED camera frames (/image_raw/compressed). Both fixes are in hand.  -->
<!-- -->
<!-- *** THE TWO ADRs ARE AT THE TOP OF THIS FILE (below the header), ahead of the   -->
<!-- ***   session log — read them first: ADR-002 (texture-pipeline reliability:     -->
<!-- ***   compressed capture + hard coverage gate) and ADR-001 (representation      -->
<!-- ***   fork: LiDAR = dimensions, photos = graphics).                             -->
<!-- -->
<!-- *** WHERE WE ARE (9-23): geometry SOLVED (planar_shell: 8–11 mm planes, square  -->
<!-- ***   walls; Poisson convicted). Architecture RATIFIED (ADR-001). Texture       -->
<!-- ***   pipeline BUILT + VALIDATED off-rig (matcher gate, shell bake, occlusion,  -->
<!-- ***   native-JPEG capture node). COVERAGE NOT SOLVED — the 130955 "walked room" -->
<!-- ***   was RETRACTED: its odom is FROZEN / single-vantage (see the ⚠️ CORRECTION  -->
<!-- ***   and the 🖼️ VISUAL PROOF block). Extrinsic code-verified, real-world        -->
<!-- ***   UNCERTIFIED (gated on the clean capture).                                 -->
<!-- -->
<!-- *** STILL OPEN from 20.13.66 (the Unreal thread — its full ACTIVE-STATE block   -->
<!-- ***   and the STAGE 1–7 RealityScan→UE5 recipe are PRESERVED VERBATIM further   -->
<!-- ***   down): recover the UE5 viewport, import photo_mesh, add collision, walk it.-->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ NEXT STEP — CLEAN CAPTURE WITH FIXED ODOMETRY AND COMPRESSED FRAMES  ⭐
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**The whole project now turns on ONE capture.** Off-rig work is done and proven; the
deliverable has never been produced because every capture has failed on one of two
things at the rig. Both are now fixed in code and waiting to be run:

1. **FIXED ODOMETRY (a moving odom, recorded).** The odom must actually MOVE — the
   `/aft_mapped_to_init` POSITIONS must span real metres — and the bag must record it.
   130955 looked room-scale but its odom was **frozen at one vantage** (see ⚠️
   CORRECTION + 🖼️ VISUAL PROOF). GATE: `capture_autopsy` on the raw odom must show real
   translation BEFORE the capture is trusted.

2. **COMPRESSED FRAMES.** Record `/image_raw/compressed`, not raw `/image_raw`. Raw
   recording (≈190 MB/s, 40 GiB / 3.6 min) chokes the Jetson recorder and drops the odom
   stream — the root cause of the 127 s hole. `rig_camera_compressed.py` publishes the
   camera's native JPEG as `CompressedImage` (no decode / no re-encode); then
   `capture_pointlio_texture.sh` auto-selects the compressed topic. Bag ~4 GB, odom stays
   dense.

**THE RIG SEQUENCE (next session):**
- (a) Bring up with `rig_camera_compressed.py`; confirm nothing else needs raw
  `/image_raw` (ADR-002 item 9 — grep for `/image_raw` subscribers first).
- (b) 20 s stationary coexistence test → bag ≪ 40 GB AND odom present.
- (c) Real WALKED perimeter traverse (parallax; scale to the room; keep translating).
- (d) GATE, in order, before any bake: `capture_autopsy` (positions MOVE) →
  `pointlio_pose_matcher` (match ≥ 90 %, no in-run hole > 2 s) → `planar_shell`
  (≤ 30 mm planes, walls < 6°).
- (e) THEN the shell + occlusion bake — and the extrinsic finally gets its real,
  parallax-bearing certification test.

**Everything below this header is the reference lineage. The two ADRs come first.**


<!-- ############################################################################## -->
<!-- ##  ARCHITECTURE DECISION RECORDS — AT THE TOP, READ BEFORE THE SESSION LOG  ## -->
<!-- ##  Full source files in the project: ADR-002_texture_pipeline_reliability.md ## -->
<!-- ##  and ADR-001_representation_fork.md. Reproduced here in full.              ## -->
<!-- ############################################################################## -->

# ADR-002: Texture-pipeline reliability — compressed capture + a hard coverage gate

**Status:** Proposed
**Date:** 2026-09-23
**Deciders:** Operator (FASTERBYBAXTER) — sole sign-off
**Prior context:** `MASTER_UPDATE_2026-09-22.md` ⛔ banner (the blocking defect); `pointlio_pose_matcher.py` audit; `capture_pointlio_texture.sh` (repo); ADR-001.

---

## Context

Two confirmed defects sit between a green capture and a usable textured deliverable — both proven on `fusioncap_130955` (2026-09-23):

1. **Raw-image recording drops odometry.** Recording raw `/image_raw` (1920×1200, ~6.9 MB/frame, ~190 MB/s, 40 GiB in 3.6 min) chokes the Jetson recorder → a 127.3 s hole in the `/aft_mapped_to_init` bag stream → the pose matcher can pose only 42 % of frames → no complete texture. Geometry survives (Point-LIO writes `scans.pcd` direct to disk), so nothing upstream turns red.
2. **The matcher writes its output regardless of coverage.** `pointlio_pose_matcher.py` correctly *refuses* to interpolate across an odom hole (its `max_gap` guard), prints "matched 42 %", and then **writes the `.npz` anyway.** The baker downstream will consume a 42 %-covered pose set and paint a two-patch room. There is no gate; the true texture-coverage number is printed and ignored.

**Check-what-exists result (per the ratified rule):** `capture_pointlio_texture.sh` already exists in the repo and already **prefers** `/camera/image_raw/compressed`, records `/aft_mapped_to_init` + image + `/unilidar/imu`, gates on live streams, runs Point-LIO headless, and saves the PCD on clean exit. It is NOT reinvented. Its one blind spot: it only *uses* compressed if that topic is published — and the current lean bringup (`rig_start_lean.sh`) publishes only raw `/image_raw`.

**Constraints:** solo operator runs all rig commands; 8 GB Jetson (IO/mem-tight); step-at-a-time, proven-before-moving; files transfer via the `rig-files` repo; verify by checksum; the project "is about catching confident wrong answers."

---

## Decision

Close the two defects with the **smallest change that reuses proven pieces**:

- **CAPTURE = publish a compressed image topic at bringup, then use the existing `capture_pointlio_texture.sh`.** The capture script is already correct; the fix is to make the rig publish `/camera/image_raw/compressed` so the script takes its compressed path. **CORRECTION (verified 2026-09-23): gscam publishes RAW `sensor_msgs/Image` only — it CANNOT emit a `CompressedImage` topic**, so "edit the gscam line" is NOT the fix. The chosen path is a small dedicated node (`rig_camera_compressed.py`) that reads the camera's *native* MJPEG via a gstreamer appsink and republishes it as `CompressedImage` with no decode and no re-encode. This spends ~zero CPU (does not compete with Point-LIO) and never touches `nvv4l2decoder`/NVJPG (so it also sidesteps the NVMM ring-buffer starvation that killed the camera on 9-22). Data path sandbox-validated; gstreamer/rclpy integration must be verified live.
- **MATCHER = add a hard coverage GATE.** After matching, if match % < threshold, or odom span doesn't bracket the images, or an in-run odom hole exceeds a threshold → print a FAIL verdict, **do not write the `.npz`**, exit non-zero. A `--force` escape hatch allows a deliberate partial bake. The proven interpolation math is untouched.

---

## Options Considered

### CAPTURE — how to get the compressed topic

#### Option A: A dedicated node republishes the camera's native MJPEG as `CompressedImage` (CHOSEN)
`rig_camera_compressed.py` — `v4l2src ! image/jpeg ! jpegparse ! appsink` → `CompressedImage`. No decode, no re-encode. (gscam cannot do this; see the correction above.)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low–Med (a ~70-line node; replaces the gscam camera start) |
| Cost (Jetson load) | **Lowest** — the JPEG already exists in HW; no decode, no encode → no CPU vs Point-LIO |
| Scalability | Best — smallest bag (~1–5 GB / 220 s), least IO |
| Team familiarity | Med — new node, but standard rclpy + gstreamer appsink |

**Pros:** removes the raw-decode load AND the re-encode load; bag ~1–5 GB; matcher already decodes `CompressedImage` via `cv2.imdecode` (validated); **avoids `nvv4l2decoder`/NVJPG so the 9-22 NVMM camera-death scar can't recur.** **Cons:** a new (small) node to maintain; its rclpy/gstreamer integration needs live verification on the Jetson; only ONE process can open `/dev/video0`, so it must REPLACE gscam at bringup, not run alongside it.

#### Option B: `image_transport republish raw → compressed` alongside the existing raw
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (one stock node) |
| Cost | Med — re-encodes already-decoded raw (extra CPU), and still records only the compressed |
| Scalability | OK |
| Team familiarity | High (standard ROS) |

**Pros:** trivial, standard, no gscam surgery. **Cons:** burns CPU re-compressing during the coexistence-critical window (the exact resource we're short of); wasteful given the camera already emits JPEG.

#### Option C: Keep raw, add a 2 TB USB capture drive (the field-data plan from Master 20.6/8J)
**Pros:** solves the IO wall generally; needed eventually for hour-long barn captures. **Cons:** hardware, doesn't reduce the decode load, over-scoped for the living-room re-shoot. Defer to the field-capture ADR.

**Choice: Option A**, with Option B as the fast fallback if the gscam rework proves fiddly on the night. Reconcile the topic name so `capture_pointlio_texture.sh` finds it (it looks for `/camera/image_raw/compressed`; the lean bringup remaps to `/image_raw`).

### MATCHER — the gate

#### Option A: Hard gate, refuse to write (chosen)
Fail-closed: no `.npz` on low coverage → the baker physically cannot consume a starved capture. `--force` for deliberate partials.

#### Option B: Soft gate (warn only)
Prints a loud warning, still writes. **Rejected** — that is essentially today's behavior; a warning is what we already ignored.

---

## Trade-off Analysis

The through-line is **fail-closed at the earliest honest gate.** Geometry already fails closed (planar_shell). Texture coverage did not — it printed a number and proceeded. Making the matcher refuse (A) converts a silent quality loss into a loud stop, at the cost of one `--force` flag for the rare intentional partial. On capture, choosing the native-JPEG path (A) spends engineering effort now to *remove* load rather than *add* it (B), which matters precisely because the 8 GB Jetson's scarcity is the root cause.

---

## Consequences

**Easier:** every future capture is ~4 GB not ~40 GB; odom stays dense; a starved bag stops at the matcher instead of wasting a bake; the matcher's "matched %" becomes a real gate in the §10 verification chain.

**Harder / to revisit:** the gscam bringup needs the compressed topic wired (one-time); the matcher's `--image-topic` must be pointed at the compressed topic for the re-shoot; thresholds (`--min-match`, in-run hole) are judgement calls to tune on the first clean bag.

**Tech-debt retired / flagged:** `rig_start_lean.sh` (raw-only, not in repo — a known hygiene item) should gain the compressed publisher and land in the repo. `fuse_to_fbx.py` still runs convicted Poisson (ADR-001) — unchanged here, still to retire.

---

## Action Items

1. [ ] **Matcher gate (this session, no rig):** add `--min-match` / in-run-hole / `--force` gate to `pointlio_pose_matcher.py`; keep the proven math verbatim; sandbox-prove it FAILS 130955-shaped input and PASSES clean input. Deliver + verify by checksum.
2. [ ] **Rig bringup (needs rig):** publish `/camera/image_raw/compressed` at bringup (Option A native MJPEG; Option B republish fallback). Verify the topic with `ros2 topic hz`.
3. [ ] **Wire capture:** run `capture_pointlio_texture.sh`, confirm it selects the compressed topic (reconcile the topic-name check if needed), do a ~20 s stationary coexistence test → confirm bag ≪ 40 GB and dense odom.
4. [ ] **Re-shoot** the living room compressed + full-perimeter traverse; run the matcher gate → expect PASS.
5. [~] **Piece 3 extrinsic — CODE-PATH verified; REAL-WORLD validation OPEN (operator-ratified 2026-09-23).** Proven: the extrinsic is applied EXACTLY ONCE in `per_shot_texture.compose_world_to_cam` (R_L2C 85.5°, T_L2C 16.9 cm), math exact to 5.6e-15 m; matcher (`APPLY_EXTRINSIC=False`) and Piece 3 both pass raw lidar-in-map poses; the zero/double-apply plumbing bug is NOT present (double-apply would be 28 m/frame off). NOT proven: that the calibrated R_L2C/T_L2C are correct for the rig as it now stands — a wrong-but-consistent extrinsic still misaligns every photo, and the sandbox has no ground truth to catch that. **The extrinsic problem remains OPEN until a CLEAN CAPTURE confirms photo-to-geometry alignment** (checkerboard-on-checkerboard / texture edges land on geometry edges / through-glass points inside the window frame, as 083911 once showed). This is a GATE on the first clean bake, not a closed item.
6. [x] **Baker fix — OCCLUSION implemented (2026-09-23, built + validated cold):** `pointlio_to_texture.py` v3 adds `--occlusion` (+ `--occluders objects.ply`): a per-camera DEPTH BUFFER of the shell mesh + the furniture points; a face is valid for a camera only if nothing nearer sits at its pixel (shadow-map visibility). Proven cold (selftest TEST F): a camera whose view is blocked by furniture is fully rejected on the occluded faces and kept where it is clear. PERF: rasterizes one depth buffer per camera (pure numpy) — for a real bag, texture from a keyframe subset and/or raise `--occ-scale`; open3d RaycastingScene (BVH) is the future speedup.
7. [x] **Baker fix — POISSON RETIRED in Piece 3 (2026-09-23, built + validated cold):** `pointlio_to_texture.py` v2 adds a `--shell shell.obj` path that textures `planar_shell`'s clean geometry directly (no Poisson, no open3d on that path). Frame-safe (shell.obj and the matcher poses are both in the Point-LIO map frame). Proven cold: 5/5 selftests incl. an OBJ-load roundtrip, plus a synthetic-room bake that routes each wall to its head-on camera. Legacy Poisson kept only behind an explicit, warned `--cloud`. Real-data validation on Shadow still pending (run with 130955's `shell.obj` + its frames). NOTE: shell-only texturing makes finding #6 (occlusion) MORE important — with furniture absent from the mesh, its pixels smear onto walls unless occlusion uses the furniture (objects.ply) as an occluder.
8. [x] **Adversarial audit + gate cry-wolf FIX (2026-09-23):** ran the *delivered* matcher on a synthetic ROS2 bag (rosbags Writer). Confirmed on real bag I/O: reads `/camera/image_raw/compressed`; gate fails-closed on a 3 s odom hole (exit 2, no npz) and passes a clean bag; **pose↔image index alignment is exact across the two-pass read** (file k ↔ content k ↔ pose at t_k, no off-by-N — the scariest seam is clean); Piece 3 assembles npz+frames in correct index order. FOUND + FIXED: the gate coupled `--max-hole` to `--max-gap` (0.5 s) → it false-failed a 99.6%-covered capture over a 1 s blip (a gate that cries wolf gets ignored — the original sin). Decoupled `--max-hole` to 2.0 s; re-verified a 1 s blip PASSES while a 5 s blind spot still FAILS. Also added a decode-failure guard to `dump_frames` (raise, never silently misalign).
9. [ ] **BRINGUP CONFLICT (rig, HIGH — verify before the re-shoot):** `rig_camera_compressed.py` replaces gscam on `/dev/video0` (only one process can open the camera). Before swapping, grep the rig for subscribers of raw `/image_raw` (rig_monitor1.py, rig_kiosk, any preview/fusion node) — they go dark on a compressed capture. If a live preview is needed during capture, point it at the compressed topic. Cannot be tested off-rig.
10. [!] **130955 ODOM IS FROZEN / SINGLE-VANTAGE — corrects the earlier "coverage solved" (2026-09-23, on real bundle data):** ran the real 130955 bundle (shell.obj + objects.ply + 30 keyframes + poses) through the delivered tools. ALL recoverable poses are frozen at ~origin: `pos` ≈ (−0.01, −0.008, 0) for keyframes 0/15/29, view-direction spread 1–2° across all 30. The room-scale `scans.pcd` extent is the L2 ranging out to the walls from ONE near-stationary vantage (near the mantel), NOT a walked trajectory. CORRECTIONS: (a) the earlier "coverage SOLVED / room-scale walk" call was WRONG — 130955 is single-vantage; (b) `capture_autopsy`'s flat/VANTAGE reading on 130955 was CORRECT, not a false negative — UN-DEMOTE it. CONSEQUENCE: the extrinsic CANNOT be certified on 130955 (no parallax, frozen poses). A frame-0 overlay (near init, a valid vantage) shows the shell projecting roughly onto the real room — no gross 85°/28 m error, a WEAK POSITIVE only, not certification. LIKELY CAUSE: recorded stretches were a stationary mantel dwell and the walk fell inside the 127 s odom hole; alternative is a Point-LIO odom freeze. NEW GATE for the clean re-shoot: require `/aft_mapped_to_init` POSITIONS to span real metres (capture_autopsy coverage check on the raw odom) BEFORE trusting a capture — a clean-looking map can sit on a frozen single-vantage odom. Master 20.13.67's "coverage solved" line must be corrected.


<!-- ─────────────────────  ADR-001 (representation fork)  ───────────────────── -->

# ADR-001: Reconstruction representation — LiDAR-dimensions / photos-graphics, forked per-deliverable on the relight gate

**Status:** Proposed
**Date:** 2026-09-22
**Deciders:** Operator (FASTERBYBAXTER) — sole sign-off
**Prior context:** `PIPELINE_AUDIT_fork_and_inversion_2026-09-22.md` (five-pass repo audit); `MASTER_REFERENCE_20_13_65_`; `planar_shell.py`.

---

## Context

The rig (Unitree L2 + Arducam global-shutter + Jetson → Shadow) produces coherent capture but has **never produced the deliverable**: a photoreal, UV-textured, **relightable**, walkable asset. The mission is day→night predictive relighting for film sets — *mesh-honesty = prediction-validity* (if the barn's dimensions are wrong, the crane clears the roof in Unreal but hits it on the day).

Forces at play, from the audit:

- **Poisson is convicted** on the project's own data (invented surface up to **1556 mm** from measured points) yet still ships in `fuse_to_fbx.py`. Ball-pivoting is honest (0 mm) but holey. **~52% of a room cloud is already clean planes at 16 mm** (the L2 limit).
- **The appearance half of the inversion is already ratified** (9-16: "texture from photos, not the colored cloud"). The dimensions half is embodied in `planar_shell.py` (pure-LiDAR crisp shell, tau- and parallax-independent).
- **Gaussian splatting is photo-native and photoreal but bakes captured light** — it does not relight and does not participate in Unreal Lumen GI. It sits in reserve (7G), gated on commercial relightable-GS maturity (not present as of 2026).
- **Open blockers** that constrain any photo-graphics path: Point-LIO **odom-cutoff drops 40–77% of frames**; **tau not closed on real data**; **no photometric pose refinement (BA)**; **no loop closure**; delight never run on a real asset.

**Constraints:** solo operator runs all captures/commands; heat-limited rig (short capture windows); processing on one Shadow cloud PC (RTX A4500, 28 GB); step-at-a-time, proven-before-moving; the project's history "is about catching confident wrong answers."

---

## Decision

Adopt **LiDAR = dimensions, photos = graphics** as the organizing architecture, and **do not pick one final representation**. Carry **two endpoints** and choose per-deliverable **at capture time**, gated on a single question: *does this deliverable need Lumen day→night relight?*

- **LiDAR-dimensions branch (always built):** `planar_shell.py` RANSAC shell + raw cloud → metric collision, light-blocking geometry, scale, and coherence verification.
- **Photos-graphics branch (the fork):**
  - **Relight = YES →** delit UV-textured mesh + PBR (Lumen-relightable).
  - **Relight = NO →** Gaussian splat (as-lit), LiDAR-anchored scale.
- **New shared hinge stage:** photometric pose refinement (SfM/BA) seeded by the LiDAR poses+points already exported by `poses_to_colmap.py`.

---

## Options Considered

### Option A: Mesh-only (status quo, hardened)
Trimmed-Poisson/planar geometry → photo texture → delight → PBR. Gaussian never adopted.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — known tools, but Poisson-babysitting persists |
| Cost | Low — no new representation |
| Scalability | Medium — drift + odom-cutoff still bite large captures |
| Team familiarity | High — this is the current path |
| Mission fit (relight) | **High** — delit PBR surface is Lumen-native |

**Pros:** relight-honest; Unreal-native; inherits LiDAR metric truth; least new tooling.
**Cons:** leaves the photoreal ceiling of splats on the table; keeps fighting the melt; single endpoint can't serve relight-optional jobs (scouts, walkthroughs) as cheaply.

### Option B: Gaussian-splat primary
Commit to 3DGS as the graphics representation; LiDAR anchors scale.

| Dimension | Assessment |
|-----------|------------|
| Complexity | High — new capture SOP, BA, splat training, splat→mesh for relight |
| Cost | Medium-High — GPU training; recapture for parallax |
| Scalability | Medium — floaters without dense multi-view + good poses |
| Team familiarity | Low — unbuilt in the repo |
| Mission fit (relight) | **Low** — bakes light, no Lumen GI; needs splat→mesh→delight to relight |

**Pros:** highest photoreal fidelity; real-time walkable; photo-native (full inversion).
**Cons:** **fails the core relight mission on its own**; demands the hardest pose pipeline; rearranges capture; relightable-GS not commercial yet.

### Option C: LiDAR-dimensions / photos-graphics, forked per-deliverable *(recommended)*
Both endpoints on a shared spine; fork decided at capture on the relight gate.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium-High — one shared spine + one extra hinge (BA); branches reuse it |
| Cost | Medium — no wasted capture (shared upstream); GPU only when splatting |
| Scalability | Medium-High — planar shell is robust to the open capture defects |
| Team familiarity | Medium — extends ratified doctrine, not a rewrite |
| Mission fit (relight) | **High** — relight jobs get the delit mesh; as-lit jobs get the splat |

**Pros:** matches how the sensors already split; nothing upstream wasted; serves both relight and relight-optional jobs; splat adoptable later without re-architecture; planar shell sidesteps tau/parallax/normal problems.
**Cons:** two back-half endpoints to maintain; requires the decision be made *before* capture; still gated on the open blockers.

---

## Trade-off Analysis

The real axis is not mesh-quality vs splat-quality — it is **relight capability vs photoreal fidelity**, and the mission puts relight first. Option B trades away the mission for fidelity and cannot buy it back without becoming Option A internally (splat→mesh→delight). Option A honors the mission but leaves fidelity and relight-optional use-cases underserved, and keeps single-repping a pipeline whose sensors already do different jobs. Option C costs one extra maintained endpoint and a discipline of deciding at capture, in exchange for: a shared, non-wasted upstream; the mission-safe relight path as default; and a clean, later, no-rework on-ramp to splats if/when relightable-GS matures (the 7G re-check). Given that **everything up to the registration output is identical across branches**, the marginal cost of carrying both is low and the optionality is high.

Decisive point: the fork is a *capture-time* decision because Gaussian's data demands (orbit-parallax, sharp frames, sub-pixel poses) rewrite the SOP. Option C is the only one that makes that a per-job switch instead of a one-way global commitment.

---

## Consequences

**Easier**
- Relight deliverables get a physically honest path (delit PBR on a metric surface).
- Relight-optional deliverables (scouts, walkthroughs) get a cheaper, higher-fidelity splat.
- `planar_shell.py` becomes the single LiDAR-dimensions asset feeding both branches and doubles as the geometry-health diagnostic.
- Splat adoption later needs no upstream rework.

**Harder**
- Pose accuracy becomes mission-critical: photos-as-graphics is unforgiving of pose error, forcing the new BA hinge and making tau-closure and the odom-cutoff fix prerequisites, not niceties.
- Two back-half endpoints to build and maintain.
- Capture discipline tightens: the branch (and flat/overcast light for delight) must be chosen before the rig leaves the stand.

**Revisit when**
- Commercial relightable-GS + Unreal Lumen-GI integration ships → the splat branch may itself carry relight, collapsing the fork (the explicit 7G trigger).
- Loop-closure / TSDF multi-pass lands → large captures (house + yard) become viable.

---

## Action Items
1. [ ] Run `planar_shell.py` on `fusioncap_163005.ply`; read the coherence report (thickness = drift, orthogonality = collapse). Decides whether Point-LIO geometry is trustworthy — the foundation both branches stand on.
2. [ ] Fix the Point-LIO odom-cutoff (HKU `LiDAR_IMU_Init` temporal-init lead). Gates every photo-graphics path.
3. [ ] Stand up the BA hinge: `poses_to_colmap.py` → COLMAP/GLOMAP bundle-adjust (LiDAR-seeded) → sub-pixel poses. Serves both branches.
4. [ ] Prove ONE relightable deliverable end-to-end: shell + delit PBR texture → Lumen day→night on a real capture. Validates the rig's reason to exist.
5. [ ] Only then A/B the splat branch on a relight-optional deliverable; re-check relightable-GS maturity.
6. [ ] Retire Poisson from `fuse_to_fbx.py` once the planar shell + object-mesh path is proven on real data.
7. [ ] Standardize capture-light (flat/overcast or bracketed) so the delight step stays physically honest.

---
*If accepted, supersede the ad-hoc "CHOSE MESH (Plan A), splat in reserve (Plan B)" framing in §7E/7G with this per-deliverable fork, and mint the change into the Master lineage.*


<!-- ============================================================================ -->
<!-- ##  END OF ADRs.  BELOW = 20.13.68 SESSION LAYER, THEN THE PRESERVED BASE.  ## -->
<!-- ============================================================================ -->


# ═══ MASTER 20.13.68 — 2026-09-22 → 09-23 SESSION LAYER (folded onto 20.13.66) ═══
### Session record: the geometry verdict, the capture-method autopsy, the architecture fork, the new tools — the BLOCKING RECORDING DEFECT — the FROZEN-ODOM correction — and the on-camera visual proof of it.
### Fold this into the lineage deliberately (Stone Clause). Nothing here is a silent drift — every claim is tagged.

═══════════════════════════════════════════════════════════════════════════
## ⛔ BLOCKING DEFECT (2026-09-23) — RAW-IMAGE RECORDING POISONS EVERY CAPTURE
##    NO GOOD DATA CAN COME OUT OF THIS UNTIL CAPTURE RECORDS COMPRESSED IMAGES
═══════════════════════════════════════════════════════════════════════════
**THE RULE:** Until the capture script records the **compressed** camera topic
(`/image_raw/compressed`), every capture is **GEOMETRY-ONLY at best.** A textured /
relightable / walkable deliverable CANNOT be produced from a raw-`/image_raw` capture.
No good data comes out of this. [PROVEN on real data 2026-09-23]

**MECHANISM (proven, not theorized):** recording raw `/image_raw` (1920×1200 ≈
6.9 MB/frame, ~190 MB/s, **40 GiB in 3.6 min**) chokes the Jetson → the rosbag
recorder drops the high-rate `/aft_mapped_to_init` odom stream mid-capture. Point-LIO
keeps tracking internally and writes `scans.pcd` **direct to disk** (bypasses the
choked bag) → the GEOMETRY survives clean. But the BAG's odom develops HOLES, and the
pose matcher (Piece 2) correctly REFUSES to interpolate camera poses across a hole →
most frames un-poseable → no complete texture. The geometry gate cannot see this: it
reads the assembled CLOUD (robust); the disease lives in the ODOM TIMESTAMP STREAM
that only the texture stage consumes.

**EVIDENCE — `fusioncap_130955` (2026-09-23):**
- ~~Coverage SOLVED at last — a real perimeter loop~~ **[RETRACTED — see the ⚠️
  CORRECTION block immediately below: 130955's odom is FROZEN / single-vantage; the
  room-scale extent is the L2's range from one spot, NOT a walked trajectory.]**
- `planar_shell` GREEN: planes **8.1–11.7 mm**, walls square **3.4°**, 59.5% planar —
  but this is a clean SINGLE-VANTAGE scan (no drift because near-stationary), not proof
  of coverage.
- Camera fine: 6,125 images. Init clean. Sensors steady (cloud 12 Hz, IMU 251 Hz).
- BUT the odom bag has a **127.3 s HOLE** (t≈9.7–137 s). Pose matcher: only
  **2,549 / 6,125 frames poseable (42%)** — AND those 42% are all a frozen vantage
  (see CORRECTION). **Texture impossible.**

**SUPERSEDES §0/§4 ("coverage is the sole remaining variable"):** the RECORDING METHOD
is the top blocker. Green geometry + green init + green camera count can ALL pass while
the deliverable is impossible.

**THE FIX (two parts):**
1. **CAPTURE:** record `/image_raw/compressed`. Bag ~4 GB, recorder keeps up, odom
   stays dense. `capture_pointlio_texture.sh` already prefers the compressed topic; the
   real gap is that the lean bringup never PUBLISHES a compressed topic —
   `rig_camera_compressed.py` (new, 9-23) publishes the camera's native JPEG as
   CompressedImage (no decode, no re-encode; also sidesteps the NVMM decoder scar).
2. **MATCHER:** coverage is now a HARD GATE (`pointlio_pose_matcher.py` v2) — fails
   (exit 2, writes no npz) if match% < 90, images fall outside the odom span, or an
   in-run hole exceeds `--max-hole` (default 2.0 s, decoupled from `--max-gap`).

**AUDIT METHOD (banked):** every transform is sandbox-proven on capture-shaped data
BEFORE it is trusted on a real bag. The matcher, the shell/occlusion baker, and the
bundle-maker were all run end-to-end (incl. a synthetic ROS2 bag proving pose↔image
index alignment to machine precision) before touching 130955.
═══════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════
## ⚠️ CORRECTION (2026-09-23 late, on REAL 130955 data) — "COVERAGE SOLVED" RETRACTED
##    130955's ODOM IS FROZEN / SINGLE-VANTAGE.  GREEN GEOMETRY ≠ GOOD POSES.
═══════════════════════════════════════════════════════════════════════════
Ran the REAL 130955 bundle (shell.obj + objects.ply + 30 posed keyframes) through the
delivered tools. Every recoverable camera pose is FROZEN at one spot: pos ≈
(−0.01, −0.008, 0) for keyframes 0/15/29; view-direction spread only 1–2° across all 30.

- **"Coverage SOLVED / room-scale walk" is RETRACTED.** The room-scale `scans.pcd`
  extent is the L2 RANGING OUT TO THE WALLS from one near-stationary vantage (near the
  mantel) — NOT a walked trajectory. 130955 is SINGLE-VANTAGE.
- **capture_autopsy's flat / VANTAGE read on 130955 was CORRECT — UN-DEMOTE it.** The
  earlier "false VANTAGE / demote it" notes (§3, §8) are themselves wrong; the odom
  really is flat. Trust capture_autopsy's coverage read on the RAW odom.
- **The extrinsic CANNOT be certified on 130955** (no parallax, frozen poses). A
  frame-0 overlay lands the shell roughly on the real room (no gross 85°/28 m error) =
  a WEAK POSITIVE that calibration isn't badly broken — NOT a certification.
- **Likely cause:** the recorded stretches were a stationary mantel dwell; the actual
  loop fell inside the 127 s odom hole (unrecorded). Alternative: a Point-LIO odom
  freeze. The clean re-shoot distinguishes them.
- **NEW RATIFIED GATE:** before trusting ANY capture, require `/aft_mapped_to_init`
  POSITIONS to span real metres (capture_autopsy coverage on the raw odom). A
  clean-looking map can sit on a frozen, single-vantage odom.
- **The delivered TOOLS are sound** (validated end-to-end on real bundle + synthetic
  bag); the defect is the INPUT capture. Caught BEFORE baking a texture on frozen poses.
═══════════════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════════════
## 🖼️ VISUAL PROOF (2026-09-23) — THE FROZEN-ODOM COST, ON CAMERA  [PROVEN]
##    THREE ROOMS WALKED · ONE ROOM (BARELY) MAPPED · ZERO POSES IN THE HOLE
═══════════════════════════════════════════════════════════════════════════
Direct confirmation of the ⚠️ CORRECTION, from the operator's own capture. Because a
geometry render "a minute in" is impossible (t≈60 s falls inside the 127 s odom hole —
no pose exists to project a photo onto the shell), we instead pulled the RAW camera
frames from across the hole (t ≈ 30 / 60 / 90 / 120 s) straight from the bag. The
CAMERA recorded them cleanly; the ODOM did not.

**What the four hole-frames show:**
- **t≈30 s** — the gallery-wall living room (red lamp, dark tufted sofa, framed-art
  grid; the dining room + brass chandelier through the arch on the left).
- **t≈60 s** — turned, looking THROUGH the plaster archway into a DIFFERENT room deeper
  in the house (Tiffany-style floor lamp, backlit French glass doors, green walls, a
  desk/study).
- **t≈90 s & t≈120 s** — the fireplace/mantel room (big gilt mirror over the white
  mantel, portraits, striped armchair) with real DAYLIGHT through the curtained windows
  — i.e. exactly the day→night relight material the mission is built for.

**THE POINT:** at least THREE distinct rooms were captured on camera during the exact
window where the map is blank. Every one of these frames sits inside the odom hole, so
NOT ONE has a pose, so NOT ONE became geometry. This is "walked three rooms, mapped
one," frame by frame — the concrete cost of the frozen/dropped odom.

**SHARPENS THE DIAGNOSIS:** the loss is NOT random. The surviving stretches (start +
end) are where the operator stood near-still at the mantel; the eaten stretch is the
MOTION. Recording backpressure devours exactly the moving frames — the most valuable
ones — which is the signature of the raw-image firehose, and precisely what the
compressed-capture fix removes. The camera, exposure, and framing are all GOOD; only
the recording path failed.

**BANKED CONCLUSION:** the instrument works and the calibration reads plausible; the
capture was thin because a frozen/dropped odom threw away the walk. Fix odom + record
compressed (see the ⭐ header) and these three rooms come back as posed, textured,
walkable geometry.


═══════════════════════════════════════════════════════════════════════════
## 0. WHAT THIS SESSION SETTLED (the one-paragraph version)
═══════════════════════════════════════════════════════════════════════════
The geometry was never the problem — **Poisson was.** Proven on real data twice. The
rig lays down 11 mm-clean, square walls every capture; the mesher was melting them.
The real remaining variable is **coverage**: not one of 26 captures ever traversed
enough of its space, so every result was clean-but-fragmented ("floating panels").
The architecture is now settled — **LiDAR sets dimensions, photos carry the
graphics**, forked per-deliverable on the relight gate.
*(9-23 addendum, CORRECTED: coverage is NOT solved — 130955 looked room-scale but its
odom is frozen/single-vantage (see ⚠️ CORRECTION + 🖼️ VISUAL PROOF). Coverage + a
working, MOVING odom remain the open capture variables; the recording method is the top
blocker.)*

═══════════════════════════════════════════════════════════════════════════
## 1. GEOMETRY IS SOLVED — PROVEN TWICE  [PROVEN]
═══════════════════════════════════════════════════════════════════════════
- `planar_shell.py` (new tool, RANSAC plane-fit + coherence report) run on the two
  best captures:
  - **163005:** planes 8–11 mm thick, walls square (2.8° max dev). GREEN.
  - **180551:** planes 10–11 mm thick, walls square (5.9°). GREEN.
  - *(9-23: **130955** — 8.1–11.7 mm, 3.4° square, 59.5% planar. GREEN thickness — but
    a clean SINGLE-VANTAGE scan, NOT proof of coverage; see ⚠️ CORRECTION.)*
- Poisson CONVICTED on the same class of cloud: invents surface up to **1556 mm** from
  any measured point (the melt). Ball-pivoting honest (0 mm) but holey.
- CONCLUSION: the rig's geometry is dimensionally true (11 mm, tighter than the
  16 mm sensor spec) and drift-free when tracking holds. Every blob ever seen was the
  mesher destroying clean data. **The geometry question is closed.**
- CONTRADICTION TO FIX [OPEN]: the shipped `fuse_to_fbx.py` still runs Poisson depth 9.
  RETIRED in the new bake path: `pointlio_to_texture.py` v3 textures `planar_shell`'s
  shell.obj directly via `--shell` (no Poisson) — validated cold.

═══════════════════════════════════════════════════════════════════════════
## 2. THE ARCHITECTURE — LiDAR = DIMENSIONS, PHOTOS = GRAPHICS  (ADR-001)  [RATIFIED]
═══════════════════════════════════════════════════════════════════════════
- The 180° inversion is now the organizing principle: **LiDAR sets scale /
  registration / the collision shell; photos carry all appearance.** The appearance
  half was already ratified 9-16 ("texture from photos, not the colored cloud"); the
  dimensions half is `planar_shell`.
- The Poisson→Gaussian question is the SAME move as the inversion, and it is a
  **per-deliverable fork decided AT CAPTURE, not at meshing**, gated on one question:
  does this deliverable need Lumen day→night relight?
  - YES → delit UV-textured mesh + PBR (the mission default). A splat can only be an
    intermediate you convert + delight.
  - NO → Gaussian splat is the deliverable, LiDAR anchors scale.
- The relight requirement does NOT dissolve the splat's baked-light problem; that's
  why mesh stays the default until commercial relightable-GS + Lumen matures.
- New hinge the inversion requires (unbuilt): **photometric pose refinement (SfM/BA)**
  seeded by the LiDAR poses+points (`poses_to_colmap.py` already emits the seed).
- Full detail: the ADR-001 + ADR-002 blocks at the TOP of this file, plus
  `SYSTEM_DESIGN_pipeline_v2.md`, `PIPELINE_AUDIT_fork_and_inversion_2026-09-22.md`.

═══════════════════════════════════════════════════════════════════════════
## 3. THE CAPTURE-METHOD AUTOPSY — 26 captures, `capture_autopsy.py`  [PROVEN]
═══════════════════════════════════════════════════════════════════════════
Ran the whole `/mnt/rigdata` pile through a new tool that reports tracking %, mid-run
gaps, and trajectory span (dX/dY/dZ). The pattern:
- **Tracking failure is an INIT problem, not duration or a code bug.** 10 of 26
  collapsed, almost all in the first **1–5 s**. FIX = init discipline (below).
- **Mid-run gaps** (6 CAUTION captures, one with a 482 s gap) = static dwelling /
  featureless aim / too-fast motion DURING the run.
- **Drift-explosion (4th failure mode):** some captures tracked 100% with no gaps yet
  positions diverged to hundreds/thousands of metres. (coverage tag needs a sanity cap.)
- **Recording hygiene:** several bags recorded 0 clouds or 0 images — verify Hz BEFORE
  recording.
- *(9-23 CORRECTED: an earlier note here called capture_autopsy's flat read on 130955 a
  "false VANTAGE" and said to demote it. That was WRONG — 130955's odom really is flat
  (see ⚠️ CORRECTION). capture_autopsy's coverage read on the raw odom is TRUSTWORTHY
  and is now a ratified pre-processing gate.)*

═══════════════════════════════════════════════════════════════════════════
## 4. COVERAGE — STILL OPEN (the earlier "SOLVED" was retracted)  [diagnosis]
═══════════════════════════════════════════════════════════════════════════
*(9-23 CORRECTED: coverage is NOT solved. 130955 was single-vantage (frozen odom), not
a walked room — see ⚠️ CORRECTION + 🖼️ VISUAL PROOF. §4 below stands as the diagnosis of
the coverage problem; the fix — a real traverse WITH a moving odom, gated — is not yet
demonstrated.)*
- Tracking (§3) is fixable by discipline. Geometry quality (§1) is solved. What's
  left is COVERAGE, and **not one of 26 captures ever traversed enough.** Best was
  180551 at ~2 m lateral in an ~18×16 m space. 163005 was 1.4 m. That's why every
  shell came out as clean-but-disconnected floating panels.
- **THE RATIFIED CAPTURE RULE — traverse scales to the space.** Coverage must be a real
  perimeter traverse, metres proportional to the room, and the ODOM MUST RECORD IT
  (verify positions actually move — the 130955 lesson).
- Good tracking ≠ good coverage ≠ moving odom: all three are measured separately
  (capture_autopsy tracking + coverage span; planar_shell geometry health).

═══════════════════════════════════════════════════════════════════════════
## 5. THE CAPTURE METHOD, EVIDENCE-BASED (layers ON the stone CAPTURE_METHOD doc)
═══════════════════════════════════════════════════════════════════════════
The stone `CAPTURE_METHOD` doc owns the mechanics (Start Rig Lean → Point-LIO
Capture → dead-still init → one Ctrl-C). This session ADDS:
- **Init discipline:** hold dead still until you SEE "IMU Initializing: 100.0 %",
  THEN move. This one step sank 10 of 26.
- **Traverse the full perimeter** (§4) — a real loop, not a shuffle — AND CONFIRM THE
  ODOM RECORDED THE MOTION (positions span real metres; 130955 froze).
- **Keep translating; never dwell static** (kills the mid-run gaps).
- **Dwell plan for the formal living room:** the fireplace + mantel ensemble is the
  hero surface → slow down + one close local orbit. Do NOT dwell the mirror (specular)
  or the glass (holes).
- **⛔ RECORD COMPRESSED IMAGES (9-23, non-negotiable):** the capture MUST record
  `/image_raw/compressed`, not raw `/image_raw`. Use `rig_camera_compressed.py` at
  bringup (publishes the native JPEG) + `capture_pointlio_texture.sh` (auto-selects the
  compressed topic).

═══════════════════════════════════════════════════════════════════════════
## 6. THE LIGHT RULE — REVISED (operator correction, ratified)  [RATIFIED]
═══════════════════════════════════════════════════════════════════════════
"Flat overcast" is a lab condition, not a film set. Superseded:
- **Geometry is light-invariant** — shoot the LiDAR in any light (glass still excepted).
- **Texture wants bracketed / HDR**; capture the light as a KNOWN quantity (grey/chrome
  ball, or logged sun angle) so it can be modeled and subtracted.
- **Hard cast shadows won't fully delight** (Agisoft's wall) → manual PBR cleanup normal.
- **The delight bar is "your inserted lights read true," not perfect albedo.**

═══════════════════════════════════════════════════════════════════════════
## 7. THE USE CASE — CLARIFIED (the barn, one of two uses)  [operator-stated]
═══════════════════════════════════════════════════════════════════════════
- EXTERIOR (becomes night): rig in daylight → sky day→night in Unreal → crane/light via
  Set.A.Light → light the interior so the windows glow. Coverage = **270° arc** (outside-in).
- INTERIOR (relit): capture in daylight → remove door light → add lanterns → pull back
  so the windows read. Coverage = **360°** (inside-out).
- Two capture geometries: exterior orbits AROUND the structure; interior orbits WITHIN.

═══════════════════════════════════════════════════════════════════════════
## 8. NEW TOOLS BUILT THIS SESSION
═══════════════════════════════════════════════════════════════════════════
- **`planar_shell.py`** — RANSAC room-shell reconstructor + coherence report. The
  dimensions-branch tool.
- **`capture_autopsy.py`** — post-mortem across many bags: tracking %, mid-run gaps,
  dX/dY/dZ coverage. TODO: drift-explosion sanity cap. *(9-23: its odom-position
  coverage read is TRUSTWORTHY — the earlier "demote" note is retracted; see CORRECTION.)*
- **`pointlio_pose_matcher.py` v2** — the proven pose matcher + a fail-closed COVERAGE
  GATE (match% / span / max-hole). Validated on a synthetic ROS2 bag (index alignment
  exact) and on real 130955 (correctly FAILS at 42%).
- **`pointlio_to_texture.py` v3** — Piece 3 baker: `--shell` textures planar_shell's
  clean geometry (Poisson RETIRED), `--occlusion` uses objects.ply as occluders. 6/6
  selftests + real-bundle run.
- **`rig_camera_compressed.py`** — publishes the camera's native JPEG as CompressedImage
  (the capture-side fix). Needs live rig verification.
- **`make_extrinsic_bundle.py`** — packages a small keyframe bundle for off-rig checks.
- **`matcher_audit.py`** — the sandbox-first audit template.

═══════════════════════════════════════════════════════════════════════════
## 9. NEW SCAR — JETSON MEMORY / NVMM STARVATION  [PROVEN]
═══════════════════════════════════════════════════════════════════════════
Camera failed with `NvMapMemAllocInternalTagged error 12` (ENOMEM) — the NVJPG decoder
couldn't allocate ring buffers because **Firefox held ~3 GB (198 MB free).** FIX:
`pkill firefox` → 5.3 GB free. **RULE: close heavy apps before capture; verify camera
Hz from the terminal before trusting the "ALL SYSTEMS STARTED" banner.** (9-23: the
native-JPEG capture node avoids the NVJPG decoder entirely, so this scar can't recur.)

═══════════════════════════════════════════════════════════════════════════
## 10. THE VERIFICATION GATES (rigor is a constant)
═══════════════════════════════════════════════════════════════════════════
Before processing any capture:
1. `capture_autopsy` on the bag: tracking in the GOOD band, no big gaps, AND
   **positions span real metres** (odom actually MOVED — the 130955 lesson; trust this
   read).
2. `planar_shell` coherence: plane thickness ≤ 30 mm, walls < 6°.
3. **Pose-matcher coverage gate: match% ≥ 90, no in-run hole > 2 s. A raw-recorded or
   frozen-odom bag FAILS here — the gate before a wasted bake.**
4. Eye check on the shell render.
Fail any → the tool names the knob (light, init, traverse, recording, moving-odom).

═══════════════════════════════════════════════════════════════════════════
## 11. DOCS PRODUCED THIS SESSION (in the project)
═══════════════════════════════════════════════════════════════════════════
- `PIPELINE_AUDIT_fork_and_inversion_2026-09-22.md`, `ADR-001_representation_fork.md`,
  `ADR-002_texture_pipeline_reliability.md` (the texture-pipeline fixes + audit),
  `SYSTEM_DESIGN_pipeline_v2.md`, `PERFECT_ROOM_CAPTURE_v2.md`,
  `PROJECT_EXECUTION_CHECKLIST.md`, and the **Rig Run Sheet** (live artifact).

═══════════════════════════════════════════════════════════════════════════
## 12. WHERE WE LEFT OFF — NEXT STEP
═══════════════════════════════════════════════════════════════════════════
- 130955 is EXHAUSTED as a data source: single-vantage, frozen odom → not a geometry
  keeper for coverage, and un-textureable. Do not process it further. (The 🖼️ VISUAL
  PROOF block banks WHY: three rooms on camera, none posed.)
- All OFF-RIG work is done + validated: matcher gate, planar_shell bake, occlusion,
  compressed-camera node, bundle-maker.
- **NEXT = the rig session (compressed re-shoot):** (1) stand up `rig_camera_compressed.py`
  at bringup and verify nothing else needs raw `/image_raw`; (2) 20 s stationary
  coexistence test → bag small + odom present; (3) real WALKED traverse; (4) gate:
  capture_autopsy (positions MOVE) → matcher (≥90%) → planar_shell — before any bake;
  (5) then the shell+occlusion bake, and the extrinsic finally gets its real test.
- Standing status: geometry solved · architecture ratified · tools built + validated ·
  coverage + moving-odom UNPROVEN · extrinsic code-verified, real-world UNCERTIFIED.

═══════════════════════════════════════════════════════════════════════════
## 13. SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- 2026-09-22: Proved geometry sound (planar_shell, 11 mm/square on 163005 & 180551) —
  Poisson convicted. capture_autopsy on 26 bags: tracking failure is an INIT problem;
  coverage the open variable. Ratified the architecture (ADR-001) + traverse rule;
  revised the light rule. New scar: Jetson NVMM starvation from Firefox.
- 2026-09-23: Found the BLOCKING DEFECT (raw-image recording drops odom; ⛔ banner).
  Built + validated the texture-pipeline fixes: matcher coverage gate, planar_shell
  bake (Poisson retired), occlusion, native-JPEG capture node — all sandbox/real-bag
  proven. Extrinsic code-path verified (applied once, exact); real-world uncertified.
- 2026-09-23 (late) — **CORRECTION:** ran the real 130955 bundle through the tools and
  found its odom is FROZEN / single-vantage (poses ≈ origin, 1–2° spread). RETRACTED the
  earlier "coverage solved / room-scale walk" call; UN-DEMOTED capture_autopsy (its flat
  read was right). Added the ratified gate: an odom must be shown to MOVE (real metres)
  before a capture is trusted.
- 2026-09-23 (late) — **VISUAL PROOF:** pulled the raw camera frames from across the
  127 s odom hole (t≈30/60/90/120 s). They show THREE distinct rooms captured on
  camera while the map was blank — confirming "walked three rooms, mapped one" and that
  the loss falls on the MOVING frames (recording backpressure). Tools sound; 130955
  exhausted. Next = compressed re-shoot on the rig (see the ⭐ NEXT STEP header).
<!-- ##  BELOW THIS LINE = MASTER 20.13.66 (2026-09-21) AND ALL EARLIER LINEAGE,  ## -->
<!-- ##  PRESERVED VERBATIM FROM github.com/BaxterBstupid/rig-files.              ## -->
<!-- ##  The "ACTIVE STATE (Master 20.13.66)" block just below is HISTORICAL —    ## -->
<!-- ##  the current active state is the 20.13.67 block at the TOP of this file.  ## -->
<!-- ############################################################################## -->


<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST - ACTIVE STATE (Master 20.13.66, 2026-09-21) ***** -->
<!-- *** REACHED UNREAL. Both meshes exported from RS; lidar_mesh IMPORTED into UE5 (Nanite -->
<!-- *** built). Then the VIEWPORT got lost (camera flew off to blank sky) - mesh is NOT gone, -->
<!-- *** just off-camera. Stopped here end-of-day. Pick up: recover view, then continue. -->
<!-- -->
<!-- WHERE WE ARE - a UE5 project exists: 'MyProject' (or rig_walkable), Third Person template, -->
<!--   level Lvl_ThirdPerson, on Shadow. Content Browser has lidar_mesh imported as a Static Mesh -->
<!--   (Nanite ON). lidar_mesh is placed in the level (Outliner shows it) at Location -720,-360,0, -->
<!--   Scale 1,1,1 (the x100 import scale baked into geometry - correct). photo_mesh.fbx is NOT -->
<!--   yet imported (still on disk in shadow_bundle). -->
<!-- -->
<!-- THE VIEWPORT PROBLEM (to fix first next session, EASY with fresh eyes): -->
<!--   Pressing F to frame the mesh flew the camera to blank BLUE SKY - mesh out of view. Mesh is -->
<!--   fine, camera is just aimed at nothing. RECOVERY OPTIONS: (a) in Outliner click lidar_mesh -->
<!--   to select, hover the VIEWPORT, press F to reframe; (b) hold RIGHT-mouse in viewport + WASD -->
<!--   to fly, S to back out until scene appears; (c) select 'Floor' (template) in Outliner + F to -->
<!--   snap back to known geometry. NOTE: photogrammetry/LiDAR meshes are often SINGLE-SIDED, so -->
<!--   from INSIDE a room the walls render invisible (backface culling) - F often puts camera -->
<!--   inside the mesh = looks blank. If so, make the material TWO-SIDED, or view from outside. -->
<!-- -->
<!-- UE5 IMPORT SETTINGS THAT WORKED (Interchange dialog - banked for photo_mesh + re-imports): -->
<!--   Import Content dialog -> Offset Uniform Scale = 100 (Common section, meters->cm). -->
<!--   Static Meshes tab > Build section: Build Nanite = ON (checked), Generate Lightmap UVs = OFF. -->
<!--   'Use the same settings for subsequent files' = ON -> photo_mesh will import with same. -->
<!--   Import -> Nanite builds (3.9M tris took ~a minute). Drag asset from Content Browser into -->
<!--   viewport to place; Details panel via Window>Details (select the actor to populate it). -->
<!-- -->
<!-- >>> NEXT SESSION (UE5, research artifact 'RealityScan 2.1.1 to UE5 Walkable' has full steps): -->
<!--   1. RECOVER THE VIEW (above). Confirm lidar_mesh is visible + a recognizable room + sane -->
<!--      scale (compare to template floor). Check if single-sided (make material two-sided if so). -->
<!--   2. IMPORT photo_mesh.fbx (same settings - scale 100, Nanite ON, Lightmap OFF, +materials/ -->
<!--      textures for its color). Drag into level at SAME origin as lidar_mesh -> they AUTO-ALIGN -->
<!--      (co-registered, same frame). This is the 'combine in Unreal' payoff. -->
<!--   3. COLLISION on each: Static Mesh Editor > Collision Complexity = 'Use Complex Collision -->
<!--      As Simple'. Save. -->
<!--   4. WALK IT: Player Start above the floor; the template already has char+GameMode+lights. -->
<!--      Play (Alt+P), WASD. If falling through holey floor -> add invisible floor plane (Cube -->
<!--      scaled wide+thin) just under Z=0. -->
<!--   5. If it walks -> STAGE 3 (and 4-7) effectively DONE = first WALKABLE environment. -->
<!--      PASS LINE: 'ACTIVE PASS - STAGE 3 - mint Master 20.13.67' (goal reached, rough tier). <<< -->
<!-- -->
<!-- HONEST STATUS: this is the CLOSEST we've ever been to the goal - geometry is IN Unreal. The -->
<!--   week's whole merge fight was sidestepped by the operator's 'combine in Unreal' insight -->
<!--   (export both co-registered meshes, let UE5 be where they meet). Just need to: recover view, -->
<!--   add photo_mesh, collision, walk. FILES: shadow_bundle\photo_mesh.fbx (14.9MB, textured, -->
<!--   425K), shadow_bundle\lidar_mesh.fbx (107MB, 3.9M, complete room). make_gcp.py + the GCP -->
<!--   CSVs also there (the co-registration method, PROVEN, reusable for future captures). -->
<!-- ============================================================================ -->


# ============================================================
# REALITYSCAN PROCEDURE — REPEATABLE RECIPE (per new capture)
# ============================================================
# HOW TO READ THIS: [PROVEN] = verified working, follow exactly. [EXPLORING] =
# best current approach, not yet passed — expect it to change. Each stage we PASS,
# its steps get promoted to [PROVEN] with the exact settings that worked.
# Goal: a clear WALKABLE 3D environment in UE5. This recipe is the "do it again" list
# so future captures are a REPEAT, not a re-exploration.
#
# ------------------------------------------------------------
# STAGE 1 — SETUP & INGEST                                    [PROVEN — Master 20.13.59]
# ------------------------------------------------------------
#  1. RealityScan 2.1.1.119 open.
#  2. RS logo -> New (Don't Save any prior project).
#  3. NO units step needed — RS is metric by default (local:1 Euclidean). Scale is
#     handled at EXPORT (Stage 7, 100x m->cm). Skip coordinate-system settings.
#  4. Ensure each img_XXXXX.xmp sits beside img_XXXXX.png (same folder, same stem) —
#     they auto-bind on import. (Our frames_163005_key already satisfies this.)
#  5. WORKFLOW tab -> [1] Inputs -> Folder -> select the frames folder -> Open.
#  6. VERIFY (the real gate): click one image -> Selected Input panel -> expand
#     "Prior pose" (Absolute pose = LOCKED, real x/y/z + Omega/Phi/Kappa) and
#     "Prior calibration" (Prior=Fixed, Focal(35mm)=15.914228, aspect=1.000556).
#  PASS = 422 imgs in list + Prior pose LOCKED + focal 15.9mm + metric. Mint Master.
#
# ------------------------------------------------------------
# STAGE 2 — ALIGN PHOTOS                                      [PROVEN — Master 20.13.60]
# ------------------------------------------------------------
#  1. NO settings tuning needed — the locked XMP priors carry alignment. (Optional:
#     ALIGNMENT settings Feature detection=High, Max features/mpx~20000, Use camera
#     priors ON — but defaults worked.)
#  2. Click Align Images (F6). Wait (several min for 422 imgs).
#  3. VERIFY in 1Ds: ONE component (named "Component 0"; RS numbers from 0; "0 models"
#     = no mesh yet, correct). 422/422 cams. ~2800 tie-points/image (healthy).
#  4. VERIFY in 3Ds: sparse cloud STRUCTURED (camera cluster + walk-path trajectory);
#     camera cones point INWARD (orientation correct — NOT the 2.1.1 XMP-flip bug).
#     [The 2800 tie-pts also prove orientation: wrong orientation = ~0 tie-pts.]
#  PASS = 1 component, >=90% (we got 100%) cams, structured cloud, cones inward. Mint.
#  GOTCHA: if a stray extra 2D/panel clutters the view -> click its small x, or
#     WORKFLOW>Layout to reset. If duplicate components appear from re-aligning,
#     start FRESH (New -> re-import -> F6) — Stages 1-2 are ~10 min and proven.
#
# ------------------------------------------------------------
# STAGE 3 — LiDAR-AS-FRAMEWORK COMPOSITE (control-point merge)  [EXPLORING]
# ------------------------------------------------------------
#  See the ACTIVE-STATE block at the very top of this file for the FULL verified
#  step-by-step (0 backup -> 1 import Intensity -> 2 verify Comp0 survived -> 3 lock photo
#  poses -> 4 delete dup components -> 5 control points on photos+.lsp -> 6 F6 merge ->
#  7 escalation). KEY PROVEN FACTS:
#   - Features source = INTENSITY on LiDAR import (Color = 'no known color channels').
#   - Bare F6 does NOT auto-merge photos+LiDAR (intensity .lsp don't match photos) -> CONTROL
#     POINTS REQUIRED (>=4, 6 rec, non-collinear, each on >=2 photos AND >=2 .lsp, turn BLUE).
#   - 'Lock pose for continue' only shows when REGISTERED photos are selected (Component 0 ->
#     Camera poses -> select photos). Not on component node / LiDAR / mixed selection.
#   - Tie-pt display ~2800->~100 after LiDAR import = CONTEXT ARTIFACT, not damage (we didn't
#     F6). Verify via SCENE 3D>VIEW>Source=Component 0.
#   - 'Merge Components' button = imported .rsalign only; use F6. 'Update' does NOT merge.
#   FALLBACK: LiDAR for SCALE only via Define Distance (F4), mesh photos-only.
#
# ------------------------------------------------------------
# STAGE 4 — MESH                                              [EXPLORING]
# ------------------------------------------------------------
#  - MESH & COLOR -> Reconstruction Settings: raise Default grouping factor (prioritize
#    LiDAR, one step at a time); Adaptive blending start = 0.45 (default); Minimal
#    distance between two vertices ~0.005-0.01m; raise Default noise factor if bumpy.
#  - Set Reconstruction Region (Ctrl+Shift+U) to the room.
#  - Calculate Model -> Normal Detail.
#  - Clean Model + Close Holes; lasso+Filter selection to delete floating islands.
#  PASS = single connected mesh, continuous floor, solid walls, no junk.
#
# ------------------------------------------------------------
# STAGE 5 — TEXTURE                                           [EXPLORING]
# ------------------------------------------------------------
#  - MESH & COLOR -> Unwrap (Geometric or Mosaicing); texel ~0.005; max res 8192;
#    Defragment charts = Yes; Gutter 2 (raise to 8 if seams).
#  - Texture (F9), Correct colors = Yes. (Texture, NOT Colorize.)
#  - If mesh simplified -> Reproject Texture from high-detail model (Trilinear+Supersample).
#  PASS = textured (not colorized), no black seams, surfaces readable.
#
# ------------------------------------------------------------
# STAGE 6 — EXPORT                                            [EXPLORING]
# ------------------------------------------------------------
#  - MESH & COLOR -> Export -> Model -> FBX. Filename NO SPACES / no Unicode.
#  - Scale = 100 (m->cm) OR plan Import Uniform Scale 100 in UE. Export texture ON;
#    keep .rsInfo; export normals.
#  PASS = FBX + textures written, no-space name, scale set.
#
# ------------------------------------------------------------
# STAGE 7 — UNREAL WALKABLE                                   [EXPLORING]
# ------------------------------------------------------------
#  - UE5 (First/Third Person template). Drag FBX in: Build Nanite ON; Generate Lightmap
#    UVs OFF; Import Uniform Scale 100 (if not pre-scaled); Compute Normals if black.
#  - Static Mesh Editor -> Collision Complexity = Use Complex Collision As Simple.
#  - Drag into level; floor ~Z=0; Player Start above floor; add light/Sky. Play.
#  PASS = character stands on floor, blocked by walls (or spectator flies). GOAL MET.
# ============================================================

<!-- Last touched 2026-09-16 SESSION-2b (Master 20.13.54): *** CONFLICT CHECK: our proven capture ARCHITECTURE vs what RealityScan 2.x + Unreal 5.8 ACTUALLY want (researched before committing captures to the wrong export). VERDICT: architecture ALIGNS in principle (RealityScan 2.1, Nov 2025, explicitly added handheld-SLAM support = images + trajectory/COLMAP + point cloud + generate virtual cameras from pose priors), BUT WE ARE EXPORTING THE WRONG ARTIFACT. *** THE CORE CONFLICT (highest-leverage fix): STOP feeding RealityScan the colored 5cm-voxel-accumulated .ply. RealityScan does NOT mesh from our colored points - it renders VIRTUAL CAMERAS from the cloud and does photogrammetry feature-matching on those renders (LSP files "look like photographs" only if the cloud is DENSE). Our voxel map is temporally dense but SPATIALLY quantized to 5cm and was only 2.7% colored -> sparse feature-poor renders -> "aligns a component but too sparse to build a model" (exactly what we saw). *** WHAT TO FEED INSTEAD (Path a, the documented best-practice "LiDAR for geometry, photogrammetry for TEXTURES"): (1) the undistorted CAMERA IMAGES (keyframe-decimated for good overlap, NOT all 26fps), (2) the Point-LIO POSES as a COLMAP-format export (cameras/images/points3D; RS 2.1 imports COLMAP + references original distorted images; Registration=Exact, Georeferenced=Local), (3) the RAW UN-VOXELIZED LiDAR cloud as PLY/LAS/E57 (LiDAR scan). Then RS meshes from LiDAR geometry + TEXTURES FROM THE IMAGES at full 1920x1200 res. *** KEY INSIGHTS: (A) PRE-COLORIZING THE CLOUD IS REDUNDANT / COUNTERPRODUCTIVE for the RS deliverable path - RS re-projects the ORIGINAL images onto the mesh itself at full res; per-point color only used when NO images present. Our colorize + accumulate is the RIGHT tool for LIVE COVERAGE QA (map_accumulator + mesh_check red->green), the WRONG tool as the RS hand-off. (B) 5cm VOXELIZATION destroys the sub-cm texture detail RS tie-points + texture baking need (RS texel targets ~mm; 16K-64K atlases). Feed raw points, not the voxel map. (C) PER-VERTEX "Colorize" (F-colorize) looks poor in Unreal + is capped by vertex density; must run "Texture" (F9) sourced from IMAGES to get a real UV ATLAS = what Unreal 5.8 Nanite+PBR wants. (D) Gaussian splats in UE5.8 = 3rd-party-plugin-only + NOT relightable -> for a RELIGHTABLE walkable env the UV-textured NANITE MESH is the target, not splats. (E) RELIGHTING: RS bakes LIT color (albedo+baked light) into the texture; true relighting needs DE-LIGHTING + authoring roughness/normal/metallic in UE, or accept baked lighting. *** TAU re the deliverable: matters MOST for the colorized-cloud path (~180ms during motion smears per-point color -> ghosting/blur, the OmniColor-documented failure) = critical to close there. Matters LESS for images+poses path (RS textures from discrete images at their own timestamps + refines poses in bundle-adjust) but still places each image's pose on the trajectory (180ms x pan-speed misplaces the camera). NEGLIGIBLE for static/slow capture (effect scales with velocity). So: close tau_solve before colorize-dependent captures; capture texture-critical areas SLOWLY if tau not yet closed. A CONSTANT-VELOCITY pan is what tau_solve needs AND feeds coverage = double duty. *** DENSIFY RESOLVED (from reading colorized_fusion_node.py): there is NO per-frame densifier. The node colorizes SPARSE points per frame (YAML-cal w/ stale-K guard cx>=960 refused; ApproximateTimeSynchronizer 0.04s slop; output stamped w/ matched-pair time for honest tau). Line 156: "the accumulated map still fills in with colour. Fewer points per frame." => DENSITY IS TEMPORAL (accumulate many sparse frames via map_accumulator), NOT spatial (no per-frame depth-fill). densify_quad.png's dense look = accumulation, not a densifier. *** RE-PLUMB PLAN (ratified, do before texture-quality captures): Stage1 add an export path = undistorted images + COLMAP(poses+intrinsics) + raw cloud (KEEP voxel map/mesh_check as LIVE QA only). Stage2 RS: import images+trajectory (or COLMAP scene) + LiDAR scan (Exact/Local) -> generate virtual cams from priors -> Align -> mesh from LiDAR -> Texture(F9) FROM IMAGES -> confirm UV atlas not vertex color. Stage3 close tau (target within ~1 frame ~40ms for images+poses path). Stage4 UE5.8: FBX+atlas -> enable Nanite -> PBR master material (Virtual Textures on for 4K+) -> de-light for relighting. THRESHOLDS: if RS still can't build from images+poses+dense cloud -> bottleneck is image overlap/density not format (slow down, more keyframes); if a colored-cloud PRODUCT is mandatory -> tau becomes mandatory + consider splat deliverable (loses relight); if relighting NOT needed -> a splat may beat the mesh. *** NET: our capture architecture SERVES live-QA perfectly and is right in principle for RS; the ONE change is the EXPORT - hand RS images+poses+raw-cloud (texture from photos), not the colored voxel map. This downgrades tau from critical to secondary and gives Unreal the UV atlas it needs. --- <!-- Last touched 2026-09-16 SESSION-2 (Master 20.13.53): *** CORRECTIONS FROM READING THE PROJECT FILES + JETSON CALIB PIPELINE (operator repeatedly had to point the assistant back to already-solved work; banking so it is not re-litigated). *** GOVERNING ADDITION (P5): BEFORE theorizing that ANYTHING is an "open problem" or writing ANY new script, LOOK AT THE PROJECT IMAGES + READ THE ACTUAL PIPELINE CODE ON THE JETSON. The assistant re-opened THREE already-solved problems this session by not looking first (FOV coverage, hole/coverage-completeness, and "does a colorize exist"). Reinvent-worse-instead-of-read-what-exists is THE recurring failure; the fix is always to read first. *** WHAT THE IMAGES PROVE (already solved, do NOT treat as open): (1) PER-FRAME CAMERA-LiDAR FUSION IS SOLVED + DENSE. fusion_triptych_f0.png (camera | LiDAR-depth | fused) and densify_quad.png (camera | raw LiDAR pts | DENSIFIED per-pixel depth | fused-full-frame) show the LiDAR fills the FULL camera FOV densely and the fusion colors the WHOLE frame edge-to-edge - NOT a narrow slice. The "camera only sees a tiny slice vs 360 LiDAR" framing the assistant used last session was WRONG. (2) THE HOLE / COVERAGE-COMPLETENESS PROBLEM IS SOLVED by map_accumulator.py + mesh_check.py: map_accumulator.py = bounded voxel accumulator (world-frame points from every pass -> capped hit-counted voxel map, runs BESIDE a live capture, hard memory cap 2M voxels); mesh_check.py = marching-cubes on that voxel occupancy, "holes cannot be ballooned over" (unscanned = no surface), and colour-codes coverage RED=thin(walk here again)->yellow->GREEN=well-seen. So holes are VISIBLE + FILLABLE-by-walking-there, not hoped-over. (check_capture.py's note "hole problem needs registration, add later" is OUTDATED - the accumulator IS that layer.) *** THE JETSON CALIBRATION PIPELINE (01-05, the source of the extrinsic + the calib-time colorize): 01_capture_multipose.py (sync LiDAR+cam board capture, +/-100ms, varied tilts, saves cloud.npy/image.png/metadata per pose) -> 02_extract_holes.py (4 hole-centers/pose; solves checkerboard-origin offset) -> 03_set_anchor.py (user sets hole correspondence ONCE; solves the symmetric-rectangle 180-flip ambiguity that fits with ZERO residual on a planar pose - non-coplanar poses then verify) -> 04_solve_extrinsic.py (Kabsch via extrinsic_solver.py + validation gates) -> 05_integrate_and_verify.py (saves extrinsic YAML + makes colorized_pose_0.ply for visual verify + reprojection error). *** KEY HONEST FINDING re COLORIZE: 05_integrate_and_verify.py's colorize_lidar_cloud() is the SAME naive single-frame per-point projection as the assistant's colorize_simple.py (T_cam_lidar@pts, project K, grab pixel, grey out-of-FOV, prints "N/M in camera FOV"). It is CALIBRATION-TIME VERIFY (one pose, "does color land = is extrinsic right"), and has the SAME per-frame FOV behavior. So colorize_simple.py did NOT reinvent something better that existed - it matched the calib-verify colorize. *** THE STILL-OPEN QUESTION (do NOT assume, must confirm from Jetson): densify_quad.png shows a DENSIFIED full-frame depth that is MORE than the naive step-05 colorize. Either (a) there is a separate DENSIFY / full-frame fusion tool (not yet located - hunt: grep densif/maximum_filter/inpaint/griddata/depth-map in ~/*.py) that the pan should feed, OR (b) densify_quad was a one-off experiment and density must come from ACCUMULATING many frames (map_accumulator), not per-frame densification. RESOLVE by reading Jetson code before building. *** RS LESSON re "the last image" (operator correction): the blurry _color.lsp RS showed was NOT a photo - it was RS's VIRTUAL CAMERA reprojecting our 3D colored cloud back into 2D from a synthetic viewpoint. So its thinness reflected CLOUD density/completeness, not source photos. RS aligns on reprojections OF THE CLOUD -> the lever for more tie-points is a DENSER, MORE-COMPLETE colored CLOUD (densify + accumulate all frames), not better photos. Static burst gave 2.7% colored -> thin reprojections -> 29 tie-points -> "0 models". Format PROVEN (colored ply -> color renders -> aligns); coverage is the gap. *** OTHER JETSON TOOLING SEEN (mature, use don't reinvent): check_capture.py (3-state capture-health gate: GOOD>75%/CAUTION 40-75%/RESHOOT<40% tracking; better than the assistant's capture_check.py), rig_monitor1.py (live FLOW/CARD/HEAT heartbeat during capture), synth_capture.py (synthetic fusioncap twin w/ known TRUE_TAU=+0.180s, lidar LAGS camera), tau_solve.py (camera-LiDAR clock offset via motion cross-correlation; gates peak<100ms + half-split<30ms; "triple-vetted, result pending"). *** GENUINELY-OPEN FRONTIER (from the files, not FOV/holes): TAU (the camera-LiDAR clock offset) is "result pending" - may be the real open item. And confirming which densify path (a/b above) is wired. *** APPROACH GOING FORWARD (ratified): use the EXISTING Jetson tools (calib 01-05 for extrinsic, map_accumulator+mesh_check for coverage, check_capture as the gate, rig_monitor live) - do NOT rewrite them. Next capture = a 360 pan (operator's call: pure-pan vs pan-with-translation; pure pan = coverage but weak parallax/tracking, pan+move = coverage AND parallax for RS tie-points). Feed it the REAL pipeline once the densify path is confirmed. --- <!-- Last touched 2026-09-16 (Master 20.13.52): *** THE END-TO-END CHAIN IS PROVEN: RIG CAPTURE -> ON-BOARD COLORIZE -> REALITYSCAN COMPONENT. First time the whole path ran clean, and the colored-cloud format UNBLOCKS RealityScan (the intensity dead-end is solved). *** HOT SESSION (operator on Jetson + Shadow, disciplined one-step-at-a-time after banking the "eight rules for incoming data" + the P1-P4 governing principles): ran the proven three-step rig flow and it all worked. (1) RIG CHECK (bash ~/rig_check.sh) caught the daily-sweep AGAIN (6 kiosk files swept off Desktop) -> restored from vault (cp ~/rig_originals/{map_accumulator.py,rig_kiosk_server.py,cloud.html,launch.html,rig_kiosk.html,three.min.js} ~/Desktop/) -> re-check ALL GREEN. (2) Powered L2. (3) RIG PRE-FLIGHT = rig_start_lean.sh -> clean lean start ("Fusion nodes SKIPPED"), LiDAR flowing, camera started. (4) Verified camera live: ros2 topic hz /image_raw = 26.08Hz (the record's rule: lean start declares success over a dead camera, so ALWAYS verify camera Hz before capture). (5) point_lio_capture.sh -> 5-sec STATIC capture (held dead-still), Ctrl-C ONCE -> clean 4-stage stop -> fusioncap_095447 (bag 2.7GiB/16s: /image_raw 410 frames, /unilidar/cloud 192, /aft_mapped_to_init 55591, /cloud_registered 54) + fusioncap_095447_scans.pcd (278,334 pts, attrs [curvature,normals,intensity,positions] via o3d.t reader). *** BUILT + RAN colorize_simple.py ON THE JETSON (the SIMPLEST colorize, held to rule #5 no-cleverness): static rig => color the accumulated PCD with ONE mid-capture camera frame via the calibrated extrinsic ONLY (p_cam = R_L2C @ p_lidar + T_L2C; loads R_lidar_to_cam/t_lidar_to_cam from extrinsic_20260816.yaml + K/DIST from calib_intrinsics_20260813.yaml; undistort via cv2.projectPoints; best pixel per point; unseen=grey; writes _COLORED.ply). *** MEASURED FINDING (was ASSUMED, now FACT): THE JETSON CAN RUN THE COLORIZE - memory stayed comfortable through the run (278k pts x projection). On-board colorize is VIABLE, not just theory. (Colorize is light: projection only, NO Poisson/mesh/atlas - unlike the texture BAKE that hard-locks the Jetson.) *** RESULT: 7,452 of 278,334 pts colored = 2.7%. DIAGNOSED clean-eyed (operator asked "is this a faulty pipeline?" - we ISOLATED before theorizing, per P3): NOT a bug. Points IN FRONT of camera = 30.5%; of those only 8.8% land in-frame; horizontal angle spread of in-front points = -89 to +90deg (a full 180deg hemisphere) while the camera FOV is ~70deg. So 2.7% = correct FOV geometry: ONE forward 70deg frame can only color a thin slice of a 360deg LiDAR cloud. The colored patch is coherent + localized (0.72x2.32x0.76m in front) = projection is CORRECT, landing where the camera looks. *** SAW THE ACTUAL CAMERA IMAGE (rqt_image_view /image_raw): a rich, sharp, well-exposed living room (fireplace mantel, gilt mirror, portraits, lamps, blue-white porcelain, curtained sunlit window) - EXCELLENT camera + a feature-rich scene. BUT aimed UP at a corner: top ~40% of frame is blank ceiling. Confirms by eye WHY 2.7%: half the FOV is featureless ceiling, content is the lower forward slice. Camera is not the problem; AIM + single-frame FOV is. Capture lesson made concrete: aim at CONTENT not ceiling (level/slightly down), MOVE around, vary height/angle. *** THE BREAKTHROUGH (the day's real win): bridged fusioncap_095447_COLORED.ply (7.3MB) Jetson->Shadow via Tailscale (scp fasterbybaxter@100.85.175.10:/mnt/rigdata/...), imported into RealityScan as LiDAR Scan with FEATURES SOURCE = COLOR (not Intensity). RS generated _color.lsp virtual-camera renders (vs the useless _intensity.lsp noise before) and the 2D view SHOWED ACTUAL COLOR. Then ALIGNMENT -> Align Images (F6, FAST - 3 virtual cams not 2200 real images) -> SUCCEEDED: Component 0, "3/3 cams, 0 models", SCENE 3D tab appeared with the component + camera positions. *** WHAT RS TOLD US (do-what-RS-says, quantified): the COLORED-CLOUD FORMAT WORKS end-to-end (colored ply -> color renders -> aligns into a component) - this is the thing the intensity-only cloud could NEVER do (its renders were noise, control points impossible). BUT 2.7% color = only 9/6/14 tie-points per camera (29 total) = "0 models": enough to place cameras, NOT enough to reconstruct. RS named the gap in numbers: NEEDS FAR MORE COLOR COVERAGE. *** NET / THE PROVEN CHAIN: rig capture (lean) -> PCD-with-intensity (o3d.t) -> on-board colorize via extrinsic -> COLORED .ply -> Tailscale to Shadow -> RealityScan (Features=Color) -> aligns into a Component. EVERY STAGE RAN. The ONLY remaining gap is COLOR COVERAGE, and its fix is known: the FULL multi-frame colorize (all frames + poses via pointlio_pose_matcher, each frame colors its FOV slice, poses place them, together they cover the cloud) ON A MOVING capture (aim at content, orbit, vary height - so successive frames cover the room). *** IMMEDIATE NEXT (focused, no wandering): build the FULL multi-frame colorize (extend colorize_simple.py: iterate all ~410 frames, place each via posed poses, accumulate best-color per point) - validate it multi-frame on cheap static data FIRST (confirm >1 frame colors more), THEN a real MOVING capture of this good room -> rich color -> RS gets thousands of tie-points -> a real model. *** ASSETS THIS SESSION: colorize_simple.py (Jetson /tmp + chat output; the simplest proven colorize), fusioncap_095447 (bag+PCD, the static test capture, /mnt/rigdata), fusioncap_095447_COLORED.ply (2.7% colored, on Jetson /mnt/rigdata AND Shadow shadow_bundle). The extrinsic ~90px soft-spot (banked) did NOT block this - projection lands correctly. --- <!-- Last touched 2026-09-15 LATE (Master 20.13.51-CORRECTION): *** THE "REMATCH LOST THE PITCH" ROOT CAUSE WAS ITSELF WRONG — a 4th failure mode found. *** DEBUG SWEEP (/debug, operator-driven "try again") proved: the 180551 bag odometry HAS full 3D rotation (mid-capture quats e.g. [-0.27,-0.66,-0.10,0.70], pitch present); deserialize_cdr reads it correctly; the REAL Jetson odom_and_stamps.npz is GOOD (pitch span 27.9deg); posed_180551.npz is GOOD (pitch 27.6deg, 82%). AND posed_images_ALL.npz DOES NOT EXIST ON THE JETSON AT ALL. => The degenerate yaw-only "posed_images_ALL.npz" I diagnosed all day was a STALE/SYNTHETIC SANDBOX ARTIFACT in the assistant's /tmp, never a real pipeline output. extract_odom_and_stamps.py and rematch_all.py are NOT proven broken (their real inputs/outputs carry full pitch). *** THE 4TH FAILURE MODE (add to postmortem): the assistant TRUSTED FILES IN ITS ANALYSIS SANDBOX AS GROUND-TRUTH PIPELINE OUTPUTS without verifying they matched the real system. A corrupted /tmp copy drove a full day of false diagnosis. SAME disease as the rest of the day: trusting an artifact without checking it against ground truth. RULE ADDED: NEVER diagnose from a sandbox/transferred copy without first confirming it byte-matches (or at least stat-matches) the real file on the rig. When a file shows a shocking property (degenerate poses), FIRST verify the file is real and current, BEFORE theorizing a pipeline bug. *** WHAT STANDS: posed_180551.npz = the trusted poses (82%). The extractor/rematch are UN-INDICTED (re-verify on real files if used, but do not assume broken). The ~90px extrinsic offset (known, banked) stands. *** NET for the audit: fewer bugs than feared — the "broken rematch" was phantom. Real open items: (a) verify a FRESH rematch on the real odom_and_stamps.npz = good (reproducibility for future captures); (b) the extrinsic ~90px never-closed translation; (c) all bakes must be re-run/verified on the REAL good poses with an IMAGE check. --- <!-- Last touched 2026-09-15 (Master 20.13.51):
*** GOVERNING PRINCIPLES (operator-ratified, these OUTRANK day-to-day tactics; read FIRST every session) ***
(P1) PROGRESS IS MEASURED BY THE IMAGE, NOT THE SCRIPT. A passing test / clean bake / "76% coverage" is NOT progress if the picture on screen is worse than a cellphone. The rendered image is GROUND TRUTH. When an image comes out worse than a phone, ALARM BELLS: STOP and isolate what is fundamentally wrong upstream - do NOT incrementally tune parameters on a broken pipeline. A bad image is a SIGNAL the pipeline is broken, not a quality knob to nudge.
(P2) EVERYTHING IS GUIDED BY TWO ACCEPTANCE QUESTIONS, ASKED BEFORE BUILDING: "Will UNREAL be able to take it?" (walkable, relightable, UV-textured mesh, Nanite, cm scale, FBX/OBJ+atlas) and "Will REALITYSCAN be able to process it?" (exact input format, poses in the right convention, LiDAR with intensity/color, one aligned component). WORK BACKWARD from these - the destination tool defines the spec; produce exactly that. Any script/conversion/capture that does not move toward "Unreal takes it / RealityScan processes it" is a SIDETRACK.
(P3) TRUST THE VISUAL/GROUND-TRUTH ARTIFACT OVER A FRESHLY-WRITTEN CHECK. When a new check contradicts a known-good result (e.g. a coverage number says 2% but the mesh is visibly 76% colored), THE CHECK IS THE SUSPECT. Isolate the failing STAGE (poses vs extrinsic vs bake vs viewer) before theorizing.
(P4) READ THE REPO + THE MASTERS AT EVERY DECISION POINT, ESPECIALLY WHEN SURPRISED. A surprising result is the SIGNAL that the answer is probably already banked. Reinvent-worse-instead-of-read-what-exists is the recurring failure; the fix is always to read first.
---  *** THE POSE BUG FOUND + FIXED (the good poses existed all along) + A HARD PROCESS-FAILURE POSTMORTEM. *** After a brutal full-day debugging spiral, the root cause of everything was: OUR OWN rematch_all.py / extract_odom_and_stamps.py re-derivation LOST THE PITCH. The re-extracted posed_images_ALL.npz came out YAW-ONLY (roll/pitch spans = 0, only 85deg yaw) and projected the camera ~90deg away from the geometry -> 2-3% coverage. The ORIGINAL matcher output, anchor_test/posed_180551.npz, was GOOD all along: 2200 frames, pos span [1.57,2.08,0.45]m, rot span [359,27.6,359]deg (HAS the 27.6deg tip-down/tip-up PITCH), convention 'T_lidar_in_map (body->map); extrinsic applied downstream by per_shot_texture'. PROVEN on Shadow: coverage with posed_180551.npz = 82% (vs 2% with the broken rematch). *** THE FIX (use, don't re-derive): USE anchor_test/posed_180551.npz (bridged to Shadow as posed_180551_GOOD.npz via Tailscale). NEVER use posed_images_ALL.npz / our rematch again for 180551 - it is degenerate. rematch_all.py interpolated the RAW /aft_mapped_to_init odometry which is itself yaw-only/degenerate; the original matcher (pointlio_pose_matcher.py) produced the correct full-3D poses that the odometry re-extraction lost. *** THE ~90px OFFSET IS KNOWN + BANKED (Master 20.13.34, Sept 7 'EXTRINSIC SOFT-SPOT'): the extrinsic ROTATION is solid (Kabsch 0.15-0.4deg) but TRANSLATION was never metrically closed (board normals span a narrow cone -> rotation_singular_values [3.06,0.87,0.07], the 0.07 = the narrow-cone degeneracy; ~1-4cm / ~90px systematic offset; Kabsch rigidly absorbs pose bias). CONSEQUENCE: a subtle UNIFORM color-shift (not random smear) = the never-closed translation, NOT a bake bug. Accepted for the motion pipeline; close via CALIBRATION_FRAMEWORK later if tighter registration is wanted. *** ================ PROCESS-FAILURE POSTMORTEM (operator-directed, banked in plain words so it is not repeated) ================ THREE compounding failures cost an entire day: (1) DID NOT READ THE REPO - the GOOD_MESH_9_7_PROCESSING_RECIPE.md (posed_180551.npz -> 76% textured, PROVEN) and the fusion tooling were in the repo the whole time; I re-derived poses instead of using the proven file. (2) DID NOT READ THE MASTERS - the ~90px extrinsic offset ('not a bake bug'), the extrinsic translation soft-spot, AND the fact 180551's original poses were validated-good (100% anchored, non-degenerate, Master 8AH) were ALL banked. The Master EXPLICITLY warns 'READ THE MASTER at every decision point, ESPECIALLY when a result is surprising (a surprise is the SIGNAL to check whether it is already known, before building an investigation)' - and I built the investigation instead. This is the SAME failure the record catches repeatedly (reinvent-worse instead of read-what-exists). (3) FAILED TO ISOLATE THE PIPELINE / IGNORED UNREAL'S VISUAL ANSWERS - Unreal (and the Open3D renders) were SHOWING the answer in visual form: the mesh was correctly colored where the camera saw it, blobby/gray where it didn't; the '90deg-off' projection was visible; the duplicate-frame scare was a viewer glitch the FILES immediately disproved. I chased numbers from broken checks (my own verification code was buggy - reported 0%/2%/3% while the mesh was visibly 76%+ colored) instead of trusting the visual evidence and isolating WHICH stage was wrong. The rule re-ratified: TRUST THE VISUAL/GROUND-TRUTH ARTIFACT over a freshly-written check; ISOLATE the failing stage (poses vs extrinsic vs bake vs viewer) before theorizing; and when my own check contradicts a known-good result, MY CHECK is the suspect. *** ALSO WASTED: an ~85deg 'flat trajectory / no parallax' panic (built capture_check.py) - which is REAL and useful for FUTURE photogrammetry/splat captures, but was NOT 180551's blocker (the blocker was the broken poses, and LiDAR supplies geometry so parallax is not required for the LiDAR-geometry+photo-texture path). capture_check.py is kept as a real capture-QC tool, not a diagnosis of 180551. *** WHAT ACTUALLY GOT DONE (real progress under the mess): Python/RealityScan env on Shadow (conda fusion py3.12 + numpy/opencv/open3d/scipy/trimesh; RealityScan 2.x installed). LiDAR->PLY WITH INTENSITY solved (the .pcd HAS intensity+normals+curvature via o3d.t reader; the basic .ply writer dropped it -> use o3d.t.io to preserve; RealityScan intensity-render import then works, 33 virtual-camera .lsp views generated). BUT the intensity .lsp renders were too sparse/noisy to place control points on (indoor 1733pts/m3 cloud, not Alcatraz-dense) - so RealityScan colorless-LiDAR-to-photo weld via GCP is uncertain for this cloud. Confirmed the 2200 frames are REAL/unique (files differ by ~6-89; RealityScan's scrub PREVIEW glitches showing duplicates - trust files not the viewer). *** THE CLEAN PATH FORWARD (with the GOOD poses, next session): now that poses project at 82%, options ranked: (A) colorize the LiDAR cloud with posed_180551.npz + extrinsic (per-scan or via the mesh) -> import a COLORED cloud to RealityScan -> auto-registration works (solves the intensity-render problem); (B) RealityScan trajectory/COLMAP import of the good poses (Registration=Exact) -> mesh from LiDAR + texture from photos; (C) re-bake the UV-atlas mesh (bake_uv_atlas.py) with the GOOD poses -> textured mesh straight to Unreal. All three now viable because the poses work. Research banked: colorize-with-extrinsic needs no trajectory for a single scan (merging needs poses, which we now have); RealityScan links trajectory images to poses BY FILENAME not timestamp; Registration=Exact preserves imported poses. *** CAPTURE DISCIPLINE (banked for future): export LiDAR as PLY/LAS WITH intensity (ideally RGB-colored) from the rig; keep raw per-scan clouds; verify frame uniqueness + parallax (capture_check.py) at capture time; the pitch-carrying original-matcher pose path (pointlio_pose_matcher.py) is the trusted one - do NOT re-derive from raw odometry. --- <!-- Last touched 2026-09-14 (Master 20.13.50): *** THE BIG ONE: PIPELINE LOSS FOUND + LARGELY UNDONE. Proved the fusion works on Shadow, then proved the weak result was PIPELINE STARVATION not capture weakness, and recovered ~20x the textured data FROM THE SAME CAPTURE. *** THE FULL FUSION PIPELINE NOW RUNS ON SHADOW: set up Python (conda env 'fusion', Python 3.12 - NOT 3.14 which has no open3d build), installed numpy+opencv-python+open3d 0.19+scipy+trimesh. All fusion work: open Anaconda Prompt -> conda activate fusion -> cd Downloads\shadow_bundle. GOTCHA: raw Python installs on Windows are a mess (PATH/alias/version hell); MINICONDA is the clean fix. Python 3.14 too new for open3d -> use 3.12. *** RAN OUR FUSION -> COLORED MESH on Shadow (the thing that HARD-LOCKED the Jetson): bake_shadow.py (per_shot_texture mesh + best-image-per-face -> colored .ply, NOT a 2D render). First run (Jetson-era limits): 161k pts + 210 frames -> 28.8% textured, shredded, dim. *** THE DIAGNOSIS (operator was RIGHT to push back on "capture is weak"): audited capture->render loss. TWO Jetson-era bottlenecks strangled a RICH capture: (1) TARGET=161000 downsample threw away 91% of 1.8M LiDAR points (a Jetson 8GB Poisson-segfault limit, irrelevant on Shadow 28GB); (2) posed_images.npz had only 307 entries (27.2s of an 81s capture) = the pose-MATCHER was run on a SUBSET; only 210 ok. So the pipeline used ~9% of LiDAR and ~10% of cameras. NOT capture poverty - PIPELINE LOSS. *** FIX 1 (bake_shadow_full.py, remove downsample): full 1.8M cloud -> 969k verts, 250k textured (25.8% of a 7x bigger mesh = 6x more textured verts). *** FIX 2 (the big recovery): the bag fusioncap_180551_0.db3 (16GB, STILL ON JETSON /mnt/rigdata/fusioncap_180551/) has /aft_mapped_to_init = 1,147,445 odometry poses over the FULL 81.2s + 2200 /image_raw. So ALL 2200 frames are pose-recoverable. extract_odom_and_stamps.py (Jetson, rosbags lib) -> odom_and_stamps.npz (0.7MB, full odom thinned to 200Hz + all 2200 img timestamps). rematch_all.py (Shadow, scipy Slerp+interp) -> posed_images_ALL.npz = ALL 2200 frames posed (vs 210). Convention verified matches old npz: T_lidar_in_map (body->map), quat[x,y,z,w], extrinsic applied downstream by per_shot_texture. *** RESULT: bake_shadow_full.py with all 2200 frames -> 788,772 textured (81.4%) - a ~20x jump from 40k. OPERATOR VINDICATED: pipeline loss, undone, same capture. *** FIX 3 (bake_clean.py, shredding+gaps): the shredding was BAD NORMALS - the old mesh_cloud used orient_normals_towards_camera_location([0,0,0]) which is WRONG for a walked capture. bake_clean.py uses orient_normals_consistent_tangent_plane + bigger 10cm normal radius + Poisson depth 10 + de-shred (drop tiny disconnected clusters) + neighbor-fill for untextured verts. Result: 1.24M verts/2.48M faces (proper 2:1 closed surface vs torn 1:1), 83.4% textured, 206k neighbor-filled. HONEST CAVEAT: the neighbor-fill created ugly pale BLOBS on Poisson-invented geometry - it OVERSHOT. Next: re-run WITHOUT neighbor-fill + HARDER density trim = clean 83%-real surface with honest gaps (no blobs). *** THE HONEST CEILING: 83% textured = what the camera SAW. The unseen ~17% cannot be invented (blobs look fake); real improvement needs BETTER CAPTURE COVERAGE = the dwell/coverage plan. So: pipeline loss = solved; remaining gap = genuinely a capture-technique problem (dwell). *** TAILSCALE SET UP (the transfer fix, banked in 49, done today): both machines on tailnet fasterbybaxter@gmail.com; Jetson=fasterbybaxter-desktop (tailscale IP 100.85.175.10), Shadow=SHADOW-QINC8AE6. Direct scp Jetson<->Shadow works (scp fasterbybaxter@100.85.175.10:~/file .) - NO more PC-hop/Drive. Asks Jetson password (no keys set up Shadow<->Jetson yet). *** TODAY'S SCRIPTS (in chat outputs + on Shadow shadow_bundle; NOT in repo yet - upload them): bake_shadow.py, bake_shadow_full.py (full-cloud), extract_odom_and_stamps.py (Jetson bag->odom npz), rematch_all.py (Shadow, pose all 2200), bake_clean.py (de-shred+fill). Also SHADOW_MINICONDA_SETUP.md. *** SHADOW shadow_bundle CONTENTS: per_shot_texture.py, pointlio_to_texture.py, pointlio_pose_matcher.py, bake_shadow*.py, rematch_all.py, bake_clean.py, fusioncap_180551_scans.pcd, posed_images.npz (NOW the 2200-frame version; posed_images_BACKUP.npz = old 210), posed_images_ALL.npz, odom_and_stamps.npz, calib_intrinsics_20260813.yaml, extrinsic_20260816.yaml, fusion_180551_MESH.ply (81.4%), fusion_180551_CLEAN.ply (83.4%+blobs). Frames: ~/Desktop/frames_180551 (2200). --- <!-- Last touched 2026-09-11-13 (Master 20.13.49): INTO UNREAL FOR REAL + THE FUSION-MESH QUESTION + SHADOW STOCKED. Multi-day: (Sept 11) bridged GOOD_MESH_9_7.glb Jetson->PC->Shadow, imported into UE5.8 on Shadow, RENDERED our captured space in Unreal for the first time. (Sept 11-13) confronted the honest quality + strategy questions and moved the whole operation onto Shadow. *** UE5.8 RUNNING ON SHADOW, our mesh IN IT: after fighting broken viewport nav (relative-mouse-mode over the stream) fixed by WINDOWS+ALT+M (Shadow mouse-mode toggle) + camera-speed Max Slider Speed=128; use the SHADOW DESKTOP APP not the browser player (browser eats mouse-wheel/right-drag). The imported mesh = the PER-VERTEX-COLOR marching-cubes mesh = dotty yellow, "nothing we havent seen in MeshLab". VERIFIED (in-chat, Open3D): the camera+LiDAR ARE correctly fused (2.22M verts=colors 1:1, colored+dark centers 1.69m apart in an 18m room = intermixed, NO offset; 82.5% colored, 17.5% coverage-gap dark). So the fusion is REAL and correct; the mesh is just the WEAK output (2.6% per-point color, the known floor). *** THE CORE REALIZATION (the whole project in one line): the CAMERA+LIDAR FUSION is the EDGE, and it already happened (the colored mesh IS the fusion). What's missing is turning it into a PHOTOREAL, WALKABLE, RELIGHTABLE UV-TEXTURED mesh. per_shot_texture.py / pointlio_to_texture.py were BUILT + PROVEN (90.3% photoreal render) but OUTPUT A 2D RENDER, not a mesh, and pointlio_to_texture HARD-LOCKED the 8GB Jetson (JETSON_BAKE_MEMORY_WALL doc: "texture bake is a PROCESSING-STATION task, NOT a Jetson task") - which is WHY the texture step was never finished: no processing station existed. SHADOW IS THAT STATION (28GB RAM, RTX A4500). *** PATH DECIDED = PATH A: keep OUR fusion (LiDAR geometry + camera texture = our edge), extend it to output a UV-TEXTURED MESH, run on Shadow. NOT hand to RealityScan (that sidelines our fusion). The UV-unwrap+atlas-bake is generic PLUMBING (not the edge) - can be done by Unreal's built-in auto-UV / Blender / or extended tool; the FUSION is the edge and it's ours. (Sandbox proof of the UV-bake hit xatlas segfaults - it's heavy, belongs on Shadow not the sandbox.) *** THE DWELL INSIGHT (operator's correction, important + banked): the L2's "2cm navigation-grade" is a SINGLE-SHOT spec. DWELL TIME (longer look at a surface = more returns = noise averages down ~1/sqrt(N)) makes the accumulated model FAR better than per-shot. This is an UNEXPLOITED LEVER (operator technique, not hardware limit) - short bursts vs long takes untested because there's no finished model to judge against. Chicken-egg: need ONE finished model to calibrate dwell. So FINISH ONE MODEL is the priority; then measure dwell. (Caveat: dwell fixes RANDOM noise not drift; stationary dwell is pure gain, walking trades dwell vs coverage.) *** CALIBRATION LOCATED (for Path A fusion): calib_intrinsics_20260813.yaml + extrinsic_20260816.yaml (+ full extrinsic test lineage -> extrinsic_final, Calib Bigboard, CALIBRATION_HANDOFF.md) all in Desktop/ALL FILES TO SEPT 3. per_shot_texture.py HARDCODES calibration (verify matches yaml before running). *** SHADOW NOW STOCKED (the big move): bundled + bridged Jetson->PC->Shadow: shadow_small.tar.gz (57MB: per_shot_texture.py, pointlio_to_texture.py, pointlio_pose_matcher.py, bake_180551_textured_mesh.ply, fusioncap_180551_scans.pcd, posed_images.npz [307 matched], calib+extrinsic yamls) EXTRACTED on Shadow; frames_180551.tar (6.6GB, 2200 frames) via Jetson->PC(scp,LAN)->GoogleDrive->Shadow. FREE FROM THE JETSON for the whole processing/Unreal phase now (Jetson=capture only; Shadow=process+Unreal). Jetson shut down. *** TRANSFER = TOO SLOW (4 hops: scp->Drive-upload[slow, home-upload-bound]->Drive-download->untar). BANK: set up TAILSCALE (VPN putting Jetson+Shadow on one virtual LAN -> direct scp Jetson<->Shadow, no PC, no Drive) as the transfer fix. Bigger win: move LESS data (process to small artifacts, not raw 6.6GB frames). *** GOTCHAS BANKED: Open3D GLB writer is buggy (use trimesh); Open3D quadric-decimation ignored target (use vertex_clustering); file-attach uploads to chat kept coming through BLANK (paste text or read from repo instead); "GOOD MESH 9 7.ply" is a 533-byte MeshLab POINTER not geometry (real mesh=bake_180551_textured_mesh.ply). *** BIG-FAT-NO applied: Vagon dead (3 walls); RealityScan considered but rejected AS THE FRAME (sidelines our fusion) though kept as a known tool. --- <!-- Last touched 2026-09-10 NIGHT (Master 20.13.48): *** INTO UNREAL. Vagon abandoned, Shadow PC live, UE5.8 running, first mesh converted + validated. *** >>> TOMORROW FIRST THING: BRIDGE THE FILE JETSON->PC->SHADOW. The converted mesh GOOD_MESH_9_7.glb (112MB, md5 44181f59) is on the JETSON at ~/Downloads/GOOD_MESH_9_7.glb. Step 1: on the PC (PowerShell), pull it via the passwordless SSH bridge: scp rig:~/Downloads/GOOD_MESH_9_7.glb "$env:USERPROFILE\Downloads\GOOD_MESH_9_7.glb" (fallback: scp fasterbybaxter@192.168.0.204:~/Downloads/...). Step 2: drag it from the PC Downloads INTO the Shadow player window (lands on Shadow's Downloads). Step 3: in Unreal Content Drawer -> Import -> GOOD_MESH_9_7.glb -> drag into viewport. THAT is the keystone: our real captured space appears in Unreal for the first time. *** VAGON = DEAD (Big-Fat-No, 3 walls: froze at install x2 under-provisioned, then rush-hour no-capacity, then flaky region-switch). "I can't trust this service." Pivoted to SHADOW PC (the record's own long-standing pick for the learning phase). *** SHADOW PC = LIVE: account created, subscribed to POWER-tier (RTX A4500, 20GB VRAM, 28GB RAM, persistent Win11), accessed via browser at pc.shadow.tech/player from the HP Celeron PC (thin client). PERSISTENT = install UE once, it stays; no rush-hour meter; flat monthly. Logout = close the browser tab (persistent+flat-fee, nothing lost, no idle-billing trap unlike Vagon). UE5.8 INSTALLED + RUNNING (12GB download completed - the exact stage that froze Vagon twice; Shadow sailed through). Project "PROJECTLIDAR" open, LiDAR Point Cloud Support plugin ENABLED. Firewall-allow on first launch = normal. First shader compile = one-time heavy (cached on persistent Shadow, so paid ONCE - a real Shadow advantage over per-session Vagon). *** THE MESH CONVERSION (done, in-chat via Open3D 0.19 + trimesh): source = ~/Desktop/bake_180551_textured_mesh.ply on Jetson (89MB, 2,223,400 verts / 4,577,476 faces, per-vertex RGB). CONVERTED -> GOOD_MESH_9_7.glb: scaled x100 (meters->cm for Unreal), normals computed, vertex color preserved, real-world size confirmed 18.16 x 16.38 x 3.54 m (a real room). GOTCHA BANKED: Open3D's GLB writer is BUGGY (wrote a corrupt 0-vertex "buffer out of range" file - caught on read-back). trimesh's GLB writer is RELIABLE - use trimesh for GLB export, not Open3D. GLB (112MB) is the file; OBJ backup exists (456MB, ASCII bloat - GLB preferred). NOTE: "GOOD MESH 9 7.ply" on the Jetson is a MeshLab PROJECT POINTER (533 bytes), NOT the geometry - the real mesh is bake_180551_textured_mesh.ply. *** HONEST EXPECTATIONS FOR THE FIRST IMPORT (so we read it right): this is the JETSON marching-cubes mesh (blocky - the Jetson ceiling) with DAYTIME LIGHT BAKED into vertex colors. It will show our space in color, but relighting will FIGHT the baked daylight. This import = prove-the-path + see-what-we-have, NOT final quality. 4.6M tris -> enable Nanite on the asset. If color doesn't show, GLB vertex-color may need a vertex-color material node in UE. *** STRATEGIC FORK RAISED (undecided, important): is this an OFF-SET prep tool (capture->process later->deliver previz, fits current cloud setup perfectly, lower risk, near-term product) or an ON-SET live tool (part of the Blackout console, real-time lighting in the room - the console's ambition, but collides with cloud latency/fragility on set -> likely needs LOCAL GPU on set eventually, a real reason to OWN hardware driven by on-set NEED not cost)? Likely end-state = HYBRID (capture anywhere, prep off-set, present live on-set from pre-built on local hardware). The first Unreal test informs this (how heavy is setup, how fast is live relight). Client-facing timeline: in-session lighting changes should be REAL-TIME (Unreal's whole point); setup-per-location = UNKNOWN until first full run measures it; the shader-compile is a ONE-TIME setup cost clients never see. --- <!-- Last touched 2026-09-10 (Master 20.13.47): STRATEGY DAY — the fork toward the deliverable half (cloud/Unreal). No hot rig work; all planning + research + one safe cleanup. *** MEMORY AUDIT (cold, done): the tight disk is the 234G eMMC (/), 47% full. The SSD (/mnt/rigdata) is fine (175G/716G free). The 54G Desktop hog = "ALL FILES TO SEPT 3", of which 48G is one folder "Fusioncap scans" holding OLD pre-Sept-3 capture bags (175244=22G, 152121=8.1G, 185945/192455/185910/083911/121359/102338...). PLAN (not yet executed): these are UNIQUE (not on SSD) so DON'T delete blind - some may be Unreal-trial keepers. RELOCATE not delete: rsync the 48G folder -> /mnt/rigdata (SSD has room), verify, then remove from Desktop = frees ~48G on the tight system disk, loses nothing. Rule reaffirmed: until we know what Unreal needs, keep captures unless clearly bad. *** VAGON DIAGNOSIS (the real cause of the twice-failed Unreal install): the free trial = Planet tier (Tesla T4, 4 vCPU, 16GB RAM, 75GB disk). UE5 needs 32GB RAM recommended + 80-120GB just to install -> the 75GB disk is SMALLER than the install, and RAM is half-spec. It froze from under-provisioning, NOT because Vagon can't do it. FIX = one properly-configured retry: Flame tier ($2.27/hr, A10G 24GB, 8 core, 32GB RAM) + pre-expand disk to ~175GB + storage sub ($7.99/mo) + install via preinstalled-app library if offered + US region (N.Virginia/Oregon). HARD STOP: if it freezes AGAIN properly-configured = 3rd strike, switch. Idle-billing trap: shut sessions down ($40-65 overnight if left). *** CLOUD ALTERNATIVES (verified this session): iRender = RTX 4090/24GB/256GB RAM, $8.20/hr, interactive UE5 via Parsec, 100% first-deposit bonus - BUT all hardware in Vietnam -> ~150-250ms US latency (fine for batch render, handicap for interactive; VERIFY with a real ping before committing). Xesktop = batch-render only (old GPUs, session-wiped U: drive) - NOT for interactive. Shadow = US, RTX A4500, flat $37.99-54.99/mo (good if heavy constant use). Paperspace CORE = US interactive (verify current offering). *** FORMAT/SCALE CHOKE POINTS (huge files, millions of pts/tris): POINT CLOUDS scale FINE - LAZ (compressed, uploads fast) + UE5 LiDAR plugin (octree-streams 100M+ pts). Avoid E57 (color bug + structured/unstructured empty-import). MESHES are the choke - FBX/OBJ strain at millions of tris (OBJ=ASCII text, worst); USD + Nanite is the scaling path. CloudCompare/conversion needs RAM the weak local machines (Celeron 8GB, SP4 4GB) DON'T have -> CONVERT ON THE CLOUD BOX (256GB RAM), not locally. Relight gotcha: camera-textured mesh has DAYTIME LIGHT BAKED IN -> must de-light to flat albedo (Agisoft De-Lighter, free) before day->night relighting works; per-vertex-color meshes need UV-unwrap+bake first. Coordinate mismatch: ROS meters/Z-up vs UE cm -> scale x100 + check handedness. *** DATA MOVEMENT ARCHITECTURE (reasoned): the PC is a COCKPIT/STAGING VAULT, not a live relay - data should NOT pass through it as a pipe. Best model: 2TB SSD on the PC as a FIELD HOLDING AREA - Jetson captures -> beam to the 2TB SSD over local network (NO internet needed in the field) -> later, with internet, upload SSD->cloud. This DECOUPLES capture from upload and largely DISSOLVES the field-router/no-WiFi problem (you may not need field internet at all). Beam path (WiFi vs wired-gigabit) UNDECIDED - depends on workflow, which we don't know yet. *** KEY REALIZATION: every open data-pipeline question (beam path, router, convert-where, transfer topology) is DOWNSTREAM of actually running Unreal once. The Unreal test is the keystone that converts all these unknowns into answers. Don't over-spec the pipeline before that test. --- <!-- Last touched 2026-09-09 NIGHT (Master 20.13.46): *** IT ALL CAME TOGETHER — LIVE, END TO END, ON BOTH MACHINES. *** The full staged flow ran clean and the live LiDAR cloud rendered BEAUTIFULLY on the PC. This is the milestone the last several days drove toward: the rig captures, the kiosk shows it live, on BOTH the Jetson AND the PC, from a clean staged pre-flight with off-ramps. *** WHAT RAN (the complete corrected flow, first clean end-to-end): (1) RIG CHECK (green button, cold) -> ALL GREEN; (2) power L2; (3) RIG PRE-FLIGHT (blue button, now = rig_start_lean.sh) -> L2 off-ramp -> rig up, LiDAR flowing 12Hz (note: a premature "LiDAR no data" WARNING fired because the L2 responded slow at 14s, but ros2 topic hz confirmed 12.008Hz - the verify check just ran too early; minor tweak someday); (4) RIG KIOSK (amber, now KILLS stale server + starts FRESH) -> live IMU/odom face, L2 RIG VIEW visible, GREEN gauges (NO deaf-0Hz - the fresh-server fix worked); (5) opened http://192.168.0.204:8080/kiosk on the PC -> live kiosk on the PC too; (6) SCAN mode -> the live LiDAR cloud rendered = "WOOOOW that looks amazing". *** THE THREE-STEP STAGED FLOW, REALIZED ON BOTH MACHINES: RIG CHECK (cold, stack whole) -> RIG PRE-FLIGHT (= rig_start_lean.sh: rig up + L2-signal off-ramp) -> RIG KIOSK (fresh server + open). Big touch buttons on the Jetson (green/blue/amber), numbered shortcuts on the PC (1/2/3), same flow both places. Off-ramp at each temperature transition (cold verify -> L2-present -> open). *** KEY FIXES THAT MADE IT WORK (all today, all vaulted): rig_kiosk_launch.sh 48d24185 (kills stale server -> always fresh -> closes the daemon-reset-deafens-server bug that caused 0Hz repeatedly); rig_preflight_button.py repointed to rig_start_lean.sh; rig_kiosk.html 360a1f1f (IMU/odom face); cloud.html f9cdda3f (L2 RIG VIEW stays visible). *** GOTCHA BANKED: a GUI button holds its code in memory once open - after editing a button's target script, pkill the button + relaunch (or close/reopen the window) or it runs the OLD code. This cost ~20 min of "the repoint didn't take" confusion; the file was correct all along, the open window was stale. *** SCAN vs MAP reminder: SCAN = live raw cloud (works whenever the rig's up, gorgeous) - what rendered on the PC. MAP = red/green coverage (needs a CAPTURE running + WALK) - the next thing to show on the PC. *** VAULT holds the entire deployed system incl. all buttons/scripts, md5-manifested at ~/rig_originals. --- <!-- Last touched 2026-09-09 LATE (Master 20.13.45): KIOSK FIXES + PC COCKPIT + THREE-BUTTON JETSON PRE-FLIGHT — all built, live-confirmed, vault-protected. *** PROBLEM #1 FIXED (RIG KIOSK opened an old no-IMU face): ROOT CAUSE was a DEPLOY GAP, not a redesign — the odom/IMU face was built 2026-09-08 as rig_kiosk_ODOM_final.html (360a1f1f) but NEVER copied over ~/Desktop/rig_kiosk.html, so the server kept serving the old df117808 (0 odom refs) at /kiosk. The launcher + URL (/kiosk) + server were all fine. FIX: deployed the ODOM face as rig_kiosk.html (now 360a1f1f). Live-confirmed: the button now serves the IMU/odom face. Old df117808 face preserved in vault as rig_kiosk_PREODOM_df117808.html. (Chain traced by reading the REAL Jetson files, not the stale repo copies — repo rig_kiosk_launch.sh/cloud.html were older than deployed.) *** PROBLEM #2 FIXED (L2 RIG VIEW settings box vanished): NOT an auto-hide timer — cloud.html line 270 DELIBERATELY hid .hud whenever embedded (?embed=1, how the kiosk iframe loads it); the "flash then gone" was the pre-JS render before line 270 ran. FIX: removed only the hud-hide from the embed block (hint/help still hidden). cloud.html 325576a0 -> f9cdda3f. Live-confirmed: L2 RIG VIEW stays visible full-time AND the buttons work; no crowding of the coverage view. *** PC COCKPIT BUILT (one-click launch from the PC): rig_cockpit.ps1 at C:\Users\janes\rig_cockpit.ps1 (stable path, out of Downloads) + a "RIG COCKPIT" desktop shortcut. One action: ssh rig runs rig_check.sh (wholeness) shown on the PC -> if ALL GREEN, starts JUST the server on the Jetson (NOT firefox-on-jetson) -> opens http://192.168.0.204:8080/kiosk in the PC browser. Eye-is-arbiter: RED stops, won't open a broken kiosk. Bugs fixed during build: apostrophe-in-double-quote broke the parser (removed); array -notmatch missed "ALL GREEN" -> switched to (-join) + -notlike "*ALL GREEN*". OneDrive-redirected-Desktop gotcha hit (real Desktop = C:\Users\janes\OneDrive\Desktop) -> shortcut saved via [Environment]::GetFolderPath("Desktop"). The kiosk server binds 0.0.0.0:8080 so it's reachable from the PC directly (Option A: just open the URL — proven). *** THREE BIG WAVESHARE BUTTONS (touch, keyboard-less, modeled on the existing rig_button.py): AMBER "RIG KIOSK" (starts the kiosk, existing) + GREEN "RIG CHECK" (~/rig_check_button.py -> rig_check.sh, cold wholeness) + BLUE "RIG PRE-FLIGHT" (~/rig_preflight_button.py -> rig_launch.sh, wholeness + rig status + kiosk path). Positioned +40/+480/+920 so they sit in a row. All three live-confirmed. NOTE: RIG CHECK and RIG PRE-FLIGHT overlap (PRE-FLIGHT includes the check + rig-status); both kept, different depths. *** VAULT NOW HOLDS THE FULL DEPLOYED SYSTEM: ~/rig_originals + manifest, all md5-recorded. Current canonical md5s: rig_kiosk.html 360a1f1f (IMU/odom face) | cloud.html f9cdda3f (L2-RIG-VIEW-visible) | rig_kiosk_server.py 6a901f2c | map_accumulator.py 6686b43a | point_lio_capture.sh b34ca627 | three.min.js eb854986 | launch.html 3bca7afe | rig_start_lean.sh f3d96d7c | rig_stop.sh a275bb48 | restore_kiosk.sh c77776e2 | rig_check.sh 4804a81b | rig_launch.sh d0b873b8 | rig_check_button.py 7e02f751 | rig_preflight_button.py (vaulted) | RigCheck.desktop d094265 | RigPreflight.desktop (vaulted) | + spares rig_kiosk_ODOM_final.html, rig_kiosk_PREODOM_df117808.html. *** OPEN (minor): rig_check.sh's LIVE map should be extended so the new tools (rig_check.sh, rig_launch.sh, buttons, .desktops) are actually verified not just vaulted (they currently show "no live path mapped - skipped"); .204 router reservation. --- <!-- Last touched 2026-09-09 PM (Master 20.13.44): PRE-FLIGHT LAUNCHER + PASSWORDLESS PC COCKPIT — BUILT & PROVEN (a good easy day after the 9-08 grind). *** THE PROTECTION PROTOCOL (now ratified, binding on all future build work): (1) Anything to be rewritten/edited is CLONED/ARCHIVED first — the pristine copy is sacred, never touched again. (2) Originals live in a SWEEP-PROOF VAULT: ~/rig_originals/ (HOME, not Desktop — the daily cleanup can't reach it) + originals_manifest.txt (md5 of each). (3) md5-confirm the archive matches BEFORE any edit — that md5 gate must pass before touching the live file. (4) Then edit the canonical file IN PLACE (keeps its name/path so everything still finds it — avoids the naming-zoo) OR clone-and-repoint; either way the original is preserved in the vault. (5) If wrong: cp from the vault = instant provable restore. Every change is ADDITIVE; the working stack is sacred. *** THE VAULT (built today): ~/rig_originals holds 10 known-good originals, md5-manifested. Canonical md5s: rig_kiosk_server.py 6a901f2c | point_lio_capture.sh b34ca627 | cloud.html 325576a0 | rig_kiosk.html df117808 | map_accumulator.py 6686b43a | launch.html 3bca7afe | three.min.js eb854986 | rig_start_lean.sh f3d96d7c | rig_stop.sh a275bb48 | restore_kiosk.sh c77776e2. This is the provable restore point AND the axiomatic source (replaces the fragile "newest dated folder"). *** THE COLD WHOLENESS CHECK (built + proven today): ~/rig_check.sh — read-only diagnostic, compares deployed stack vs the vault manifest, reports GREEN/RED per file (CRITICAL vs advisory), NAMES the fix (cp from vault), never auto-heals. Catches EXACTLY the 9-08 silent-missing-map_accumulator failure BEFORE launch. Sandbox-proven (RED on missing/wrong-version) AND real-system-proven (ALL GREEN on the live stack). This is the Trouble-Box cold tier, real. *** THE LAUNCHER (built + proven today): ~/rig_launch.sh — Stage 1 runs rig_check.sh and GATES (RED -> STOPS, shows fix, does not proceed; GREEN -> continues). Stage 2 checks if the rig is responding (tries localhost then 192.168.0.204, so the SAME script works on the Jetson OR driven from the PC). Then prints READY + the /kiosk URL + "MAP tab -> capture -> WALK". Eye-is-arbiter: gates and reports, never powers the L2 / starts a capture / auto-heals. Both cases sandbox-proven + real-system-proven. *** THE PC COCKPIT (proven today): ssh rig works AND is now PASSWORDLESS (ed25519 key "rig-cockpit" generated on the PC, public half installed in the Jetson's authorized_keys). From the PC, passwordless: ssh rig "bash ~/rig_check.sh" and ssh rig "bash ~/rig_launch.sh" run the pre-flight ON the Jetson with the result ON the PC screen = the 1st-AC cockpit realized. Closes the banked "passwordless SSH key owed" item from RIG WATCH (8V). *** RIG WATCH VERDICT (Big-Fat-No applied): NOT used as the frame — its "double-click/step-away" DNA is the opposite of our eye-is-arbiter "stay and read" instrument. SALVAGED only: the proven SSH link + .204 target. The launcher/check are built fresh to fit the chosen path, not retrofitted into RIG WATCH. *** STILL OPEN: .204 router reservation (so the IP can't drift — router-config, anytime); the "where to aim next"=true-gap-mapping (harder, its own design; the current red=thin=go-back is the weak version). --- <!-- Last touched 2026-09-09 (Master 20.13.43): *** RIG WATCH ALREADY EXISTS — the PC cockpit is BUILT; pre-flight = EXTEND it, do NOT reinvent. *** Read-first win (4th time the answer was already in the repo): the PC-cockpit / 1st-AC station reasoned in Master 42 is ALREADY BUILT as RIG WATCH. Confirmed by reading C:\Users\janes\rig_watch.ps1 (PC) + RIG WATCH.lnk (repo, -> powershell). WHAT RIG WATCH IS (verbatim from the .ps1): a PowerShell script, "double-click and step away", polls http://192.168.0.204:8080/data every 3s until HTTP 200, then Start-Process opens THREE things: the /kiosk tab, the /cloud tab, and a PowerShell running `ssh rig`. Window titled RIG WATCH. It IS the hands-full PC auto-launch cockpit (built 2026-09-01, Master 8V). *** THE ONE GAP (this is exactly our pre-flight): RIG WATCH checks "is the server ANSWERING" (/data 200), NOT "is the server WHOLE". /data returns 200 even when map_accumulator.py is missing (that is precisely what happened 2026-09-08 - server up, /data fine, coverage dead on the missing module). So RIG WATCH would have opened the kiosk onto the broken-empty coverage with NO warning. It verifies reachability, not stack-completeness. *** THE FIX = FOLD PRE-FLIGHT INTO RIG WATCH'S WAIT-LOOP (extend, don't rebuild): between "rig answers 200" and "open the tabs", add a WHOLENESS check. Concretely: (1) add a /health (or reuse /regdiag) endpoint on the server that reports stack-completeness — 6 files present + md5s + map_accumulator importable -> "ready" vs "broken: <which file>"; (2) RIG WATCH calls it after the 200 and BEFORE Start-Process — if broken, it PRINTS the truth + names the fix (does NOT open a broken kiosk, does NOT auto-heal — eye-is-arbiter); (3) optionally a cold pre-check over SSH before the rig is even up. That is the entire Master-42 Trouble-Box cold-tier, living inside the RIG WATCH that already exists. *** RIG WATCH OPEN ITEMS (banked from Master 8V, still owed): passwordless SSH key for the `ssh rig` window; router reservation for .204 (so the IP RIG WATCH hardcodes can't drift); OneDrive-redirected-Desktop gotcha on the PC; STOP-before-power rule (Capture stop -> Stop Rig -> shutdown -> power; exiting the kiosk stops NOTHING). *** NET: the PC cockpit is done (RIG WATCH). The remaining pre-flight work is small and precise: a server /health endpoint + ~5 lines in rig_watch.ps1's loop to check-and-report wholeness before opening tabs. Everything in Master 42 still holds as the design; this grounds it — the cockpit isn't built-new, it's RIG-WATCH-extended. --- <!-- Last touched 2026-09-09 10:01 (Master 20.13.42): PRE-FLIGHT / TROUBLE-BOX ARCHITECTURE — DESIGN REASONED (think-deeply session, NOT yet built). Building on the confirmed coverage-HUD win (20.13.41), reasoned the architecture for a reliable PRE-FLIGHT that bolsters the existing kiosk-diagnostic. Decisions reached (all design, no code yet): *** CORE PRINCIPLE: the kiosk we already built IS the live (warm/hot) diagnostic — gauges/odom-band/coverage-panel = live truth. What was MISSING is the cold PRE-FLIGHT that guarantees the kiosk launches WHOLE (the whole map_accumulator saga = absence of this). So: pre-flight (cold gate) + kiosk (live diagnostic) = two phases, one handoff. Do NOT rebuild the kiosk; rely on it. *** THE TROUBLE BOX = a DIAGNOSTIC CHECKLIST that SHOWS truth to the eye and NAMES the fix, but NEVER auto-heals (self-healing = the anti-pattern; the silent except:pass that hid the missing module for a session is exactly what a self-regulating background box would perpetuate). Eye-is-arbiter: instrument advises, human acts. *** CHECK TIERS (a check may only go RED once its preconditions are met; else greyed "not yet", never false-red): COLD (valid with nothing running): 6 kiosk files present + md5s right — the ONLY true gate (kiosk crippled without them). WARM (needs rig+lean+server+discovery): server up on :8080, gauges live-vs-0/dropped — but these ARE the running kiosk, so the kiosk face IS the warm diagnostic. HOT (needs a capture running): capture alive, /regdiag msgs/added/err, odom alive — the kiosk face (odom band, coverage panel) IS the hot diagnostic; odom "red" is an INSTRUCTION ("walk") not a fault. So the doctor's UNIQUE job = the COLD tier (what the kiosk cant self-check because it isnt up yet); warm/hot are already the kiosk. *** PC-LINK CHECK = a COLD ADVISORY (ping+SSH to the PC): warns, NEVER gates (capture always works to the SSD; PC-down only blocks offload). Lowest-priority brick. *** HANDOFF: cold-green GATES the kiosk launch (only true trigger point); operator taps to launch (keep the eye in charge; don't auto-fire). Warm/hot = the running kiosk being watched, not a pre-launch gate. *** FILM-SET ROLE MODEL (the key clarification): operator (on rig, lost in the capture/walk, glances at coverage) vs 1st-AC (on the PC: pre-flight, start/stop, diagnostics, offload — catches technical failures so the operator doesnt have to). TWO HUMANS = TWO ARBITERS of two domains; machine decides nothing. This fixes the "operator overloaded, fumbling start/stop mid-walk" failure that plagued every capture. SOLO IS THE FLOOR (like now — one person does both, technical-first then walk), TWO-PERSON IS THE CEILING (1st-AC role filled). Same system; 2nd person is a role that can be filled/empty, never a dependency. Reliable pre-flight is precisely WHAT MAKES SOLO VIABLE — front-loads the 1st-AC "is it all good?" verification BEFORE the walk, so the solo operator can commit to moving without watching for failures. *** ONE SHARED TRUTH-SCRIPT (Jetson-side) read TWO ways so they can never disagree: from the PC over SSH (cockpit: keyboard+big monitor+eyes = preferred, and the PC-link check becomes self-evident) OR on the Waveshare touch (field-solo fallback). Build the check ONCE, surface it two ways. *** DEV SETUP (Sept 9): bench the Jetson + PC beside it = build/test BOTH faces cold, keyboard, no rig-time. Run the WAVESHARE HDMI INTO THE PC as a PREVIEW DISPLAY — see the real 1024x600 touch face live while building on the PC, instead of running back and forth Jetson->rig->monitor (headless 1024x600 render was only a proxy; this is the real screen, touchable). Content still served by the Jetson (http://192.168.0.204:8080/kiosk) or PC-local for pure-UI mockups. Does NOT change deployed arch (on the rig the Jetson drives the Waveshare as normal). *** FIRST BRICK when building: the shared COLD check-script (6 files + md5s + server-launchable -> green/red + named fix). Pure cold, bench-testable, exactly the gap that cost the sessions. Everything else (4-box Waveshare board, PC cockpit UI, PC-link advisory, role split) builds on it. --- <!-- Last touched 2026-09-08 EVENING (Master 20.13.41): *** COVERAGE HUD CONFIRMED WORKING — LIVE, ON SCREEN. *** The red/green coverage MAP panel that "never worked" is now RENDERING live coverage during a walking capture. Confirmed visually: ~14,485 voxels accumulated in the MAP panel during a capture (fusioncap_170751), gauges all green (LiDAR 12, Camera 23, IMU 120, Odom 120Hz — Odom tracking properly because the operator WALKED), the room rendered as coherent 3D coverage, orbitable. The fix that did it: map_accumulator.py restored to the Desktop (it had been swept by daily cleanup -> reg_cb's import failed -> every /cloud_registered dropped -> empty map). With the module present, add_points runs, the map accumulates, /map.bin serves it, cloud.html MAP mode renders it. FULL CHAIN VERIFIED END-TO-END LIVE: lean start -> capture -> Point-LIO tracks (walking) -> /cloud_registered streams -> map_accumulator accumulates -> panel renders coverage. The capture is USABLE: BAG ok + PCD ok (8.1M, saved fresh). NOTE on color: rendered mostly yellow/gold (the mid-range of the red->green ramp) under fairly uniform coverage; dwell-vs-rush differentiation (red thin / green dwelt) shows more with deliberate varied motion. But the MECHANISM is confirmed working. The /regdiag curl was not even needed — the voxels on screen ARE the proof (they cannot render unless add_points ran). PREVENTION IN PLACE: restore_kiosk.sh restores all 6 required Desktop files (server, rig_kiosk.html, cloud.html, launch.html, three.min.js, map_accumulator.py) — run it at session start so the daily sweep never silently breaks the kiosk again. --- <!-- Last touched 2026-09-08 EVENING (Master 20.13.40): *** RED/GREEN PANEL ROOT CAUSE FOUND: map_accumulator.py missing from the Desktop. *** The coverage MAP panel "never worked" for a definitive, now-proven reason: the kiosk server (~/Desktop/rig_kiosk_server.py) imports map_accumulator in reg_cb to accumulate /cloud_registered into the voxel map. map_accumulator.py was NOT on the Desktop next to the server (swept into dated folders by the daily cleanup, like three.min.js and launch.html before it). So EVERY /cloud_registered message hit ModuleNotFoundError('No module named map_accumulator') in reg_cb, got caught, and was dropped -> add_points never ran -> map stayed empty -> panel blank. PROVEN by the /regdiag instrumentation built this session: it reported {"msgs": 288, "added": 0, "err": "ModuleNotFoundError(No module named 'map_accumulator')", "fields": "x,y,z,intensity,normal_x,normal_y,normal_z,curvature"}. 288 registered clouds RECEIVED, 0 accumulated, on the missing-module error. This is why the old silent `except: pass` in reg_cb hid it for a whole session+ -> the REGDIAG change (log instead of swallow + /regdiag endpoint) is what caught it. FIX APPLIED: cp map_accumulator.py -> ~/Desktop/. NOT yet confirmed rendering (L2 killed before the post-fix walk), but the chain is now complete: 288 msgs prove receipt, cloud_to_bin handles the fields (offset-based, the normals/curvature extra fields are fine), map_accumulator now importable -> add_points should work -> red/green. *** ELIMINATED COLD THIS SESSION (all verified, saved us from wrong fixes): QoS (Point-LIO publishes /cloud_registered RELIABLE per laserMapping.cpp:793, compatible with server's RELIABLE sub); scan_publish_en (true, wired to scan_pub_en via parameters.cpp:91/151); odom_only (false in mapping_unilidar_l2.launch.py, the launch the capture uses; the odom_only:True was in correct_odom_*, unused); cloud_to_bin format (offset-based, handles XYZI+normals+curvature). So the ONLY break was the missing module. *** THE SYSTEMIC ENEMY (now undeniable, 3rd instance): the daily-cleanup sweeps REQUIRED kiosk files off the Desktop. The kiosk needs on the Desktop: rig_kiosk_server.py, rig_kiosk.html, cloud.html, launch.html, three.min.js, AND map_accumulator.py (6 files, not 5 - map_accumulator was the missed one). A restore_kiosk.sh that copies all 6 from the newest dated folder is the permanent fix - this is the 3rd file (after three.min.js, launch.html) whose absence silently broke the kiosk. *** ALSO this session: live odom band TRACKING confirmed (0.12m, RESET->INIT->TRACKING); Point-LIO + kiosk coexist via the daemon-safe capture (no blackout); nvmap camera-decoder error 12 recurred (hardware-decode exhaustion -> reboot clears; irrelevant to red/green which is LiDAR-path). Deploy set: rig_kiosk_server_REGDIAG.py (6a901f2c), point_lio_capture_REGDIAG.sh (b34ca627), map_accumulator.py now on Desktop. --- <!-- Last touched 2026-09-08 (Master 20.13.39): ODOM BAND BUILT + CONFORMED TO THE AUTHORITATIVE FACE + DEBUG-PASSED (deploy-ready, not yet live). *** WHAT WAS DONE (Sept 8): built the odometry measure into the kiosk by ALTERING the deployed files in place (not rewriting). RigKiosk.desktop + rig_kiosk_launch.sh = UNTOUCHED (they just launch whatever is on the Desktop; the odom measure reaches the kiosk purely by replacing the Desktop rig_kiosk.html + rig_kiosk_server.py). *** THE AUTHORITATIVE-BASE RECONCILIATION (important, avoided a stale-base trap): the deployed face is rig_kiosk.html md5 df117808 (the BENCH face, title "Rig Field Control [BENCH]", coverage via <iframe src=/cloud?embed=1&mode=MAP> = MAP is ALREADY the default view here). Server = 0ce776db. I had first patched the odom strip into the REPO v3 (different, 13495B) - wrong base; re-integrated against the real df117808 face. Daily-cleanup habit clarified: Desktop files get swept into dated folders (ALL FILES <date>) each day; newest dated folder = last authoritative set; "deploy" = put files on TODAY's Desktop. *** TOUCH-ONLY CONSTRAINT (hard requirement, operator: "touch only or we can't use it"): kiosk must be fullscreen (--kiosk, untouched) + no-scroll at 1024x600 + finger-tappable. First tried a TALL strip -> risked stealing ~90px from the coverage panel -> scroll risk. Then option-2 (odom folded into the monitor column, no coverage-panel theft) - fit-verified. Then operator asked full-width -> built a FULL-WIDTH ODOM BAND between status and main; fixed the connector-line-striking-through-labels by stacking labels BELOW the dots/line; trimmed ~30px (status 92->74, gaps 12->8, pad 14->10, band padding) to land EXACTLY 600px no-scroll. RENDER-VERIFIED at 1024x600 via headless chromium (scrollH=clientH=600, no H/V scroll). *** THE DEPLOY SET (built, DEBUG+CONFLICT-CHECKED, 7/7 checks pass): rig_kiosk_ODOM_final.html (df117808 face + full-width band: RESET->INIT->TRACKING->CAPTURING scale, dist meter, RESET btn armed only on LOST, green/amber/red health), rig_kiosk_server_ODOM.py (0ce776db + odom pose-stash in make_cb + pose-aware health emitting odom.{stage,state,dist_m,msg} + reset_odom in SCRIPTS; compiles; all existing gauges/outputs preserved), reset_odom.sh (HONEST STUB: marker-only, logs request + emits /rig/reset_marker; does NOT restart Point-LIO - the real re-anchor/stitch is unbuilt, so the stub does not fake it). Cross-file contract verified: every field the face reads, the server emits; ok/warn/lost vocab matches; reset route end-to-end. *** HONEST BOUNDARY (unchanged): all checks are STATIC - they prove internal consistency, NOT live behavior. The server odom-health block only runs against real /aft_mapped_to_init msgs, so INIT->TRACKING->CAPTURING transitions + warn/lost triggering are UNVERIFIED until a real capture. Cold-verify (curl /data | grep odom, rig on) confirms fields APPEAR; hot test confirms they BEHAVE. *** DEPLOY (needs Jetson): cp final.html->~/Desktop/rig_kiosk.html, server->~/Desktop/rig_kiosk_server.py, reset_odom.sh->~/ (chmod +x), cloud.html->~/Desktop/; pkill -f rig_kiosk_server.py; launch; curl -s localhost:8080/data|grep -A6 odom. --- <!-- Last touched 2026-09-08 (Master 20.13.38): THE COVERAGE HUD ALREADY EXISTS (kiosk MAP mode) — the "feed was never correct" was a CONFLATION, resolved. *** THE RESOLUTION (load-bearing, read after foundational-doc sweep): the accumulation-meter HUD the HUD_AND_EYE doc specs (relative red->green by dwell-TIME, registered to the scene, live, eye-judged) IS ALREADY BUILT AND DEPLOYED — it is the kiosk cloud.html MAP MODE. Verified in code: MAP mode fetches /map.bin (map_accumulator hit-counted voxels), finds max hit-count (RELATIVE normalization), colors each voxel via covColor(log2(1+hits)/denom) = red->yellow->green, updates live. That is the doc spec LINE FOR LINE. The server side (/map.bin serving [x,y,z,hit_count] from get_map().snapshot) also already exists. NOTHING to build for the coverage feed. *** WHAT "NEVER GOT THE FEED CORRECT" ACTUALLY WAS — a CONFLATION of two different things: (1) the kiosk live panel (SCAN/MAP/MESH modes) — MAP mode = the real deployed coverage meter (the "23,883 voxels" moments were this, working); vs (2) SEPARATE OFFLINE OVERLAY PNGs (hud_overlay_180551.png, cam_lidar_view_115614.png, hud_coverage) rendered from bags by side scripts, opened as files — the noisy blue/orange LiDAR-on-photo speckle. Those PNGs are the "wrong question" the HUD doc explicitly warns against (per-frame density: "a frame almost always covers what it points at"), and they are a PARALLEL REINVENTION of a coverage view the kiosk already had (same pattern as the fusion-script and bake reinventions). The failure images shown were these PNGs, NOT the kiosk MAP mode. So the coverage feed was never broken — the offline reinvention was, and it was never the HUD. *** REMAINING REAL ITEMS (small, NOT "build the feed"): (a) DEFAULT MODE — cloud.html DEF.mode="SCAN"; operators may never land on MAP. Fix: default to MAP during capture, or auto-switch to MAP when capture starts. (b) MAP->MESH AUTO-SWITCH on capture-stop (v3.1) — the "did it switch or stay stuck" tangle; verify/fix the mode transition (a transition bug, not a feed bug). (c) RETIRE the offline coverage-overlay PNGs (hud_overlay/cam_lidar_view/hud_coverage) as a HUD approach — wrong question; keep the fusion TRIPTYCH only for texture-proof. (d) VALIDATE MAP mode live on a DELIBERATELY VARIED walk (dwell here / rush there) — the doc says validation needs this; 180551 was too uniform to show red/green differentiation. Live test question is NOT "does MAP work" (code says yes) but "does a varied walk make reds/greens differentiate legibly." *** NET: the capture-assurance HUD = kiosk MAP mode (coverage, BUILT) + the odom-integrity strip (built today, Master 37) + the recovery loop. Much closer to complete than the speckle PNGs implied. --- <!-- Last touched 2026-09-08 (Master 20.13.37): CAPTURE-ASSURANCE HUD — DESIGN RESOLVED + BUILT + COEXISTENCE PROVEN (Sept 8). *** THE ODOM WARNING + RESET + COVERAGE = ONE INTEGRATED RECOVERY LOOP (operator resolved the design). The "two tiers" (clean-restart vs seamless-continue) COLLAPSE INTO ONE, because the HUD makes the trajectory gap visible and closeable on-site: (1) odom drops -> strip flashes red "ODOMETRY LOST" + the COVERAGE MAP FREEZES (coverage is built from poses; no poses = no new coverage even while the rig moves) = the frozen map IS the gap, shown LIVE; (2) operator taps RESET -> Point-LIO re-inits IN PLACE (coverage map PRESERVED, not cleared); (3) operator RE-SWEEPS the already-covered area the frozen map shows them -> creates the OVERLAP that makes the stitch trivial -> gap fills green -> continuous. The hard computational problem (relocalization/stitch) becomes an easy human problem (walk back over the green you can see) BECAUSE the HUD makes it visible. Instrument advises, eye acts, gap closes. *** KEY DATA FACT (load-bearing): odom-stop loses LIVE TRACKING, NOT DATA. ros2 bag record is a SEPARATE process and keeps writing raw /unilidar/cloud + /imu + /image_raw + /aft_mapped_to_init THROUGHOUT. So: frame-A poses saved, raw data through-and-past the drop saved, last-good-pose saved (server stashes odom_pose xyz). The whole capture can be RE-PROCESSED offline (raw topics present) -> the seamless-continue is a POST-processing stitch (ICP on real operator-made overlap, NOT a blind transform) from intact raw data. Reset button's REAL-TIME job = recover tracking so the coverage view keeps working; continuity is resolved in post from data that was never lost. *** BUILD STATE (Sept 8, all sandbox-verified): (a) HTML — odom strip INTEGRATED into rig_kiosk v3.html (CSS + 4-stop scale RESET->INIT->TRACKING->CAPTURING + dist meter + reset btn; JS updateOdomStrip reads d.odom.{state,msg,dist_m,stage}; div-balanced 74/74; 6-state logic tested ALL PASS). File: rig_kiosk_v3_odom.html. (b) SERVER — rig_kiosk_server.py (0ce776db) patched: odom pose stash in make_cb, pose-aware health block (stage + warn/lost + dist_m + msg) in build loop, reset_odom added to SCRIPTS (fires ~/reset_odom.sh). COMPILES OK. File: server_odom.py (in sandbox /tmp - re-derive/re-present to deploy). (c) COEXISTENCE PROVEN both ways: map_accumulator under realistic 70s load = add_points 1.1ms/cloud (of 83ms budget @12Hz -> never backs up), merge 65ms/1.5s off-path, 5.6% of ONE core avg, 147MB peak (hit 2M-voxel cap = bounded by design; NOTE: very large captures stop adding new voxels past cap, existing counts still update). Architecture: kiosk server is a SEPARATE PROCESS from the capture (point_lio_capture.sh); within it, dedicated spin thread + threaded HTTP + off-path merge = no shared lock on capture's critical path. Empirical: 202126 was captured WITH the kiosk live, camera held 28Hz. VERDICT: Jetson runs capture + HUD together, safe on compute; thermal monitored separately (56C idle, watch under load). *** STILL PENDING (needs rig = the hot test): reset_odom.sh script (does in-place Point-LIO restart, MUST NOT clear coverage map; post-stitch=ICP-on-overlap, its own proven-once step), deploy to live kiosk, live smoke test (render + state transitions on real odometry). *** REMAINDER of today's plan: Task 2 = the capture-assurance HUD proper ("what is captured enough to move on", mesh-look-surface ideal, + camera-coverage the NEW signal predicting texture completeness); Task 3 = hot test w/ HUD + sync PC; Task 4 = cloud work if time. --- <!-- Last touched 2026-09-07 (Master 20.13.36): THE CAPTURE-ASSURANCE HUD = the next workstream, and the project's reframe. *** THE REFRAME (operator, ratified): the CAPTURE PROCESS WORKS END TO END (lean start -> camera survives full duration [proven, 202126: 1968 frames/70s]; translate-from-first-second -> odom lives; 4-sensor wire check; point_lio_capture -> clean bag+PCD; processing recipe -> GOOD MESH 9 7). The missing piece is NOT capturing better - it is KNOWING WHAT YOU HAVE, on-site, before you leave, so you can MOVE ON with confidence. A gap found at the station = a drive back to a location you already left. The HUD is the ONLY point where a gap is still fixable (walk back over it) vs fatal. So the HUD is the PIPELINE QUALITY GATE: the second half (station, Unreal) can only ever be as good as what the capture CONTAINS - Unreal cannot relight a wall never scanned, the station cannot texture a surface no frame saw. *** THE HUD'S BOUNDED MANDATE: answer ONE question live, before pack-up - "WHAT DO I HAVE?" Three signals: (1) GEOMETRY coverage (map_accumulator red->green surface, mode=MAP) - EXISTS/deployed. (2) CAMERA coverage (which surfaces frames actually SAW, not just LiDAR hit) - NEW, and the key piece: it predicts TEXTURE completeness (the 24% gray in GOOD MESH 9 7 = geometry-but-no-camera = a gap Unreal cannot fill). (3) ODOM INTEGRITY warning (green tracking / amber "NOT MOVING-WALK" / red "ODOMETRY LOST") - BUILT + logic-tested this session (health logic passes all cases incl. the 202126 death); makes the coverage TRUSTWORTHY (a coverage map on dead odom is a lie - 202126 looked full, poses were garbage). Operator's EYE judges "enough for this shot" (HUD/Eye principle: instrument shows, eye decides; NO fake "you're done" green - repeatedly ruled a lie). *** RE-ANCHOR + CONTINUE (operator's goal, HARD/UNPROVEN tier): when odom dies mid-capture after good tracking, RESET should re-anchor and CONTINUE (one continuous map), not just restart. Buildable version: save last-good-pose (server already stashes odom_pose xyz), operator holds still + taps RESET, Point-LIO re-inits in-place, stitch happens at PROCESSING time (transform segment B into frame A). KEY INSIGHT: the coverage map both GUIDES the operator's resume (walk into the captured/non-captured boundary) AND provides the OVERLAP that makes the stitch accurate (match overlapping geometry, more robust than assume-B-starts-where-A-ended). Needs: read Point-LIO start/stop mechanism, verify mid-bag re-init, prove the seam is acceptable. Unproven - its own experiment. *** PRIORITY ARGUMENT (ratified): the capture-assurance HUD likely comes BEFORE more station/Unreal effort - build the GATE before the FACTORY, or the station just processes incomplete captures into deficient deliverables and sends you back to re-capture. *** ODOM-WARNING PATCH STATUS: built + logic-tested (sandbox, against 202126 death case + pan-frozen + walking - all pass). NOT yet: HUD render (amber/red + "WALK" text + dist_m meter), live smoke test on rig. Patch adds odom-pose stash to make_cb + pose-aware health block to the build loop in rig_kiosk_server.py (0ce776db). Deploy = next-session focused task, with the rig, ideally right before the hot experiment so the experiment HAS the warning live. --- <!-- Last touched 2026-09-07 (Master 20.13.35): JETSON MESH CEILING ESTABLISHED + CLOUD-STATION PLAN. *** THE JETSON CEILING, PROVEN TODAY: the best 3D textured mesh the Jetson can produce on a WALK capture = "GOOD MESH 9 7.ply" (bake_180551.py, MARCHING CUBES @ 2cm voxel, MAXDIM raised to 1400): 2,223,400 verts / 4,577,476 faces, 76.1% textured from 37 frames, intact (no shred), 92.9MB, ~74s. Operator verdict: "better than before, but MILES away from a deliverable." So GOOD MESH 9 7 = the Jetson's honest ceiling for walk data, NOT the deliverable. *** WHY POISSON IS OFF THE TABLE ON THE JETSON (proven exhaustively today): Open3D 0.18 (the Jetson's ONLY installable version - no newer aarch64 wheel, upgrade attempts confirmed "already satisfied" = dead end) SEGFAULTS on 180551's walk cloud at every size tried: full 426k -> crash; cleaned uniform 404k -> crash ("corrupted double-linked list"); random 161k -> RAN but produced a SHREDDED confetti mesh (torn triangles, unusable). Root: Poisson iso-surface extraction ("Failed to close loop") cannot handle a WALK-accumulated cloud's geometric inconsistency on 0.18. The crisp Aug-21 pointlio_bridge_realproof.png (90.3%, flat) was SINGLE-VANTAGE (161k dense, one viewpoint, self-consistent) + a 2D RENDER, not an orbitable mesh - that is why it worked and walk-Poisson doesn't. mesh_check.py's own docstring already said it: "No Open3D (no aarch64 wheel for the Jetson)" - the whole marching-cubes instrument exists BECAUSE the Jetson can't run Open3D. Today re-learned that the hard way. *** THE PERMANENT DIVISION (now concrete): JETSON = capture + poses + INSTRUMENT-grade marching-cubes mesh (blocky-by-design, GOOD MESH 9 7 class). CLOUD STATION = DELIVERABLE-grade (working Open3D Poisson on FULL cloud + ALL 2200 frames = Image-2 crispness AS an orbitable mesh). The deliverable is NOT buildable on the Jetson - proven, not assumed. *** CLOUD STATION - THE PLAN: the generic PC (HP 14-dq0, Celeron N4120, 8GB, Intel UHD 600 - specs seen) is a THIN CLIENT, NOT the processor (it is weaker than the Jetson). It accesses a CLOUD SERVICE which does the real work. Jetson<->PC connection ALREADY PROVEN (Stage 8): SSH over WiFi (ssh fasterbybaxter@192.168.0.204, PC PowerShell drives the Jetson; scp moves files; IP is DHCP - wants a router reservation). Two DISTINCT cloud jobs with DIFFERENT needs, do NOT conflate: (1) MESH BAKE = headless Python + Open3D(>=0.19) + numpy/opencv, NO GPU needed (Poisson is CPU), ~16-32GB RAM, cheap (~$0.30-0.50/hr on RunPod/Vast, or FREE on Colab). Runs on the 180551 data the Jetson already made. THIS IS THE CURRENT BLOCKER TO A DELIVERABLE and is nearly free - do it FIRST. (2) UNREAL RELIGHT (day->night, place lights) = GPU workstation + desktop-streaming, ~$1-2/hr (Vagon/AWS-DCV) to $9/hr (iRender). Only after a mesh exists. *** VAGON UNREAL PLAN (the "it wouldn't load" fix): almost certainly the DX12-vs-virtualized-GPU startup crash - the #1 cloud-Unreal failure, and Vagon's OWN docs prescribe the fix. STEPS next session: (0) launch UE once, read newest log in Saved\Logs\ for the failure line (D3D12/DX12/RHI = confirms it); (1) FORCE DX11: add " -dx11" to the UnrealEditor.exe shortcut Target, OR Epic Launcher > Additional Command Line Arguments > -dx11 (HIGHEST ODDS); (2) if not, try -vulkan; (3) delete Saved/Intermediate/Config + Shift-safe-mode; (4) update the instance GPU driver + reboot; (5) try a stable UE (5.3 / latest 5.5) - 5.4.4 & 5.6 have known startup-crash bugs. Vagon CAN run Unreal (does for many users); the crash was config, not incompatibility. Free trial = 1hr + 7day storage (Unreal install eats most of the hour - have -dx11 ready). If 1-5 all fail -> iRender (Unreal-specialist, Parsec/RDP, RTX4090, pre-configured, $9/hr) or AWS g6e+DCV ($1.86/hr). --- <!-- Last touched 2026-09-07 (Master 20.13.34): DEEP CHAT-SWEEP CORRECTIONS + CONVENTION. *** NEW CONVENTION: DATE-STAMP every Master entry (today = 2026-09-07); version numbers alone drift, dates anchor. *** CORRECTION 1 (endpoint): Master 33 said "endpoint OPEN". HALF-WRONG. The REPRESENTATION (textured MESH) was SETTLED 2026-08-18/19 from first principles ("lighting always interacts with surfaces" -> needs surfaces -> mesh, NOT point cloud, NOT Gaussian splat). This is a FLAGGED RETURNABLE FORK (Plan A = mesh CHOSEN; Plan B = Gaussian Splatting documented + held in reserve). What is OPEN is only the DESTINATION TOOL (Set.A.Light vs Unreal vs Blender), gated on the import question. So: mesh = settled; tool = open. *** STANDING RE-CHECK (from the fork's own instructions): is COMMERCIAL relightable-Gaussian-Splatting mature NOW? As of 2026-04 it was research-only (Relightable-3DG NeurIPS23, LumiGauss WACV25), in NO commercial DCC, no Unreal-Lumen GI participation -> that immaturity is WHY mesh was chosen (GS bakes lighting in; our whole job is RELIGHT day->night = GS's weakest area). The fork says RE-CHECK GS maturity on return; if commercial relightable-GS now exists, Plan B's disqualifier may be GONE = could flip the endpoint. ~5 months elapsed; worth a web-research pass before sinking more into the mesh. *** CORRECTION 2 (today's bake in TRUE context): pointlio_bridge_realproof.png (the CRISP 90.3% textured room, flat checkerboard) is dated 2026-08-21 and is a 2D RENDER (texture_render_multiview rasters to an image), NOT an orbitable .ply. Made by the PROVEN bridge: per_shot_texture.mesh_cloud (Open3D POISSON) + pointlio_to_texture, on a 161k-pt SINGLE-VANTAGE dense cloud (R=I,t=0) -> 385k-face mesh -> 90.3% photoreal. So texture QUALITY was achieved 17 days ago (in 2D); the orbitable .ply IS still new ground (today's bake was the first .ply attempt). Today's bake was BLOCKY (73%, marching-cubes) because: (a) fed the FULL 1.8M-pt walk map downsampled to 426k (vs Image-2's clean 161k single-vantage), and (b) Open3D POISSON SEGFAULTED on 180551's cloud ("Failed to close loop" -> core dump, at d9 AND d8) so we fell back to marching_cubes (mesh_check method, blocky but intact, no crash, 1.17GB peak). *** THE PROVEN PATH forward (not the marching-cubes reconstruction): downsample 180551 HARDER toward ~161k (Image-2 size where Poisson worked; the segfault may be size/density-specific), run the PROVEN bridge (per_shot_texture+pointlio_to_texture), get Image-2 crispness AS an orbitable mesh. *** LANDMINE C3 (banked in the Aug runbook, hit today): the extrinsic is HARDCODED in per_shot_texture (R_L2C/T_L2C), NOT loaded from extrinsic_20260816.yaml. My bake_180551.py copied constants from the overlay -> MUST verify they match the calibrated yaml or texture SILENTLY misregisters. *** SKIPPED GATE: the runbook's COLD-PREP 0 explicitly requires reproducing the realproof render ON THE JETSON to prove the ARM Poisson path BEFORE trusting it ("import success is NOT proof") — this gate was NEVER run; had it been, today's segfault surfaces pre-emptively. *** EXTRINSIC SOFT-SPOT (recovered): calibration banked "done" but honestly: ROTATION solid (plane-normals Kabsch 0.15-0.4deg), TRANSLATION only VISUALLY verified, never metrically closed. Translation from plane-centroids is STRUCTURALLY weak (board normals span a narrow cone); holes (which pin translation via point features) were abandoned for detection reasons, so translation quietly reverted to the weakly-conditioned centroid. ~1-4cm systematic offset remained (43/48/11px). Kabsch RIGIDLY ABSORBS pose bias (a 12deg/49mm bias was once invisible to reprojection AND Kabsch residual). CONSEQUENCE: a subtle UNIFORM color-offset in any bake (everything shifted the same ~1-4cm, not random smear) = this never-closed translation, not a bake bug. *** PRIOR-ART SHORTCUT (recovered, worth investigating): HKU-MARS (the Point-LIO lab) open-sourced LIV_handhold_2 / "LIV-Eye" = a ~$700 fully open handheld LiDAR-Inertial-Visual kit: no-solder assembly, one-click reproducibility, ROS1/2, FULL calibration workflow incl. TIME-SYNC (our tau), colored cloud + odometry in 5min. = precisely our rig, released as reference design, solving the exact problems we grind from scratch. Leica BLK2GO ($50k) uses identical LiDAR+cam+IMU fusion = we independently built the pro architecture. *** FIELD MONITORING (recovered, more resolved than logged): portable ROUTER -> Jetson joins as WiFi client (ethernet stays with L2) -> Foxglove to a phone/tablet for live coverage view + bag offload. Cleaner than the Waveshare tether. --- <!-- Last touched 2026-09-07 (Master 20.13.33): ENDPOINT CORRECTION + 3D BAKE AUDITED/READY. *** ENDPOINT IS OPEN, NOT set.a.light. Correcting the Master 32 (and Stage-8) claim that "endpoint = set.a.light not Unreal": set.a.light is a TEMPLATE/CANDIDATE, not the ratified destination. The endpoint (which relight/previz tool, which format, how much detail) CANNOT be chosen yet BECAUSE NO IMAGE EXISTS to test candidates against. Choosing a tool now = picking the destination before building anything to send there = backwards. So: endpoint OPEN (set.a.light / Unreal / Blender / other all just candidates); the decision is GATED ON having a real textured capture in hand. Consequence: the bake outputs a NEUTRAL colored .ply (opens in MeshLab/Blender/3dviewer.net, imports most places) — pre-commits to no tool. The bake's TRUE purpose restated: produce the FIRST camera-textured 3D artifact from real translating data, because until that image exists every downstream decision is unanswerable. The image unlocks the endpoint question, not vice versa. *** 3D TEXTURED BAKE — BUILT +
