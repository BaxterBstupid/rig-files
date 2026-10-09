<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.81, 2026-10-09) *****            -->
<!-- Additive layer on 20.13.80 (Stone Clause: nothing lost; 80 is verbatim below).       -->
<!-- THE EYE SAID FAIL on the first merged mesh — and the fail was SPLIT the same day:     -->
<!--   GEOMETRY: every surface carries a uniform cm-scale ripple (Solid render). It is the -->
<!--     LiDAR block's: photos alone cannot mesh this capture at all (905 K tris of wisps). -->
<!--   TEXTURE: grey smear, wrong colour. NOT the LiDAR views' colour (their texturing      -->
<!--     weight is 0.01 by default; photos-only texture = same smear). It is sharp,        -->
<!--     colourful photos averaged across rippled geometry.                                -->
<!--   => one root: the cloud's surface noise. Fix it upstream of RealityScan.             -->
<!-- TWO RS FACTS THAT COST A RUN EACH: -selectImage regex must be written g/.../ (a bare   -->
<!--   pattern is a path and selects NOTHING, silently) — so the photo lock in every lidar -->
<!--   run so far applied to zero photos (the merge held on priors alone); and             -->
<!--   -enableMeshing / -enableTexturingAndColoring act on the selection (observed).       -->
<!-- WORK FROM: XII below, then RESUME_HERE.md. Rig state unchanged: L2 OFF; Shadow only.  -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  20.13.81 — THE EYE: FAIL, SPLIT AND ROOT-CAUSED (2026-10-09)
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

## XII-A. THE EYE ON THE FIRST MERGED MESH (S4_mesh_georef.rsproj, GUI, Project Files 2026-10-09 103210 → 112356, 1bMesh_georef_mantel_solid.png)

Mesh facts: Model 1 = 3,342,012 triangles / 1,667,892 vertices, one part, texture 16 384 → RS wrote one 8192×8192 diffuse (70,077,416 B). Built in 822 s on 1800 inputs (3.50 GB RAM, reconstruction 129 s).

| gate item (CANONICAL_ROOM_GEOGRAPHY) | seen | verdict |
|---|---|---|
| one rectangular room, one arch, one fireplace wall | yes — the reconstruction box is one volume, the arch is an arch, the chimney breast returns, the red lamp is where it belongs, no second copy of anything | **merge holds** |
| flat walls, straight frames | **no** — in Solid every surface (walls, ceiling, arch soffit) carries the same uniform centimetre ripple, "sandpaper", with horizontal corduroy rows on the ceiling | **GEOMETRY FAIL** |
| mantel, firebox, gilt mirror, lamp readable in texture | **no** — grey-brown smear with no edges; the panorama has pale-blue walls and white trim; only the lamp's red survives | **TEXTURE FAIL** |
| floaters, torn sheets near the floor | present | cosmetic; not the gate |

Operator: "Its so bad I can't find the mantle" (on the photos-only mesh, XII-B run 2).

## XII-B. THE SPLIT — three meshes from THE MERGE, same recipe, one switch each (all headless, GUI closed, gate PASS, FBX/PNG guard "different")

| run | switches | RAM / reconstruction | result | what it proves |
|---|---|---|---|---|
| 1 baseline `S4_mesh_georef` (10-08) | photos + LSP views mesh and texture | 3.50 GB / 129 s | 3.34 M tris, rippled, grey | — |
| 2 `S4_mesh_georef_photosmesh_photostex` | LSP views `-enableMeshing false` + `-enableTexturingAndColoring false` | **1.03 GB / 56 s**, FBX 28 MB | **905,210 tris of wisps and tilted sheets; no floor, no walls, no mantel** (Screenshot 160457/160634/160712) | the photos of 130955 cannot triangulate geometry on their own; **the LiDAR is the geometry** (ADR-001 fork confirmed the hard way) |
| 3 `S4_mesh_georef_photostex` | LSP views `-enableTexturingAndColoring false` only | 3.50 GB / 100 s | same 3.34 M-tri ripple; texture 8192², 69,597,581 B (0.7 % from baseline); **same grey smear** (Screenshot 165043/165116) while the selected photo's 2D thumbnail is a sharp, colourful, well-exposed room | the smear is not LiDAR colour; it is photos projected onto rippled geometry and averaged across ~900 misregistered views (misregistration → desaturation) |

A first attempt at run 2 produced a byte-near-identical FBX (109,667,232 vs 109,664,768 B, same 3,342,012 triangles) — the switches had selected nothing (XII-C #1). It is in `out_130955` as the overwritten `_photosmesh_photostex` of 15:30; the 16:5x files are the real run.

**Reading.** One root cause for both halves: the cloud's cm-scale surface noise (planar_shell measured our room clouds at ~16 mm plane thickness = L2 sensor limit; the LSP views are also rendered at 1/8–1/4 size, so their depth is coarse). RealityScan meshes the noise faithfully, then the photos — which are fine — cannot land on it. The merge is not the suspect; RealityScan is not the suspect; the mesh recipe is right as far as it goes. The fix is a smoother/snapped cloud before the LiDAR import, then the same three commands.

## XII-C. FACTS LEARNED (each cost a run; now in the emulator and the suite — 67 checks PASS)

1. **`-selectImage` takes a direct image path, or a regular expression written `g/…/`** (RS help "Examples of image selection": `-selectImage g/DSC.*[02468]\.jpg/`). A bare pattern such as `.*\.[lL][sS][pP]` is read as a path, matches nothing and says nothing. [DOC + OBS 2026-10-09: `enableMeshing false` after a bare regex changed no triangle.] Driver now uses `g/\.[jJ][pP][gG]/` and `g/\.[lL][sS][pP]/`.
2. **Lineage correction:** every `lidar` run to date (adopt excluded) issued `-selectImage ".*\.[jJ][pP][gG]" set -lockPoseForContinue true` → zero photos were locked. THE MERGE (XI) was obtained with free photos held by their exact XMP priors + `sfmMergeGeoreferencedComponents`; the lock contributed nothing. XI-B's "lock photos" step is retained in the recipe (now effective) but is **not** part of what made the merge; 20.13.79 §2 #3 / 20.13.80 XI-B are corrected here, not deleted.
3. `-enableMeshing true|false` and `-enableTexturingAndColoring true|false` act on the selected inputs, laser-scan views included; the flags persist in the saved project (Selected input panel showed "Enable meshing: Disable / Enable texturing and coloring: Disable" on the LSP). [DOC: RS help "Commands for Selected Images"; OBS 2026-10-09.] `-editInputSelection key=value` with `inpMeshing`, `inpTexturing`, `inpImageColorsWeight` (0–1) is the equivalent.
4. **LSP inputs carry "Weight in texturing 0.01" by default** (Selected input panel, OBS) — RS already nearly ignores them for colour; `--texture-from photos` is correct hygiene, not the fix.
5. `RealityScan.exe -stdConsole -headless -help` prints only the banner (181 B); the command list is online only.
6. The reconstruction region auto-box for the merged component is one rectangular volume (OBS, first screenshot).
7. RS chose an 8192² diffuse for this model despite `unwrapMaxTexResolution=16384` (OBS; AdaptiveTexelSize decides).
8. Timing on 8 cores: load 5–23 s; reconstruction 1800 inputs 100–129 s, 900 photos 56 s; texturing 178–465 s; FBX export 3–13 s.

## XII-D. TOOLS (in place, same names; `C:\rig\rs\tools`)

`rs_merge.py` **v8**: mesh stage takes `--from <proj>` (mesh THE MERGE directly), `--mesh-from both|photos|lidar`, `--texture-from both|photos|lidar` (the switched-off kind gets `-selectImage g/…/ set` + the enable flag false + `-deselectAllImages` before `-calculateNormalModel`); the output tag gains `_photosmesh` / `_photostex`; inputs keep the base tag; the input project is never written. New guard: a geometry experiment whose FBX is within 0.5 % of the base-tag FBX — or a texture experiment whose diffuse PNG is — **fails** with "the mesh/texture did not change: the switches selected nothing". `fake_rs.py`: `g/…/` vs path semantics, per-input flags, `flags_ignored` scenario, FBX size follows inputs. `test_rs_merge.py`: 67 checks. Deliveries: `rs_tools_update_2026-10-09.zip` efc9c55d… → `…09b.zip` ffc40ad8… (rs_gate MERGED detection, re-issued — update "c" of 10-08 had never been extracted; the suite caught it) → `…09c.zip` 967a2a7a… (the g/…/ fix + guard). Project docs this layer: `RESUME_HERE.md` (rewritten twice), this Master.

## XII-E. DECISION (ratified by the eye, 2026-10-09)

- The RealityScan ladder (align → lidar --merge-georef → mesh) stays the recipe. Add `--texture-from photos` to the mesh step as standard. The photo lock now works and stays.
- **The next move is on the cloud, not in RealityScan**: measure the ripple at its source (`planar_shell.py` on `cloud_color.ply` → per-plane thickness), then produce a snapped/denoised cloud (plane inliers projected onto their fitted planes; objects untouched; voxel + outlier removal elsewhere) → `rs_bundle` v4 with that cloud → the three commands on a fresh tag → the eye. Two outcomes only: flat walls + readable texture (PASS; UE next) or flat walls + still-smeared texture (then and only then the photos are the debt — sharpness/registration — and the stills pass of FORWARD_PLAN is the answer).
- Photos-only geometry is retired as an option for this rig's captures (XII-B run 2). planar_shell's planar shell is promoted from "post-RS" to a candidate source of the walls themselves.

## NEXT (in order)
1. Shadow: `python planar_shell.py --cloud C:\rig\rs\rsbundle_130955_v3\cloud_color.ply --out C:\rig\rs\shell_130955` → `report.txt` thickness per plane + `shell_render.png` → Project Files. (Env with open3d: `rigstation` or `fusion`.)
2. Snap/denoise tool (new, sandboxed, selftested) → `cloud_snapped.ply` → bundle v4 → `align --tag _snap` / `lidar --merge-georef --lidar-params lidar_import_georef.xml --tag _snap` / `mesh --tag _snap --texture-from photos` → the eye (mantel Solid + Color/Texture, arch, windows, top-down).
3. PASS → UE 5.8 import (Uniform Scale 100, Nanite ON, Lightmap UVs OFF, two-sided) → walk it.
4. Standing debts unchanged: calibration 1.52 px with the 3 px cap binding; next capture under the shutter lock; `frame_qc` as a gate; D5 stand-pan capture; GLIM dry-run.

## SESSION LOG LINE
- **2026-10-09:** Resumed from RESUME_HERE + Master 80. The eye on S4_mesh_georef: merge holds, geometry rippled, texture smeared — FAIL, recorded. `-help` prints nothing; online help gave the per-input flags; rs_merge v8 (`--from`, `--mesh-from`, `--texture-from`), emulator + 65 checks; Shadow suite caught the never-extracted gate update (re-issued). First photos-only run changed nothing → the `g/…/` selection fact found in the RS help; driver/emulator/tests fixed (67 checks) + "unchanged mesh" guard; the photo lock of every earlier lidar run found to have selected nothing (lineage correction). Real photos-only mesh: 905 K wisps — photos cannot carry geometry. Photo-texture-on-LiDAR-mesh: same smear — the smear is misregistration on ripple, not LiDAR colour. Decision: fix the cloud upstream (planar_shell measure → snap → re-run ladder). Master 20.13.81 written.

<!-- ============================================================================ -->
<!-- ##  END 20.13.81 LAYER. 20.13.80 follows VERBATIM (Stone Clause).              ## -->
<!-- ============================================================================ -->


<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.80, 2026-10-08) *****            -->
<!-- Additive layer on 20.13.79 (Stone Clause: nothing lost; 79 is verbatim below).       -->
<!-- THE MERGE HAPPENED. Photos + LiDAR are in ONE RealityScan component, headless,        -->
<!--   measured: Component 0 (1) = 1800 cameras (900 photos + 900 LSP views), 635,177     -->
<!--   points, georeferenced + metric, reproj 1.52 px, BOTH blocks 0.000 m from their      -->
<!--   priors. RealityScan 2.1.1.119166, no control points, no GUI. 8 minutes machine time. -->
<!-- HOW: both blocks made the SAME KIND (georeferenced): photos via XMP exact priors,      -->
<!--   LiDAR via import Georeferenced = YES (From component), then ONE align with           -->
<!--   sfmMergeGeoreferencedComponents = true. The 79 reference's section 4 ("not staff-    -->
<!--   recommended") is this rig's PRIMARY route; section 3 (control points) is the route   -->
<!--   for blocks that share no frame.                                                    -->
<!-- WORK FROM: XI below (recipe, mechanism, corrections), then RS_DECISION_TREE.md and    -->
<!--   ADR-005. Rig state unchanged: L2 OFF; Shadow only. S4 mesh running at close.         -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ 20.13.80 — THE MERGE HAPPENED (2026-10-08) ⭐
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

## XI-A. THE RESULT (measured, not screenshotted)

Project `C:\rig\rs\out_130955\S2_lidar_georef.rsproj`, reports `S2_lidar_georef.html` / `S2b_lidar_lsp_georef.html`, console `S2_lidar_georef.log`:

| component | cameras | points | CPs | reproj mean / med / max (px) | georef | metric | photo frame check | LSP frame check |
|---|---|---|---|---|---|---|---|---|
| Component 0 (photo source block) | 900 | 39,286 | 0 | 1.52 / 1.54 / 3.00 | True | False | 0.000 m | — |
| Laserscan component (LSP source block) | 900 | 622,935 | 0 | 0 / 0 / 0 | True | True | — | 0.000 m |
| **Component 0 (1) — THE MERGE** | **1800** | **635,177** | 0 | **1.52 / 1.53 / 3.00** | **True** | **True** | **0.000 m (n=900)** | **0.000 m (n=900)** |

RealityScan creates the merged component as a NEW component and keeps the two sources beside it. Every "duplicate component" in the lineage since 09-18 was this behaviour; the duplicates were never the failure, the missing join was. Focal round-trips: f = 0.4421 × 36 = 15.91 mm (bundle 15.914).

## XI-B. THE RECIPE (three commands; `C:\rig\rs\tools`, RIGSTATION prompt, RealityScan GUI closed)

```
python rs_merge.py C:\rig\rs\rsbundle_130955_v3 C:\rig\rs\out_130955 align --tag _georef                                                   (106 s)
python rs_merge.py C:\rig\rs\rsbundle_130955_v3 C:\rig\rs\out_130955 lidar --merge-georef --lidar-params C:\rig\rs\tools\lidar_import_georef.xml --tag _georef   (336 s)
python rs_merge.py C:\rig\rs\rsbundle_130955_v3 C:\rig\rs\out_130955 mesh --tag _georef
```
- `align`: new scene, `images\*.jpg + .xmp` (PosePrior **exact**, FocalLength35mm 15.914, Fixed), `sfmMaxFeatureReprojectionError=3`, `sfmEnableCameraPrior=true`, `sfmMergeGeoreferencedComponents=false`, `sfmForceComponentRematch=false`, one align → ONE component 900/900 at 0.000 m. (First clean headless align of these photos; identical to the 10-06 GUI block.)
- `lidar`: load S1 → `importLaserScan cloud_color.ply lidar_import_georef.xml` → report → select Component 0 → select `.*\.[jJ][pP][gG]` → `lockPoseForContinue true` → `sfmMergeGeoreferencedComponents=true` → ONE align → **save before any selection** → reports with Component 0 and Laserscan selected.
- `lidar_import_georef.xml` = LiDAR Scan Import dialog, exported once: Mobile LiDAR · Exact · **Georeferenced = Yes** · Features Color · Noise free · With original files · Use camera poses = **From component → Component 0** · Single camera. (`lidar_import_fromcomponent.xml` = same with Georeferenced = No: the 10-06/adopt route — two blocks, never joins.)
- Tools: `rs_tools_v7.zip` + in-place updates 2026-10-08 (a, b, c). Emulator `fake_rs.py` + `test_rs_merge.py` = 57 checks PASS; every real run promoted its `[ASSUMED]` rules.

## XI-C. THE MECHANISM — proven in three measured steps the same day

1. **`adopt` on FIRST TRY AT REAL RENDER** (the 10-06 GUI project, carried forward, never written — ADR-005): photo block georef=True / metric=False at **0.000 m** from its XMP priors; LSP block georef=False / metric=True sitting **4.814 m** (p90 4.839, max 4.857 — a 4 cm spread = one rigid translation) from its own priors. Both copies of each block identical. → The LSP block was *free* in absolute space and RS had parked it 4.8 m away. Audit risk 4-A: photo side cleared; the offset was always on the LiDAR side. Saved as `S2_lidar_adopt.rsproj`.
2. **S3 control points on the adopted project**: six corners (CANONICAL_ROOM_GEOGRAPHY CP1–CP6) clicked in 3 sharp photos each (`cp_click.py`, 18 clicks), mirrored onto the matching `_1_color.lsp` views **scaled to each LSP view's size** (RS renders LSP views at 240×150 / 320×200 / 480×300 / 960×600 against 1920×1200, identical normalised f/px/py — unscaled rows fail "Coordinates of the control point are out of range [err:18008]"). RS: "Control points imported successfully", and the solves show **CPs 6 used in BOTH blocks** — and still two components (plus RS's new copies). → Control points constrain each block internally; they do not reconcile a georeferenced block with a non-georeferenced one.
3. **Experiment B** (fresh S1 because RS has no command to remove images from a project; the adopted project kept as baseline): import Georeferenced = Yes → LSP block georef=True / metric=True at **0.000 m** from priors *immediately after import* → one align with merge-georeferenced on → **1800 cameras in one component, 0.000 m both sides.**

Why: with LSP views rendered *From component* the two blocks already share one frame (Point-LIO's). RealityScan only needed to be told the LiDAR block is absolute. Control points are the bridge when two blocks have *no* common frame; this rig always had one.

## XI-D. LINEAGE CORRECTIONS (banked; nothing deleted)

- 20.13.79 reference §2 #5 *"Exact + Georeferenced = No is the correct import for a CP merge"* — true for a CP merge, **wrong for this rig**: Georeferenced = **Yes**. §4 *"documented but NOT staff-recommended… try only if §3 step 7 fails"* → the **primary** route. §3 (CPs) → the fallback for unshared frames.
- RS_IMPORT_AUDIT #7 *"merge-georeferenced F6 — invalid test — nothing was georeferenced"* was right about the *test*, and the setting it dismissed is the one that works once the cloud IS georeferenced. Forum 2564929's "shifted doubles" concerned blocks georeferenced *separately*; ours share one frame.
- "Documented outcome 2" (duplicate components after align) = RS keeping source components beside a new one. Not a failure signature; `rs_gate.py` now reports a ≥1.8N-camera component as MERGED whatever else is present.
- Risk 4-C (Locked prior "stacks") and 4-B (Fixed calibration) untouched: the merge ran at 1.52 px with the 3 px cap binding; calibration remains the debt it was.
- RealityScan is **2.1.1.119166** on Shadow (not 2.2, as 77–79 say). 2.2 is no longer needed for the merge.
- FUSION_SOLUTION A0 ("enable Merge georeferenced components… re-run F6") was half right: the setting matters, the import flag it omitted is what makes it apply.

## XI-E. FACTS LEARNED FROM THE REAL INSTALL (each cost one run; now in the emulator)

Headless cannot load a project the GUI holds (0x82000017) · `-stdConsole` is mandatory or failures are silent · report templates need `$Using(…FunctionSet)` lines and bare `componentGUID` arguments; `$ExportCameras` writes the *application-selected* component only; `imageExt` carries the dot · `importControlPointsMeasurements` validates pixel range per image · `deleteSelectedComponent` / `renameSelectedComponent` work headlessly; no command removes images · a GUI-saved project loads headlessly in 5–17 s; a 900-photo align takes 106 s, LiDAR import + lock + align 336 s on 8 cores.

## XI-F. ADR-005 (banked): the merge step never restarts from zero
The RealityScan project file is the unit of progress; a stage reads a saved project and writes a new one; a fresh align is a conclusion of evidence, never a default (20.13.17 §8Y). FIRST TRY AT REAL RENDER was carried forward by `adopt`, not discarded; experiment B ran from a fresh S1 only because RS cannot drop images from a project, and on its own tag. Tools update in place under the same names; the sandbox suite is the regression gate.

## NEXT (in order)
1. S4 mesh on `S2_lidar_georef.rsproj` (`mesh --tag _georef`; running at close) → `S4_room_georef.fbx` → **the eye** and the drift gate (one lamp, one arch, one front window, one side window, one mirror).
2. UE 5.8 import (×100, Nanite, two-sided) → walk it.
3. Then, and only then: the next capture's debts — calibration (1.52 px, cap binding), blur (130955 pre-shutter-lock), coverage.

## SESSION LOG LINE
- **2026-10-07:** Test 0 headless on FIRST TRY (template/engine facts learned: $Using, bare GUID, selected-component export, dotted imageExt); four components measured; georef/metric asymmetry found; rs_tools v5→v7 + emulator (57 checks); ADR-005 written after a full read of every Master and RS doc (45 files). Operator's reading test: FOX in Master 20.13.69 (the project copy served to the assistant did not carry the edit — noted).
- **2026-10-08:** `adopt` carried FIRST TRY forward (photo 0.000 m, LSP 4.81 m rigid offset); S3 CPs attached (CPs 6 both blocks) yet no join; experiment B (Georeferenced = Yes + merge-georeferenced) → **ONE component, 1800 cameras, 0.000 m both sides.** Banked `RS_MERGE_ACHIEVED_2026-10-08.md`. Mesh started.

<!-- ============================================================================ -->
<!-- ##  END 20.13.80 LAYER. 20.13.79 follows VERBATIM (Stone Clause).              ## -->
<!-- ============================================================================ -->


<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.79, 2026-10-05 late) *****       -->
<!-- Additive layer on 20.13.78 (Stone Clause: nothing lost).                            -->
<!-- THIS 20.13.79 LAYER banks the RealityScan photo+LiDAR MERGE REFERENCE: the           -->
<!--   documented procedure (RealityScan help + Epic staff threads, every claim linked),  -->
<!--   the full timeline of every RS attempt (09-15 -> 10-05), the root cause per the     -->
<!--   docs, and the errata to 20.13.78's "THIS IS HOW WE IMPORT" (kept below, unedited).  -->
<!--   Operator order: "Attach this to the Master as a reference as we work in Reality    -->
<!--   Scan." Rig state unchanged: L2 OFF; Shadow only. Procedure NOT yet executed.       -->
<!-- WORK FROM: the REFERENCE section (first), then 20.13.78 Part X for tools/bundle.      -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  **REALITYSCAN PHOTO + LiDAR MERGE — THE DOCUMENTED REFERENCE (work from this)**
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
*(Project doc `claude/RS_PHOTO_LIDAR_MERGE_DOCUMENTED_2026-10-05.md`, md5 902679c4…, reproduced in full.)*

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


═══════════════════════════════════════════════════════════════════════════
## ERRATA TO THE 20.13.78 SECTION BELOW ("THIS IS HOW WE IMPORT INTO REALITY SCAN")
═══════════════════════════════════════════════════════════════════════════
The 20.13.78 text is kept verbatim (Stone Clause) but is SUPERSEDED where it conflicts with the
reference above. Specifically:
- **Its step 1** (*Merge georeferenced components* = Yes) is meaningless with Georeferenced = No
  (the setting only acts when "each [component] is georeferenced"). Leave it at No on the
  control-point path.
- **Its step 3** is right about the door (LiDAR Scan button, Mobile LiDAR, Exact, Color,
  Georeferenced = No) but *Use camera poses* should be **From component → Component 0**, after the
  photos are aligned alone — not From camera pose priors with the cloud imported before any alignment.
- **Its step 4** says "Lock pose for continue on the LiDAR component". Wrong: it goes on the **photo**
  component, after aligning the photos (staff, forum 2707328). And it implies a bare F6 fuses photos
  and LiDAR; it does not — fusion needs feature matches or control points (6 CPs, each on ≥3 photos
  AND ≥3 LSPs).
- **Its "why" paragraph** (RS needs the sensor path) explains the hollow-crate preview correctly but
  is not why photos and LiDAR split; the split is the observation graph (see reference §2).
- The lineage claim "Intensity is the root cause" (FUSION_SOLUTION A1) is refuted: the 97 %-coloured
  cloud split identically on 10-05. Color is necessary (readable LSP views), not sufficient.
Measured 10-05 after 20.13.78 was written: Laserscan component = 900 `img_…_1_color.lsp` (LiDAR
virtual cams named after their source photos), Component 0 = 900 photos, Component 1 = a duplicate
of the LSP set; a further F6 with the merge setting on produced four more duplicates. Project files:
`Screenshot 2026-10-05 151458.png`.

═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  **THIS IS HOW WE IMPORT INTO REALITY SCAN**
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**Why this section exists.** Every RealityScan attempt in the lineage failed at the same
place: the data was good, the render went south. 2026-10-05's rehearsal on the 130955 cloud
(X-E below) and RealityScan's own documentation explain it: **RealityScan was never given the
sensor path.** It builds surfaces from line-of-sight — for every point it must know where the
sensor stood when it saw that point, so it can carve the space between as empty. A terrestrial
scanner carries that inside its file (the "ordered" requirement). A SLAM / mobile-LiDAR cloud
like ours does not; RealityScan reconstructs it from **camera poses you give it first**. No
poses → no visibility → a closed crate with a blank interior. That is not a data defect and
not a RealityScan defect. It is the import order.

RealityScan 2.1 release notes, verbatim: *"First import images and their trajectories, or
open a Colmap Scene… Import the point cloud and generate virtual cameras based on camera pose
priors or an imported component."* Poses first. Cloud second. The cloud's cameras come FROM
the poses.

**THE SEQUENCE (RealityScan 2.2, Shadow). Do it in this order, every time.**

0. **Inputs** = one `rsbundle_<capture>/` from `rs_bundle` (v3+): `images/*.jpg` each with its
   `.xmp` pose prior (CV convention, FocalLength35mm 15.914228, zero distortion — frames are
   undistorted), `cloud_color.ply` (the SAME offline solve's cloud, photo-coloured), `manifest.csv`,
   `README_RS.txt`. Poses and cloud must come from the **same offline Point-LIO solve** (ADR-004
   D1/D2) — never a live solve, never a cloud from one run and poses from another.
1. **New project.** ALIGNMENT → Settings (Advanced): *Merge georeferenced components* = Yes;
   *Max feature reprojection error* = 3 px.
2. **Images FIRST.** WORKFLOW → **Images** (or **Folder**) → the whole `images/` folder. Each
   `.jpg` picks up its `.xmp` sidecar automatically (PosePrior = exact).
3. **Cloud SECOND, through the right door.** WORKFLOW → **"LiDAR Scan"** button → `cloud_color.ply`.
   In the import dialog: **LiDAR type = Mobile LiDAR** (set it by hand — PLY cannot be
   auto-detected), **Registration = Exact**, **Features source = Color**, **Georeferenced = No**,
   **Use camera poses = From camera pose priors**. The cloud defines the coordinate system (metres).
   - NOT the generic laser-scan import. NOT drag-and-drop onto the 3D view. Both accept only
     ORDERED terrestrial scans and **silently reject** our cloud — nothing happens, no error.
     (Measured today: both silent on a correct 5.27 M-point PLY.)
   - NOT "Generate aerial poses" for an interior. It puts the invented cameras outside the room
     → RealityScan carves the OUTSIDE as empty and the whole inside as solid → a hollow crate.
     (Measured today, X-E.) Aerial is for drones.
4. **Align Images (F6).** GATE: **one** component, **≥ 90 %** of cameras aligned, camera cones
   pointing **inward** (a cone pointing out of the room = an XMP rotation flip — stop).
   If photos and LiDAR land in separate components: *Lock pose for continue* on the LiDAR
   component, then 3+ control points on 3+ images/LSPs, re-align.
5. **Mesh.** MESH & COLOR → Settings: raise *Default grouping factor* (LiDAR-priority meshing).
   Set the reconstruction region (for a dollhouse view, drag its top face ~1 m below the
   ceiling). **Normal Detail.** (Preview is fine for a first look.)
6. **Texture.** Texture settings: *Correct colors* = Yes, adaptive texel size, max texture
   resolution 16384. **GATE: reads as the room — the eye.**
7. **Export.** Model → GLB or FBX, scale ×100 (m → cm), no spaces in filenames, UDIM if the
   atlas clips → UE 5.8 (Nanite).

**What the viewport shows you is not the data.** RealityScan draws laser scans as a thinned
preview at 1 px — a 5.27 M-point cloud looks like dust at a distance. Judge the mesh, not the
point draw. (`Max points to display`, WORKFLOW → Settings → Application, default 10 M, is the
only documented draw setting.)

**Fallback if alignment misbehaves with XMPs:** RealityScan's native SLAM path is an
images+trajectory import (WORKFLOW → Import Metadata → Trajectory; formats in `flightlogs.xml`)
or a COLMAP scene (`cameras.txt / images.txt / points3D.txt` — the forum thread shows
`points3D.txt` must be header-only or RS throws "track referencing image feature out of
bounds"). Same poses, different container — a fallback, not a redesign. `rig-files` has a
`poses_to_colmap.py` lineage for this.

**LiDAR-only route (parked, tech debt):** the Trajectory import + a cloud with per-point
timestamps (what resolver v2's `/cloud_registered` recording can supply) would let RealityScan
mesh a capture with no usable photos at all. Not needed for the 130955 gate; noted so it is not
rediscovered.

Sources: RealityScan 2.1 release notes (dev.epicgames.com/documentation/realityscan/realityscan-2-1);
RealityScan Help › LiDAR Scans (rshelp.capturingreality.com/en-US/tutorials/importlaser.htm);
Help › Trajectory Import (…/tools/flightlogimport.htm); Help › keys and values
(`appMaxPointsToDisplay`); Epic forum "Is it possible to import unregistered PLY" (dev: RS "takes
laser scan data as camera positions, not as point clouds"); Epic forum "Tutorial: SLAM Support".


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART X — 2026-10-05, after the control image (re-solves, forward plan, bundle) ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## X-A. FOUR OFFLINE RE-SOLVES ON THE JETSON (L2 OFF, nothing else running)
═══════════════════════════════════════════════════════════════════════════
`resolve_pointlio.sh <BAG> <stock|imuin|imuin_map1000> [0.5]` replays a raw bag into Point-LIO
at half speed, records the re-solved odom (+IMU, v2: +`/cloud_registered`), SIGINTs, and proves
the PCD saved fresh (mtime). Launch variants are generated by `sed` into the install share dir;
the deployed launch is never edited. Outputs: `/mnt/rigdata/resolve_<bag>_<mode>_scans.pcd` +
`resolve_<bag>_<mode>/` odom bag + `/tmp/resolve_<mode>.log`.

| Bag | Mode | Result (top_down on Shadow, Desktop) |
|---|---|---|
| `fusioncap_080826` | stock | **clean** — z −2.76..+2.66 m; walls single lines; `1Topdown_080826_stock` |
| `fusioncap_080826` | imuin (`use_imu_as_input: 1`) | **diverged** — z to −3400 m; accelerometer runaway in ~15 s on a moving start. NEGATIVE RESULT. ADR-004 D3's first-pass param is retracted as a drop-in. |
| `fusioncap_115614` | stock | **clean** — `2Topdown_115614` |
| `fusioncap_130955` | stock | **clean** — 5,274,770 pts; extent x −6.0..9.2, y −7.0..10.4, z −2.2..4.7 m; `3Topdown_130955` |

`bag_health` on the stock re-solves: gyro-vs-odom tracks to **≤ 5°** over the whole capture (vs
157° divergence on live 141733). **Offline stock Point-LIO at 0.5× on an idle Jetson is the
geometry of record** (ADR-004 D1/D2 confirmed on three bags). The defect of 141733 was the live,
loaded, rotating-in-place case; it is not in the raw data.

Inventory (`ros2 bag info` + `bag_motion.py`): archive bags recorded `/unilidar/cloud` at
1.4–8.6 Hz against the sensor's 12 Hz — the **live** path dropped cloud frames under load. The
offline solves are clean anyway; a raw-only capture (no live Point-LIO) removes the load.
`bag_motion` thresholds are miscalibrated (accSD 0.35 too high — 180551 walk = 0.25; still-start
floor ~1.7 °/s) — verdict column not to be trusted until recalibrated.

Desktop naming rule (ratified): `1Topdown_<capture>_<mode>.png`, `2Topdown_…`, in the order made.

═══════════════════════════════════════════════════════════════════════════
## X-B. THE FORWARD PLAN (banked: `FORWARD_PLAN_2026-10-05_geometry_to_relightable_UE.md`)
═══════════════════════════════════════════════════════════════════════════
Question asked: RS or straight to Unreal, and is the data a dead end? Answer: **not a dead end.**
Route: offline re-solve → `rs_bundle` → **RealityScan 2.2** (fuse LiDAR + photos, mesh, texture,
Correct colors) → planar_shell (walls/floors/ceilings as separate meshes ≥ 10 cm for HW-RT
Lumen) → Agisoft De-Lighter 2.3.2 (free; "Unreal/Quixel De-Lighter" does not exist) → **UE 5.8**
(Nanite, Lumen, MegaLights, physical light units/IES/barn doors, ACES 2.0, ARRI LUKA plugin
June 2026 w/ sACN/Art-Net → Blackout iPad console; DMX plugin) → Set.A.Light 3D imports FBX/OBJ/
GLB (4096 px maps, one-way). Texel density: Arducam ~4.2 px/cm at 2 m; a stills pass (24–45 MP)
= 13–40 px/cm — the hero-surface upgrade path. Practical capture-to-UE: Jetson records raw →
Jetson re-solves (or Shadow when it can) → Shadow: bundle, RealityScan, shell, de-light → UE on
the workstation. Six machine-steps, two eye gates (top-down; textured mesh).

═══════════════════════════════════════════════════════════════════════════
## X-C. `rs_bundle` — THE REALITYSCAN BUNDLER (v1 → v4 in one day)
═══════════════════════════════════════════════════════════════════════════
`python rs_bundle_vN.py --bag <orig> --odom <resolve odom bag> --cloud <resolve pcd> --out <dir>
[--tau 0.18] [--prior exact|locked|initial] [--min-move 0.08] [--min-rot 4] [--max-frames 900]`
- Embedded K / DIST / `R_L2C` / `T_L2C` verbatim from `fuse_pano.py`; `compose_world_to_cam`
  applied exactly once; matcher-v2 pose math; association on **header.stamp** with
  tau = lidar − camera (tau_solve_v2 sign), pose at t_img + tau. Frames undistorted with K
  unchanged → XMP intrinsics exact, brown3 zero coefficients. Motion-spaced selection
  (0.08 m / 4°), sharpest of 3 by Laplacian variance. Z-buffer colourization (best-centred
  camera) → `cloud_color.ply`.
- **v2:** frames written as kept (v1 held every raw frame in RAM — 6.9 MB each).
- **v3:** `--max-frames` thins **evenly over the whole walk**. v2 **stopped reading at frame
  3,381 of 6,125** when it hit the 600-frame cap — the second half of 130955 had cloud but no
  photos (the "100 %-coloured" first bundle was half a walk). Depth buffer gets a 3×3 min-filter
  so a sparse wall still occludes the room behind it (the 100 % was partly bleed-through).
  Synthetic room test: XMP rotation error 2e-9, centre 0.0000 m, colour round-trip 1.7/255,
  thinned set spans t = 0.2 → 29.3 s of a 30 s walk. ALL PASS.
- **v4:** `README_RS.txt` corrected to the sequence at the top of this file (images first, cloud
  second via the LiDAR Scan button, From camera pose priors). Bundle DATA identical to v3.
- First bundle (v2, Jetson): `/mnt/rigdata/rsbundle_130955/` — 600 frames, first half only.
  Second (v3, Jetson, in progress at close): `/mnt/rigdata/rsbundle_130955_v3/` — all 6,125
  frames read, 900 kept over the whole walk. **This is the first dataset in the lineage where
  both halves are good at once:** poses from a clean offline solve AND the cloud from the same
  solve.
- Ruling: one more pass on the Jetson, then the bundler runs on Shadow (compressed captures
  carry the frames; the Jetson is not to be overburdened).

═══════════════════════════════════════════════════════════════════════════
## X-D. TOOLS DELIVERED THIS LAYER (md5-locked; project `claude/` + chat download)
═══════════════════════════════════════════════════════════════════════════
| Tool | md5 | Machine |
|---|---|---|
| `resolve_pointlio.sh` v2 (records `/cloud_registered`) | `65b3a617d2d947038ec178c0cae144c4` | Jetson `~/` (v1 `d95c7645…` is what ran today — replace) |
| `bag_motion.py` | `da03021403beac000c15be90219ee43d` | Jetson / Shadow — thresholds miscalibrated |
| `rs_bundle_v3.py` | `4c65c4e9a8bd799a5195a0da1b5df447` | Jetson `~/` (the 130955_v3 build) |
| `rs_bundle_v4.py` | `6c19c35f5eddd10034a1bfb6e2c4bc54` | Shadow from here on (README fix only) |
| `pcd2ply.py` v1 | `aaa1cdba5d605d79b585a78a460747a8` | Shadow — Point-LIO pcd → binary PLY, intensity as gray |
| `FORWARD_PLAN_2026-10-05_…md` | `c8d7b7373139782d0898b02b8bf99c93` | project + Desktop |

═══════════════════════════════════════════════════════════════════════════
## X-E. THE REALITYSCAN REHEARSAL ON 130955 (LiDAR-only, Shadow) — what it measured
═══════════════════════════════════════════════════════════════════════════
Done while the Jetson built the v3 bundle, on the cloud alone (`130955_cloud_gray.ply` via
`pcd2ply`, 5,274,770 pts).
1. Generic laser-scan import: **silent** (no dialog, no error). Drag-and-drop onto 3D: **silent**.
   → unordered clouds are rejected without a message. (Top section, step 3.)
2. WORKFLOW → LiDAR Scan → Mobile LiDAR, Exact, Color, poses = *Generate aerial poses*, camera
   height 1.5 m: **imported.** Thinned 1-px preview; operator "vaguely recognises the room".
3. Align (F6): one component, reconstruction region around the cloud, two aerial cameras at the
   box corners (outside the room).
4. Preview mesh: **a closed crate — blank interior.** Exactly the no-visibility failure. The cloud
   was fine; the cameras were fiction.
Conclusion banked: the lineage's "data good, RS render bad" was the same cause every time —
RS never had the poses. Don't repeat the aerial-pose preview for interiors; it cannot work.

═══════════════════════════════════════════════════════════════════════════
## X-F. LINEAGE CORRECTIONS (banked)
═══════════════════════════════════════════════════════════════════════════
1. ADR-004 D3 (`use_imu_as_input: 1` as the first-pass fix) is **retracted as a drop-in**: it
   diverges in ~15 s on a moving start (X-A). Stock offline is the geometry of record.
2. `README_RS.txt` v1–v3 had the cloud before the images. Wrong order; corrected (v4 + top section).
3. "Import Laser Scans" ≠ "LiDAR Scan" in RealityScan 2.2. Only the latter takes a mobile cloud.
4. The v2 bundle's "frames 3381 / 100 % coloured" was a half-walk with bleed-through, not a
   result. Superseded by v3.
5. The RealityScan 3D viewport's point draw is a thinned preview — it is not evidence of cloud
   density. Judge top-downs (density raster) and meshes.

═══════════════════════════════════════════════════════════════════════════
## X-G. HOUSE RULES ADDED THIS LAYER
═══════════════════════════════════════════════════════════════════════════
- **Changed scripts get a new version label** (`_v2`, `_v3`…) — never the same filename.
- Chat downloads land in `C:\Users\Shadow\Downloads\` even though the Desktop is home; give
  commands with full paths, never `cd`-relative.
- Desktop images: `1Topdown_…`, `2Topdown_…` in the order made.
- Prefer not to overburden the Jetson: bundling moves to Shadow after the 130955_v3 pass.
- "My eye is the ultimate arbiter" — a gate is passed when the operator recognises the room.

═══════════════════════════════════════════════════════════════════════════
## NEXT (in order)
═══════════════════════════════════════════════════════════════════════════
1. ~~Jetson: confirm `rsbundle_130955_v3` DONE → Taildrop → Shadow~~ DONE (bundle on Shadow at
   `C:\rig\rs\rsbundle_130955_v3\`). NOW: **the REFERENCE procedure §3 at the top of this file**,
   one step per turn: fresh project → photos-only F6 (gate: one Component 0, ≥ 810/900) → LiDAR Scan
   From component → Lock pose for continue on the photos → one F6 → if split, 6 CPs on ≥3 photos AND
   ≥3 `_color.lsp` → F6 → ONE component of 1800 → mesh (grouping factor up) → texture → the eye.
2. Replace Jetson `~/resolve_pointlio.sh` with v2; `rs_bundle_v4.py` to Shadow (`rigstation`).
3. Then: planar_shell → De-Lighter → UE 5.8 (FORWARD_PLAN §3).
4. Tech debt (FORWARD_PLAN §4): `capture_raw.sh` in the kiosk CAPTURE slot; `rig_camera_compressed`
   PTS stamp; push the toolset to `rig-files`; recalibrate `bag_motion`; kiosk render off the
   Jetson; D5 stand-pan capture (ADR-004 Accepted); GLIM dry-run; stills pass; 180728 static
   top-down; RS Trajectory/COLMAP fallback scripted; `ros2 param dump /laserMapping`.

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-10-05 (cont.):** Jetson up, L2 OFF. `resolve_pointlio.sh` built; 080826 re-solved stock
  (clean) and imuin (diverged, −3400 m — negative result); 115614 and 130955 re-solved stock
  (clean). `bag_health` on the re-solves: ≤ 5° gyro-vs-odom. Inventory: live cloud path dropped
  to 1.4–8.6 Hz in the archive. FORWARD_PLAN written (RS 2.2 → UE 5.8, not a dead end).
  `rs_bundle` v1→v2→v3 (RAM fix; even thinning after v2 truncated at frame 3,381/6,125;
  occlusion fix); first bundle built on the Jetson, v3 rebuild started. On Shadow meanwhile:
  `pcd2ply` + the LiDAR-only RealityScan rehearsal → import path found (LiDAR Scan button,
  Mobile LiDAR), hollow-crate mesh with aerial poses → the root of every RS failure in the
  lineage: no poses. Operator: "I think there is something we aren't doing." There was: the
  order. README corrected (v4). Master 20.13.78 written with **THIS IS HOW WE IMPORT INTO
  REALITY SCAN** at the top.
- **2026-10-05 (late):** v3 bundle on Shadow; images + XMP read (f 15.9 mm); cloud imported (LiDAR
  Scan, Mobile LiDAR, Exact, Color, Georef No, from priors) → F6 → THREE components (Laserscan 900
  LSPs / Component 0 900 photos / Component 1 duplicate LSPs); merge-georeferenced F6 → four more
  duplicates. Operator: "we've been here before… sloppy guessing… find the docs." Full read of every
  Master and RS screenshot (09-15 → 10-05), then the RealityScan help set + five Epic staff threads.
  Result: the DOCUMENTED procedure (reference above) — align photos alone, cloud From component,
  Lock pose for continue on the photos, 6 control points on ≥3 photos AND ≥3 LSPs, one F6. Our two
  earlier CP attempts failed for documented reasons (unreadable intensity LSPs; photo-only GCPs).
  20.13.78's import section corrected by errata, kept verbatim. Master 20.13.79 written.

<!-- ============================================================================ -->
<!-- ##  END 20.13.79 LAYER (= 20.13.78 + the RS merge REFERENCE + errata). Additive.     ## -->
<!-- ##  RS merge reference: claude/RS_PHOTO_LIDAR_MERGE_DOCUMENTED_2026-10-05.md 902679c4…  ## -->
<!-- ##  Tools: resolve_pointlio v2 65b3a617… · rs_bundle_v3 4c65c4e9… · v4 6c19c35f… ## -->
<!-- ##  pcd2ply aaa1cdba… · bag_motion da030214… · FORWARD_PLAN c8d7b737…            ## -->
<!-- ##  Deep lineage (ADRs + STAGE 1-7 UE) in 20.13.68. Stone Clause: nothing lost.  ## -->
<!-- ============================================================================ -->
