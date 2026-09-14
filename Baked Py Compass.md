# Recovering Camera Poses for All 2,200 Frames in a Unitree L2 + Arducam LiDAR-Camera Capture

## TL;DR
- **The odometry is almost certainly NOT your bottleneck** — the Unitree L2 Point-LIO config publishes a continuous, high-rate pose stream on `/aft_mapped_to_init` for the entire time the LiDAR streams, so the fix is overwhelmingly likely to be a **re-interpolation problem in your `pointlio_pose_matcher.py`** (and/or a camera-vs-LiDAR clock offset), not lost tracking. Re-run pose interpolation against the full odometry stream from the bag and you should recover most of the 2,200 frames cheaply.
- **Do the diagnosis first**: extract the true time-span and rate of `/aft_mapped_to_init` from the bag and compare it to the 70 s / 2,200-frame camera timeline. The number 307 is diagnostic — it closely matches "one entry per scan-rate odometry pose" (307 / 5.55 Hz ≈ 55.3 s) rather than "one entry per image," which would mean the matcher looped over poses instead of images.
- **Staged plan**: (1) re-interpolate all 2,200 image timestamps against the full bag odometry (SLERP + linear); (2) if odometry coverage is genuinely short, re-run Point-LIO (or KISS-ICP/GLIM) offline on the recorded bag to regenerate a complete trajectory; (3) for any residual unmatched frames, use COLMAP/hloc visual localization anchored to the LiDAR-posed frames. Frames captured while the LiDAR was truly not streaming, or outside all overlap, are genuinely unrecoverable from odometry and must go through the visual route.

## Key Findings

**1. Point-LIO on the Unitree L2 publishes poses continuously and at high rate — coverage gaps are unlikely to originate there.** The odometry topic is `/aft_mapped_to_init`, message type `nav_msgs/Odometry`, carrying position + orientation quaternion (and twist). In the Unitree L2 configuration (`unilidar_l2.yaml`), `publish_odometry_without_downsample` is set true, which makes Point-LIO publish odometry at the point-update rate rather than downsampled to the LiDAR frame rate. The Point-LIO paper (He et al., "Point-LIO: Robust High-Bandwidth Light Detection and Ranging Inertial Odometry," *Advanced Intelligent Systems* 2023, 5, 2200459, Wiley) states: "This framework allows an odometry at the point sampling rate in theory and 4–8 kHz in practice." Once the filter initializes (Point-LIO needs a stationary warm-up of a few seconds for IMU bias/gravity estimation), it emits a pose every processing step continuously for the whole time LiDAR+IMU data arrive — it does not wait for motion and keeps publishing even while stationary. It has no clean "tracking lost → stop" state; degenerate geometry or desync tends to produce diverged poses rather than a gap. Frames: parent `camera_init` (world/init), child `body` (sensor).

**2. The "307 / 210" signature points to a matcher-side bug.** 2,200 frames over ~70 s at ~28 Hz is a dense, continuous camera stream. If the matcher had simply interpolated a pose at each image timestamp within the odometry window, you would expect ~2,200 outputs (minus a small edge fraction), not 307. Two hypotheses fit 307:
   - **(a) The matcher iterated over odometry poses, not images.** The Unitree 4D LiDAR L2 User Manual (2024.10 v1.1) specifies "a circumferential scanning frequency of 5.55 Hz, a vertical scanning frequency of 216 Hz"; 307 poses at 5.55 Hz ≈ 55.3 s. If Point-LIO in *your* run actually had `publish_odometry_without_downsample` false (scan-rate odometry), and the matcher produced one row per odometry pose (finding the nearest image to each pose, keeping `ok=True` only when an image fell within a dt threshold), you get ~307 rows and ~210 hits. **Fix is trivial: invert the loop and interpolate a pose at each of the 2,200 image timestamps.**
   - **(b) A camera-vs-LiDAR clock offset restricted the temporal overlap.** 307 frames at 28 Hz is ~11 s. If the Arducam timestamps and the LiDAR/odometry clock differ (a very common ROS2/Jetson problem — camera frames stamped on a different clock, or on device time vs wall time), only the ~11 s of accidental overlap would fall inside the pose window and produce `ok=True`; a matcher clamping to the window discards the rest.
   The diagnosis below distinguishes these.

**3. You can re-read the full odometry stream without a ROS install.** The pure-Python `rosbags` library (`pip install rosbags`) reads ROS2 `.db3`/MCAP bags on Windows with no ROS dependency and deserializes `nav_msgs/Odometry`. This lets you pull every `/aft_mapped_to_init` message (timestamp, position, quaternion) and re-interpolate.

**4. Interpolation math is standard and well-supported.** Use `scipy.spatial.transform.Slerp` for the rotation (spherical linear interpolation gives constant-angular-velocity shortest-path between quaternions) and linear interpolation (`numpy.interp`) for translation, evaluated at each image timestamp. This is exactly what a correct pose matcher does.

**5. Point-LIO can be re-run offline on the recorded bag.** The documented workflow is to launch the Point-LIO node and `ros2 bag play` the recorded `/unilidar/cloud` and `/unilidar/imu` topics; the node regenerates the full trajectory. Caveats: per-point LiDAR timestamps must be preserved in the bag (the "Failed to find match for field 'time'" warning means they are missing, which breaks Point-LIO because it processes at each point's sampling time); play with `--clock` and `use_sim_time:=true`; play at real-time rate (fast playback risks dropped messages). Set `pcd_save_en`/`pcd_save_enable` to save `scans.pcd`; `path_en` publishes the trajectory as `nav_msgs/Path`.

**6. Alternatives regenerate a complete trajectory if Point-LIO's is poor.** KISS-ICP (LiDAR-only point-to-point ICP, no IMU required, runs directly on a ROS2 bag via `ros2 launch kiss_icp odometry.launch.py bagfile:=... topic:=...`) and GLIM (GPU-accelerated range-inertial SLAM with global optimization; its offline viewer dumps trajectories in TUM format `odom_lidar.txt`/`traj_lidar.txt`) are strong options. FAST-LIO2 and LIO-SAM are also candidates. These give a dense, drift-corrected trajectory you can interpolate against.

**7. Visual localization recovers frames LiDAR odometry cannot.** COLMAP can register all 2,200 images by SfM, then align/scale to the LiDAR frame using the LiDAR-posed frames as anchors (Sim(3) via correspondences + ICP), placing all camera poses in metric world coordinates. Colmap-PCD registers images directly against the prior LiDAR point cloud with correct metric scale (it seeds from an approximately known initial pose and uses point-to-plane constraints in a factor graph). hloc (SuperPoint + LightGlue/SuperGlue + NetVLAD retrieval + PnP/RANSAC) localizes query images against an existing SfM model and is the most robust route for the frames COLMAP's incremental mapper drops.

**8. Open3D closes the loop for texturing.** `run_rigid_optimizer`/`run_non_rigid_optimizer` (color map optimization; Q.-Y. Zhou and V. Koltun, "Color Map Optimization for 3D Reconstruction with Consumer Depth Cameras," SIGGRAPH 2014, cited verbatim in the Open3D 0.19.0 documentation) paints the mesh from all posed images and refines the 6-DoF camera poses to sharpen the texture — directly turning more posed frames into a denser, sharper photoreal texture.

## Details

### Step 0 — Diagnose which failure you have (30 minutes, decides everything)
On the Windows workstation, `pip install rosbags numpy scipy`. Open the bag and, for `/aft_mapped_to_init`, print: message count, first/last header stamp, and median inter-message dt (→ publish rate). Do the same for the camera topic (or read your image timestamps from disk/sidecar). Then compare:

- **Odometry span ≈ 70 s, rate high (kHz) or ~5.55 Hz, and it covers the camera span** → your odometry is fine; this is a matcher bug (Hypothesis 2a). Re-interpolate all 2,200 timestamps. Expected recovery: ~2,150–2,200 frames.
- **Odometry span ≈ 70 s but the 210 matched images cluster in a ~11 s sub-window** → clock offset (Hypothesis 2b). Estimate the constant offset (align the two clocks by cross-correlating motion, or from a known sync event), add it to the image timestamps, then interpolate. Recovery: most frames.
- **Odometry span itself is short (e.g. ~11 s) or has large gaps** → Point-LIO genuinely tracked only part of the capture. Go to Step 2 (re-run LIO offline).

Key sanity numbers: 2,200 frames / 70 s = ~31 Hz nominal (you observed ~28 Hz); 307 frames at 28 Hz = ~11 s; 307 poses at 5.55 Hz ≈ 55.3 s. Which of these the 307 corresponds to tells you the cause immediately.

### Step 1 — Re-interpolate all image timestamps against the full odometry (the cheap win)
Extract arrays `t_odom`, `xyz_odom`, `quat_odom` from the bag. Build `slerp = Slerp(t_odom, R.from_quat(quat_odom))` and interpolate translation with `np.interp` per axis. For each image timestamp `t_i` inside `[t_odom[0], t_odom[-1]]`, compute the interpolated `body`-in-`camera_init` pose, then apply the fixed LiDAR→camera extrinsic from your calibration YAML to get the camera pose. Write a new `posed_images.npz` with all recovered frames. Mark frames outside the odometry window as not-ok (candidates for Steps 2–3). This alone typically converts 210 → ~2,000+ posed frames if the odometry was complete.

**Do not blindly extrapolate** beyond the odometry window: SLERP/linear extrapolation of pose is only safe for a few tens of milliseconds (a fraction of one inter-pose interval) at handheld speeds. For frames a few hundred ms outside the window you can dead-reckon using the L2's built-in IMU — the Unitree L2 User Manual confirms an "IMU module with 3-axis acceleration and 3-axis gyroscope built-in, supporting a sampling frequency of 1 kHz and a reporting frequency of 500 Hz" — by integrating from the last known state, but drift accumulates quickly on a low-cost MEMS IMU; treat IMU-extrapolated poses as provisional and prefer the visual route (Step 3) for anything more than a short gap.

### Step 2 — Regenerate a complete trajectory offline (if odometry coverage is genuinely short)
Re-run Point-LIO on the bag on a Linux box or WSL2/Docker (ROS2 Humble):
```
ros2 launch point_lio mapping_unilidar_l2.launch.py use_sim_time:=true
ros2 bag play <bag> --clock            # publishes /unilidar/cloud + /unilidar/imu
```
Confirm per-point timestamps are intact (no "Failed to find match for field 'time'"), keep the extrinsic and IMU saturation/`acc_norm` values from the L2 config, and start from the stationary warm-up portion of the bag so initialization succeeds. Record the regenerated `/aft_mapped_to_init` to a new bag (or save `scans.pcd`/path), then repeat Step 1.

If Point-LIO still initializes late or diverges, run **KISS-ICP** (`ros2 launch kiss_icp odometry.launch.py bagfile:=<bag> topic:=/unilidar/cloud`) — LiDAR-only, needs no IMU, robust for handheld — or **GLIM** for a globally-optimized, loop-closed trajectory (use its offline viewer to export `traj_lidar.txt` in TUM format). Interpolate against whichever trajectory is cleanest. Note the L2's data richness for scan-matching: the User Manual lists a 128,000 pts/s sampling frequency and 64,000 pts/s effective frequency, so LiDAR-only odometry has ample geometry to work with.

### Step 3 — Visual localization for residual frames
For frames that no LiDAR trajectory can cover (LiDAR wasn't streaming, or no temporal overlap):
- **Best-effort, integrated route — COLMAP + anchor alignment.** Run COLMAP SfM on all 2,200 images (they heavily overlap at 28 Hz, so matching is easy). This yields poses in an arbitrary scale/frame. Compute the Sim(3) transform (scale + rotation + translation) that maps the COLMAP poses of the *already-LiDAR-posed* frames onto their known LiDAR poses (least-squares on ≥3 correspondences, then ICP refinement of the COLMAP point cloud onto the `.pcd`). Apply that transform to *all* COLMAP camera poses → every frame is now in metric LiDAR world coordinates.
- **Direct-to-pointcloud route — Colmap-PCD.** Registers images against your existing LiDAR `.pcd` with correct metric scale, seeded from an approximately known initial pose (you have hundreds from Step 1). Output camera poses are already in the point-cloud frame (note its x-front/y-left/z-up convention).
- **Most robust registration — hloc.** Build an SfM/reference model from the well-posed frames, then localize the dropped frames with SuperPoint + LightGlue + NetVLAD retrieval + PnP/RANSAC. `image_registrator`/`mapper` in COLMAP can also register new images into the existing model, but hloc's learned features recover harder frames.

### Step 4 — Texture the mesh from all recovered poses
Feed the mesh (from the `.pcd`), the images, and the full posed set into Open3D's color map optimization (`run_rigid_optimizer`, then optionally `run_non_rigid_optimizer`). It refines each camera's 6-DoF pose to minimize photometric inconsistency, converting your denser frame set into a sharper, more complete texture. More correctly-posed frames = fewer untextured regions and better color blending.

### Honest recoverability assessment
- **Recoverable and cheap (Steps 0–1):** every image whose timestamp falls inside the odometry window — likely the large majority (potentially ~2,000+). If the cause was a matcher loop-over-poses bug or a fixable clock offset, you get almost all 2,200 back.
- **Recoverable with more work (Step 2–3):** frames in short odometry gaps, or during LiDAR initialization warm-up, via re-run LIO or visual localization.
- **Genuinely lost from odometry, visual-only:** frames captured while the LiDAR truly wasn't producing data. These are recoverable *only* if they visually overlap the reconstructed scene (Step 3); if they don't, they cannot be posed.
- **Unrecoverable entirely:** frames that are motion-blurred, feature-poor, or of a region not covered by the LiDAR map and not covisible with any posed image.

## Recommendations
1. **Run Step 0 today.** The single most valuable action is reading the bag's `/aft_mapped_to_init` span/rate with `rosbags` and comparing it to your image timestamps. This ~30-minute diagnostic tells you whether you have a 30-minute fix or a re-processing job. **Benchmark that changes the plan:** if odometry span ≥ camera span and rate is steady, skip Step 2 entirely.
2. **Implement the re-interpolation (Step 1)** with `scipy` `Slerp` + `np.interp`. If recovered `ok` frames jump from 210 to >~2,000, you are done up to texturing — go to Step 4.
3. **If matched frames cluster in a short window, fix the clock offset**, not the interpolation. Estimate the constant camera-vs-LiDAR offset and re-run Step 1. **Threshold:** if adding a single constant offset makes the matched-frame span jump to ~70 s, the offset was the whole problem.
4. **Only if odometry coverage is genuinely short**, re-run Point-LIO offline (or KISS-ICP/GLIM). **Benchmark:** target a regenerated trajectory spanning ≥95% of the camera timeline before re-interpolating.
5. **Reserve COLMAP/Colmap-PCD/hloc (Step 3) for the residual** — it is the most compute-heavy step and best justified once you know how many frames actually remain unposed.
6. **Texture with Open3D color map optimization (Step 4)** once you have the maximal posed set.
7. **Prevent recurrence:** next capture, hardware- or PTP-sync the camera clock to the LiDAR/Jetson clock (or log a sync event), enable Arducam hardware timestamping, and verify the pose matcher loops over images (not poses) and reports coverage as posed/total.

## Caveats
- The precise value of `publish_odometry_without_downsample` in *your* run determines whether the recorded odometry is kHz-rate or scan-rate (~5.55 Hz); confirm it in your `unilidar_l2.yaml` and by measuring the bag rate. This single flag is the crux — verify it directly rather than assuming.
- The `camera_init`/`body` frame names and the availability of a `use_sim_time` launch arg are the standard hku-mars/FAST-LIO convention; confirm against your actual `/tf` and launch file, since the ROS2 port may strip leading slashes.
- Interpolation is only valid *inside* the odometry time window; extrapolation and IMU dead-reckoning across gaps degrade quickly and should be treated as provisional.
- COLMAP poses are scale-free until aligned; the anchor-based Sim(3) alignment is only as good as the accuracy of the anchor (LiDAR) poses and the correspondence quality — verify with reprojection/ICP residuals.
- Re-running Point-LIO requires a Linux/ROS2 environment (native, WSL2, or Docker); it is not a pure-Windows step, unlike the `rosbags`/Open3D/COLMAP work.
- All quantitative "307 ≈ 5.55 Hz × 55 s" vs "307 ≈ 28 Hz × 11 s" reasoning is a hypothesis framework to guide diagnosis, not a measured conclusion — the bag inspection in Step 0 is what confirms the actual cause.