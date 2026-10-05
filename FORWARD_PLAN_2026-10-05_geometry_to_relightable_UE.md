# FORWARD PLAN — from clean geometry to photoreal, walkable, relightable Unreal
### ADR-005 (route decision) · SYSTEM DESIGN v3 (stages + gates) · TECH-DEBT REGISTER · the work-back roadmap
**Date:** 2026-10-05 · **Status:** Proposed · **Decider:** operator (eye is the arbiter)
**Stands on:** ADR-001 (LiDAR = dimensions, photos = graphics), ADR-003 (RS route, image-quality myth-buster), ADR-004 (record RAW, solve offline), SYSTEM_DESIGN_pipeline_v2, FUSION_SOLUTION, Masters 20.13.68–77.
**Research basis:** three primary-source sweeps on 2026-10-05 (RealityScan 2.2 docs + staff answers; Unreal 5.8 docs/release notes + ARRI LUKA; reconstruction/relighting literature + PyPI). Every load-bearing claim below carries its source in §7.

---

## 0. THE ANSWER IN ONE PARAGRAPH

**Not a dead end. The data is the expensive half, and every professional tool treats it as the reference the photos align to.** The clean metric cloud + posed frames you now get from an offline re-solve is exactly what RealityScan 2.2 is built to consume ("Mobile LiDAR", registration **Exact** — "the imported model defines the scene's coordinate system"; camera priors **locked**). RealityScan is the right place to fuse, mesh and texture; Unreal 5.8 is the stage, not the fuser — **Unreal does not texture a mesh from photos**, so "straight to Unreal" is not a route, it is a destination. The relight mission is natively supported in UE 5.8 (physical light units, IES, barn doors, MegaLights production-ready, ACES 2.0) and ARRI shipped **LUKA** in June 2026 — measured SkyPanels etc. as UE fixtures, free 3-month trial, Art-Net/sACN control, which is the protocol your Blackout console speaks. Gaussian splats remain a sidecar (not Lumen-relightable; UE has no native support). The one thing the current camera caps is **texture detail** (~4 px/cm at 2 m — fine for 1080p previs, under-resolved for 4K/long lenses); the documented fix is a stills pass registered into the same LiDAR frame, not a new rig. The one thing nobody sells is honest **de-lighting**; the free Agisoft tool + flat-light capture is the 2026 answer.

---

## 1. WHERE WE ARE (proven, 2026-10-05)

- Offline stock Point-LIO re-solves of raw bags produce **clean floor plans** (080826, 115614, 130955 — the last a 5-room, 219 s, 735°-of-turning walk the live rig had frozen on). Control image 180551. Live stand pan 141733: bent (157° heading error, measured).
- `resolve_pointlio.sh` (Jetson, L2 off) + `top_down.py` / `bag_health.py` / `bag_motion.py` (Shadow) are the working offline chain. 22 re-solvable bags on the SSD.
- Camera: Arducam 1920×1200 global shutter, native MJPEG, compressed-recorded (quality-neutral, ADR-003 §2); calibrated K/DIST; camera↔LiDAR extrinsic certified at panorama scale (GOLDEN_360 §9); τ_cam↔lidar ≈ +180 ms measured; the compressed node stamps `now()` not PTS (ADR-003 #1, still open).
- Tools on Shadow: RealityScan 2.2 (free tier), Anaconda `rigstation`, kiss-icp (py3.12), Open3D available. UE 5.8 (the last UE5; UE6 EA targeted end-2027).
- Shadow cannot virtualize (no Docker/WSL2) → Linux-only tools run on the Jetson.

---

## 2. ADR-005 — THE FORWARD ROUTE

### Context (what the research settled)
1. **RealityScan 2.2** accepts an unordered metric cloud as **Mobile LiDAR** (PLY/E57/LAS/XYZ/PTS), with virtual cameras "taken from prior camera poses"; **Registration = Exact** keeps our frame and scale; **Features source = Color** is the default (the Intensity-vs-Color contradiction in the lineage is closed: Color); **Merge georeferenced components** merges "even without visual overlap"; **Default grouping factor** up = "laser scans will be prioritized for meshing"; **Correct colors** equalizes exposure across frames; exports FBX/GLB/USD with a single atlas up to 65 536 px or UDIM. 2.2 "Fixed a crash that occurred during alignment when using locked camera positions" — use 2.2, not 2.1.
2. **Camera priors:** XMP with `xcr:PosePrior="locked"`, `xcr:Rotation` = **world→camera, row-major, CV axes (x right, y down, z into scene)**, `xcr:Position` = camera centre; or `importTrajectory` (OPK in ENU / YPR in NED) or `loadColmap` (FULL_OPENCV supported since 2.1.1). 2.1 fixed "Omega and Kappa values are swapped in the export."
3. **RealityScan has no de-lighting and no Gaussian-splat training** (staff: "no, it wasn't created"); it exports COLMAP for external trainers (Postshot etc.).
4. **Unreal 5.8:** Nanite takes photogrammetry meshes directly; **Lumen wants walls/floors/ceilings as separate meshes, ≥10 cm thick**, a whole furnished room as one mesh "is not expected to work"; base colour must be albedo ("the color when photographed using a polarizing filter"); physical units (cd/lm/nits, EV100, Kelvin, IES with candela brightness, rect-light barn doors); **MegaLights production-ready** (orders of magnitude more shadowed area lights); OCIO 2.5.1 with ACES 2.0 built in; Path Tracer as ground truth. No native splats; LiDAR Point Cloud plugin for reference only.
5. **ARRI LUKA** (June 2026): UE plugin, "ARRI Virtual Fixtures are built using the detailed specifications of real lighting fixtures", works with any fixture that has IES data, Lumen-based, Art-Net/sACN + LiveLink, ARRI camera models + false colour, free 3-month trial (commercial pricing unpublished). **This is the predictive-lighting layer the mission described.**
6. **Blackout** = "Blackout Lighting Console" (iPad, Art-Net/sACN DMX). UE's DMX plugin "supports both Art-Net and sACN". Protocol-compatible; no documented integration — ours to build. **Set.A.Light 3D** imports FBX/OBJ/GLB via the 3D Import add-on (colour maps capped at 4096 px, one-way, no Unreal link) — it can receive a decimated copy of our mesh; it is not on the critical path.
7. **Relightable splats, 2026:** research only (GS-IR, R3DG, SGS-Intrinsic, AEGIR); commercially, Volinga Plugin Pro relights by **proxy meshes** (Studio/Enterprise tier). Our LiDAR mesh *is* that proxy. Splats stay a sidecar for as-lit walkthroughs.
8. **Texture ceiling:** Arducam fx = 849 px → **8.5 px/cm at 1 m, 4.2 at 2 m, 2.8 at 3 m**. A 1080p UE camera at 90° HFOV needs ~4.8 px/cm at 2 m; 4K or a 40° cine lens needs 13–26. A 24–45 MP stills camera gives 13–40 px/cm at 2–3 m. Metashape's stated minimum for photogrammetry is 5 MP; RealityScan says "use the highest resolution possible". Mixed sensors are a documented workflow (per-input **Weight in texturing**, **Calibration group**, LiDAR **Locked**).
9. **Honest geometry upgrade without Poisson:** TSDF with free-space carving from **per-frame registered scans** (Open3D VoxelBlockGrid on Windows via per-frame depth images; VDBFusion/PIN-SLAM on Linux); GS-SDF (hku-mars, LiDAR+camera → SDF mesh, Linux/CUDA). All need `/cloud_registered` per frame — which an offline re-solve can record.
10. **Scale beyond a room:** GLIM (Jetson Orin / JetPack 6.1 supported, loop closure, multi-session merge, `glim_rosbag`); UE World Partition / HLOD; split and tile meshes.

### Decision
- **D1. RealityScan 2.2 is the fuse/mesh/texture station (Route A, confirmed).** Inputs: the offline-re-solved cloud (colorized via `colorize_cloud.py`, imported Mobile LiDAR, **Exact**, Color) + undistorted frames with **locked XMP poses** written in the CV convention above. LiDAR-priority meshing, Correct-colours texturing, export GLB/FBX ×100 + UDIM/large atlas. Our baker (Route B) stays the fallback and the A/B check.
- **D2. Unreal 5.8 is the stage.** Nanite import (no lightmap UVs), **hardware-RT Lumen** (evaluates at the hit, less dependent on surface-cache cards), MegaLights, physical units, manual EV100 exposure, ACES 2.0 — and **ARRI LUKA on the trial** as the fixture library, driven over sACN/Art-Net from Blackout. Path Tracer renders as the ground-truth check.
- **D3. The LiDAR-dimensions shell (`planar_shell.py`) is promoted, not retired:** Lumen's "separate walls/floors/ceilings, ≥10 cm thick" rule is the planar shell's exact output shape. Shell = collision + light-blocking + Lumen-clean geometry; the RealityScan textured mesh = graphics. Both from the same B1.
- **D4. De-lighting = Agisoft Texture De-Lighter 2.3.2 (free) on the RealityScan atlas + flat-light capture discipline + Epic's HDR-panorama un-lighting method when a hero surface demands it.** The lineage's "Unreal/Quixel De-Lighter" does not exist — struck.
- **D5. Splats are a sidecar**, produced from RealityScan's COLMAP export (Postshot) when an as-lit walkthrough is wanted; promoted only if Volinga Pro (proxy-mesh relighting) earns its licence.
- **D6. Fidelity upgrade path is data, not a new rig:** (a) record `/cloud_registered` in every capture → TSDF/GS-SDF geometry; (b) a **stills pass** (24–45 MP, bracketed where possible) registered into the locked LiDAR frame as its own calibration group → hero textures; (c) GLIM on the Jetson for loop closure when captures leave the room; (d) hardware camera trigger retires τ (research thread, 20.13.74).

### Options considered
| Option | Fit for relight mission | Maturity | Why / why not |
|---|---|---|---|
| **A. RealityScan fuse → UE** (chosen) | High | Documented end to end; 2.1/2.2 added exactly our SLAM-cloud + trajectory pattern | Only route with LiDAR-priority meshing + multi-image colour-corrected texturing + locked metric frame, for free |
| B. Own baker (Poisson/shell + per-face bake) | Med | Built, rougher atlas, Poisson convicted | Fallback and A/B; shell survives as D3 |
| C. "Straight to Unreal" | — | UE has no photo-texturing; point-cloud plugin is reference-only | Not a route |
| D. Splat-primary (Postshot/Volinga) | Low (bakes light) | Mature as-lit; relight only via proxy meshes, paid | Sidecar (D5) |
| E. GS-SDF / neural SDF geometry | Med-High | Linux/CUDA research code | Geometry upgrade after A is proven (D6a) |

### Consequences
- Easier: one documented path to a walkable, dimensionally true, relightable room; predictive fixtures without writing a photometric model ourselves (LUKA); the shell finally has a job Lumen rewards.
- Harder: XMP writer must be exact (CV convention, locked, single extrinsic apply); capture adds a stills pass and flat-light discipline for hero rooms; `/cloud_registered` grows bags (~130 MB/90 s, acceptable).
- Revisit: when UE6 EA lands (end-2027) or when relightable splats become commercial-with-shadows.

---

## 3. SYSTEM DESIGN v3 — the stages, with what is PROVEN today

```
 JETSON (capture + offline Linux solve)         SHADOW (Windows station)                       UNREAL 5.8 (Shadow)
 ─────────────────────────────────────         ────────────────────────────                   ───────────────────
 [S0] CAPTURE (raw only)                        [S2] AUTOPSY + CONTROL IMAGES                  [S6] STAGE
   /unilidar/cloud + /unilidar/imu                 bag_motion → bag_health → top_down            Nanite (no lightmap UVs)
   + /camera/image_raw/compressed                  gate: clean floor plan (eye)                   HW-RT Lumen + MegaLights
   no live Point-LIO, no browser                        │                                          physical units, EV100, ACES 2.0
        │                                               ▼                                          ARRI LUKA fixtures (IES)
        ▼                                       [S3] REGISTER (B1)                                  DMX plugin ⇐ Blackout (sACN)
 [S1] RE-SOLVE (offline, L2 OFF)                   colorize_cloud → cloud_COLOR.ply                 Path Tracer = truth
   resolve_pointlio.sh stock (+ /cloud_registered)  frames (undistorted) + XMP locked (CV conv.)       ▲
   → scans.pcd + odom bag                           gate: XMP round-trip exact, 1 extrinsic apply       │
   (GLIM for loop closure, later)                       │                                              │
        │                                               ▼                                              │
        └──── Taildrop ───────────────▶         [S4] REALITYSCAN 2.2  ──────────── GLB/FBX ×100 ───────┤
                                                   Mobile LiDAR Exact, Color · align (locked)          │
                                                   gate: ONE component, ≥90 % cams, reproj < 3 px      │
                                                   mesh LiDAR-priority · texture Correct colors         │
                                                        │                                              │
                                                        ▼                                              │
                                                [S5] DIMENSIONS + DELIGHT                              │
                                                   planar_shell → wall/floor/ceiling meshes ≥10 cm ─────┤ (collision + Lumen shell)
                                                   Agisoft De-Lighter → albedo atlas ──────────────────┘ (graphics)
                                                   (sidecar: COLMAP export → Postshot splat)
```

**Stage contracts and gates (each must pass before the next consumes it):**
- **B0 raw capture:** cloud 12 Hz (no live drops), IMU ~251 Hz, camera present, `bag_motion` row sane; 15 s still start.
- **B1 re-solve:** `top_down` = one crisp outline beside the 180551 control; `bag_health` heading tracks the gyro (≤ 5°); no flyers (z-range a room).
- **B2 register:** XMP round-trip exact; extrinsic applied once at export (not again in RS); frame filenames carry the ns `header.stamp` (RS keeps no timestamps).
- **B3 RealityScan:** one component after align; ≥ 90 % cameras; max reprojection ≤ 3 px (RS guidance); cones point inward (no XMP flip); LiDAR merged (Exact/Color, or control points ≥ 3 CPs on ≥ 3 images/LSPs per staff).
- **B4 mesh/texture:** mesh follows the LiDAR (no photo-stereo melt); tape-measure check: an in-engine dimension matches the room; texture reads as the room (eye).
- **B5 UE:** character walks; day→night with a LUKA SkyPanel reads plausibly against a phone photo of the real room at night (the mission's own test); Path Tracer vs Lumen agree.

---

## 4. TECH-DEBT REGISTER (scored: Priority = (Impact + Risk) × (6 − Effort))

| # | Item | Type | I | R | E | Pri | Fix |
|---|---|---|---|---|---|---|---|
| 1 | **Live Point-LIO is still the capture's geometry of record** (kiosk CAPTURE runs it live; bags from `capture_pointlio_texture.sh` have no `/unilidar/cloud`) | Architecture | 5 | 5 | 2 | **40** | `capture_raw.sh` in the CAPTURE slot (cloud+imu+compressed, no PLIO); retire the texcap fork; bless |
| 2 | `/cloud_registered` not recorded by the re-solve → TSDF/GS-SDF path blocked | Architecture | 4 | 3 | 1 | **35** | add the topic to `resolve_pointlio.sh`'s recorder (one line) |
| 3 | `rig_camera_compressed.py` stamps `now()` at drain, not buffer PTS (τ jitter; ADR-003 #1) | Code | 4 | 4 | 2 | **32** | stamp from GStreamer PTS mapped once to ROS time; verify τ with `tau_solve_v2` |
| 4 | XMP/pose writer unverified against RS 2.2 (CV convention, locked prior, single extrinsic apply) | Test | 5 | 4 | 3 | **27** | synthetic round-trip test; `pose_xmp_roundtrip.py` exists — re-run against the June-2026 coordinate-systems PDF |
| 5 | Offline toolset not in `rig-files`; `pointlio_pose_matcher.py` md5 split | Doc/Infra | 3 | 4 | 1 | **35** | push `top_down`, `bag_health`, `bag_motion`, `resolve_pointlio`, `tau_solve_v2`, `make_full_pan_anchor` (portable) ; reconcile md5 |
| 6 | GOLDEN_360 recipe's reference numbers were built on a drifted cloud; II-H static-coverage claim; 09-24 retraction | Doc | 3 | 4 | 1 | **35** | rebase the recipe on an offline-re-solved bag; fold IX-F corrections |
| 7 | Dual calibration sources (`fuse_pano` embeds K; `fuse_to_fbx` loads yaml) | Code | 3 | 3 | 2 | 24 | one `calib.yaml`, both load it |
| 8 | Bundle format split (`img_%03d.jpg` vs `img_%05d.png`) | Code | 2 | 3 | 2 | 20 | one bundle schema (B1 `posed_images.npz` + `img_%05d`) |
| 9 | Poisson still in `fuse_to_fbx.py` | Code | 3 | 3 | 2 | 24 | TSDF from per-frame scans (after #2) or RS mesh; delete Poisson |
| 10 | Jetson freeze: kiosk 3D render on the Jetson (II-I fix untested) | Infra | 4 | 4 | 2 | 32 | server on Jetson, view from Shadow; `tegrastats` before capture |
| 11 | No sharpness / overlap gate on frames (RS needs sharp, >60 % overlap, ≤30° view change) | Test | 3 | 3 | 2 | 24 | `frame_qc.py` exists — wire it as a B2 gate |
| 12 | Docs claim a non-existent "Unreal/Quixel De-Lighter"; Intensity-vs-Color contradiction | Doc | 2 | 2 | 1 | 20 | strike; Color is RS default |
| 13 | `bag_motion.py` thresholds miscalibrated (accSD walk/pan; still-start noise floor ~1.7 °/s) | Code | 2 | 2 | 1 | 20 | recalibrate on 180551/180728 |
| 14 | Masters: 69/69(1) incomplete; lineage corrections scattered | Doc | 2 | 3 | 2 | 20 | 20.13.78 consolidates IX-F + today's six |
| 15 | τ_imu↔lidar never measured; LI-Init unusable for us | Research | 2 | 2 | 4 | 8 | parked — offline re-solves are clean without it |

---

## 5. THE WORK-BACK ROADMAP (gated; the eye decides every gate)

**Target state (the deliverable that validates the rig):** one real room, walkable in UE 5.8, dimensionally true (tape check), textured from our photos, de-lit, relit day→night with a LUKA SkyPanel from the Blackout console, judged against a photo of the real room at night.

**Working back from it:**

- **Phase 4 — Stage it (UE).** Import GLB ×100, Nanite, HW-RT Lumen, MegaLights; LUKA trial; manual EV100; ACES 2.0; DMX plugin on sACN; Path Tracer check. *Needs:* a textured mesh + shell + albedo atlas. *Gate B5.*
- **Phase 3 — Make the asset (RealityScan 2.2 + shell + De-Lighter).** Mobile LiDAR Exact/Color + locked XMP frames → one component → LiDAR-priority mesh → Correct-colours texture → GLB/UDIM; `planar_shell` → separate wall/floor/ceiling meshes; Agisoft De-Lighter → albedo. *Needs:* a verified XMP writer (#4), a clean re-solved bag with camera frames, `frame_qc` gate (#11). *Gates B2–B4.*
- **Phase 2 — Pick and prepare the first bag (no rig).** Candidates already on disk: **130955** (5 rooms, 2633 frames of camera? — its `rs_export` keyframes exist; check the compressed topic span) and **180551** (control; camera died at 14 s → geometry-only). Re-solve with `/cloud_registered` recorded (#2); `colorize_cloud`; export frames with ns-stamped names; write XMPs. *Gate B1.*
- **Phase 1 — Close the capture loop (one rig session).** `capture_raw.sh` blessed (#1); kiosk render off the Jetson (#10); the D5 stand-pan capture recorded RAW → re-solved → top-down (ADR-004 Accepted); then a **hero-room capture**: 15 s still → Golden walk with pans accepted → stop-and-shoot at hero surfaces → flat light. *Gate B0 + B1.*
- **Phase 0 — Now (no rig, today/tomorrow).** Bank 20.13.78; add `/cloud_registered` to the resolver; re-run `bag_health` thresholds (#13); push the toolset to `rig-files` (#5); strike the doc errors (#12).

**After the first relightable room:** Phase 5 fidelity (stills pass as its own calibration group, HDR brackets, texel ≥ 10 px/cm on hero walls); Phase 6 scale (GLIM loop closure on the Jetson, multi-session merge, World Partition tiles); Phase 7 sidecar (COLMAP → Postshot splat; Set.A.Light import of a decimated copy for the lighting-design side).

---

## 6. DEAD END OR EXPANDABLE? — the verdict, with limits

**Expandable.** The cloud + poses are what every tool locks to; the photos are replaceable and upgradeable without touching the rig. Concretely:

| What the current data becomes | Enough for | Not enough for |
|---|---|---|
| Honest ~2 cm metric architecture (walls, floors, openings, furniture masses) | light placement, shadow casting, collision, blocking, Lumen shell, Volinga proxy | sub-2 cm detail (mouldings, fabric), watertight closure of unseen regions |
| Textured mesh at ~3–4 px/cm (2–3 m capture distance) | 1080p previs wide shots, lighting prediction, scouts | 4K, 40° cine lenses, close-ups — needs the stills pass (13–40 px/cm) |
| De-lit albedo (Agisoft + flat light) | plausible day→night with real fixtures | physically exact BRDFs ("delighting in strong shadows is not supported") |
| LiDAR-depth-supervised splat (sidecar) | photoreal as-lit walkthrough at camera resolution | Lumen relight (no native splats; proxy-mesh relight is paid) |

**Unlocks, in order of leverage:** (1) per-frame `/cloud_registered` → TSDF/GS-SDF honest surfaces; (2) a stills pass locked to the LiDAR frame → hero textures; (3) GLIM → rooms become floors and streets; (4) hardware trigger → τ retired; (5) UE6 / relightable splats → revisit D5.

---

## 7. SOURCES (primary)
- RealityScan help: import LiDAR https://rshelp.capturingreality.com/en-US/tutorials/importlaser.htm (+ `_2.htm`); alignment settings https://rshelp.capturingreality.com/en-US/appbasics/alignsettings.htm ; model settings (grouping factor) https://rshelp.capturingreality.com/en-US/appbasics/modelsettings.htm ; texturing (Correct colors, texel size) https://rshelp.capturingreality.com/en-US/tools/texturing_part2.htm ; XMP https://rshelp.capturingreality.com/en-US/tools/xmpalign.htm ; trajectory https://rshelp.capturingreality.com/en-US/tools/flightlogimport.htm ; export https://rshelp.capturingreality.com/en-US/tools/export.htm ; selected inputs (weight, calibration group, locked) https://rshelp.capturingreality.com/en-US/appbasics/selectedinputs.htm ; merge by control points https://rshelp.capturingreality.com/en-US/tutorials/mergecomponents_cp.htm ; taking pictures https://rshelp.capturingreality.com/en-US/tutorials/takingpictures.htm
- RealityScan release notes 2.1 / 2.1.1 / 2.2: https://dev.epicgames.com/documentation/realityscan/release-notes ; coordinate-systems reference (Hornáček, 2026-06-08): https://dev.epicgames.com/documentation/realityscan/camera-geometry-in-realityscan-camera-models-and-coordinate-systems-reference ; licensing https://www.realityscan.com/licensing ; staff answers https://forums.unrealengine.com/t/aligning-lidar-and-photogrammetry/2595131 , https://forums.unrealengine.com/t/aligning-dslr-photos-to-slam-lidar-component-without-deforming-internal-camera-poses/2707328 , de-lighting https://forums.unrealengine.com/t/delighting-tool/708904
- Unreal 5.8: release notes https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes ; MegaLights https://dev.epicgames.com/documentation/en-us/unreal-engine/megalights-in-unreal-engine ; Lumen technical details https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine ; Nanite https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine ; physical light units https://dev.epicgames.com/documentation/en-us/unreal-engine/using-physical-lighting-units-in-unreal-engine ; IES https://dev.epicgames.com/documentation/en-us/unreal-engine/using-ies-light-profiles-in-unreal-engine ; auto exposure https://dev.epicgames.com/documentation/en-us/unreal-engine/auto-exposure-in-unreal-engine ; PBR https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine ; LiDAR point cloud plugin https://dev.epicgames.com/documentation/unreal-engine/lidar-point-cloud-plugin-overview-in-unreal-engine ; DMX https://dev.epicgames.com/documentation/en-us/unreal-engine/dmx-overview ; World Partition https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine ; 5.8 news https://www.unrealengine.com/en-US/news/unreal-engine-5-8-is-now-available
- ARRI LUKA: https://www.arri.com/en/solutions/workflow-innovation/luka , https://www.arri.com/en/solutions/workflow-innovation/digital-twins , https://www.cined.com/arri-luka-unreal-engine-plugin-announced-virtual-arri-lights-and-cameras-real-time-lumen-previs-dmx-and-livelink-control/
- Blackout Lighting Console: https://apps.apple.com/app/id1414562959 ; Set.A.Light 3D import: https://www.elixxier.com/en/docs/set-a-light-3d/reference/file-formats/ , https://www.elixxier.com/en/docs/set-a-light-3d/workflows/import-a-location-or-prop/
- Splats/relight: Volinga Pro https://www.cgchannel.com/2026/08/volinga-plugin-pro-lets-you-relight-4dgs-data-inside-unreal-engine/ ; XScene https://github.com/xverse-engine/XScene-UEPlugin ; GS-IR https://arxiv.org/abs/2311.16473 ; R3DG https://arxiv.org/abs/2311.16043 ; SGS-Intrinsic https://arxiv.org/abs/2603.27516 ; DiffusionRenderer https://arxiv.org/abs/2501.18590
- Geometry: GS-SDF https://github.com/hku-mars/GS-SDF ; Open3D VoxelBlockGrid https://www.open3d.org/docs/release/python_api/open3d.t.geometry.VoxelBlockGrid.html ; VDBFusion https://github.com/PRBonn/vdbfusion ; PIN-SLAM https://github.com/PRBonn/PIN_SLAM ; DN-Splatter https://github.com/maturk/dn-splatter ; GLIM https://github.com/koide3/glim
- De-lighting: Agisoft Texture De-Lighter https://agisoft.freshdesk.com/support/solutions/articles/31000158376-agisoft-texture-de-lighter-general-workflow ; Epic Kite un-lighting https://www.unrealengine.com/en-US/blog/creating-assets-for-open-world-demo ; Metashape manual (laser scans, 5 MP, HDR) https://www.agisoft.com/pdf/metashape-pro_2_3_en.pdf
- Practice: U. Melbourne NExT Lab LiDAR×photogrammetry https://ms-kb.msd.unimelb.edu.au/next-lab/3d-scanning/guides/combining-lidar-x-photogrammetry ; texel density https://rebusfarm.net/blog/texel-density-basics-every-artist-should-know
