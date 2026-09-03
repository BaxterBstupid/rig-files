# LiDAR–Camera Calibration for Virtual Production — Master Project Record

**Purpose of this document:** a complete, honest, self-contained record of the project
to hand to a fresh Claude chat. It covers the end goal (Unreal Engine previs), the full
milestone arc from board design to the current architecture, every major finding, the
errors we made and corrected, and pointers to the pertinent images/PDFs/code in this
folder. Read `START_HERE_NEXT_SESSION.md` alongside this — that is the authoritative
"what to do next"; this is the "how we got here and why."

> **Honesty note:** where something is a GOAL or UNVERIFIED, it says so. Several
> plausible-sounding summaries generated along the way OVERSTATED progress (claimed
> "<15 mm achieved / ready for RTAB-Map"). Those were wrong. This document and
> START_HERE (v2) are the corrected record.

---

## 1. THE END GOAL — Unreal Engine virtual-production pipeline

The calibration is not the product; it is one link in a virtual-production/previs chain:

```
Unitree L2 LiDAR ─┐
                  ├─► time-synced capture ─► COLORIZED 3D point cloud ─► RTAB-Map SLAM
Arducam camera ───┘        (needs the extrinsic)      (needs the extrinsic)
                                                              │
                                                              ▼
                                                   room-scale textured mesh
                                                              │
                                                              ▼
                                                   Unreal Engine previs / virtual set
```

- The LiDAR gives geometry (3D points); the camera gives color/texture. To paint camera
  color onto LiDAR points you must know **exactly where the camera is relative to the
  LiDAR** — that rigid 6-DOF transform is the **extrinsic** this project exists to find.
- Downstream, RTAB-Map builds a room-scale colorized mesh that is imported into Unreal
  for previs / virtual-set work.

**Status of the UE end: NOT YET REACHED.** No RTAB-Map runs, no mesh, no UE import have
been done. Everything so far is upstream calibration. UE matters *now* only because it
sets the accuracy bar (see §7: rotational error × range is what degrades a room-scale
mesh, which reshaped the whole approach).

---

## 2. HARDWARE / PLATFORM (verified facts)

- **Compute:** Jetson Orin Nano, JetPack 6.2.1, Ubuntu 22.04, user `fasterbybaxter`,
  ROS 2 Humble.
- **LiDAR:** Unitree L2, wired ethernet 192.168.1.62 (iface enP8p1s0). Publishes
  `/unilidar/cloud` ~12 Hz, frame `unilidar_lidar`, **QoS = BEST_EFFORT** (RViz must
  match or nothing shows). Mounted **on its side** (dome forward). Densest at the dome
  pole. **Dome-tip → optical-center offset = +5.4 cm** (true distance = laser-tape
  reading from dome tip + 5.4 cm; verified: 89.1 tape → 94.5 data).
- **Camera:** Arducam AR0234 global shutter, 110° M12 lens, 1920×1200 via `/image_raw`.
  **Intrinsics currently IN DOUBT — see §8.**
- **Cheese plate:** rigid mount added mid-project; killed vibration and fixed framing.
  Did NOT fix LiDAR surface-return sparsity (§6).
- **Measured camera↔LiDAR mount offset:** lens is 13.5 cm behind, 11 cm left, 16 cm
  down relative to the LiDAR center (viewpoint: standing behind rig, looking at board).
  Straight-line ≈ **23.9 cm**. Leave as-is — calibration MEASURES the offset, it does
  not need to be zeroed. L2-axis sign mapping NOT yet verified.

---

## 3. THE TWO BOARDS (this is the corrected architecture — §7 explains why)

**Hole board (built, verified):** flat foam board **815 × 1020 mm**, rigidly clamped.
Centered checkerboard **7×10 inner corners, 33 mm squares** (measured: 5 squares =
16.5 cm; the design's 35 mm was WRONG — 33 mm, a ~6% scale fix). Four **127 mm (5")
holes** (re-cut concentric over original 51 mm holes; 51 mm proved too small — the L2
beam spot ~2–3 cm paints over them beyond ~65 cm).
→ Job: **the EXTRINSIC.** The only object BOTH sensors see at once with known geometry.
   checkerboard→camera pose, flat surface→LiDAR plane, four holes→LiDAR point feature.
Drawings: `calibration_board_drawing.svg`, `cut_guide_127mm.svg`, `hole_overlay_detail.svg`.

**Big board (checkerboard only):** larger board, **63.5 mm squares**, single professional
print (NOT assembled tiles), ~61% frame coverage.
→ Job: **CAMERA INTRINSICS** (USB VideoCapture, no LiDAR). Needs the pattern to reach
   frame edges/corners because lens-distortion signal grows as r³.
Print PDFs: `checkerboard_A2_true-scale.pdf` (true-scale big board),
`checkerboard_4tiles_Letter.pdf` (the old 4-tile letter print — this tile print is part
of why the intrinsics went wrong, §8).

---

## 4. STEP 0 — physical ground truth (COMPLETE, verified ~1 mm)

Hole centers measured with laser tape from the board's top-left corner (mm):
`TL(117.5,117.5)  TR(701.5,116.5)  BL(117.5,904.5)  BR(701.5,906.5)`.
Board 815×1020 mm. Spacings: top/bottom pairs 58.4 cm, side pairs 78.7/79.0 cm,
diagonals 98.2/98.1 cm — all within ~1 mm of nominal. **Board confirmed built correctly.**
Measurement method diagrams: `step0_edges.svg`, `step0_arrows.svg`,
`step0_measurement_diagram.svg`.

This is the trustworthy geometry the whole calibration references. The "3 cm-off hole"
worry never materialized.

---

## 5. MILESTONE ARC (beginning → present)

1. **Board design & build** → hole board built; checkerboard centered; holes re-cut to
   127 mm after 51 mm proved too small for the L2 beam.
2. **Step 0 ground truth** → hole centers to ~1 mm (§4). Square size corrected 35→33 mm.
3. **Sensor characterization** → +5.4 cm dome offset; QoS/BEST_EFFORT; board reads at
   ~1.0–1.05 m; cloud metrically correct (board width 82.8 cm vs true 81.5).
4. **Camera side working** → `findChessboardCorners` (7×10) + `solvePnP`; hole centers
   via centered-checkerboard geometry reproduce the 58/79/98 rectangle to <1 mm.
   Images: `cam_corners.jpg`, `cam_corners2.jpg`, `hole_predict.jpg`.
5. **Extrinsic solver (synthetic-validated)** → Kabsch/Umeyama + gates; 2.4 mm / 0.13°
   on synthetic multi-pose. `extrinsic_solver.py`.
6. **Cheese plate** → killed vibration, clean framing; but surface still ~75% solid.
7. **LiDAR hole detection saga** → flat-projection/occupancy detectors FAIL at 75% solid
   (board is topologically porous; see §6). Invented the **NN-distance detector** which
   works. `nn_hole_detector.py`. Images: `cheese1_detect.png`, `cheese1_occ.png`,
   `nn_detect.png`, `nn_detect2.png`, `nn_template.png`, `nn_final.png`.
8. **Mount offset measured** → 13.5/11/16 cm ≈ 23.9 cm; this **disambiguates the
   symmetric-rectangle correspondence** (|t| check picks the right permutation: NN → 22.6,
   clicks → 25.1, both ≈ 24). Real result.
9. **First real end-to-end solve** → residual **71–92 mm** (NOT tight; target <15 mm).
10. **Board-isolation fragility found** → full-plane survey showed the board sits in
    room-scale COPLANAR clutter; the range-gated isolation can carve a disc.
    Image: `full_plane_survey.png` (the key diagnostic — board + four holes are real,
    but embedded in wall/floor clutter).
11. **THE ARCHITECTURE CORRECTION (biggest insight)** → two boards; and **rotation comes
    from the PLANE, translation from the HOLES**; intrinsics must be re-done FIRST (§7–8).

---

## 6. KEY TECHNICAL FINDING — why LiDAR hole detection was so hard

At ~75% surface return the board is **topologically porous**: the holes are NOT enclosed
voids — they connect to the outside through ring-gap channels in the speckle (13006 of
13014 "empty" grid cells reach the border). So every fill-holes / flood-fill / occupancy
method FAILS. The fix that works: a **nearest-neighbour distance field** — a hole is a
region where the nearest ACTUAL point is far (~44 mm) vs ~2 mm on the surface (20×
separation that survives the speckle). Template-match "disc of HIGH nn-dist ringed by LOW
nn-dist", then pick the 4 best-forming the 58×79 rectangle. `nn_hole_detector.py`.
Result on the cheese cloud: 4 holes, correctly scaled, rect-RMS ~27 mm.
Caveat: the board-**isolation** feeding it is still fragile against coplanar clutter (§5.10).

---

## 7. THE ARCHITECTURE CORRECTION — the centerpiece

**Two boards, two jobs:**
- **Big board → intrinsics** (USB, no LiDAR): pattern must reach frame edges/corners
  because distortion signal grows as r³ (~0.95 px across the old tiny pattern vs ~17.9 px
  full-frame). The hole board's checkerboard is ~2% of frame + tile-printed — calibrating
  from it STARVED the fit and pushed lens error into fx/fy + tangential terms (→ §8).
- **Hole board → extrinsic:** the only object both sensors observe at once.

**The split that changes everything:**
- **PLANE → ROTATION.** Tens of thousands of plane points constrain the normal (plane-fit
  precision ~0.0054°). Rotation error **multiplies with range** → dominates room-scale
  mesh accuracy → put precision HERE; the plane gives it almost for free.
- **HOLES → TRANSLATION only** (3 DOF, rotation already fixed). Translation error is
  **constant with range** (91 mm stays 91 mm at 10 m).
- **Consequence:** hole detection — the hardest thing we built — was carrying rotation,
  which 4 noisy points are terrible at. **It never needed to.** The hole-precision problem
  that blocked us is retired: holes only carry translation, where they're adequate.
- Caveat: 0.0054° is the plane-fit *ceiling*, not delivered system accuracy.

**Why the order is FORCED:** `solvePnP` uses the intrinsics. A wrong lens model biases
the board pose (measured ~12° / ~49 mm). Kabsch absorbs that bias RIGIDLY, so **no
residual gate can ever see it.** Calibrate the extrinsic on bad intrinsics → invisible,
permanent error. **Intrinsics first, always.**

---

## 8. CAMERA INTRINSICS ARE IN DOUBT (must recalibrate first)

Current K has fx=856.21, fy=926.52 (fy/fx = 1.082). Three independent signals say that
anisotropy is likely **spurious**:
1. **Image contradiction:** a square grid at the measured 9.5° tilt should image with
   spacing ratio ~1.086 if fy/fx=1.082; measured ratio is **0.9989** (squares image
   square).
2. **Reprojection:** forcing fx=fy (isotropic ~891) halves reprojection **1.21 → 0.57 px**
   on the same image. (Weak alone — one near-fronto-parallel pose can't separate fx/fy —
   but consistent.)
3. **LiDAR cross-check:** board tilt reads **2.5° isotropic vs 9.5° calibrated**; LiDAR
   independently measures **3.79°**. Isotropic reconciles the two sensors.

**NOT proven** that 891 is the correct focal length (it's an average, not a calibration),
nor that this fully explains the 92 mm residual. **Action:** proper multi-pose
`cv2.calibrateCamera` on the big board settles it. Do NOT adopt 891 by hand.

This also corrects an earlier belief that "1.1 px was floored by the tile-print." Same
image gives 0.57 px isotropic — the print wasn't the floor; the intrinsics were.

---

## 9. ERRORS WE MADE AND CORRECTED (kept deliberately — they prevent repeats)

- **35 mm square size** assumed → actually **33 mm** (measured). ~6% scale error, fixed.
- **51 mm holes** too small for the L2 beam → re-cut to **127 mm**.
- Believed **cheese plate / density / dwell would fix the ~75% solid** → it won't;
  it's the surface's return behavior. NN-detector was the real fix.
- **Flat-projection hole detection** pursued too long → fails by topology at 75% solid.
- **Manual RViz rim-clicks** carry an unexplained **~12% spacing inflation** → not
  calibration-grade; used only to anchor correspondence.
- Read session-2's "clean 82.8×88 cm framing" as good → partly **ROI clipping** an the
  board sitting in coplanar clutter (`full_plane_survey.png`).
- **Overstated-progress summaries** ("<15 mm achieved / Session 3 done / ready for
  RTAB-Map") → FALSE. Best real residual is 71–92 mm; no bootstrap was ever built/run.
- **`cx=320,cy=240` placeholders** (640×480 defaults) lurking in some scripts → wrong by
  ~640 px on a 1920×1200 sensor; any pose from those is garbage. Purge them.
- **Transposition hazard:** pattern (7,10) vs (10,7) on one image → 113.8 vs 106.2 cm,
  IDENTICAL reprojection, no warning. Lock orientation + square size as asserted args.
- **Two boards, identical 7×10 grids:** nothing in code distinguishes them → tag captures.
- Believed hole detection had to be precise for the whole extrinsic → **only for
  translation**; rotation comes from the plane (§7).

---

## 10. CURRENT HONEST STATUS

- Ground truth ✓. Camera detection pipeline ✓ (but intrinsics suspect). NN LiDAR detector
  ✓ (isolation fragile). Offset measured ✓ and disambiguates correspondence ✓. Synthetic
  solver ✓.
- Best REAL residual **71–92 mm** — and possibly an INTRINSICS artifact, not a LiDAR one.
- **NOT done:** trustworthy intrinsics; plane→rot/holes→trans extrinsic; rotational-error
  characterization; hold-out validation; full-scene edge alignment; multi-pose; robust
  isolation; any UE/RTAB-Map integration.

---

## 11. THE PLAN (what the next chat should do, in order)

1. **Recalibrate camera intrinsics** on the BIG board (15–20 varied poses reaching frame
   edges, `cv2.calibrateCamera`, USB, no LiDAR). Lock square size (63.5 mm) + pattern
   orientation as asserted args. Write the NEW K/DIST to a shared file.
2. **Rebuild the extrinsic** on the HOLE board with the decomposition: **plane normal →
   rotation, holes → translation.** (Supersedes the Kabsch-4-point `extrinsic_solver.py`.)
3. **Re-derive P_cam** with trustworthy intrinsics; solve; validate.
4. **Validation gates:** report ROTATIONAL error explicitly; hold-out on checkerboard
   corners; full-scene LiDAR→image edge alignment at near AND far depths; multi-pose
   (≥3 tilts). Point residual alone is insufficient.
5. **Only then** → RTAB-Map first run → colorized mesh → Unreal import.

---

## 12. MAPPING STAGE (FUTURE — do not start until intrinsics + extrinsic are solved)

The map-building stage sits AFTER a trustworthy camera↔LiDAR extrinsic. Two candidate
backbones; this is a filed decision, not current work.

**RTAB-Map** — more natively RGB-D/visual-friendly; likely the easier path to a
*colorized* mesh for Unreal previs. Was the original assumed backbone.

**LIO-SAM** (Tixiao Shan et al., MIT) — tightly-coupled LiDAR-INERTIAL odometry + mapping
via factor graphs. Strong geometry/trajectory backbone with loop closure. Key facts for
THIS rig:
- **It needs an IMU.** Stock LIO-SAM expects a **9-axis** IMU (accel+gyro+magnetometer for
  absolute yaw). The **Unitree L2's built-in IMU is likely 6-axis** (accel+gyro, no mag).
  Feeding a 6-axis IMU to stock LIO-SAM misbehaves. → Use a **6-axis fork**, not stock:
    * `liorf` (LIO-SAM w/ 6-axis IMU + more LiDAR support)
    * `LIO_SAM_6AXIS` (LIO-SAM adapted for 6-axis)
    * `SC-LIO-SAM` (adds Scan Context = better loop closure)
- **First unknown to confirm:** does the L2 actually expose an IMU stream, at what rate,
  6- or 9-axis, and is it time-synced to the LiDAR? Verify before committing.
- **LIO-SAM is geometry-only** — it does NOT colorize from a camera. You STILL need the
  camera↔LiDAR extrinsic to paint camera texture onto the map for Unreal. LIO-SAM
  consumes the calibration output; it does not replace this project.
- **Implies a THIRD calibration:** LiDAR↔IMU extrinsic (transform between L2 optical
  center and its IMU). See `lidar_imu_calib`. Separate from camera↔LiDAR.

**Summary:** LIO-SAM (a 6-axis fork) is a good mapping/odometry backbone but is downstream
of the current blockers. It adds an IMU requirement and a LiDAR↔IMU calibration. Decide
RTAB-Map vs LIO-SAM only after intrinsics + extrinsic are trustworthy.

## 13. PERTINENT FILES IN THIS FOLDER

**Read first:** `START_HERE_NEXT_SESSION.md` (authoritative v2), this file.
**Session-1 detail:** `CALIBRATION_HANDOFF.md`, `CALIB_PLAN.md`.
**Working code:** `nn_hole_detector.py`, `ring_hole_detector.py` (has `_plane_project` /
`_isolate_board`), `extrinsic_solver.py` (to be superseded), `lidar_hole_pipeline.py`,
`capture_board_cloud.py`.
**Real data:** `real_data/hole_centers.txt` (+ `.npy`).
**Board/print assets:** `calibration_board_drawing.svg`, `cut_guide_127mm.svg`,
`hole_overlay_detail.svg`, `step0_*.svg`, `checkerboard_A2_true-scale.pdf`,
`checkerboard_4tiles_Letter.pdf`.
**Key images:** `full_plane_survey.png` (clutter/isolation diagnostic),
`nn_final.png` (working NN detection), `cheese1_occ.png` (why flat projection fails),
`cam_corners2.jpg` / `hole_predict.jpg` (camera side), `cheese1_detect.png`.

**⚠ Be skeptical of** other files here from parallel chats (e.g. `COMPLETE_TECHNICAL_GUIDE.md`,
`PROJECT_REVIEW.md`, `auto_calibrate*.py`, various summaries) — some OVERSTATE progress
("<15 mm / ready for RTAB-Map"). Where they conflict with START_HERE (v2) or this record,
those are wrong.
