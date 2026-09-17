# Arducam + Unitree Unilidar L2 → RealityScan 2.1: Sensor Conflicts and Fixes for a Handheld LiDAR‑Mesh + Photo‑Texture Rig

## TL;DR
- **The single biggest risk is time‑sync, not color.** RealityScan 2.1 explicitly supports importing SLAM point clouds + images + trajectories and can register a colorless intensity‑only cloud (set **Features source = Intensity** on import), but the unsynced offset between the Arducam and the L2 is what will actually smear your textures — because at handheld walking speed a 150–200 ms offset places each camera ~18–25 cm from where it really was. Close tau first.
- **Your Arducam is likely a fixable non‑issue on two fronts:** the popular 1920×1200 Arducam is the AR0234 **color global‑shutter** module (Arducam's own page: "Capture crisp images of high‑speed motion, free from rolling artifacts"), and exposure/white‑balance drift is solved by locking AE/AWB in the driver plus RealityScan's built‑in **Correct Colors**. Verify your exact model — if it's a rolling‑shutter IMX‑series sensor, capture slowly and expect worse alignment.
- **The L2's non‑repetitive scan and lack of RGB are compatible with RealityScan's mobile‑LiDAR path but not "natively" as a handheld ground scanner.** Export a single fused, motion‑deskewed cloud from Point‑LIO to LAS/PLY, feed camera poses via the trajectory/SLAM importer, and — for best texture fidelity — pre‑colorize the cloud from the Arducam using your calibrated extrinsic so RealityScan has color features to lock photos onto.

## Key Findings
1. **RealityScan 2.1, released November 26, 2025, added SLAM import** — "Now supporting SLAM point‑cloud imports (e.g. XGRIDS, NavVis) → Import trajectories + images, COLMAP scenes, and auto‑generate virtual cameras" — which is exactly this rig's workflow, but Epic's own forum staff say handheld ground‑SLAM datasets are "not naturally supported" yet, so you drive the mobile‑LiDAR path manually.
2. **Colorless clouds register fine via the Intensity feature channel.** Per RealityScan Help: "Features source — Select whether to use a color or an intensity channel for registering photos to LiDAR scans. Color is the default value." Intensity is the correct setting for the L2. Control points are a complementary fallback, not mandatory.
3. **The common 1920×1200 Arducam (AR0234) is color global shutter.** This removes conflict #3 entirely *if* that's your model. Many other Arducam MIPI modules (IMX219/IMX477/IMX708) are rolling shutter.
4. **Non‑repetitive/solid‑state clouds import as unstructured "mobile LiDAR"** (LAS/LAZ/E57/PLY/CSV/XYZ/PTS), not structured terrestrial scans. Livox/Unitree users confirm they must merge frames into one cloud first.
5. **Motion distortion is real and worse for non‑repetitive scanners**; Point‑LIO deskews per‑point using the built‑in IMU, so export the *registered/deskewed* map, not raw frames.
6. **Time offset is the dominant texture‑quality lever during motion.** Published LiDAR‑camera rigs measure the offset from shared motion events and correct it to <3 ms (and, with quadratic‑fit refinement, below 0.5 ms); you should do the same or capture slowly/statically.

## Details — Every Conflict and Its Fix

### The hardware, verified
- **Unitree Unilidar L2** (per Unitree's official L2 spec page): non‑repetitive omnidirectional scanning, 360°×90° FOV (extendable to 360°×96° in negative‑angle mode), 64,000 effective points/s (128,000 sampling), circumferential scan 5.55 Hz, vertical scan 216 Hz, range 0.05–30 m (30 m @ 90% reflectivity), distance resolution 4.5 mm, **measurement accuracy ≤ 2.0 cm**, 4D output = 3D position + 1D grayscale/intensity (**no RGB**), built‑in 6‑axis IMU (1 kHz sample / 500 Hz report), Class 1 eye‑safe, 230 g. ROS2 via `unilidar_sdk2`, default topics `/unilidar/cloud` and `/unilidar/imu`; SLAM via `point_lio_unilidar` (and community ROS2 port `point_lio_ros2`). Points carry per‑point timestamps used for motion compensation.
- **Arducam:** The widely used 2.3MP 1920×1200 Arducam is the **AR0234 color global‑shutter** module (USB3 or Jetson MIPI); low‑distortion M12 lens ~95° DFOV, programmable up to 960×600@80fps (up to ~90–100 fps at lower res). Note: on Jetson the MIPI AR0234 board "does not support ISP functionality," so AE/AWB/CCM happen off‑sensor.

### Conflict 1 — Intensity‑only (no RGB) LiDAR vs RealityScan's color‑default registration
**The conflict:** RealityScan registers photos to LiDAR using a feature channel that defaults to **Color**. The L2 cloud has only intensity/grayscale, so with the default setting there is no color channel to match photos against.

**The fix (verified):** On LiDAR import, set **Features source = Intensity**. Epic's help states this option selects "whether to use a color or an intensity channel for registering photos to LiDAR scans." Once imported and converted to LSP, "registration, meshing, texturing and coloring… works exactly like for images," and you align with the **Align images** button (F6). Epic staff explicitly advised a Livox Mid‑360 handheld user: "If you don't want to use the colors, use the Intensity import option."

**Better fix for texture fidelity (recommended):** Pre‑colorize the L2 cloud from the Arducam using your calibrated intrinsics+extrinsic (open‑source tools: Mindkosh colorize‑lidar‑pointcloud, leo‑drive color‑point‑cloud, tu‑darmstadt color_cloud_from_image; or FAST‑LIVO2 which outputs a colorized cloud directly), export as PLY/LAS with RGB, and import with **Features source = Color**. This gives RealityScan strong, dense color features to lock the Arducam photos onto, which is what actually drives good photo‑to‑cloud registration. Community consensus (Laser Scanning Forum) is that RealityCapture is among the best tools for image‑based colorization/texturing of scans.

**If registration still fails:** add **Control Points** — Epic's docs note you "can add additional images, control points or place constraints to improve the registration quality" for unregistered/draft inputs.

### Conflict 2 — Non‑repetitive / solid‑state scan pattern vs photogrammetry expectations
**The conflict:** RealityScan distinguishes **structured terrestrial** LiDAR (points in the scanner's acquisition grid; PTX/E57/PLY/ZFS) from **unstructured mobile** LiDAR. The L2's flower/petal non‑repetitive pattern is not a structured grid, and point density varies strongly with dwell time and range. Historically, Livox users hit walls importing "unstructured" clouds into RealityCapture/Pix4D/Metashape.

**The fix:** Treat the L2 as **Mobile LiDAR** and import a single, fused cloud in **LAS/LAZ, E57, PLY, CSV, XYZ, or ASCII PTS**. LiDAR type is auto‑detected from format; leave it on Mobile. This is exactly what Epic's forum staff told the Livox Mid‑360 user: "it looks like this device could be used as a aerial lidar for importing into RealityScan… you will need to use LAS point cloud format," and "for most cases is better to have an unified point cloud." Density variation itself is not fatal — RealityScan's reconstruction settings expose **Minimal distance between two points** to normalize scan density and **Minimal intensity** to drop unreliable low‑intensity returns.

### Conflict 3 — Rolling shutter (Arducam) vs global‑shutter pinhole assumption
**The conflict:** Photogrammetry assumes each image is captured instantaneously (global shutter). A rolling‑shutter sensor exposes rows sequentially; if the rig moves during readout, the image skews and the pinhole model RealityScan solves is corrupted, degrading tie‑point matching and camera calibration. Pix4D notes rolling shutter "may cause problems for feature matching and thus inaccurate camera parameters."

**The fix:** **Verify your Arducam model.** If it is the AR0234 (the standard 1920×1200 global‑shutter Arducam), this conflict disappears — Arducam's product page states "Color Global Shutter: Capture crisp images of high‑speed motion, free from rolling artifacts." If your module is a rolling‑shutter MIPI sensor (IMX219/477/708), then: capture slowly, prefer a static "stop‑and‑shoot" pattern, keep exposure short, and accept that RealityScan has no dedicated rolling‑shutter correction model (unlike Pix4D/Metashape), so global shutter is strongly preferred here.

### Conflict 4 — Time sync (tau ≈ 150–200 ms) between Arducam and L2
**The conflict:** The sensors have independent clocks. When you assign each Arducam image a pose sampled from the LiDAR‑inertial trajectory, an uncorrected offset tau means you look up the pose at the wrong instant. During motion the positional error is roughly velocity × tau: at the preferred ~1.23 m/s human walking pace (Ralston 1958, via Wikipedia "Preferred walking speed": "gross cost of transport is minimized at about 1.23 m/s… which corresponded to the preferred speed of his subjects"; typical range 1.10–1.65 m/s), 150–200 ms = **~18–25 cm** of camera‑position error, which projects onto the mesh as blurred/ghosted/doubled texture and mis‑registered photos. This is the dominant texture‑quality problem for this rig.

**The fix (in priority order):**
1. **Measure and remove tau.** Estimate the offset offline by cross‑correlating a shared motion event (e.g., a sharp yaw) seen in the LiDAR‑inertial trajectory and in the image stream. Published rigs demonstrate this works well: the arXiv paper "Development and Validation of an Integrated LiDAR‑Camera System for Real‑Time Monitoring of Underground Longwall Operations" reports "the offset is estimated to be approximately 32 ms… The estimated offset is then used to correct the LiDAR timestamps, aligning them with the camera timeline and reducing the residual synchronisation error to below 3 ms." Sub‑millisecond is achievable — per a 2025 MDPI *Sensors* review (25(17):5409), a quadratic‑fit refinement "achieved a mean offset error below 0.5 ms, with performance unaffected by large temporal offsets." Bake the corrected timestamp into the pose you write to each image's trajectory entry.
2. **Software‑stamp consistently.** Timestamp both ROS2 streams against one clock (same host, `use_sim_time` off, PTP/chrony if across machines) and interpolate the Point‑LIO pose to each image's corrected timestamp.
3. **Reduce velocity × tau.** Capture slowly, or best of all capture **stop‑and‑shoot** (pause, grab frame while static). When the rig is stationary, tau contributes zero positional error regardless of its size — the cheapest way to neutralize this conflict.

### Conflict 5 — Auto‑exposure / white balance (Arducam) vs consistent texturing
**The conflict:** RealityScan blends texture from many overlapping images. If AE/AWB is active, brightness and color jump frame‑to‑frame (e.g., panning past a window), producing visible seams and a patchwork texture atlas.

**The fix:**
1. **Lock exposure and white balance in the Arducam driver before capture** (fixed exposure, fixed gain, fixed AWB / manual color temperature). This is the primary fix and matches standard photogrammetry practice ("ensure consistent exposure and white balance"). Note the Jetson MIPI AR0234 has no on‑board ISP, so set these in software/V4L2.
2. **Let RealityScan normalize residual differences.** Enable **Correct Colors** ("Automatically compensate the color, brightness and contrast differences across all images in the selected component"). You can disable badly exposed frames or mark a reference image.
3. **Use Image Layers** if needed: align on the raw set, texture from a separately color‑corrected export.
4. Consider a **color chart / grey card** in a reference frame to calibrate texture output.

### Conflict 6 — Coordinate frame / extrinsic between L2 and Arducam
**The conflict:** The cloud lives in the LiDAR frame, images in the camera frame; RealityScan needs everything in one metric coordinate system with correct relative pose. A bad extrinsic mis‑projects color onto the cloud (colorization) and/or biases photo‑to‑cloud registration.

**The fix:** Calibrate the LiDAR‑camera extrinsic with a method built for **non‑repetitive** scanners, which exploit the L2's dense dwell to find checkerboard corners precisely:
- **Target‑based:** Livox's own `livox_camera_lidar_calibration` (checkerboard corners), **ACSC** (automatic, reflectance‑based corner estimation for solid‑state LiDAR), or **RCLC** (reflectance‑feature checkerboard, pixel‑level reprojection, from the Optics Express 2022 paper by Lai et al.). These use PnP/RANSAC and report reprojection error you can gate on.
- **Targetless/automatic:** Koide's `direct_visual_lidar_calibration` (NID‑based direct registration; "can accurately calibrate the transformation between spinning and non‑repetitive scan LiDARs and pinhole and omnidirectional cameras").
Feed the resulting intrinsics+extrinsic into your colorization step and/or into the trajectory you hand RealityScan. Because RealityScan then refines camera poses during alignment (unless you import as **Exact**), small extrinsic residuals are partly absorbed — but a gross error will prevent photos from registering, so validate the reprojection visually before importing.

### Conflict 7 — Resolution / density mismatch (~1.75 M points vs 1920×1200 images)
**The conflict:** The geometric detail of the L2 cloud and the texel density of the Arducam images differ; if you let LiDAR drive mesh density where images are sharper (or vice‑versa) you waste detail or get a poor UV atlas.

**The fix:** In **Reconstruction Settings**, control density explicitly: **Minimal distance between two points** sets scan‑derived model density ("parts of the model that come from images (photogrammetry) can be denser"); the **Default grouping factor** can be raised — the docs note "when both images and LiDAR scans are being used to mesh, increasing this value will mean the laser scans will be prioritized for meshing." Let the LiDAR carry geometry (its ≤2 cm accuracy is the strength) and let the Arducam carry texture resolution; RealityScan's UV tools in 2.1 (checker‑map visualization, improved defragmentation) help balance the atlas. Down‑sampling the cloud to a uniform spacing before import also produces a cleaner, more even mesh.

### Conflict 8 — The Unitree L2 specifically in RealityScan (and Livox analogues)
**What's documented:** There is no public report of a *fully successful* Unitree L2 → RealityScan texture‑mapping pipeline yet, but the directly analogous **Livox Mid‑360** case is on Epic's forum (Nov 2025). Key takeaways confirmed by Epic staff:
- Convert per‑frame PCDs + trajectory into **one unified cloud**; import as **LAS** (or PLY/E57/etc.).
- Handheld ground SLAM is "not naturally supported" as a preset, but you can force it: use **Exact** registration + **georeferenced in local CS**, and set **Use camera poses** appropriately (from prior poses / from an existing component / generate automatically).
- For a colorless cloud, use the **Intensity** import option.
- Historic Livox‑into‑RealityCapture failures stem from unstructured data lacking per‑scan structure/IMU (one user: "they cannot do it without IMU data presented for every point"); the 2.1 SLAM path + a deskewed fused cloud + a trajectory is what resolves this.

**RealityScan 2.1 SLAM path, step by step (from Epic's official 2.1 documentation):**
1. Import **images + their trajectories** (or open a COLMAP scene — "also provided with XGrids data").
2. Import the **point cloud**.
3. **Generate virtual cameras** from camera‑pose priors (or from an imported/COLMAP component).
4. **Combine with photogrammetry** or other LiDAR, then **Align (F6)**.
The trajectory importer (formerly Flight Logs) accepts custom CSV with `name x y z omega phi kappa`, configurable Euler order, separators and coordinate system — this is how you feed Point‑LIO poses (one row per Arducam image, at the tau‑corrected timestamp). Note the "Use camera poses" modes: **from prior poses** (uses your imported trajectory), **from existing component** (uses an already‑registered component, e.g. a COLMAP/photogrammetry alignment), or **generate automatically** (synthesizes poses using Height reference / Camera height / overlap / cluster settings).

## Recommendations — Pre‑Capture and Capture Checklist

**Before capture (bench):**
1. **Confirm the Arducam sensor.** If AR0234 global shutter → good. If rolling shutter → plan stop‑and‑shoot and slow motion. (Resolves/limits Conflict 3.)
2. **Calibrate the camera intrinsics + lens distortion** (checkerboard, OpenCV) and **the LiDAR‑camera extrinsic** with ACSC/RCLC/`direct_visual_lidar_calibration`. Gate on reprojection error; visually verify projection. (Conflict 6.)
3. **Lock Arducam exposure, gain and white balance** in the driver; disable AE/AWB. (Conflict 5.)
4. **Measure tau** once with a deliberate shake and motion cross‑correlation; hard‑code the offset into your pose‑to‑image association, and put both ROS2 streams on one clock. (Conflict 4.)

**During capture:**
5. Run **Point‑LIO** so points are IMU‑deskewed; keep the L2 static for the first few seconds for IMU init. Move slowly and smoothly; prefer **stop‑and‑shoot** at key viewpoints. (Conflicts 2, 4.)
6. Ensure image overlap (photogrammetry needs redundancy); don't over‑capture (thin video to every Nth frame later).

**Post‑capture / import:**
7. Export **one fused, deskewed cloud** (registered map) to **LAS/PLY**; optionally **pre‑colorize** it from the Arducam via the extrinsic.
8. In RealityScan: import images + a **trajectory CSV** (tau‑corrected poses, `name x y z omega phi kappa`); import the cloud as **Mobile LiDAR**; set **Features source = Intensity** (or **Color** if pre‑colorized); choose **Use camera poses = from prior poses**; **Registration = Exact** (or Draft to let it fine‑tune) in **local coordinate system**.
9. **Align (F6).** If photos don't lock, add **control points** and/or switch to the pre‑colorized (Color) cloud.
10. **Reconstruct:** set **Minimal distance between two points** and **grouping factor** to let LiDAR drive geometry; **Minimal intensity** to prune noise.
11. **Texture:** enable **Correct Colors**; consider Mosaicing/Photo‑consistency styles; use the 2.1 UV checker map to refine the atlas.

**Thresholds that change the plan:**
- If measured tau‑induced error (velocity × tau) exceeds ~1 texel of ground sampling distance at your capture range → switch to stop‑and‑shoot or improve sync.
- If photo‑to‑cloud alignment success rate is low with Intensity → pre‑colorize and use Color, then add control points.
- If mesh shows scan‑density banding → uniformly downsample the cloud before import.

## Caveats
- **No end‑to‑end Unitree L2 → RealityScan success story is publicly documented.** The workflow here is assembled from the official RealityScan 2.1 SLAM/LiDAR docs, the closely analogous Livox Mid‑360 forum thread with Epic‑staff answers, and standard LiDAR‑camera fusion practice. Treat the exact click‑path as verified from docs but the L2‑specific result as **projected, not confirmed**.
- **Epic staff called handheld ground‑SLAM "not naturally supported" in the current release** — expect manual setting tweaks and some trial‑and‑error; the SLAM importer is oriented toward vendor systems like XGrids/NavVis.
- **Whether setting Features source = Intensity is *sufficient* on its own for robust photo registration to a colorless cloud is inferred** from the documented purpose of the option, not from an explicit L2/Livox success report. Pre‑colorizing is the safer route and is why it's recommended.
- **"~150–200 ms" tau and "~1.75 M points" are your stated assumptions**, not measured facts — measure both. Actual tau depends on your driver/buffering; actual point count depends on dwell time and room size. (Note the arXiv longwall rig measured a real offset of ~32 ms on its hardware, so your suspected 150–200 ms is plausible but should be verified.)
- **Verify your specific Arducam model's shutter and interface** (USB vs MIPI) — Arducam sells both global‑ and rolling‑shutter modules at 1920×1200‑class resolutions; the fix for Conflict 3 hinges on this.
- RealityScan is Windows/Linux; the 2.1 Linux CLI enables headless processing on the capture PC if desired.