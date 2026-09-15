#!/usr/bin/env python3
"""
poses_to_colmap.py — RUN ON SHADOW in the 'fusion' env, in shadow_bundle folder.
Converts posed_images_ALL.npz (2200 frames) -> COLMAP text model for Gaussian splat training.
Reuses the PROVEN compose_world_to_cam from per_shot_texture.py (same math that textured the meshes).
Outputs: colmap_model/cameras.txt, images.txt, points3D.txt (+ undistorted images).
Includes the CAMERA-CENTER UNIT TEST (must pass before training).
"""
import numpy as np, os, cv2
from scipy.spatial.transform import Rotation as Rot
import per_shot_texture as pst   # gives K, DIST, R_L2C, T_L2C, IMG_W, IMG_H, compose_world_to_cam

NPZ   = 'posed_images_ALL.npz'          # the 2200-frame recovered poses
PCD   = 'fusioncap_180551_scans.pcd'
FRAMES= os.path.join(os.path.expanduser('~'),'Desktop','frames_180551')
OUTDIR= 'colmap_model'
UNDIST_DIR = 'images_undist'            # pre-undistorted images (so we use PINHOLE, no distortion ambiguity)
os.makedirs(OUTDIR, exist_ok=True); os.makedirs(UNDIST_DIR, exist_ok=True)

K, DIST = pst.K, pst.DIST
W, H = pst.IMG_W, pst.IMG_H
fx, fy, cx, cy = K[0,0], K[1,1], K[0,2], K[1,2]

z = np.load(NPZ, allow_pickle=True)
pos, R_all, ok = z['pos'], z['R'], np.asarray(z['ok'], bool)
N = len(pos)
print(f"loaded {N} poses, ok={int(ok.sum())}")

# --- STEP 1+2 (proven): world-to-camera via compose_world_to_cam(R_wl=R, t_wl=pos) ---
# compose_world_to_cam returns R_w2c, t_w2c such that p_cam = R_w2c @ p_world + t_w2c
# COLMAP images.txt wants exactly this (world-to-camera), quaternion (qw,qx,qy,qz).

# --- new undistorted intrinsic (after undistort, distortion = 0, use PINHOLE) ---
newK, _ = cv2.getOptimalNewCameraMatrix(K, DIST, (W,H), 0, (W,H))
nfx, nfy, ncx, ncy = newK[0,0], newK[1,1], newK[0,2], newK[1,2]

# --- cameras.txt (single PINHOLE camera, undistorted) ---
with open(os.path.join(OUTDIR,'cameras.txt'),'w') as f:
    f.write("# Camera list\n# CAMERA_ID MODEL WIDTH HEIGHT PARAMS[]\n")
    f.write(f"1 PINHOLE {W} {H} {nfx} {nfy} {ncx} {ncy}\n")

# --- images.txt + undistort images + UNIT TEST ---
print("=== converting poses + undistorting images + UNIT TEST ===")
max_center_err = 0.0
lines = []
mapx, mapy = cv2.initUndistortRectifyMap(K, DIST, None, newK, (W,H), cv2.CV_32FC1)
n_written = 0
for i in range(N):
    if not ok[i]: continue
    fn = f'img_{i:05d}.png'
    src = os.path.join(FRAMES, fn)
    if not os.path.exists(src): continue
    R_w2c, t_w2c = pst.compose_world_to_cam(R_all[i], pos[i])
    # UNIT TEST: camera center recovered from (R_w2c,t_w2c) must equal the camera-in-world position.
    # camera center in world = -R_w2c^T @ t_w2c. The TRUE camera center = pos + R@(lidar->cam offset)
    cam_ctr = -R_w2c.T @ t_w2c
    true_cam_ctr = pos[i] + R_all[i] @ (-pst.R_L2C.T @ pst.T_L2C)  # lidar pos + camera offset in world
    err = np.linalg.norm(cam_ctr - true_cam_ctr)
    max_center_err = max(max_center_err, err)
    # quaternion from R_w2c, reorder xyzw -> wxyz for COLMAP
    q = Rot.from_matrix(R_w2c).as_quat()  # x,y,z,w
    qw,qx,qy,qz = q[3],q[0],q[1],q[2]
    lines.append(f"{n_written+1} {qw} {qx} {qy} {qz} {t_w2c[0]} {t_w2c[1]} {t_w2c[2]} 1 {fn}\n\n")
    # undistort + save
    img = cv2.imread(src)
    if img is not None:
        cv2.imwrite(os.path.join(UNDIST_DIR, fn), cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR))
    n_written += 1
    if n_written % 500 == 0: print(f"  {n_written} done")

with open(os.path.join(OUTDIR,'images.txt'),'w') as f:
    f.write("# Image list\n# IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME\n")
    f.writelines(lines)

print(f"\n*** UNIT TEST: max camera-center error = {max_center_err*1000:.3f} mm ***")
print("    (should be < ~1mm. If large, the pose convention is WRONG - do not train.)")

# --- points3D.txt from the LiDAR cloud (world frame, same as poses) ---
print("=== writing points3D.txt from LiDAR cloud ===")
import open3d as o3d
pc = o3d.io.read_point_cloud(PCD)
pc = pc.voxel_down_sample(0.03)  # 3cm downsample -> plenty for init, keeps file sane
pts = np.asarray(pc.points)
cols = (np.asarray(pc.colors)*255).astype(int) if pc.has_colors() else np.full((len(pts),3),128)
with open(os.path.join(OUTDIR,'points3D.txt'),'w') as f:
    f.write("# 3D point list\n# POINT3D_ID X Y Z R G B ERROR TRACK[]\n")
    for j,(p,c) in enumerate(zip(pts,cols)):
        f.write(f"{j+1} {p[0]} {p[1]} {p[2]} {c[0]} {c[1]} {c[2]} 0\n")
print(f"  wrote {len(pts)} init points")
print(f"\nDONE. COLMAP model in {OUTDIR}/, undistorted images in {UNDIST_DIR}/")
print(f"wrote {n_written} images to the model")
