# LiDAR-Camera Capture Architecture vs. RealityScan 2.x → Unreal Engine 5.8: Conflict Analysis

## TL;DR
- **Your capture architecture largely ALIGNS with RealityScan's newest (2.1) LiDAR/SLAM path — but you are exporting the WRONG artifact.** RealityScan wants the *raw camera images + the SLAM trajectory/poses + the dense(st possible) LiDAR point cloud*, not a 5 cm voxel-accumulated colored PLY. The voxel map and the per-point colorization are excellent for live coverage QA but are the wrong deliverable to hand to RealityScan.
- **Feed RealityScan images+poses+geometry, not a pre-colored cloud.** RealityScan textures the mesh from full-resolution photos (your 1920×1200 global-shutter frames), producing a proper UV texture atlas that Unreal 5.8 Nanite + PBR wants. Pre-colorizing at ~per-point resolution and voxelizing to 5 cm throws away exactly the texture detail RealityScan would otherwise recover, and your last test failed (2.7% colored, too sparse) precisely because you fed the voxel/colored-cloud artifact rather than images+poses.
- **Close TAU before you commit texture-quality captures, but it mostly matters for the colorized-cloud path.** A ~180 ms LiDAR-camera offset during motion smears per-point color and would ghost a colored-cloud texture; it matters far less if RealityScan textures from the discrete images at their own timestamps. TAU is critical for your colorize/QA path and for pose-time alignment, near-negligible for a static/slow capture.

## Key Findings

1. **RealityScan 2.1 (released November 26, 2025) explicitly supports handheld SLAM data.** Per Epic's official RealityScan 2.1 documentation: *"Importing point clouds from SLAM scanners, such as XGrids, is now supported. First import images and their trajectories, or open a Colmap Scene… Import the point cloud and generate virtual cameras based on camera pose priors or an imported component from a Colmap scene."* This is exactly your rig's output class (Point-LIO poses + global-shutter images + LiDAR cloud). The architecture is *conceptually* a first-class citizen now, and per the official RealityScan news page the SLAM path specifically "enables fast data acquisition with live tracking and coverage visualization… [and] cleaner geometry on surfaces problematic for photogrammetry."

2. **RealityScan does not mesh directly from your colored points; it renders virtual cameras from the cloud and does photogrammetry-style feature-matching on those renders.** Density therefore matters enormously: Epic's own Alcatraz spotlight (VCTO Labs / Pete Kelsey) states that because their cloud "was very dense, the .lsp files looked like actual photographs, making ground control point marking easy and accurate." A 5 cm-voxelized, 2.7%-colored cloud produces sparse, feature-poor virtual renders — which is why your last import aligned a component but was "too sparse to build a model."

3. **The recommended high-quality workflow is explicitly "LiDAR for geometry, photogrammetry for textures"** — a verbatim section heading in the Alcatraz spotlight, which continues: *"we used the aerial LiDAR data to reconstruct the mesh and the photogrammetry to generate high-resolution textures… The LiDAR-based mesh reconstruction produced over 200 million polygons, and RealityScan generated twenty-one 8K textures for maximum detail."* When real images are present, RealityScan generates the texture atlas from full-resolution photos, not from per-point cloud color. Your pre-colorization is therefore redundant-to-counterproductive for the RealityScan deliverable path.

4. **RealityScan's "Colorize" (per-vertex) vs "Texture" (UV atlas) are different operations.** Per-vertex colorize looks poor in Unreal and its detail is capped by mesh vertex density; "Texture" bakes a real UV-mapped image. You must run Texture (F9), sourced from images, to get what Unreal 5.8 wants.

5. **Unreal 5.8 wants a UV-textured (Nanite) mesh with PBR materials for a walkable, relightable environment.** Per Epic's official UE 5.8 Nanite documentation, it is "possible to directly import film-quality source arts, such as ZBrush sculpts and photogrammetry scans," and while "Virtual textures are not required for use with Nanite… they are highly recommended" for high-resolution PBR. Per-vertex color and raw point clouds are not the native relightable path. (Gaussian splats are an alternative but are third-party-plugin-only in UE 5.8 and are generally not relightable.)

## Details

### Your architecture, mapped to the tools
Your rig is a textbook handheld SLAM capture rig: a Unitree L2 4D LiDAR with built-in IMU, a calibrated 1920×1200 global-shutter camera at ~26 fps, Point-LIO odometry on a Jetson, and checkerboard/Kabsch extrinsics. Per the official Unitree 4D LiDAR L2 User Manual (v1.1, 2024.10), the L2 has a 128,000 pts/s sampling rate (64,000 effective pts/s), a 360°×90° FOV (extendable to 360°×96° in negative-angle mode), 30 m max range at 90% reflectivity, 4.5 mm ranging resolution, a 500 Hz-reporting IMU, and weighs 230 g. Point-LIO is Unitree's vendor-referenced mapping algorithm for it. This is precisely the "handheld SLAM scanner" class RealityScan 2.1 added support for in November 2025.

Your five pipeline stages serve two *different* goals that you have conflated:
- **Live capture QA (stages 2–4):** per-frame sparse colorize → bounded 0.05 m voxel accumulation (capped 2M voxels, hit-counted) → marching-cubes coverage viz with RED→GREEN hit-count coloring. This is an excellent operator-guidance loop and is genuinely well-designed. Notably, RealityScan itself now advertises "live tracking and coverage visualization" as the *reason* SLAM workflows are valuable — so your QA loop mirrors the tool's own philosophy. Nothing about it needs to change for its own purpose.
- **The RealityScan deliverable (stage 6):** this needs a *different* export. RealityScan does not want your bounded, quantized, pre-colored map; it wants the primary sensor data.

### Conflict 1 — Sparse colored points vs. RealityScan's needs
RealityScan's LiDAR/SLAM pipeline converts point clouds into "LSP files—an internal format which resemble images," generates virtual cameras that "render the laser scan," and then aligns and meshes "just like with terrestrial LiDAR" — i.e., it does feature detection on rendered views (official RealityScan Help; Alcatraz spotlight). The density of the cloud directly controls how photograph-like those renders are and therefore how well alignment and GCP marking work (Alcatraz: dense cloud → ".lsp files looked like actual photographs").

Your voxel-accumulated map is *temporally* dense but *spatially* quantized to 5 cm and, in your last test, only 2.7% colored. That is the worst case for RealityScan's render-and-match approach: sparse, color-holed virtual renders with no fine texture for tie-points. The result you observed — aligns into a component but "too sparse to build a model" — is the predictable symptom. There is a real conflict between "bounded 2M-voxel map for live feedback" and "RealityScan wants maximum density/detail."

### Conflict 2 — 0.05 m voxelization vs. texture quality
5 cm voxels are coarse relative to indoor texture detail and RealityScan's texel targets. RealityScan lets you set texel size in coordinate units (its docs give "the texel can be 5 mm big" as an example) and, per Nira's RealityScan texturing guide, supports a "Maximal texture resolution [of] 16,384 x 16,384" and can output "all of your textures into a single texture file up to 64K (65,536 x 65,536)." Quantizing geometry and color to 5 cm destroys the sub-cm color/texture variation that both RealityScan's tie-point matching and its texture baking rely on. **Do not feed the voxel map for the final model.** If you must feed a cloud, feed the raw per-frame colored points (pre-voxelization) or, better, the raw LiDAR cloud + images.

### Conflict 3 — Colored point cloud vs. images+poses (the central issue)
This is where your proven architecture most clearly diverges from the deliverable. RealityScan supports two starting points: (a) import images + trajectories (or a COLMAP scene) then import the point cloud and generate virtual cameras from pose priors; or (b) import the cloud alone and auto-generate cameras. Path (a) is strongly preferable for you because:
- **Texture comes from the images at full resolution, not from per-point color.** The documented best-practice is "LiDAR for geometry, photogrammetry for textures." Your 1920×1200 frames carry far more texture detail than any per-point colorization of a 5 cm cloud.
- **Pre-colorizing is redundant for this path.** RealityScan will re-project the original images onto the mesh itself. Per-point color is only used when no images are present.
- **Indoor caution:** photogrammetric feature-matching struggles on blank walls/uniform texture (a well-documented indoor failure mode — smooth featureless surfaces produce a "severe scarcity of distinctive visual features"). Your LiDAR geometry is the antidote — this is exactly why the hybrid "LiDAR geometry + image texture" path exists, and why importing the LiDAR cloud *with poses* to seed the geometry/alignment is valuable. But the color/texture should still come from images.

Concretely: export (1) the undistorted images, (2) the Point-LIO trajectory as camera poses — RealityScan 2.1 rebuilt its trajectory importer and, per Radiance Fields' 2.1 coverage, added "improved COLMAP exports that correctly reference original distorted images" plus new OpenCV and XMP outputs, so a COLMAP-format export of your images+intrinsics+poses is the cleanest bridge — and (3) the raw (un-voxelized) LiDAR cloud in PLY/LAS/E57 as a LiDAR scan, registered "Exact," georeferenced "Local."

### Conflict 4 — TAU / time-sync vs. reconstruction quality
The ~180 ms LiDAR-lags-camera offset matters differently per path:
- **Colorized-cloud path (your current export):** during motion, color is painted onto LiDAR points from a different instant. This produces exactly the failure documented by Liu et al. (OmniColor, arXiv:2404.04693, 2024), where LiDAR-camera colored point cloud maps "still suffer from blurring, ghosting, and other visual artifacts, due to inaccurate camera poses and illumination variations." At a modest handheld pan, 180 ms is a large spatial displacement, so a colored-cloud texture would show visible color-geometry misalignment. TAU is critical to close before trusting this path.
- **Images+poses path (recommended):** RealityScan textures from discrete images at their own capture instants and refines camera poses during alignment, so the color source is not smeared. TAU still matters for placing each image's pose correctly on the trajectory (a 180 ms error at pan speed misplaces the camera), but RealityScan's own bundle-adjustment/alignment can absorb residual pose error better than fixed per-point painting can.
- **Static/slow capture:** TAU's effect scales with velocity; for a near-static or very slow capture it is negligible. This is a legitimate mitigation if you cannot close TAU immediately: capture texture-critical areas slowly/statically.

Verdict: close TAU (finish `tau_solve.py`) before committing colorize-dependent captures; it is less critical — but not zero — for the images+poses path.

### Conflict 5 — What Unreal 5.8 actually wants
For a walkable, relightable environment, Unreal wants a UV-textured mesh with PBR material inputs (base color, normal, roughness, metallic, AO), ideally Nanite-enabled. Nanite is designed to ingest "photogrammetry scans" directly and supports (and highly recommends) virtual texturing for high-resolution PBR maps. Key facts:
- **Per-vertex color is not what you want.** RealityScan's "Colorize" bakes color to vertices and "does not create the same detail quality as the texturing"; its quality is capped by mesh vertex density. In Unreal you'd need a vertex-color material and it looks poor. RealityScan's "Texture" (F9) instead unwraps UVs and bakes an image atlas — this is the Unreal-ready output.
- **RealityScan produces a UV atlas when you run Texture, regardless of whether the source is a colored cloud or images** — but the atlas *quality* depends on the color source. Images → sharp atlas. 5 cm colored cloud → soft, low-detail atlas.
- **PBR/relighting caveat:** RealityScan bakes lit color (albedo+baked lighting) into the texture. For a truly relightable environment you'll need to de-light the texture and author roughness/normal/metallic, or accept baked lighting. Nanite handles the geometry; relighting quality is on your material authoring, not on RealityScan.
- **Gaussian splatting alternative:** UE 5.8 has no shipping first-party Gaussian Splatting module; splats are supported only via third-party plugins (NanoGS, WallGS for UE 5.3–5.8, XScene, Volinga) and are generally not relightable. For a *relightable* walkable environment, the UV-textured Nanite mesh is the correct target, not splats.

### The honest verdict
Your capture architecture and RealityScan are **aligned in principle** (handheld SLAM is now supported) but **your export artifact is misaligned in practice.** The voxel accumulator and per-frame colorize are the right tools for live coverage feedback and the wrong tools for the RealityScan hand-off. The single highest-leverage change is to **stop feeding RealityScan the colored voxel map and start feeding it images + Point-LIO poses (COLMAP format) + the raw un-voxelized LiDAR cloud**, then texture from the images. This resolves Conflicts 1, 2, 3, and 5 simultaneously and downgrades Conflict 4 (TAU) from critical to secondary.

## Recommendations

**Stage 1 — Re-plumb the export (do this first).**
- Add an export path that writes: (a) undistorted JPEG/TIFF frames (keyframe-decimated to good overlap, not all 26 fps), (b) a COLMAP-format `cameras/images/points3D` export carrying your intrinsics + Point-LIO poses (RealityScan 2.1 imports COLMAP and references original distorted images), and (c) the **raw, un-voxelized** accumulated LiDAR cloud as PLY/LAS/E57.
- Keep the 0.05 m voxel map and `mesh_check.py` exactly as-is — but only as the live QA tool, not as the RealityScan input.

**Stage 2 — Validate in RealityScan.**
- Import images+trajectory (or COLMAP scene), import the LiDAR cloud as a LiDAR scan with Registration = **Exact**, Georeferenced = **Local**. Generate virtual cameras from pose priors / the imported component.
- Align, build the mesh from LiDAR geometry, then **Texture (F9) from the images**. Confirm you get a UV atlas, not vertex color.
- Benchmark: aim for a cloud dense enough that virtual-camera renders "look like photographs." If alignment still fragments, add real image overlap or control points on blank indoor surfaces.

**Stage 3 — Close TAU before texture-critical captures.**
- Finish `tau_solve.py`; treat a result within roughly ±1 camera-frame (~40 ms) as good enough for the images+poses path. For the colorize/QA path you want it tighter.
- Interim mitigation: capture texture-critical areas slowly or statically so velocity×TAU error is negligible.

**Stage 4 — Unreal 5.8 finishing.**
- Import the RealityScan FBX/OBJ + texture atlas; enable Nanite on the static mesh; wire a PBR master material + instances (with Virtual Textures enabled for 4K+ maps).
- For relighting, de-light the baked albedo and author roughness/normal; otherwise accept baked lighting for a lit-look walkthrough.

**Thresholds that would change the plan.**
- If RealityScan still can't build a model from images+poses+dense cloud → your bottleneck is image overlap/quality or cloud density, not the export format; increase keyframe density and slow the capture.
- If you cannot decouple color from the cloud (must ship a colored-cloud product) → TAU becomes mandatory and you should also consider a Gaussian-splat deliverable (third-party UE plugin), accepting loss of relightability.
- If the deliverable does not actually need relighting → a Gaussian splat may be faster/higher-fidelity than the mesh path.

## Caveats
- **The official RealityScan 2.1 "SLAM Support" tutorial body could not be text-extracted** (JavaScript-rendered); the step-level SLAM workflow above is corroborated from Epic's release notes/docs, the official RealityScan 2.1 news page, the official Alcatraz spotlight, the Univ. of Melbourne NExT Lab guide, and a forum user replicating the tutorial. Registration=Exact / Georeference=Local for handheld SLAM is supported by those secondary sources, not by a verbatim tutorial quote.
- **The Alcatraz spotlight describes aerial LiDAR (RealityScan 2.0), not handheld SLAM**, but uses the same virtual-camera/.lsp mechanism; the "dense cloud → photograph-like renders" and "LiDAR geometry + photogrammetry texture" principles carry over.
- **No official numeric point-density threshold exists** for RealityScan indoor texturing; guidance is qualitative (denser is better; texel targets in mm). Treat the "2.7% colored is too sparse" as an empirical failure point, not a published limit.
- **One community practitioner cautioned that "SLAM is the least reliable laser scanning method… do not use SLAM for anything requiring high accuracy, especially without Control."** This is opinion, not Epic guidance, but flags that adding control points helps registration accuracy for handheld captures.
- **Unreal 5.8 released mid-2026** (June 2026); its Nanite/photogrammetry ingestion and virtual-texturing behavior are consistent with UE5 generally. Gaussian-splat support in 5.8 remains third-party-plugin-only as of this writing.
- **TAU quantitative impact** (how many mm of ghosting per 180 ms) depends on your actual pan velocity, which was not measured here; the direction of the effect is certain, the magnitude is capture-dependent.
