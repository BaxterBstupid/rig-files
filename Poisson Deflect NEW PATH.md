# The Proven Pipeline for Turning a Noisy Handheld SLAM LiDAR Capture Into a Clean, Set-Design-Quality Mesh

## TL;DR
- **Stop feeding Poisson a single pre-accumulated SLAM cloud — that is the root cause of the torn geometry.** The proven professional fix is *volumetric TSDF fusion of individual posed LiDAR frames* (VDBFusion or Open3D), which weighted-averages the 2–3 cm multi-pass drift into one clean surface. This is exactly the path HKU-MARS's FAST-LIVO2 ships for its own meshing, and it is the single highest-value change you can make.
- **If you cannot re-integrate per-frame data (you only have the merged cloud), the proven point-cloud path is CloudCompare/PCL: Statistical Outlier Removal → Moving Least Squares surface resampling (to collapse the double-wall to a thin sheet) → clean normal computation with MST orientation → Screened Poisson → trim by the Poisson "density" scalar field.** MLS is the step that specifically fixes SLAM "double walls."
- **For a textured set-design deliverable, the reliable ranking is: (1) TSDF fusion (VDBFusion/Open3D) of posed frames, then texture in RealityScan or OpenMVS; (2) CloudCompare SOR+MLS+Poisson; (3) RealityScan 2.1's native SLAM path (import cloud → generate virtual cameras → mesh → texture from your 422 photos).** RealityScan 2.1 (released 26 November 2025) added a genuine SLAM/point-cloud path that solves your "won't-merge" problem.

## Key Findings

**1. The diagnosis: Poisson is the wrong tool for a pre-merged noisy SLAM cloud.** Screened Poisson fits one global implicit surface through *all* the points at once. When the same wall is represented by 2–3 cm of overlapping drifted passes, Poisson has no way to know which points are the "true" surface — it tries to fit a surface through the whole noisy slab, producing bulges, floating shells and torn fragments. Increasing octree depth (9→11) makes this *worse*, not better, because higher depth fits finer detail to the noise. This is well documented: Poisson "is unable to deal with sharp object edges where it creates bulges" and "sometimes creates multiple unconnected meshes for input models containing holes."

**2. TSDF volumetric fusion is the method that structurally fixes multi-pass noise.** Open3D's own documentation states the mechanism plainly: "TSDF volume works like a weighted average filter in 3D space. If more frames are integrated, the volume produces smoother and nicer mesh," and "the weighted average of TSDF is great in addressing the Gaussian noise along surface normal and producing a smooth surface output. The carving is great in removing outlier structures like floating noise pixels and bumps along structure edges." Crucially, this only works if you feed it *individual posed frames*, not a merged cloud — each frame's sensor origin is used to ray-cast and average. This is the core structural difference from Poisson.

**3. VDBFusion is the production-grade TSDF tool for LiDAR, and it is what FAST-LIVO2 uses.** VDBFusion (Vizzo, Guadagnino, Behley, Stachniss, *Sensors* 2022, 22(3):1296) takes "as input point clouds Pᵢ with their corresponding poses Tᵢ" — its `integrate(scan, origin)` call processes one scan plus its global sensor origin at a time. FAST-LIVO2 (HKU-MARS, arXiv:2408.14035) states directly: "For meshing, we employ VDBFusion based on the Truncated Signed Distance Function… The sharp edges on the columns and the distinct structure of the roof are clearly visible, demonstrating the high quality of the mesh," then textures with OpenMVS using the estimated camera poses. The same paper reports its dense-cloud + pose pipeline "significantly reduces the time required to obtain dense point clouds and poses from 9 hours to 21 s" versus COLMAP (test on "CBD Building 01," 300 of 1,180 frames).

**4. MLS is the specific point-cloud operation that fixes "double walls."** If you can only work from the merged cloud, PCL/CloudCompare Moving Least Squares resampling is the proven denoiser for SLAM registration artifacts: MLS "is used to smooth and resample the noisy data… resampling using 'double walls' can fill the missing parts… and the artefacts caused by registering multiple scans together, so the resultant point cloud will be a smoothed one," with the result that noisy surface normals become homogeneous. The standard sequence is SOR → MLS, confirmed by CloudCompare's maintainer.

**5. RealityScan 2.1 added a real SLAM path — this likely solves your merge problem.** Earlier versions treated LiDAR and camera components as separate and would not auto-merge co-located labels. Per the Epic Developer Community documentation for RealityScan 2.1: "Importing point clouds from SLAM scanners, such as XGrids, is now supported. First import images and their trajectories, or open a Colmap Scene… Import the point cloud and generate virtual cameras based on camera pose priors… Combine with photogrammetry or other LiDAR data." The University of Melbourne NExT Lab confirms the approach: "RealityScan generally produces a better mesh result compared to other methods… Import point cloud dataset as a mobile dataset — RealityScan wants to work with cameras/photos, it will automatically generate cameras by projecting the scan data into cameras. Ensure georeference is on, use Local if not actually georeferenced."

**6. ImMesh and SLAMesh mesh in real time but produce rougher surfaces — not the best final-quality choice.** ImMesh (HKU-MARS, T-RO 2023) does per-voxel plane fitting; independent benchmarking on the Oxford Spires Dataset (PlanarMesh, Oxford Robotics Institute, arXiv:2510.13599) found verbatim: "ImMesh produces noisier meshes (green box) due to per-voxel plane fitting, resulting in rougher surfaces… VDBFusion tends to oversmooth shapes, which results in a loss of detail such as the door frame and the sign on the floor" (both run at a fixed 0.1 m voxel). For set-design geometry, oversmoothed-but-clean beats noisy-but-detailed.

## Details

### Why your three attempts failed (and what it tells you)
- **Naive Poisson on the merged cloud → 8.4M shredded triangles.** Poisson is a *global* fit; it cannot distinguish true surface from 2–3 cm of registration drift, so it balloons and tears. Higher depth fits the noise harder. This is expected behavior, not a parameter mistake.
- **Photogrammetry-only in RealityScan → 83K blobby mesh.** Indoor scenes have large low-texture surfaces (blank walls, uniform floors) where multi-view stereo produces weak, blobby geometry. This is the classic photogrammetry failure mode indoors, and precisely why LiDAR is used for the geometry.
- **Colorizing works but Poisson still fails.** Color is a per-point attribute; it does nothing to fix the geometric thickness. Meshing quality is governed entirely by point positions and normals.

### Option A (RECOMMENDED): TSDF fusion of posed frames
This is the method that structurally cancels your 2–3 cm drift. You need your **per-scan LiDAR frames plus the Point-LIO per-frame poses** — not the accumulated cloud.

**A1. VDBFusion (best for large LiDAR scenes, CPU-only, watertight-capable):**
- Install `vdbfusion` (PRBonn). Constructor: `VDBVolume(voxel_size, sdf_trunc, space_carving)`.
- **Parameters for ~7 mm indoor data:** set `voxel_size` in the **1–3 cm** range (do not go below the point spacing or you get holes/noise; TSDF cannot resolve sub-voxel detail). Set `sdf_trunc ≈ 3 × voxel_size` (so 0.03–0.09 m). Set `space_carving=True` for handheld multi-pass indoor data to suppress ghost/floating artifacts. These are extrapolated from a published indoor precedent of 1.1 cm voxel / 3× truncation / space carving on; VDBFusion's own README example (0.1 m / 0.3 m / False) is tuned for outdoor 64-beam KITTI and is too coarse for you.
- **Feed loop:** `for scan, origin in frames: vdb.integrate(scan, origin)` where each `scan` is transformed to the global frame and `origin` is that frame's global sensor position from Point-LIO. **This per-frame origin is what enables the drift-cancelling weighted average — a single merged cloud cannot do this.**
- Extract mesh: `extract_triangle_mesh(fill_holes, min_weight)`. Raise `min_weight` (observation count, ~2–5) to prune under-observed noisy voxels; enable `fill_holes` only if you want watertight output. (`min_weight` default is unverified — tune empirically.)

**A2. Open3D ScalableTSDFVolume (best if you have or can render posed RGB-D frames):**
- `o3d.pipelines.integration.ScalableTSDFVolume(voxel_length=…, sdf_trunc=0.04, color_type=RGB8)`.
- For 7 mm data set `voxel_length` around **0.008–0.01 m** (the docs' 4.0/512 = 7.8 mm example is coincidentally near-ideal). `sdf_trunc` ~0.02–0.04.
- Integrate each posed depth/RGBD frame with `volume.integrate(rgbd, intrinsic, np.linalg.inv(pose))`, then `volume.extract_triangle_mesh()`. Because you have a LiDAR-camera rig, you can render per-frame depth maps from the posed LiDAR into the camera model and integrate those with the real photos for color.
- Note Open3D's `ScalableTSDFVolume` integrates *RGBD images*, not raw point clouds directly (a long-standing limitation confirmed in the isl-org/Open3D issue tracker); VDBFusion is the more natural fit for raw posed LiDAR scans.

### Option B: CloudCompare / PCL point-cloud cleanup → Poisson (when you only have the merged cloud)
This is the proven offline recipe and the one most VFX/survey practitioners actually run in CloudCompare. Exact sequence:

1. **Statistical Outlier Removal (SOR).** CloudCompare: *Tools > Clean > SOR filter*. Start with ~6–8 neighbors, std-dev multiplier 1.0. Run once; repeat tighter if ghost points near glass/metal remain. (CloudCompare's SOR is a PCL port assuming neighbor distances are Gaussian.)
2. **(Optional) Radius Outlier Removal** for residual small clusters — e.g. 2–5 cm radius, min 2–3 neighbors.
3. **Moving Least Squares smoothing/resampling** — the key step for your double-wall problem. CloudCompare qPCL plugin *MLS smooth*, or PCL `MovingLeastSquares`. Set `setSearchRadius` to roughly **3–5× your point spacing (≈2–4 cm)** so the local plane fit spans the full noisy slab and collapses it to one sheet; `setPolynomialOrder(2)`; `setSqrGaussParam(searchRadius²)`. This projects the noisy points onto a smooth surface, killing the 2–3 cm thickness. Warning: MLS overwrites/alters previously computed normals — recompute normals *after* MLS.
4. **Voxel downsample** to a uniform density (e.g. 5–8 mm) so Poisson sees even sampling.
5. **Compute normals AFTER cleaning.** CloudCompare *Edit > Normals > Compute*: for walls/floors use the *Plane* local model (tolerant of noise), radius ≈ 5–10× the subsample spacing; orient with **Minimum Spanning Tree, KNN 10–20** (increase neighbors when noisy). Good, consistently-oriented normals are the single biggest determinant of Poisson quality.
6. **Screened Poisson** (CloudCompare PoissonRecon plugin), depth ~10–11, **with "output density as scalar field" enabled.**
7. **Trim by density.** Use the Poisson density scalar field: *SF display params* to interactively hide low-density triangles (those farthest from real points — i.e. the ballooned/floating parts), then *Edit > Scalar fields > Filter by value* to cut. This is the proven CloudCompare way to remove Poisson's spurious closed-surface bubbles and get clean wall extents.

Realistic expectation: with a noisy indoor SLAM cloud this gets you usable walls/openings but is fiddly, and MLS can round sharp corners. TSDF (Option A) is generally cleaner with less babysitting.

### Option C: RealityScan 2.1 native SLAM path (best if you want texture + minimal coding)
RealityScan (formerly RealityCapture) is a photogrammetry-first engine that meshes LiDAR well and, per NExT Lab, "generally produces a better mesh result compared to other methods." Workflow for your data:
- Update to **RealityScan 2.1** (the SLAM path did not exist before 26 November 2025; per RealityCapture-Training it "now supports SLAM point-cloud imports, e.g. XGRIDS, NavVis").
- Import the point cloud **as a mobile/SLAM dataset with trajectory**; RealityScan "wants to work with cameras/photos, it will automatically generate cameras by projecting the scan data into cameras." Ensure georeference is on (use *Local* if not truly geo-referenced) so pre-alignment is preserved.
- Generate virtual cameras at multiple heights/overlaps for coverage; then align, bringing in your **422 real photos** so they merge with the LiDAR-derived component via shared features (set *Prefer images as feature source = Yes*).
- **Reconstruction Settings that tame noisy mobile LiDAR:**
  - *LiDAR Scans > Minimal distance between two points* — raise this to set scan density and stop RealityScan resolving sub-noise detail.
  - *Point-cloud cropping radius* — drop far, low-accuracy returns.
  - *Minimal intensity* — discard low-intensity (unreliable) returns.
  - *Advanced > Default noise factor* — increase for a smoother mesh ("the bigger the noise factor, the smoother the mesh").
  - *Advanced > Default grouping factor* — increase to **prioritise the LiDAR over the photos** for geometry ("when both images and LiDAR scans are being used to mesh, increasing this value will mean the laser scans will be prioritized for meshing").
  - *Adaptive blending start* — leave at default 0.45 unless you know what you're changing.
  - Use a **reconstruction region** and consider *Remove marginal triangles*.
- Texture from the 422 photos.

The prior "won't-merge" behavior is because pre-2.1 RealityScan treated a co-located LiDAR component and camera component as separate; the 2.1 SLAM importer with pose priors / virtual cameras is designed specifically to bridge them. If they still won't merge, use *Merge Components* with control points, or add more overlapping images.

### Option D / E: Direct live meshers and commercial tools
- **ImMesh / SLAMesh** mesh LiDAR-inertial data in real time on CPU and are excellent for *live capture feedback*, but produce rougher (ImMesh) surfaces and are not the cleanest final deliverable. Use ImMesh's live preview during capture to ensure coverage, but do the final mesh with TSDF.
- **FAST-LIVO2** is the strongest end-to-end path if you can re-run your raw data through it: it outputs a dense pixel-accurate colored cloud *and* the group's reference meshing/texturing pipeline (VDBFusion + OpenMVS). It reduced dense-cloud + pose generation from 9 hours (COLMAP) to 21 s in their tests.
- **Commercial:** Leica Cyclone 3DR and similar embed tuned Poisson/Delaunay variants with survey workflows if budget allows.

## Recommendations

**Stage 1 — Do this first (highest leverage): switch from point-cloud Poisson to TSDF fusion of posed frames.**
- Recover your per-frame LiDAR scans + Point-LIO poses (rosbag or logged frames). Run **VDBFusion** with `voxel_size = 0.01–0.02 m`, `sdf_trunc = 3× voxel_size`, `space_carving = True`. Extract mesh; tune `min_weight` up until floaters disappear.
- If you only have RGB-D-style posed frames, use **Open3D ScalableTSDFVolume** at `voxel_length ≈ 0.008 m`.
- **Benchmark that changes the plan:** if the TSDF mesh shows clean, continuous single-surface walls with readable openings, you are done geometrically — proceed to texturing. If it is oversmoothed and loses furniture/opening detail, *lower* voxel_size toward 0.008 m and reduce sdf_trunc.

**Stage 2 — Texture for set-design use.**
- Bring the TSDF mesh + 422 posed photos into **RealityScan 2.1** (import mesh, use *Texture from images*) or **OpenMVS** `TextureMesh` (the FAST-LIVO2 route). Either gives readable, photo-accurate walls/furniture.

**Stage 3 — Fallback if you cannot get per-frame data.**
- Run the **CloudCompare SOR → MLS (radius 2–4 cm, poly order 2) → voxel 5–8 mm → normals (Plane, MST KNN 10–20) → Screened Poisson depth 10–11 → density trim** recipe. Accept slightly rounded corners.

**Stage 4 — Or try RealityScan 2.1's native SLAM path directly** (import cloud + trajectory, generate virtual cameras, merge 422 photos, mesh with *Minimal distance between two points* raised and *Default noise/grouping factors* increased to favor LiDAR). This is the least-code route and may be sufficient on its own.

**Thresholds that change the recommendation:**
- Median spacing 7 mm and 2–3 cm noise → TSDF voxel ≈ 1–2 cm is the sweet spot; if you needed sub-cm detail (you don't for set design) TSDF would start to hole and you'd revert to MLS+Poisson.
- If walls read cleanly but you see oversmoothing of trim/openings → drop voxel size or switch the fallback to MLS+Poisson.
- If RealityScan still won't merge components in 2.1 → fall back to Stage 1+2 (TSDF then external texture), which sidesteps RealityScan's alignment entirely.

## Caveats
- **Verified vs. inferred:** The Open3D TSDF averaging mechanism, VDBFusion's per-frame `integrate(scan, origin)` API, FAST-LIVO2's use of VDBFusion, MLS's double-wall fix, the CloudCompare SOR→MLS→Poisson→density-trim sequence, and RealityScan 2.1's SLAM import are all directly documented (primary sources: Open3D docs, VDBFusion README/paper, FAST-LIVO2 arXiv:2408.14035, CloudCompare wiki/forum, RealityScan Help + Epic Developer Community release notes). The **specific numeric voxel_size/sdf_trunc for your 7 mm data are extrapolations** from a published 1.1 cm indoor precedent and the voxel-≥-spacing constraint, not an official spec — tune empirically. VDBFusion's `min_weight` default is unverified.
- **You must have per-frame data for Options A and C-virtual-cameras to work at their best.** If Point-LIO only saved the accumulated map, TSDF's drift-cancelling advantage is lost and you are limited to the MLS+Poisson path (Option B), which is inherently more manual.
- **RealityScan 2.1 SLAM support is very new (Nov 2025)** and validated mainly on XGRIDS/NavVis-class scanners; behavior with a DIY Unitree L2 / Livox + Point-LIO rig is not specifically documented and may need the "create ordered point cloud from unordered" step.
- **ImMesh/SLAMesh quality claims** come partly from the authors' own papers and one independent benchmark (PlanarMesh, arXiv:2510.13599, which reported 3–4 cm mean mesh-to-point error on the Oxford Spires Dataset while outperforming VDBFusion, ImMesh and OctoMap baselines); treat "cleaner than Poisson" claims as method-and-dataset-dependent.
- No single published head-to-head table ranks VDBFusion vs Poisson vs ImMesh vs RealityScan on *identical handheld indoor data*; the ranking here is synthesized from the mechanism, the PlanarMesh VDBFusion-vs-ImMesh benchmark, and practitioner writeups.