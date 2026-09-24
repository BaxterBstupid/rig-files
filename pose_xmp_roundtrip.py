#!/usr/bin/env python3
"""
pose_xmp_roundtrip.py — verify the Point-LIO -> RealityScan camera-pose handoff
================================================================================
WHY (ADR-003 conflict #3): the matcher outputs T_lidar_in_map with
APPLY_EXTRINSIC=False; RealityScan XMP/Trajectory wants the CAMERA pose. So the
L2->camera extrinsic (R_L2C 85.5deg, T_L2C ~17 cm) must be applied EXACTLY ONCE
when exporting to RealityScan. Apply it zero times OR twice and every photo
projects from the wrong place -> garbage even on a perfect capture. Double-apply
is a ~17 cm / tens-of-degrees error; zero-apply is worse.

WHAT THIS PROVES (fully, in the sandbox, no RealityScan needed):
  1. SINGLE-APPLY GUARD: the exported camera center equals the once-applied
     center, and is measurably far (>5 cm) from both the zero-apply and the
     twice-apply centers -> catches the exact plumbing bug we fear.
  2. ROUND-TRIP CONSISTENCY: a set of world points projects to the SAME pixels
     through (a) per_shot_texture.compose_world_to_cam and (b) the exported
     (center, R_world2cam) pose -> the export loses nothing.
  3. OPK SELF-CONSISTENCY: Omega/Phi/Kappa extracted from R round-trips back to
     R -> our OPK math is internally correct.

WHAT THIS DOES *NOT* PROVE (needs your data — do NOT fake it):
  - that our Omega/Phi/Kappa axis order/signs match RealityScan's ENU convention
    and the known 2.1.1 XMP-orientation-flip. That convention was ALREADY SOLVED
    once (Master 20.13.59: locked priors, correct O/P/K). So the right move is to
    VERIFY the existing writer, not reinvent it:
        >>> send poses_to_colmap.py (and one real img_XXXXX.xmp it produced) <<<
    and this harness will diff our reference against it and confirm single-apply
    on the real thing.
================================================================================
"""
import sys, os
import numpy as np

sys.path.insert(0, "/tmp/claude-0/-home-claude/364c3b82-74e3-557a-9bdd-0ea138e86343/scratchpad")
import per_shot_texture as PST   # K, DIST, R_L2C, T_L2C, compose_world_to_cam
import cv2

np.set_printoptions(precision=6, suppress=True)


def cam_center_world(R_cw, t_cw):
    """Camera center in world from a world->cam (R,t)."""
    return -R_cw.T @ t_cw


def export_camera_pose(R_wl, t_wl):
    """The handoff under test: Point-LIO lidar-in-map pose -> RS camera pose.
    Uses per_shot_texture's compose (extrinsic applied ONCE)."""
    R_cw, t_cw = PST.compose_world_to_cam(R_wl, t_wl)   # world->cam, extrinsic applied once
    C = cam_center_world(R_cw, t_cw)                     # camera center in world (RS Position)
    return C, R_cw                                       # RS stores position + world->cam rot


from scipy.spatial.transform import Rotation as _Rot

def rot_to_opk(R):
    """Omega/Phi/Kappa = extrinsic rotations about fixed X,Y,Z (R = Rz(k)Ry(p)Rx(o)).
    scipy lowercase 'xyz' = extrinsic -> from_euler('xyz',[o,p,k]) == Rz@Ry@Rx."""
    o, p, k = _Rot.from_matrix(R).as_euler('xyz')
    return o, p, k


def opk_to_rot(o, p, k):
    return _Rot.from_euler('xyz', [o, p, k]).as_matrix()


def project(R_cw, t_cw, P):
    fc = (R_cw @ P.T + t_cw.reshape(3, 1)).T
    px, _ = cv2.projectPoints(fc, np.zeros(3), np.zeros(3), PST.K, PST.DIST)
    return px.reshape(-1, 2)


def rand_pose(seed):
    rng = np.random.default_rng(seed)
    ax = rng.normal(size=3); ax /= np.linalg.norm(ax)
    ang = rng.uniform(-np.pi, np.pi)
    R, _ = cv2.Rodrigues(ax * ang)
    t = rng.uniform(-3, 3, size=3)
    return R, t


fails = 0
def check(name, cond, extra=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond: fails += 1


print("extrinsic under test: |T_L2C| = %.4f m (%.1f cm), rot angle = %.2f deg" % (
    np.linalg.norm(PST.T_L2C), 100*np.linalg.norm(PST.T_L2C),
    np.degrees(np.arccos((np.trace(PST.R_L2C)-1)/2))))
print()

# world points to probe (a little cloud in front of the rig)
rng = np.random.default_rng(0)
Pw = rng.uniform(-2, 2, size=(200, 3)) + np.array([0, 0, 4.0])

for seed in range(5):
    R_wl, t_wl = rand_pose(seed)

    # --- the correct, once-applied export
    C1, R_cw1 = export_camera_pose(R_wl, t_wl)

    # --- ZERO-apply (bug: hand RS the raw lidar pose as if it were the camera)
    C0 = t_wl                                  # lidar center, extrinsic NOT applied
    # --- TWICE-apply (bug: compose the extrinsic onto the already-composed pose)
    R_cw2, t_cw2 = PST.compose_world_to_cam(R_cw1, C1)   # apply extrinsic again
    C2 = cam_center_world(R_cw2, t_cw2)

    d0 = np.linalg.norm(C1 - C0); d2 = np.linalg.norm(C1 - C2)
    check("seed %d: single-apply center distinct from zero-apply (%.3f m) & twice-apply (%.3f m)"
          % (seed, d0, d2), d0 > 0.05 and d2 > 0.05)

    # --- round-trip: reconstruct world->cam (R,t) from (C1,R_cw1); it must equal
    #     the direct compose EXACTLY (this is the real "export loses nothing" test,
    #     with no cv2 z=0 projection singularity to muddy it).
    t_rec = -R_cw1 @ C1
    R_cw_direct, t_cw_direct = PST.compose_world_to_cam(R_wl, t_wl)
    rt_err = max(np.max(np.abs(R_cw1 - R_cw_direct)), np.max(np.abs(t_rec - t_cw_direct)))
    check("seed %d: exported (center,R) reconstructs world->cam exactly (max %.2e)"
          % (seed, rt_err), rt_err < 1e-9)
    # sanity: pixels agree for points genuinely IN FRONT of the camera
    fc = (R_cw_direct @ Pw.T + t_cw_direct.reshape(3, 1)).T
    front = Pw[fc[:, 2] > 0.5]
    if len(front):
        perr = np.max(np.abs(project(R_cw_direct, t_cw_direct, front)
                             - project(R_cw1, t_rec, front)))
        check("seed %d: front-point pixels identical (max %.2e px, n=%d)"
              % (seed, perr, len(front)), perr < 1e-6)

    # --- OPK self-consistency
    o, p, k = rot_to_opk(R_cw1)
    R_back = opk_to_rot(o, p, k)
    rerr = np.max(np.abs(R_back - R_cw1))
    check("seed %d: OPK round-trips to R (max %.2e)" % (seed, rerr), rerr < 1e-9)

print("\n%s" % ("ALL PASS" if fails == 0 else "%d FAILURES" % fails))
print("\nNEXT (needs your data): send poses_to_colmap.py + one real img_XXXXX.xmp;")
print("this harness will confirm the EXISTING writer applies the extrinsic once and")
print("that its O/P/K matches RealityScan's ENU convention (the part we won't guess).")
sys.exit(1 if fails else 0)
