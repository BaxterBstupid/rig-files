# LiDAR + Posed-Camera Capture → Relightable UV-Textured Mesh for UE5: 2026 Software Guide

## TL;DR
- **RealityScan (Epic's rebranded RealityCapture) is your primary tool and it is free** for anyone/any company under $1M annual gross revenue: it can import your Unitree L2 point cloud as "mobile LiDAR," reuse your existing camera poses (via COLMAP scene import or XMP priors) instead of re-solving structure-from-motion, mesh the LiDAR geometry, and bake a UV texture atlas from your registered photos — exporting FBX/OBJ straight into UE5.
- **De-lighting is the hard part, not the meshing.** Your daytime photos have baked shadows; run the resulting texture through the free Agisoft De-Lighter (or Metashape Pro's Remove Lighting) to get flatter albedo, but expect only partial success — Agisoft's own documentation states "delighting in strong shadows is not supported." The most robust fix is to re-capture in flat overcast light where feasible, or plan manual cleanup.
- **Budget pipeline:** RealityScan (free) for mesh+texture → Agisoft De-Lighter (free) for albedo → UE5 import as a Nanite static mesh with a relightable PBR material. A Blender-based projection-bake path (free) is the fallback if you want tighter control or RealityScan's pose import fights you.

## Key Findings

### The single best fit: RealityScan 2.1+ (free)
RealityScan is uniquely suited to your exact assets because, as of version 2.1 (released November 2025) and 2.1.1 (April 2026), it explicitly supports the "LiDAR geometry + posed photos, no fresh SfM" workflow. Per Epic's RealityScan 2.1 documentation, "Importing point clouds from SLAM scanners, such as XGrids, is now supported. First import images and their trajectories, or open a Colmap Scene... Import the point cloud and generate virtual cameras based on camera pose priors or an imported component from a Colmap scene." Your Unitree L2 point cloud + posed frames are the same shape of data as an XGrids SLAM rig, so this pathway was effectively built for your case.

Concretely, RealityScan can:
- **Import COLMAP scenes** (cameras.txt / images.txt / points3D.txt) carrying your known intrinsics + extrinsics. Version 2.1.1 added FULL_OPENCV camera-model import — per Radiance Fields (April 2026), "RealityScan 2.1.1 improves both import and export compatibility with COLMAP by adding support for the FULL_OPENCV camera model" — so your K + distortion coefficients map in cleanly.
- **Import mobile LiDAR** (LAS/LAZ/E57/PLY/CSV/XYZ/PTS) and take camera poses "from prior camera poses, from an existing component with registered poses, or generated automatically."
- **Mesh the LiDAR and texture that mesh with the registered images** — LiDAR provides geometry, photos provide texture. Per the official Capturing Reality help, "RealityScan enables automatic registration, filtering, coloring, texturing, and meshing of LiDAR data. There are no limitations on the number of scans or the size of your project."
- **Export FBX/OBJ with a UV texture atlas**, and it is a first-class UE5 citizen (Nanite, Datasmith ecosystem, direct tutorials).

**Licensing:** Per Epic's RealityScan licensing page and CG Channel (Nov 2025), "RealityScan is free to artists and studios with revenue under $1 million/year. For larger studios, subscriptions cost $1,250/seat/year" (or $1,850/seat/year bundled with Unreal Engine and Twinmotion). You qualify for the free tier. Free licenses are obtained through the Epic Games Launcher / Developer Portal.

### Others, ranked
- **Agisoft Metashape** (per Agisoft's official store, $179 Standard / $3,499 Professional, node-locked perpetual licenses that are "NOT time-limited" and include 12 months of support plus free updates through version 2.x.x): can combine LiDAR + photos and build/texture a mesh, and Professional has a built-in "Remove Lighting" de-lighter. But Metashape builds meshes from its own depth maps, not directly from an imported LiDAR cloud (the cloud is used as reference/guidance), and reusing pre-solved external poses is more awkward than in RealityScan. Its edge is integrated de-lighting and a predictable perpetual license.
- **Meshroom (AliceVision, free):** can import known poses via a cameras.sfm JSON, but the workflow is fragile — multiple GitHub issues document it silently re-solving or failing at the mesh stage when fed external poses — and it's weaker at fusing an external LiDAR cloud. Fallback only.
- **Blender (free):** the universal fallback — import the LiDAR-derived mesh, set up cameras from your poses, project photos, and bake to a UV atlas using the native UV Project modifier + bake, or add-ons like Eyek ($15+, multi-image projection to one UV with occlusion handling). Most manual but total control and free.
- **CloudCompare + MeshLab (free):** CloudCompare for Screened Poisson meshing of the cloud (use the Density output to trim spurious surfaces), MeshLab for raster-based texture projection from posed images (Filters → import raster → raster alignment → parameterization + texturing). Viable free path but clunkier UVs.
- **Autodesk ReCap:** survey-oriented, weak as a textured-mesh-for-VFX exporter; not recommended here.

### De-lighting reality check
- **Agisoft De-Lighter** is a free, cross-platform standalone tool that removes lighting gradients and ambient occlusion from an existing textured mesh, outputting flatter albedo. It requires the user to paint rough lit/shadow brush strokes and is optimized for 8-bit JPEG textures.
- **Metashape Professional's "Remove Lighting"** (Tools → Mesh → Remove Lighting) is the same technology built-in. Per Agisoft's Helpdesk, "delighting in strong shadows is not supported... removing shadows and recovering lighting-neutral color while preserving texture features is impossible." This is a fundamental limitation, not a tuning problem.
- **Unity De-Lighting Tool** is free but requires you to pre-bake AO/bent-normal maps and is Unity-oriented.

The honest takeaway: de-lighting will *improve* daytime textures but will not fully erase strong cast shadows. For day-to-night previz, that residual can matter. The cheapest high-quality fix is at capture time — shoot in overcast/diffuse light.

### The Unreal-native path is NOT sufficient alone
UE5's LiDAR Point Cloud plugin renders points, which do not relight — not what you want. There is no UE5 plugin that meshes + UV-textures a cloud + photos end-to-end. RealityScan is the Epic-blessed front end; you export the mesh from it and import to UE5, then enable Nanite (a single flag on the static mesh) and apply a PBR material.

## Details

### Why RealityScan reuses your poses instead of re-solving
Your pain point with the old Open3D script was that it only produced a 2D render. RealityScan solves the actual "3D textured mesh" problem and can largely skip the expensive SfM step because you already have poses. Two mechanisms:

1. **COLMAP import.** Open → set the format to "Colmap Text Format" in the Open Project dialog → select the file; or use the `importColmap` CLI command, which "imports a COLMAP project using the path to any of the three COLMAP text files." Convert your `posed_images.npz` + calibration into COLMAP text format with a short Python script (well within your existing toolchain).

2. **XMP priors.** RealityScan reads per-image XMP files with `xcr:PosePrior` and `xcr:CalibrationPrior`. The three prior modes are **draft** (absolute positions, adjustable during alignment), **exact** (relative positions preserved — good for rig geometry), and **locked** (both relative and absolute positions "remain fixed and are not adjusted during the alignment phase"). Use **locked** to freeze your known world-frame poses. The export save type is literally named "RealityScan XMP (exact priors, absolute coordinates)."

Then import the Unitree L2 cloud as mobile LiDAR, set the pose-reuse option to take poses from your existing component ("Extract from component"), mesh the LiDAR, and texture with the images. **Caveat:** even with imported poses, RealityScan typically still runs an alignment pass that *consumes* (rather than re-solves) the poses; it is not documented as a 100% SfM skip. The analogous Bundler/CMPMVS imports require an alignment run that reuses the imported cameras.

### Hardware fit (Shadow PC, RTX A4500, 28GB RAM)
Good news on RAM. Per Epic's RealityScan Hardware & Software Requirements, "Processes such as meshing, coloring, and texturing are fully out-of-core... Even with very large datasets (e.g., over a million images or scans), these tasks can be completed effectively on machines with as little as 16 GB of RAM." Your 28GB is therefore comfortable for the mesh/texture stages.

The only RAM-heavy step is **alignment (SfM)**, which scales with image count × features/image — and your pose-reuse approach specifically minimizes that. If any alignment runs and RAM gets tight with 2,200 images, reduce features/image. Per Puget Systems (quoting the RealityCapture developers), the approximate formula is "RAM = features × images × 200 bytes," and "by decreasing the number of detected features to half you can approximately decrease the memory consumption by half," i.e. dropping from the default 40,000 to ~20,000.

Your **RTX A4500** — per NVIDIA's datasheet, 20GB GDDR6, 7,168 Ampere CUDA cores, 56 RT cores, 200W — vastly exceeds RealityScan's recommended minimum (4 CPU cores, 16GB RAM, 1024 CUDA cores) and is a strong meshing/texturing card. Use a fast NVMe scratch disk, since out-of-core processing = heavy disk I/O. Note that Puget Systems recommends 32GB as a practical baseline ("The 16GB minimum recommendation... is viable, but 32GB provides a better baseline without costing much more"; 16GB tested only ~12% slower than 128GB on their biggest map). Your 28GB sits just under that soft recommendation but is fine for the non-alignment stages you'll lean on.

### Getting to relightable in UE5
1. In RealityScan: mesh from LiDAR, build texture (e.g. 8K atlas, Mosaic/natural blending; note 2.1 enabled texture defragmentation charts by default for higher-quality UVs), export FBX + texture. RealityScan can also export a companion `.rsInfo` file so you can round-trip the mesh out for cleanup and back in for re-texturing.
2. De-light the texture in Agisoft De-Lighter → albedo.
3. Import the FBX to UE5, enable Nanite on the static mesh, plug the de-lit albedo into a PBR material as base color (set roughness/metallic manually or flat), then add your own day/night lighting for previz.

### Note on Gaussian splatting (adjacent, not your ask)
Splatting tools (Postshot — free tier, needs RTX 2060+; Polycam) and UE5 splat plugins (XScene-UEPlugin free/open-source; Postshot, Volinga, Akiya "3D Gaussians" on Fab) give fast photoreal capture and can even import RealityScan camera alignments. But per multiple 2026 production write-ups, splats do NOT dynamically relight in UE5 — "the baked radiance does not respond to a flashlight, muzzle flash, or time-of-day system." For day-to-night relighting previz you specifically need a mesh + albedo, so splatting is the wrong primitive here despite the hype.

## Recommendations

**Stage 1 — Prove the pipeline (this week, $0):**
1. Install RealityScan free via the Epic Games Launcher; confirm you're under the $1M revenue threshold (you are).
2. Write a small Python converter: `posed_images.npz` + intrinsics/distortion + `.pcd`/`.npy` → COLMAP text format (cameras.txt/images.txt/points3D.txt) and a LAS/PLY of the cloud. Match your distortion model to FULL_OPENCV so intrinsics import faithfully.
3. Import the COLMAP scene, import the cloud as mobile LiDAR with pose reuse "from component," mesh, texture, export FBX. Import to UE5 and enable Nanite. This validates the geometry + texture round-trip end to end.

**Stage 2 — Relighting quality:**
4. Run the exported texture through Agisoft De-Lighter (free). Judge whether the flattened albedo relights acceptably under a UE5 day/night rig.
5. If cast shadows remain objectionable (likely, given daytime capture), decide between (a) manual paint cleanup in Substance/Photoshop, or (b) re-shooting future captures in flat overcast light.

**Fallback if RealityScan's pose import fights you:**
6. Mesh the cloud in CloudCompare (Screened Poisson, trim by density), then in Blender: place cameras from your poses, project + bake to a UV atlas (native UV Project + bake, or the Eyek add-on), de-light, export to UE5.

**Thresholds that change the recommendation:**
- Need certified/georeferenced accuracy → Metashape Professional.
- Company crosses $1M gross revenue → budget $1,250/yr for RealityScan or move to the fully-free Blender path.
- De-lit daytime textures look unacceptable and you can re-capture → shoot overcast; this eliminates most of the de-lighting problem at the source and is cheaper than any software fix.
- Alignment RAM errors on 2,200 images → cut features/image to ~20,000 (halves RAM per the developer formula), or import poses as "locked" priors to minimize the alignment burden.

## Caveats
- **SLAM tutorial specifics unverified verbatim:** Epic's SLAM Support tutorial page is JavaScript-rendered and could not be scraped; the workflow is confirmed by Epic's 2.1 release notes and documentation, but view the tutorial in a browser for exact click-by-click steps and screenshots.
- **COLMAP import may still run an alignment pass:** it is not documented as a 100% SfM skip; analogous Bundler/CMPMVS imports require an alignment run that reuses (not re-solves) poses. Expect an alignment step that consumes your priors.
- **Camera model mapping:** confirm your distortion model maps to a RealityScan-supported model (FULL_OPENCV, added in 2.1.1) or intrinsics may need manual adjustment.
- **De-lighting is inherently limited:** per Agisoft, strong cast shadows cannot be removed; treat de-lighting as improvement, not perfection. This is the single biggest risk to your day-to-night relighting goal.
- **28GB RAM** is below Puget's 32GB soft-recommendation; per Epic it's ample for out-of-core texturing/meshing, but monitor memory during any alignment step.
- **Metashape LiDAR handling:** it uses imported clouds as reference/guidance but builds the mesh from its own depth maps — verify this behavior before committing if you require the LiDAR cloud to *be* the geometry (RealityScan is stronger on that specific point).
- **Version note:** features you need (SLAM/COLMAP import + LiDAR-photo fusion) landed in RealityScan 2.1 (Nov 2025) and were refined in 2.1.1 (April 2026); ensure you're on 2.1.1 or later. Pricing and licensing figures are current as of publication but Epic/Agisoft can change terms — verify on the vendor sites before purchasing.