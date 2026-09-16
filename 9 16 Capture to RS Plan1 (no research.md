# Hot-Capture-to-RealityScan: A Colored-LiDAR Pipeline for a Unitree L2 + Camera Rig

> **Verification note:** My live web-search and web-fetch tools failed for this session (hard "tool not provided" errors), and the dispatched research subagent's tools failed identically. The report below is built from established domain knowledge of RealityCapture/RealityScan, ROS2 colorization packages, and the Unitree L2 SDK. Claims I could not confirm against a live primary source this session are explicitly marked **[VERIFY]**. Treat those as high-confidence engineering guidance that still warrants a 5-minute doc/GitHub check before you commit hardware time.

## TL;DR
- **Yes — build the colorize-on-rig path and drop the pose file entirely.** The single most reliable minimal build is: colorize each raw `/unilidar/cloud` scan against the temporally-nearest `/image_raw` frame using your trusted extrinsic, let Point-LIO's trajectory accumulate those colored scans into one merged RGB cloud, export `.ply` (uint8 RGB) or `.e57`, and hand RealityScan the colored cloud + the image folder. No poses, no COLMAP, no XMP.
- **RealityScan 2.x does auto-register a colored cloud to photos by rendering "virtual/synthetic images" from the cloud's color and feature-matching them to your real photos into one component — but this is reliability-sensitive, not magic.** A dense, well-colored ~1.8M-point indoor cloud with real texture will usually align; feature-poor/repetitive interiors will still need a handful of control points. Color-based features are materially more robust than intensity-based ones (your intensity path failed because reflectance renders noisy and low-contrast). **[VERIFY the exact "Features source = Color" label.]**
- **Use `leo-drive/color-point-cloud` (ROS2-native) as the colorizer if it accepts your topics/extrinsic config; otherwise write a ~150-line rclpy node** (project → distort → sample → append RGB). Colorize-then-accumulate beats colorize-the-finished-map for robustness because per-scan geometry is closest to the camera and time-sync error is smallest.

## Key Findings

1. **The one new build you need is per-scan colorization from the extrinsic — and it requires no SLAM pose.** For each scan, transform points into the camera frame with `p_cam = R_L2C · p_lidar + t_L2C`, apply `K` + distortion to get pixel coordinates, keep points with positive depth that land inside the image, sample the RGB, and write it to the point. This needs only intrinsics, the extrinsic, and time-sync between `/unilidar/cloud` and `/image_raw`. It is the highest-leverage, lowest-risk component.

2. **Accumulation should happen AFTER colorization, using Point-LIO's trajectory as the placement engine.** "Colorize-then-accumulate" is more robust than "colorize-the-finished-map" because (a) each raw scan is captured from the closest possible camera vantage, minimizing projection error and occlusion mismatch, and (b) you only rely on the trajectory for rigid placement (a transform you already trust for mapping), not for the harder many-frames-onto-old-geometry projection.

3. **Occlusion handling matters moderately for RealityScan input, less than for a beauty render.** Because RealityScan only needs the color cloud to be *feature-consistent enough* to synthesize matchable virtual images, a modest z-buffer / hidden-point-removal pass per scan is worth doing but does not need to be perfect. Per-scan colorization is naturally occlusion-friendly (single close viewpoint).

4. **Formats: `.ply` with 8-bit RGB is the path of least resistance; `.e57` is the most "RealityScan-native" for colored scans; `.las 1.4` works but has a 16-bit RGB scaling trap.** RGB scaling (0–255 uint8 vs 0–1 float in PLY; 8-bit values dumped into LAS's 16-bit fields producing a near-black cloud) is the single most common reason a colored cloud imports as gray/black.

5. **Your pose-file pain disappears in this architecture** because RealityScan derives the registration itself from color features — you never author or convert a pose file again.

## Details

### 1. Colorizing the cloud on/near the rig using the extrinsic

**The math (the whole "new" algorithm).** For each LiDAR point `p_lidar = [X, Y, Z]` in the L2 frame:
1. Transform to camera frame: `p_cam = R_L2C · p_lidar + t_L2C`.
2. Cull points with `p_cam.z <= 0` (behind the camera).
3. Normalize: `x = p_cam.x / p_cam.z`, `y = p_cam.y / p_cam.z`.
4. Apply the distortion model (Brown-Conrady/`plumb_bob` radial-tangential `k1,k2,p1,p2,k3`, or fisheye/`equidistant` if that's your lens) to `(x,y)`.
5. Project with intrinsics: `u = fx·x_d + cx`, `v = fy·y_d + cy`.
6. Keep only `(u,v)` inside image bounds; sample the pixel (nearest or bilinear); write `r,g,b` onto the point.

This is exactly the per-scan colorization you described and it needs **no odometry**.

**ROS2 tools/packages, ranked for "bolt onto an existing bag":**
- **`leo-drive/color-point-cloud` — ROS2-native, top recommendation [VERIFY current ROS2 Humble branch + config schema].** Designed to fuse one or more calibrated cameras with a LiDAR using extrinsics and publish a colored cloud. If it accepts remappable topics and a camera-info + extrinsic config, this is the least-code option: point it at `/unilidar/cloud` and `/image_raw`, feed `K`/distortion and `R_L2C, t_L2C`, done.
- **`ctu-vras/point_cloud_color` (Czech Technical University) — mature colorizer, but historically ROS1 [VERIFY ROS2 support/branch].** Projects points into calibrated camera images and assigns color. If a ROS2 port exists, it is a strong fallback; if not, it's ROS1-only and you'd bridge or port.
- **`KevinJia1212/colored_pointcloud` — ROS1, saves colored `.pcd` [VERIFY].** Good reference implementation for the projection math, but likely not ROS2, so treat it as code to read, not to run.
- **Custom rclpy/rclcpp node — the guaranteed-to-fit option.** ~150 lines: subscribe to cloud + image (with `message_filters` ApproximateTime sync), vectorize the projection above in NumPy/OpenCV (`cv2.projectPoints` handles distortion), append `rgb` as a packed float32 field or `r,g,b` uint8 fields to a new `PointCloud2`, and either republish or write to disk. This is the surest way to avoid dependency/version friction, and the math is small.

For **extrinsic calibration validation** (if you ever need to re-check `R_L2C, t_L2C`): `koide3/direct_visual_lidar_calibration` (ROS2-capable) and `hku-mars/livox_camera_calib` are the standard targets-or-targetless tools. **[VERIFY]** — you already trust your extrinsic, so this is only for sanity checks.

**Unitree L2 driver note.** The L2 ships with `unilidar_sdk2` / `unitree_lidar_ros2` **[VERIFY exact repo + field layout]**, publishing a cloud with per-point intensity and a per-point time offset (plus built-in IMU on `/unilidar/imu`). Those per-point time fields are what let Point-LIO de-skew motion; preserve them upstream of colorization even though RealityScan itself only needs XYZ+RGB.

**Accumulated-cloud colorization — colorize-then-accumulate vs colorize-the-map:**
- **(a) Colorize-then-accumulate (RECOMMENDED):** colorize each raw scan at capture, then transform each colored scan by its Point-LIO pose (`/aft_mapped_to_init` gives the trajectory) and merge into one map. Every point is colored from the nearest camera view, so projection error, motion blur exposure to time-sync error, and occlusion are all minimized. A `map_accumulator`-style node (transform each cloud into the map frame via the odometry and concatenate, with a voxel-grid downsample to control density) is exactly the right home for the merge step.
- **(b) Colorize the finished map:** build the intensity map first, then reproject many camera frames onto old geometry using per-frame poses. This is more fragile: it *requires* an accurate per-frame trajectory (the very thing that "sometimes needs re-derivation"), suffers parallax/occlusion mismatch because the geometry was seen from many distances, and needs careful multi-view color blending. Use only if per-scan clouds are too sparse to colorize well.

**Verdict:** Path (a). It keeps your dependence on the trajectory limited to rigid placement — a transform you already trust for mapping — and never asks the camera to color surfaces it saw from far away.

**Occlusion handling.** A per-frame z-buffer (keep only the nearest point per pixel bucket) or hidden-point-removal (Katz et al., available in Open3D as `compute_point_cloud_hidden_point_removal`) prevents a background point from stealing a foreground pixel's color. For RealityScan input this matters *moderately*: bad occlusion creates "bleeding" color halos that can mislead the synthetic-image feature matcher, but per-scan colorization from a single near viewpoint already avoids most of it. Do a cheap z-buffer; skip elaborate HPR unless you see color bleed.

### 2. Does RealityScan 2.x actually auto-register a colored cloud to photos?

**Mechanism [VERIFY exact wording against CapturingReality/Epic docs].** RealityScan/RealityCapture aligns laser/LiDAR scans and photographs in the same alignment run. For a scan it **renders synthetic ("virtual") images from the scan data**, detects features on those rendered images, and matches them against features on the real photographs — merging scans and photos into a single component with no user-supplied camera poses. When the scan carries **RGB color**, the rendered images look like real photographs (real texture/edges), so the cross-matching to your Arducam photos is far stronger than when the render is driven by **intensity/reflectance**, which is low-contrast and noisy — precisely why your intensity path produced unusable control points.

**The setting.** In the scan's alignment/registration settings there is an option controlling what channel drives the rendered image; selecting **Color** (vs Intensity/Reflectance) is what you want. I could not re-confirm the literal label **"Features source = Color"** against a live doc this session — **[VERIFY the exact control name in RealityScan 2.x; the concept is correct, the string may differ].**

**Reliability for an indoor ~1.8M-point RGB cloud.** Realistic expectation: a *good* colored cloud makes alignment work most of the time, but it is not guaranteed "just works," especially indoors. Interiors are the classic hard case: blank walls, repeating fixtures, symmetric rooms, and low overlap between the synthetic views and your photo vantage points all reduce matchable features. So: budget for a **small number of control points** as a fallback, not as the default. If your photos have real parallax and texture and the cloud is dense and well-colored, expect single-component auto-registration; if the room is featureless, expect to place 3–6 control points to seed it.

**Bottom line:** color-based auto-registration is the right, more-reliable mechanism; treat control points as a documented contingency, not a routine step.

### 3. The full hot-capture-to-RS framework, step by step

**A. Capture discipline (for reconstruction, not just SLAM).**
- **Parallax is mandatory for photogrammetry alignment:** orbit each surface, vary height, shoot convergent (toe-in) rather than pure pans. RealityScan needs translation between photos to triangulate.
- **Translate from the first 1–2 seconds** so LiDAR-inertial odometry (Point-LIO) sees motion and initializes cleanly — avoid a static pan-only start that "pan-starves" the estimator.
- **Lean capture / duration discipline:** keep runs short enough that the camera and Jetson survive the full take (thermals, USB bandwidth at ~28fps, bag size). Prefer several short deliberate passes to one marathon.
- **Overlap:** ensure the camera FOV that colorizes the cloud also overlaps the areas you'll photograph for texture, so color features and photo features cover the same geometry.

**B. On-rig / on-Jetson processing (produce the RS-ready package).**
- Run (live or on the recorded bag) the colorization node → per-scan colored clouds.
- Accumulate colored scans via Point-LIO trajectory → **one merged colored map**, voxel-downsampled to a sensible density (e.g. 3–5 mm indoors) to keep it near your ~1.8M-point target.
- Export the **colored cloud** as `.ply` (uint8 RGB) or `.e57`.
- Export an **image folder** (JPG, sharp, well-exposed) — see formats below for the undistortion caveat.
- Write a tiny manifest (units = meters, coordinate convention, camera model) so future-you isn't guessing.

**C. Transfer to Shadow (cloud Windows workstation, RTX A4500):** copy the colored cloud + the image folder. That's the entire package — no pose files.

**D. In RealityScan:**
1. Import the colored cloud (as Mobile/LiDAR scan), set the features source to **Color**, enable generation of virtual/synthetic images. **[VERIFY labels.]**
2. Import the images.
3. **Align** → RealityScan renders color images from the cloud and matches them to your photos → single component. If it splits into multiple components, add control points and re-align.
4. **Reconstruct mesh from the LiDAR geometry** (clean metric geometry) rather than from dense photo stereo.
5. **Texture from the photos** (high-res color) → **UV atlas/unwrap**.
6. **Export FBX** (+ textures) for Unreal.

**E. Where it can still fail — go/no-go checkpoints.**
- **Time-sync drift** between cloud and image (fast motion) → smeared color → weak features. *Go/no-go:* spot-check a colored scan; edges should be crisp, not rainbow-fringed.
- **Extrinsic error** → color offset from geometry. *Go/no-go:* project a known scan onto a known image; check a straight edge lands on its color.
- **Trajectory glitch** (the "sometimes needs re-derivation" risk) → doubled/ghosted map. *Go/no-go:* inspect merged cloud for ghosting before export; re-run Point-LIO if doubled.
- **RGB scaling wrong on export** → gray/black cloud in RealityScan → alignment fails. *Go/no-go:* open the exported cloud in CloudCompare and confirm it's in color.
- **Featureless interior** → alignment splits components. *Go/no-go:* if auto-align yields >1 component, place control points.
- **Insufficient photo parallax** → texturing/alignment weak. *Go/no-go:* verify photos have translation, not just rotation.

### 4. Formats

- **`.ply` with RGB — easiest.** Store color as `uchar red/green/blue` (0–255). The classic bug is writing float 0–1 color (some exporters) into a viewer/importer expecting 0–255, yielding a black cloud; or binary-vs-ASCII/endianness mismatches. Use binary_little_endian PLY with uint8 RGB. **[VERIFY any current RealityScan PLY import quirk.]**
- **`.e57` — most robust for colored scans.** Native container for structured/colored scans with color and (optionally) intensity; generally the safest interchange into RealityCapture/RealityScan. If your toolchain can write E57, prefer it.
- **`.las 1.4` with RGB — works, but 16-bit trap.** LAS stores RGB as 16-bit (0–65535). If your writer puts 8-bit values (0–255) into the 16-bit fields without scaling (×257), the cloud reads near-black. Either scale to full 16-bit or confirm the importer normalizes. `.laz` is the compressed equivalent.
- **Images:** high-quality **JPEG** (or TIFF) — sharp, low compression, correct exposure. **Undistortion caveat:** if you feed pre-undistorted images, you must tell RealityScan the lens is already rectified (zero-distortion model) or it will try to solve distortion on top; many workflows instead feed *original* images plus the known camera model and let RealityScan handle distortion. Pick one convention and be consistent. **[VERIFY RealityScan's preferred handling.]**

### 5. The minimal-build answer

Given you are burned out on pose conversion, the **single most reliable rig-side build** is a **colorize-then-accumulate** pipeline that never emits a pose file:

**Tool:** `leo-drive/color-point-cloud` (ROS2) if it accepts your topics + extrinsic/intrinsic config **[VERIFY]**; otherwise a ~150-line custom rclpy node using `message_filters` + `cv2.projectPoints`. Reuse `Point-LIO` for the trajectory and a small `map_accumulator` node for the merge.

**Recipe (5 steps):**
1. **Colorize each scan:** run the colorizer on `/unilidar/cloud` + nearest `/image_raw`, using `K`/distortion + `R_L2C, t_L2C`. Output colored scans (add a cheap per-frame z-buffer).
2. **Accumulate:** transform each colored scan by its Point-LIO pose and concatenate; voxel-downsample to your target density → one merged RGB cloud.
3. **Export:** write `.ply` (binary, uint8 RGB) — or `.e57` — plus the image folder.
4. **Verify color:** open the cloud in CloudCompare; confirm it's in color and not doubled.
5. **RealityScan:** import cloud (Mobile LiDAR, Features = Color, virtual cameras on) + images → Align → mesh from LiDAR → texture from photos → FBX. Control points only if alignment splits.

This leverages existing ROS2 colorization + your already-trusted mapping trajectory, adds essentially one node, and produces a drag-and-drop package.

## Recommendations
1. **Build per-scan colorization first and validate it in isolation** (color a single scan, overlay on the source image). Threshold to proceed: straight edges' color aligns with geometry within ~1 px and no rainbow fringing on motion.
2. **Adopt colorize-then-accumulate**; only consider colorize-the-map if per-scan clouds prove too sparse to color densely. Threshold to switch: per-scan colored coverage of target surfaces <~50%.
3. **Standardize on binary PLY with uint8 RGB** as your export, with an E57 fallback. Always open the export in CloudCompare before transfer. Threshold to change format: any gray/black import into RealityScan → check scaling, then try E57.
4. **Run one full dry-run scan end-to-end before real production**, hitting every go/no-go checkpoint. If RealityScan auto-aligns to a single component with no control points on a real interior, you're production-ready; if it needs control points, bake a fixed control-point routine into your workflow.
5. **Verify the uncertain items against live docs/repos** (RealityScan "Features source"/Color label + virtual-camera mechanism; leo-drive ROS2 Humble support; ctu-vras ROS2 status; unilidar_sdk2 field layout; RealityScan's undistortion expectation) before committing a shoot day.

## Caveats
- **Live-source verification failed this session.** Items marked **[VERIFY]** — especially the exact RealityScan UI string for color-based features, the leo-drive/ctu-vras ROS2 support status, the Unitree L2 driver field layout, and RealityScan's undistorted-image handling — are high-confidence from domain knowledge but were not re-confirmed against primary sources here. Because I could not run searches, I have not cited specific URLs; do a quick confirming pass on each repo/doc named above.
- **"Auto-register just works" is conditional.** Featureless/repetitive indoor spaces, low photo parallax, or thin overlap between synthetic views and photos can still force control points; do not design the workflow assuming zero manual intervention.
- **Everything downstream depends on time-sync and the extrinsic.** Colorization quality is only as good as scan↔image temporal alignment and `R_L2C, t_L2C`; fast motion amplifies both errors.
- **Point-LIO trajectory is the one non-color dependency.** Colorize-then-accumulate still needs the trajectory for placement; a bad trajectory ghosts the map. This is much less fragile than exporting/converting poses for RealityScan, but it is not zero-dependency.