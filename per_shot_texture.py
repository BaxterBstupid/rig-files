#!/usr/bin/env python3
"""
per_shot_texture.py  —  PER-SHOT TEXTURING TOOL
================================================================================
Turns (LiDAR cloud) + (camera image) + (calibration/pose) into a TEXTURED render
from a chosen viewpoint. This is the "per-shot local texturing" path: instead of
baking one global texture, we PROJECT the real photo onto the mesh from the camera's
known position, then render.

Consolidates the scattered texture-probe logic into ONE reusable tool.

PIPELINE:
  1. load cloud + image + calibration (intrinsics K, dist D, extrinsic R,t lidar->cam)
  2. mesh the cloud (edge-preserving; trimmed Poisson = continuous surfaces for texture)
  3. TEXTURE: project the image onto the mesh from the camera pose (per-face image sample)
  4. RENDER from a chosen viewpoint (default = camera viewpoint; can move for parallax test)

USAGE (sandbox / dev):
  python3 per_shot_texture.py CLOUD.npy IMAGE.png  [--view camera|top|custom]

REQUIREMENTS THIS IMPLIES FOR THE RIG (important):
  - each texturing image MUST be saved WITH its camera pose (world position+orientation).
  - our calibration (intrinsics + extrinsic) gives camera-relative-to-lidar; the rig's
    per-keyframe pose gives lidar-in-world. Compose them for image-in-world.
  - the pan capture that stored NO images cannot feed this. Capture must store images.
"""
import sys, argparse
import numpy as np
import cv2

# ---- VETTED CALIBRATION (from calib_intrinsics_20260813.yaml + extrinsic_20260816.yaml) ----
K = np.array([[848.759, 0, 921.002],
              [0, 849.231, 565.962],
              [0, 0, 1]], dtype=np.float64)
DIST = np.array([-0.014979, -0.013547, -0.001997, 0.000698, 0.003842])
# extrinsic: p_cam = R_l2c @ p_lidar + t_l2c
R_L2C = np.array([
    [0.079231956747140869, 0.99456000522703925, -0.067621690549788172],
    [-0.98716139340257103, 0.087718305377614436, 0.13348364048516903],
    [0.13868915028045117, 0.056177352237994721, 0.9887413335600036]])
T_L2C = np.array([0.018336757321533628, -0.053568141733719279, -0.15964461058920226])
IMG_W, IMG_H = 1920, 1200


def load_cloud(path):
    a = np.load(path)
    xyz = a[:, :3].astype(np.float64)
    if len(xyz) < 1000:
        raise ValueError("cloud has only %d points (<1000) — too sparse to mesh; "
                         "check the capture." % len(xyz))
    return xyz


def mesh_cloud(xyz, trim_quantile=0.05, remove_outliers=True):
    """Edge-preserving-ish mesh: trimmed Poisson (continuous surfaces for texture).
    remove_outliers: strip stray far points that stretch density normalization and
    starve the mesh (even a handful of points at 15m+ noticeably sparsens the mesh)."""
    import open3d as o3d
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz)
    if remove_outliers:
        pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.05, max_nn=30))
    pcd.orient_normals_towards_camera_location(camera_location=[0, 0, 0])
    mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
    dens = np.asarray(dens)
    mesh.remove_vertices_by_mask(dens < np.quantile(dens, trim_quantile))
    return mesh


def texture_render(mesh, image, view='camera', scale=2):
    """
    Project `image` onto `mesh` from the CAMERA pose (via calibration), render from `view`.
    view='camera' renders from the capture camera (texture looks like the photo where
    geometry exists). Other views test parallax/how texture holds when you move.
    Returns an (H/scale, W/scale, 3) BGR render.
    """
    import open3d as o3d
    V = np.asarray(mesh.vertices)
    Tr = np.asarray(mesh.triangles)

    # project every vertex into the CAMERA image to get its texture coordinate
    Vc = (R_L2C @ V.T + T_L2C.reshape(3, 1)).T           # vertices in camera frame
    vpx, _ = cv2.projectPoints(Vc, np.zeros(3), np.zeros(3), K, DIST)
    vpx = vpx.reshape(-1, 2)                              # texture coord per vertex (image px)
    vz_cam = Vc[:, 2]

    # choose the RENDER camera (where we look FROM)
    if view == 'camera':
        # render from the capture camera: render-space == camera-space
        Vr = Vc
        Rpx, _ = cv2.projectPoints(Vr, np.zeros(3), np.zeros(3), K, DIST)
        Rpx = Rpx.reshape(-1, 2)
        rz = Vr[:, 2]
    elif view == 'top':
        # a top-down orthographic-ish view (parallax test): look down -Z of lidar frame
        # simple: use lidar-frame x,y as screen, depth = z
        Rpx = np.column_stack([(V[:, 0] - V[:, 0].min()) / (np.ptp(V[:, 0]) + 1e-9) * IMG_W,
                               (V[:, 1] - V[:, 1].min()) / (np.ptp(V[:, 1]) + 1e-9) * IMG_H])
        rz = V[:, 2] - V[:, 2].min() + 0.1
    else:
        Vr = Vc
        Rpx, _ = cv2.projectPoints(Vr, np.zeros(3), np.zeros(3), K, DIST)
        Rpx = Rpx.reshape(-1, 2); rz = Vr[:, 2]

    w, h = IMG_W // scale, IMG_H // scale
    out = np.zeros((h, w, 3), np.uint8)
    zbuf = np.full((h, w), np.inf)
    Rpx_s = Rpx / scale

    def sample_img(u, v):
        ui = int(min(max(u, 0), IMG_W - 1)); vi = int(min(max(v, 0), IMG_H - 1))
        return image[vi, ui]

    for tri in Tr:
        i0, i1, i2 = tri
        p0, p1, p2 = Rpx_s[i0], Rpx_s[i1], Rpx_s[i2]
        z0, z1, z2 = rz[i0], rz[i1], rz[i2]
        if min(z0, z1, z2) <= 0:
            continue
        # texture coords (in full-res image space) at each vertex
        t0, t1, t2 = vpx[i0], vpx[i1], vpx[i2]
        # skip triangles whose texture coords fall outside the image (not seen by camera).
        # check BOTH x (width) AND y (height) for all 3 verts, else edge pixels smear.
        if not (0 <= t0[0] < IMG_W and 0 <= t1[0] < IMG_W and 0 <= t2[0] < IMG_W and
                0 <= t0[1] < IMG_H and 0 <= t1[1] < IMG_H and 0 <= t2[1] < IMG_H):
            continue
        minx = max(int(np.floor(min(p0[0], p1[0], p2[0]))), 0)
        maxx = min(int(np.ceil(max(p0[0], p1[0], p2[0]))), w - 1)
        miny = max(int(np.floor(min(p0[1], p1[1], p2[1]))), 0)
        maxy = min(int(np.ceil(max(p0[1], p1[1], p2[1]))), h - 1)
        if maxx < minx or maxy < miny:
            continue
        if (maxx - minx) * (maxy - miny) > 8000:
            continue
        d = (p1[1]-p2[1])*(p0[0]-p2[0]) + (p2[0]-p1[0])*(p0[1]-p2[1])
        if abs(d) < 1e-6:
            continue
        for yy in range(miny, maxy+1):
            for xx in range(minx, maxx+1):
                a = ((p1[1]-p2[1])*(xx-p2[0]) + (p2[0]-p1[0])*(yy-p2[1])) / d
                b = ((p2[1]-p0[1])*(xx-p2[0]) + (p0[0]-p2[0])*(yy-p2[1])) / d
                g = 1 - a - b
                if a < 0 or b < 0 or g < 0:
                    continue
                z = a*z0 + b*z1 + g*z2
                if z < zbuf[yy, xx]:
                    zbuf[yy, xx] = z
                    # interpolate texture coordinate, sample full-res image
                    tu = a*t0[0] + b*t1[0] + g*t2[0]
                    tv = a*t0[1] + b*t1[1] + g*t2[1]
                    out[yy, xx] = sample_img(tu, tv)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cloud'); ap.add_argument('image')
    ap.add_argument('--view', default='camera')
    ap.add_argument('--out', default='per_shot_out.png')
    ap.add_argument('--trim', type=float, default=0.05)
    a = ap.parse_args()
    xyz = load_cloud(a.cloud)
    img = cv2.imread(a.image)
    print("cloud %d pts, image %s" % (len(xyz), img.shape))
    mesh = mesh_cloud(xyz, trim_quantile=a.trim)
    print("mesh %d verts %d tris" % (len(mesh.vertices), len(mesh.triangles)))
    out = texture_render(mesh, img, view=a.view)
    cov = (out.sum(2) > 0).sum()
    print("render coverage %.1f%%" % (100*cov/(out.shape[0]*out.shape[1])))
    cv2.imwrite(a.out, out)
    print("wrote", a.out)


if __name__ == '__main__':
    main()


# ============================================================================
# MULTI-VIEW PER-SHOT TEXTURING (pose-aware)  [restored 2026-08-20 from transcript]
# ============================================================================
# For a mesh in WORLD frame + several images each with their camera WORLD pose,
# texture each face from the BEST image that sees it (most head-on, in-frame).
# This is what a 270-pan or a walk produces: many images, each a different pose.
#
# Camera world pose per image is given as (R_wl, t_wl) meaning the LIDAR-in-world
# pose for that frame; we compose with the fixed extrinsic to get world->camera.

def compose_world_to_cam(R_wl, t_wl):
    """frame's lidar-in-world (R_wl,t_wl) -> single world->camera (R,t).
    p_cam = R @ p_world + t.  Verified: R = R_L2C@R_wl^T ; t = t_L2C - R@t_wl."""
    R = R_L2C @ R_wl.T
    t = T_L2C - R @ t_wl
    return R, t


def face_normals(V, Tr):
    a = V[Tr[:, 1]] - V[Tr[:, 0]]
    b = V[Tr[:, 2]] - V[Tr[:, 0]]
    n = np.cross(a, b)
    ln = np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return n / ln


def best_image_per_face(V, Tr, images_poses):
    """For each face, choose the image whose camera sees it most head-on and in-frame.
    images_poses: list of dicts {img, R_wl, t_wl}. Returns per-face (best_img, best_score).
    best_img[f] = index into images_poses (or -1 if no image sees the face);
    best_score[f] = head-on score in [0,1] (1=face-on) or -1 if unseen."""
    fcent = V[Tr].mean(axis=1)          # face centroids (world)
    fn = face_normals(V, Tr)            # face normals (world)
    nfaces = len(Tr)
    best_score = np.full(nfaces, -1.0)
    best_img = np.full(nfaces, -1, dtype=int)
    for gi, ip in enumerate(images_poses):
        R, t = compose_world_to_cam(ip['R_wl'], ip['t_wl'])
        cam_ctr_world = -R.T @ t         # camera position in world
        to_cam = cam_ctr_world[None, :] - fcent
        to_cam /= (np.linalg.norm(to_cam, axis=1, keepdims=True) + 1e-12)
        headon = np.abs((fn * to_cam).sum(axis=1))   # 1=head-on, 0=edge-on
        fc_cam = (R @ fcent.T + t.reshape(3, 1)).T
        infront = fc_cam[:, 2] > 0
        px, _ = cv2.projectPoints(fc_cam, np.zeros(3), np.zeros(3), K, DIST)
        px = px.reshape(-1, 2)
        inframe = (px[:, 0] >= 0) & (px[:, 0] < IMG_W) & (px[:, 1] >= 0) & (px[:, 1] < IMG_H)
        valid = infront & inframe
        score = np.where(valid, headon, -1.0)
        take = score > best_score
        best_score[take] = score[take]
        best_img[take] = gi
    return best_img, best_score
