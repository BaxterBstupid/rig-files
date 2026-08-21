# TEXTURE BRIDGE — RUNBOOK (cold-prep complete; hot window = execution only)
Point-LIO geometry + calibrated camera → photoreal textured render, ready to relight.
Everything below the "HOT WINDOW" line is proven cold; the hot steps are just capture.

---

## STATUS — what is PROVEN vs UNVALIDATED (be honest at the rig)

PROVEN COLD (in sandbox, reproducible):
- Pose math (Piece 2): interpolation (LERP + SLERP) recovers a constant-velocity trajectory
  to 5e-16 m / 0.0 deg (`pointlio_pose_matcher.py --selftest`, 7 tests).
- Convention lock: matcher output (R, pos) == per_shot_texture (R_wl, t_wl), verified to
  7e-16 m against the real `compose_world_to_cam`. `APPLY_EXTRINSIC=False`.
- Multi-view baker (Piece 3): per-face routing + sampling (`--selftest`, 4 tests).
- Piece 2 -> Piece 3 FILE interface: the saved `posed_images.npz` + dumped frames load into
  Piece 3 with EXACT pose values and index alignment (integration test).
- Whole bridge on REAL data: 161k-pt L2 cloud + real image -> 385k-face mesh -> textured
  render 90.3% coverage, photoreal (`pointlio_bridge_realproof.png`).
- Point-LIO L2 config/topics: confirmed from the real repos (topics match our rig, odom
  `/aft_mapped_to_init`, geometry `PCD/scans.pcd`, gravity-aligned z-up map).

NOT YET VALIDATED (needs the first real capture — the risk lives here):
- Coexistence: camera + Point-LIO together (CPU/USB load) — never done. #1 unknown.
- Bag I/O: `read_bag` / `dump_frames` / pcd load — written to spec, run on NO real bag.
- Clock alignment: matcher assumes odom stamps and image stamps share ONE clock (see C2).
- Multi-pose (walked) texturing: single-vantage is occlusion-free; walked needs `--occlusion`.

---

## COLD-PREP 0 — OPEN3D ON THE JETSON (do this first, no rig)
Open3D does the meshing + PCD read. On Jetson (aarch64) the OFFICIAL pip wheel is the
supported path — Open3D lists Nvidia Jetson as the example device with `pip install open3d`
= Yes, "special build flags: not needed". It is CPU-only on ARM (no CUDA) — which is ALL we
use. So the CUDA build failure in isl-org/Open3D#6885 does NOT apply: we never build the CUDA
module. If a wheel ever doesn't fit the Python version, fallback is a CPU-only build
`cmake -DBUILD_CUDA_MODULE=OFF -DBUILD_GUI=OFF` (sidesteps that exact error).

  1. INSTALL + IMPORT CHECK:
       pip install open3d
       python3 -c "import open3d; print(open3d.__version__)"
  2. *** REAL GATE (import success is NOT proof the ARM meshing path works) ***
     Reproduce the realproof render ON THE JETSON from data we already have
     (dense_test_pose_clean_cloud.npy + its image, via the COLD-2 form).
     PASS if you get a ~385k-face mesh and a photoreal render matching
     pointlio_bridge_realproof.png. THAT proves the ARM meshing path, not just import.

## COLD-PREP 1 — ISOLATE THE PROCESSING ENV (resolves the numpy clash, C1 below)
ROS2 Humble ships numpy 1.x; pip-installing Open3D can pull numpy 2.x and break rclpy/cv_bridge.
The matcher + bridge read bags via rosbags (pure python — NO ROS install needed), so run ALL
cold processing in an isolated venv, decoupled from system ROS2. Still one machine (one roof):
       python3 -m venv ~/tex_env && source ~/tex_env/bin/activate
       pip install open3d rosbags opencv-python numpy
   Capture (HOT-*) runs in the SYSTEM ROS2 env; processing (COLD-*) in ~/tex_env. They never
   share a Python process, so their numpy versions can't collide.

---

## ============ HOT WINDOW (rig on — minimize L2 heat) ============
In order. Each has a PASS gate; if one fails, stop and diagnose cold — don't improvise hot.

### HOT-1 — COEXISTENCE TEST (short, stationary, ~20s). The load-bearing unknown.
Bring up LiDAR + camera (lean — NO fusion node). Then:  `./capture_pointlio_texture.sh`
Hold STILL, Ctrl+C after ~20s.
PASS if: gates [3]/[5] passed, bag recorded without a flood of dropped-message warnings, and
`scans.pcd` saved on exit. Frames dropping badly -> you're on raw `/image_raw`; use compressed
or lower fps. No odom -> check `/tmp/pointlio.log` cold. Prove coexistence ONLY.

### HOT-2 — GEOMETRY SANITY. Did Point-LIO fix rotation?
Slow ~270 deg STOP-AND-GO pan (stationary 5s for IMU init first). Ctrl+C. Then COLD:
    python3 -c "import open3d,numpy as np; p=open3d.io.read_point_cloud('scans_<stamp>.pcd'); \
      x=np.asarray(p.points); print('extent',(x.max(0)-x.min(0)).round(2),'npts',len(x))"
PASS if the room is COHERENT: walls ~square, height ~2.5-3 m (NOT 13 m), full room present.
Direct test that Point-LIO beat RTAB's rotation collapse. If still collapsed -> stop, reassess
(7K); do not texture.

### HOT-3 — rig can go OFF. Everything below is cold processing.

---

## COLD PROCESSING (rig off — in ~/tex_env)

### COLD-1 — pose match + extract frames (Piece 2)
    python3 pointlio_pose_matcher.py plio_texcap_<stamp> \
        --image-topic /camera/image_raw/compressed \
        --dump-frames plio_texcap_<stamp>/frames
PASS if "matched N/M images" is high AND frame count == stamp count (script warns if not).

### COLD-2 — texture (Piece 3)
    python3 pointlio_to_texture.py scans_<stamp>.pcd \
        posed_images.npz plio_texcap_<stamp>/frames --scale 3 --out bridge_<stamp>.png
PASS if coverage high and photoreal where geometry is clean (compare realproof). Black = mesh
holes (meshing limiter), not a bridge bug. WALKED capture -> add `--occlusion` (once built).

### COLD-3 — inspect / iterate
Compare to realproof. Meshing the limiter (shred/holes) -> tune `--trim`/Poisson depth. Texture
OFFSET (not just holey) -> suspect pose/time mismatch: confirm stop-and-go + stamp alignment (C2).

---

## DEPENDENCY & CONFLICT SCAN (debug pass, 2026-08-21)

RESOLVED BY DESIGN (no action):
- Piece 2<->3 file interface: PROVEN exact (integration test — count, values, index alignment).
- Convention R_wl/t_wl: PROVEN to 7e-16 vs the real engine. No double-apply.
- Frame co-framing: `scans.pcd` AND `/aft_mapped_to_init` are BOTH in Point-LIO's gravity-
  aligned map frame, so mesh + poses share one world frame — consistent with compose_world_to_cam.
  NOTE: the realproof used identity pose because that dense cloud is a single-vantage SENSOR-
  frame cloud. The real Point-LIO pcd is MAP-frame; use the MATCHED poses, never identity.
- Topics match the rig (`/unilidar/cloud`, `/unilidar/imu`) — no remap.

MANAGE (real risks, mitigated):
- C1 numpy clash (Jetson): ROS2 numpy 1.x vs Open3D's pull. MITIGATED by the ~/tex_env venv
  (COLD-PREP 1); rosbags needs no ROS, so processing is fully decoupled from system Python.
- C2 clock/time-base: matcher assumes odom + image stamps share one clock. VERIFY on the first
  bag (spans overlap, sane); residual is the unmeasured ~175ms tau. Stop-and-go makes it benign
  (zero angular velocity during holds). If texture is offset not holey, this is the suspect.
- C3 extrinsic hardcoded in per_shot_texture (audit T1): not loaded from extrinsic_20260816.yaml.
  If the camera arm shifts / recalibration happens, update per_shot_texture's R_L2C/T_L2C too, or
  projection silently diverges from geometry.
- C4 bag-read order: `read_bag` (stamps) and `dump_frames` (PNGs) iterate the same single topic
  in log order -> aligned by construction; UNVALIDATED on a real bag. Count-mismatch warning
  catches gross misalignment.

MINOR (noted, non-blocking):
- Coverage metric counts a genuinely BLACK-textured pixel as "empty" — slightly undercounts very
  dark regions. Irrelevant for real photos.
- `--render-idx` out of range now guarded (falls back to 0).

---

## AFTER THIS WORKS -> the actual product question (7K, still open)
A clean textured render proves CAPTURE->TEXTURE. The rig's real differentiator is RELIGHT
(day->night, Unreal light placement — Polycam can't). Next milestone after a good textured mesh:
prove delight -> PBR -> relight on it. That, not a prettier mesh, justifies the rig.
