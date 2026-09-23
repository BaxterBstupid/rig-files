# MASTER UPDATE — 2026-09-22  (ready to mint as MASTER_REFERENCE 20.13.66)
### Session record: the geometry verdict, the capture-method autopsy, the architecture fork, and the new tools.
### Fold this into the lineage deliberately (Stone Clause). Nothing here is a silent drift — every claim is tagged.

═══════════════════════════════════════════════════════════════════════════
## 0. WHAT THIS SESSION SETTLED (the one-paragraph version)
═══════════════════════════════════════════════════════════════════════════
The geometry was never the problem — **Poisson was.** Proven on real data twice. The
rig lays down 11 mm-clean, square walls every capture; the mesher was melting them.
The real remaining variable is **coverage**: not one of 26 captures ever traversed
enough of its space, so every result was clean-but-fragmented ("floating panels").
The architecture is now settled — **LiDAR sets dimensions, photos carry the
graphics**, forked per-deliverable on the relight gate. Tonight's live capture was
blocked by a Jetson memory scar (Firefox), fixed but out of time before the re-bringup.

═══════════════════════════════════════════════════════════════════════════
## 1. GEOMETRY IS SOLVED — PROVEN TWICE  [PROVEN]
═══════════════════════════════════════════════════════════════════════════
- `planar_shell.py` (new tool, RANSAC plane-fit + coherence report) run on the two
  best captures:
  - **163005:** planes 8–11 mm thick, walls square (2.8° max dev). GREEN.
  - **180551:** planes 10–11 mm thick, walls square (5.9°). GREEN.
- Poisson CONVICTED on the same class of cloud: invents surface up to **1556 mm** from
  any measured point (the melt). Ball-pivoting honest (0 mm) but holey.
- CONCLUSION: the rig's geometry is dimensionally true (11 mm, tighter than the
  16 mm sensor spec) and drift-free when tracking holds. Every blob ever seen was the
  mesher destroying clean data. **The geometry question is closed.**
- CONTRADICTION TO FIX [OPEN]: the shipped `fuse_to_fbx.py` still runs Poisson depth 9.
  Retire it once the planar-shell + object-mesh path is proven on real data.

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
- Full detail: `ADR-001_representation_fork.md`, `SYSTEM_DESIGN_pipeline_v2.md`,
  `PIPELINE_AUDIT_fork_and_inversion_2026-09-22.md` (all in the project).

═══════════════════════════════════════════════════════════════════════════
## 3. THE CAPTURE-METHOD AUTOPSY — 26 captures, `capture_autopsy.py`  [PROVEN]
═══════════════════════════════════════════════════════════════════════════
Ran the whole `/mnt/rigdata` pile through a new tool that reports tracking %, mid-run
gaps, and trajectory span (dX/dY/dZ). The pattern:
- **Tracking failure is an INIT problem, not duration or a code bug.** 10 of 26
  collapsed, almost all in the first **1–5 s** (odom initialized, published briefly,
  died). Meanwhile 250 s+ captures tracked 100%. Same rig, same software → the
  variable is the start. Cause: motion during the dead-still init, or a static/no-
  translation start. FIX = init discipline (below), NOT a code fix — 10 clean
  captures prove the method works when the start goes right.
- **Mid-run gaps** (6 CAUTION captures, one with a 482 s gap) = static dwelling /
  featureless aim / too-fast motion DURING the run.
- **Drift-explosion (new 4th failure mode):** some captures tracked 100% with no gaps
  yet their positions diverged to hundreds/thousands of metres. Odom can track
  continuously and still blow up. (`capture_autopsy`'s coverage tag needs a sanity
  cap to flag these — noted.)
- **Recording hygiene:** several bags recorded 0 clouds or 0 images — a whole sensor
  stream wasn't flowing. The kiosk FLOW gauges (or the terminal Hz check) catch it if
  you verify BEFORE recording.

═══════════════════════════════════════════════════════════════════════════
## 4. COVERAGE IS THE SOLE REMAINING VARIABLE — AND THE RULE THAT FIXES IT  [PROVEN diagnosis]
═══════════════════════════════════════════════════════════════════════════
- Tracking (§3) is fixable by discipline. Geometry quality (§1) is solved. What's
  left is COVERAGE, and **not one of 26 captures ever traversed enough.** Best was
  180551 at ~2 m lateral in an ~18×16 m space. 163005 was 1.4 m. That's why every
  shell came out as clean-but-disconnected floating panels.
- **THE NEW RATIFIED CAPTURE RULE — traverse scales to the space.** A fixed 1–2 m
  shuffle is what produced every fragmented result. Coverage must be a real
  perimeter traverse, metres proportional to the room: a ~5 m room needs the full
  perimeter walked (10 m+ of path); the 18 m barn proportionally more. The rule isn't
  "orbit," it's *"traverse enough that every surface is seen from a few metres of
  baseline."*
- Good tracking ≠ good coverage: 163005 is GOOD on tracking yet single-vantage. The
  two axes are measured separately (capture_autopsy = tracking + coverage span;
  planar_shell = geometry health).

═══════════════════════════════════════════════════════════════════════════
## 5. THE CAPTURE METHOD, EVIDENCE-BASED (layers ON the stone CAPTURE_METHOD doc)
═══════════════════════════════════════════════════════════════════════════
The stone `CAPTURE_METHOD` doc owns the mechanics (Start Rig Lean → Point-LIO
Capture → dead-still init → one Ctrl-C). This session ADDS:
- **Init discipline:** hold dead still until you SEE "IMU Initializing: 100.0 %",
  THEN move. This one step sank 10 of 26.
- **Traverse the full perimeter** (§4) — a real loop, not a shuffle.
- **Keep translating; never dwell static** (kills the mid-run gaps).
- **~0.7 m/s**, closed loop, two overlapping ~50 s passes (Pass A perimeter/mid;
  Pass B tip-up + tip-down + foreground local orbits), registered by ICP.
- **Dwell plan for the formal living room:** the fireplace + mantel ensemble is the
  hero surface (dense complex objects) → slow down + one close local orbit. Short
  local orbits on furniture. Do NOT dwell the mirror (specular phantom) or the glass
  (holes). Steady pace past plain walls.

═══════════════════════════════════════════════════════════════════════════
## 6. THE LIGHT RULE — REVISED (operator correction, ratified)  [RATIFIED]
═══════════════════════════════════════════════════════════════════════════
"Flat overcast" is a lab condition, not a film set. Superseded:
- **Geometry is light-invariant** — shoot the LiDAR in any light (glass still excepted).
  Never compromise the shoot's timing for the scan.
- **Texture wants bracketed / HDR** so highlight and shadow detail survive; capture
  the light as a KNOWN quantity (a grey/chrome ball, or logged sun angle) so it can be
  modeled and subtracted rather than blind-delit.
- **Hard cast shadows won't fully delight** (Agisoft's wall) → manual PBR cleanup on
  those regions is normal, not failure.
- **The delight bar is "your inserted lights read true," not perfect albedo** — for
  a night relight with strong motivated sources, residual day-light in the shadows is
  low-signal.

═══════════════════════════════════════════════════════════════════════════
## 7. THE USE CASE — CLARIFIED (the barn, one of two uses)  [operator-stated]
═══════════════════════════════════════════════════════════════════════════
- EXTERIOR (becomes night): locked-off shot, rig it in daylight → sky day→night in
  Unreal → crane/light placement via Set.A.Light → light the interior so the windows
  glow out. Coverage = **270° arc around the facade** (outside-in).
- INTERIOR (relit): capture in daylight → remove the light through the door → add
  lanterns → pull back so the windows read. Coverage = **360°** (inside-out).
- Two capture geometries: exterior orbits AROUND the structure; interior orbits
  WITHIN it. Both need real traverse + tilt bands. (Second of the two uses not yet
  described — thread left open.)

═══════════════════════════════════════════════════════════════════════════
## 8. NEW TOOLS BUILT THIS SESSION
═══════════════════════════════════════════════════════════════════════════
- **`planar_shell.py`** — RANSAC room-shell reconstructor + coherence report (per-plane
  thickness = drift check, wall orthogonality = collapse check, trajectory span =
  coverage read). Pure LiDAR, no normals, tau-independent. The dimensions-branch tool.
- **`capture_autopsy.py`** — post-mortem across many bags: tracking %, mid-run gaps,
  dX/dY/dZ coverage, and a pipeline-candidate flag. Fixes what `check_capture.py`
  couldn't (its AnyReader lacked `default_typestore=get_typestore(Stores.ROS2_HUMBLE)`
  — the same typestore fix already in `pointlio_pose_matcher.py`). TODO: add a
  sanity cap so drift-explosions aren't tagged ORBIT.
- Both delivered to the Jetson `~/Downloads` and used live this session.

═══════════════════════════════════════════════════════════════════════════
## 9. NEW SCAR — JETSON MEMORY / NVMM STARVATION  [PROVEN tonight]
═══════════════════════════════════════════════════════════════════════════
Tonight's capture failed at the camera: `NvMapMemAllocInternalTagged error 12`
(ENOMEM) — the hardware JPEG decoder (NVJPG) couldn't allocate its ring buffers.
Root cause: **Firefox was holding ~3 GB, leaving only 198 MB free.** The 8 GB Jetson
is too tight to run a browser during capture. LiDAR bringup was clean (12 Hz); only
the camera died, and a lean start declares "ALL SYSTEMS STARTED" over a dead camera —
so the terminal Hz check (`ros2 topic hz /image_raw`) is mandatory, not optional.
FIX (proven): `pkill firefox` → free jumped to 5.3 GB available.
**NEW RULE: close Firefox and any heavy app before capture; verify camera Hz from the
terminal before trusting the banner.**

═══════════════════════════════════════════════════════════════════════════
## 10. THE VERIFICATION GATES (rigor is a constant)
═══════════════════════════════════════════════════════════════════════════
Before processing any capture:
1. `capture_autopsy` on the bag(s): tracking in the GOOD band, dX & dY both a couple
   of metres (real orbit, not VANTAGE), no big gaps. Never process a starved bag.
2. `planar_shell` coherence: plane thickness ≤ 30 mm, walls < 6°.
3. Eye check on the shell render.
Fail any → the tool names the knob (light, init, traverse, pass length).

═══════════════════════════════════════════════════════════════════════════
## 11. DOCS PRODUCED THIS SESSION (in the project)
═══════════════════════════════════════════════════════════════════════════
- `PIPELINE_AUDIT_fork_and_inversion_2026-09-22.md` — full as-is audit.
- `ADR-001_representation_fork.md` — the fork decision.
- `SYSTEM_DESIGN_pipeline_v2.md` — the buildable to-be spec.
- `PERFECT_ROOM_CAPTURE_v2.md` — capture recipe (needs the §5/§6 updates folded in).
- `PROJECT_EXECUTION_CHECKLIST.md` — the end-to-end gated spine.
- **Rig Run Sheet** (live fillable artifact) — Gate A ticked GREEN; Phase 1 covgate/
  light/tau ticked; odom-cutoff consciously deferred (contingency = split-pass).

═══════════════════════════════════════════════════════════════════════════
## 12. WHERE WE LEFT OFF — NEXT STEP
═══════════════════════════════════════════════════════════════════════════
- Rig bringup was mid-recovery: Firefox closed, memory freed (5.3 GB avail). The
  **next command was `bash ~/rig_start_lean.sh`** (clean re-bringup), then the terminal
  Hz check to confirm the camera at ~30 Hz.
- Then: the **two-pass orbit capture of the formal living room** per §5 (full-perimeter
  traverse — the thing no prior capture did), gated with `capture_autopsy` (want a real
  dX/dY, not another VANTAGE), then `planar_shell` — which should finally show a room,
  not floating panels.
- Standing status: geometry solved · architecture ratified · coverage is the one open
  variable · the fix is capture discipline (init + traverse), verified by the gates.

═══════════════════════════════════════════════════════════════════════════
## 13. SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- 2026-09-22: Proved geometry sound (planar_shell, 11 mm/square on 163005 & 180551) —
  Poisson convicted as the melt. Ran capture_autopsy on all 26 bags: tracking failure
  is an INIT problem (not duration/bug); coverage is the sole open variable (no capture
  ever traversed >2 m). Ratified the architecture (LiDAR=dimensions/photos=graphics,
  per-deliverable fork on the relight gate; ADR-001) and the traverse-scales-to-space
  capture rule; revised the flat-light rule for real film sets. Built planar_shell.py +
  capture_autopsy.py. New scar: Jetson NVMM starvation from Firefox (close it before
  capture; verify camera Hz from terminal). Live capture halted at re-bringup — out of
  time.
