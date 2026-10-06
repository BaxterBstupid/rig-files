# RealityScan photo + LiDAR merge — the DOCUMENTED procedure (incident write-up, 2026-10-05)

**Status:** Identified (procedure documented, not yet executed) · **Severity:** SEV2 (the deliverable is blocked at one stage)
**Scope:** getting our 900 photos (XMP priors) and our Point-LIO cloud (`cloud_color.ply`) into ONE RealityScan component so the mesh is built from LiDAR geometry and textured from photos.
**Sources:** every claim below carries a link. Read the links; they are short.

---

## 1. Timeline — every attempt, what was done, what RealityScan did

| Date | What went in | Settings | Result |
|---|---|---|---|
| 09-15 | 180551 cloud, intensity PLY | LiDAR Scan, Intensity | 33 `_intensity.lsp` views, unreadable; no CPs possible |
| 09-16 | 095447 cloud, 2.7 % coloured, cloud only | LiDAR Scan, **Color** | one component, 3/3 virtual cams, 29 tie-points, "0 models" |
| 09-17/18 | 163005: 422 PNG + locked XMP, photos only | defaults | **Component 0, 422/422, ~2 800 tie-pts/img** (STAGE 2 proven) |
| 09-18 | + 163005 cloud, Intensity, 33 LSPs | Intensity | Component 0 (422 photos, 1 model = the triangle-soup "blob", 9 750 pts) + Laserscan 33 + two duplicates of the 33 |
| 09-18 | CloudCompare Poisson on the colour cloud | — | blob (Poisson, not RealityScan) |
| 09-21 | 422 photos + 422 virtual cams (from priors) + 8 GCPs **measured in photos only** | Intensity | six components (0, Laserscan, 0(1), 1, 0(2), 1(1)); "co-registered 0.00 m, not merged"; two separate FBX to UE |
| 09-24 | 141733: 324 keyframes, no XMP, no cloud | from scratch | 281 + 40 (99 %), 3.8–8.3 K tie-pts/img |
| 10-05 | 130955 v3: 900 JPEG + XMP (exact) + 97 % coloured cloud | Mobile LiDAR, Exact, **Color**, Georef = No, from priors | Laserscan 900 + Component 0 (photos) + Component 1 (duplicate of the LSPs); LSPs 57–242 features |
| 10-05 | same project, *Merge georeferenced components* = Yes, F6 | cloud still Georef = No | four more duplicates; nothing merged |

The "blobs" were never a LiDAR mesh. 09-18's mesh was built from the **photo component alone** (RealityScan reconstructs one selected component at a time — FUSION_SOLUTION §0), and the CloudCompare blob was Poisson. The LiDAR has **never been inside the component that was meshed.**

## 2. Root cause — what the documentation actually says

1. **An LSP is treated as an ordinary image.** "After conversion you continue like if .lsp file was an ordinary image… You do not need to do anything special" — [Combining Photos & LiDAR Scans](https://rshelp.capturingreality.com/en-US/tutorials/laserandimages.htm); "registration, meshing, texturing… works exactly like for images" — [LiDAR Scans, part 2](https://rshelp.capturingreality.com/en-US/tutorials/importlaser_2.htm). So photos and LSPs join one component **only** by feature matches between them, or by control points. Our LSP views are pale renders of the cloud (57–242 features) and our 130955 photos are motion-blurred (var-Laplacian 68–145, WATERTIGHT A2) → no cross-matches → separate components. Every time.
2. **"Merge georeferenced components" never applied.** Its definition: "When multiple components are created and **each is georeferenced**, enabling this setting allows them to be merged even without visual overlap" — [Alignment Settings](https://rshelp.capturingreality.com/en-US/appbasics/alignsettings.htm). The cloud was imported Georeferenced = No in every attempt, so no attempt ever tested it. (And making the cloud Georeferenced = Yes has a cost — see §4.)
3. **The staff answer for exactly our situation is control points, with a specific step order.** Three threads, 2016 → 2026, same answer from Epic's Ondrej Trhan:
   - "When you have generated two components (first from images and second from scans) then use control points there… minimally three points, but more is better… on minimally three images and also three LSP" — [Need help combining laser scan and photogrammetry](https://forums.unrealengine.com/t/need-help-combining-laser-scan-and-photogrammetry/712196)
   - "at least 3 CPs placed over at least 3 images/LSPs" — [Aligning LiDAR and photogrammetry](https://forums.unrealengine.com/t/aligning-lidar-and-photogrammetry/2595131)
   - "Firstly align, then set Lock pose for continue for the component", then control points to merge — [Aligning DSLR photos to SLAM LiDAR component](https://forums.unrealengine.com/t/aligning-dslr-photos-to-slam-lidar-component-without-deforming-internal-camera-poses/2707328) (a SLAM cloud + separate camera, March 2026, RealityScan 2.1 — our case)
   - Control-point minimums in the help: "Create at least 4 control points, such that all of them are assigned to more than one image **in every component**"; to connect two components, "any 6 control points" — [Merging Components Using Control Points](https://rshelp.capturingreality.com/en-US/tutorials/mergecomponents_cp.htm)
4. **Why our two control-point attempts failed, per the same docs.** 09-15/09-18: intensity LSPs were unreadable, so no CP could be placed on an LSP. 09-21: the 8 GCPs were placed in photos only — zero placements in the Laserscan component — which the help page explicitly rules out ("in every component"). The colour LSPs rendered from photo poses (today's 2D pane) are the first LSP views we have ever had that a human can place a point on.
5. **Exact + Georeferenced = No is the correct import for a CP merge.** Staff: "Exact: imported poses will be preserved; in this case the imported model defines the scene coordinate system"; two exact **georeferenced** sets ignore control points and "stack"; the fix is "exact but Georeferenced = No", which "permits control-point-based merging while maintaining scan integrity" — [How to merge 2 laser-scan components imported with exact registration](https://forums.unrealengine.com/t/how-to-merge-align-2-laser-scan-components-imported-with-an-exact-registration/2418588). So the 20.13.54 "Exact/Local" note and the Master 78 "Georeferenced = No" are not in conflict for this path: **No** is right.
6. **Virtual cameras come from priors or from a component.** 2.1 release notes: "First import images and their trajectories, or open a Colmap Scene… Import the point cloud and generate virtual cameras based on camera pose priors or an imported component" — [RealityScan 2.1](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-1). Import dialog: "Use camera poses: taken from prior poses, existing registered component, or auto-generated; Extract from component" — [LiDAR Scans](https://rshelp.capturingreality.com/en-US/tutorials/importlaser.htm). Generating from an **aligned component** gives LSP views at the solved photo poses, which is the best possible chance of automatic matching and makes CP placement trivial (each LSP view is the same framing as a photo).
7. **XMP prior type.** "exact" = relative positions preserved, absolute free; "locked" = relative and absolute fixed — [XMP](https://rshelp.capturingreality.com/en-US/tools/xmpalign.htm). The SLAM thread shows locked absolute priors on both sides → "two separate coordinate systems"; the staff fix is the *relative* lock ("Lock pose for continue": "Lock the relative positions of the selected cameras in the selected component for further processing" — [Selected inputs](https://rshelp.capturingreality.com/en-US/appbasics/selectedinputs.htm)). Our rs_bundle writes **exact** — that is the right prior for this path. Do not switch to locked for the merge.

## 3. THE PROCEDURE (documented; every step cites its source). Fresh project. One step per turn.

0. **Inputs:** `C:\rig\rs\rsbundle_130955_v3\images\*.jpg + .xmp` (PosePrior exact), `cloud_color.ply`.
1. **New project.** ALIGNMENT → Settings: *Max feature reprojection error* = 3 px ("set it maximum to 3px" — [Alignment Settings](https://rshelp.capturingreality.com/en-US/appbasics/alignsettings.htm)). Leave *Merge georeferenced components* = No (nothing is georeferenced on this path). Leave camera-prior settings default (STAGE 2 proven with defaults, 20.13.60).
2. **Photos only:** WORKFLOW → Folder → `images\` → **Align Images (F6)**. GATE: ONE Component 0, ≥ 90 % of 900, cones inward (STAGE 2). Nothing else is in the project yet.
3. **Cloud, generated from the component:** WORKFLOW → **LiDAR Scan** → `cloud_color.ply`: LiDAR type **Mobile LiDAR**, Registration **Exact**, Georeferenced **No**, Features source **Color**, Use camera poses **From component → Component 0** ([LiDAR Scans](https://rshelp.capturingreality.com/en-US/tutorials/importlaser.htm); [2.1 notes](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-1)). Result: a Laserscan component of `_color.lsp` views at the solved photo poses.
4. **Relative-lock the photos:** 1Ds → Component 0 → Camera poses → select all 900 → Selected input(s) → **Lock pose for continue = Yes** ("Firstly align, then set Lock pose for continue" — [SLAM thread](https://forums.unrealengine.com/t/aligning-dslr-photos-to-slam-lidar-component-without-deforming-internal-camera-poses/2707328)).
5. **One F6, as the cheap test.** If Component 0 now reports 1800 cameras → merged by features; go to 8. If still Component 0 (900) + Laserscan (900) → step 6. (Do **not** F6 repeatedly — each pass breeds duplicate components; the recipe GOTCHA and the SLAM thread both record this.)
6. **Control points — the staff procedure.** ALIGNMENT → Add Control Points. Make **6** CPs ([merge-by-CP page](https://rshelp.capturingreality.com/en-US/tutorials/mergecomponents_cp.htm)), each placed on **≥ 3 photos AND ≥ 3 `_color.lsp` views** (staff minimum 3/3 — [712196](https://forums.unrealengine.com/t/need-help-combining-laser-scan-and-photogrammetry/712196)), spread around the room, on fixed hard corners (frame corners, mantel edge, outlet, door jamb), never on soft furnishings or the mirror. Open each `_color.lsp` from the Laserscan component in the 2D view; it has the same framing as its photo, so the same corner is found in seconds. "You don't need physical control points… it is also possible to do it with features" (Trhan, 712196). Spread matters: "if they would be concentrated to small area it can cause not very precise alignment" ([PTX + Photos](https://forums.unrealengine.com/t/ptx-photos/706878)).
7. **F6 once.** GATE: ONE component containing 1800 (900 photos + 900 LSPs). Check CP reprojection errors (1Ds → Control points) — all ≤ 3 px.
8. **Mesh:** MESH & COLOR → Settings → raise *Default grouping factor* (LiDAR-priority) → region → Normal Detail. Texture: Correct colors = Yes. **GATE: reads as the room — the eye.** Only then export.

## 4. The alternative that is documented but NOT staff-recommended for our case
*Merge georeferenced components* with both sides georeferenced (photos: *Use camera priors for georeferencing* = Yes; cloud: Georeferenced = Yes, local:1). The setting's own definition supports it, but the laser-scan thread above shows that an exact + georeferenced cloud then **ignores control points**, so this route forfeits the staff fallback. Try it only if §3 step 7 fails outright, in a separate fresh project.

## 5. What the docs say about the next capture (so this is not re-fought)
- Photos must be sharp and overlapping; blur "split[s] components and raise[s] reprojection error" (ADR-003 #4; `frame_qc.py` exists, not yet wired as a gate). 130955 is blurry (shot 09-23, before the 09-30 shutter lock).
- RealityScan keeps no timestamps; the ns stamp in the filename is the only join key (RS post-mortem doc).

## 6. Tech-debt register — contradictions this write-up retires (Impact+Risk)×(6−Effort)
| # | Item | Fix | Score |
|---|---|---|---|
| 1 | Master 78 step 4: "Lock pose for continue on the **LiDAR** component" | It is on the **photo** component, after aligning them (2707328) | (5+4)×5 = 45 |
| 2 | Master 78 step 1: Merge georeferenced components = Yes, while the cloud is Georeferenced = No | Remove; meaningless on this path (alignsettings definition) | (4+4)×5 = 40 |
| 3 | FUSION_SOLUTION A1: "Intensity is the root cause of the split" | Refuted 10-05 (Color split identically). Color is necessary (readable LSPs), not sufficient | (4+3)×5 = 35 |
| 4 | STAGE 3 recipe: CPs "≥ 4, each on ≥ 2 photos and ≥ 2 .lsp" vs staff/help | 6 CPs, each on ≥ 3 photos AND ≥ 3 LSPs, in every component | (4+3)×5 = 35 |
| 5 | 09-21 "8 GCPs" recorded as a merge attempt | They were photo-only; not a valid CP merge (help: "in every component") | (3+3)×5 = 30 |
| 6 | 20.13.54 "Exact/Local" vs Master 78 "Georeferenced = No" | No is correct for the CP path (2418588); Local only for the §4 alternative | (3+3)×5 = 30 |
| 7 | rs_bundle README v4 click-sequence | Rewrite to §3 (v5) | (3+2)×4 = 20 |
| 8 | `frame_qc` not a gate; blur reaches RS | Wire as B2 gate (FORWARD_PLAN #11) | (3+3)×3 = 18 |
| 9 | Master 78 "images first then cloud" implies that alone fuses | Keep the order (2.1 notes) but state that fusion needs matches or CPs | (2+2)×5 = 20 |

## 7. Sources (all read 2026-10-05)
- https://rshelp.capturingreality.com/en-US/tutorials/laserandimages.htm — Combining Photos & LiDAR Scans
- https://rshelp.capturingreality.com/en-US/tutorials/importlaser.htm — LiDAR Scans (import dialog, Mobile LiDAR, Use camera poses / Extract from component)
- https://rshelp.capturingreality.com/en-US/tutorials/importlaser_2.htm — LiDAR Scans, registration (Exact / Draft / Unregistered)
- https://rshelp.capturingreality.com/en-US/appbasics/alignsettings.htm — Alignment Settings (verbatim definitions)
- https://rshelp.capturingreality.com/en-US/appbasics/selectedinputs.htm — Selected input(s): Lock pose for continue, Enable in component, prior pose types
- https://rshelp.capturingreality.com/en-US/tutorials/mergecomponents.htm — Merging Components (the five ways)
- https://rshelp.capturingreality.com/en-US/tutorials/mergecomponents_cp.htm — Merging Components Using Control Points (4 min / 6 to connect two)
- https://rshelp.capturingreality.com/en-US/tools/controlpoints.htm — Control points
- https://rshelp.capturingreality.com/en-US/tools/xmpalign.htm — XMP (exact vs locked)
- https://rshelp.capturingreality.com/en-US/appbasics/components.htm — Component workflow
- https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-1 — 2.1 release notes (SLAM workflow order)
- https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-2-2 — 2.2 release notes (locked-camera alignment crash fixed)
- https://forums.unrealengine.com/t/aligning-dslr-photos-to-slam-lidar-component-without-deforming-internal-camera-poses/2707328 — staff, March 2026
- https://forums.unrealengine.com/t/aligning-lidar-and-photogrammetry/2595131 — staff, 2025
- https://forums.unrealengine.com/t/need-help-combining-laser-scan-and-photogrammetry/712196 — staff
- https://forums.unrealengine.com/t/how-to-merge-align-2-laser-scan-components-imported-with-an-exact-registration/2418588 — staff (exact + georeferenced ignores CPs)
- https://forums.unrealengine.com/t/ptx-photos/706878 — CP spread
- https://forums.unrealengine.com/t/tutorial-slam-support/2678560 — SLAM/COLMAP import tutorial thread
