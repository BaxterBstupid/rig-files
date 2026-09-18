#!/usr/bin/env python3
"""
colorize_cloud.py -- color a LiDAR cloud from N posed images (ADR-002).
By-frame vectorized + per-frame z-buffer occlusion + nearest-visible-camera.
Calib loaded from YAML (not hardcoded). Pose<->extrinsic composition matches make_xmp_v2.

USAGE:
  python colorize_cloud.py --cloud fusioncap_163005.ply --poses posed_163005.npz \
     --extr extrinsic_20260816.yaml --intr calib_intrinsics_20260813.yaml \
     --images frames_163005_key --out fusioncap_163005_COLOR.ply [--limit N] [--zbuf 480]
--limit N : only use the first N frames (subset validation). 0 = all.
"""
import sys, os, argparse, glob, numpy as np, cv2

def load_yaml_mat(path, key):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    m = fs.getNode(key).mat(); fs.release()
    return np.asarray(m)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cloud', required=True); ap.add_argument('--poses', required=True)
    ap.add_argument('--extr', required=True); ap.add_argument('--intr', required=True)
    ap.add_argument('--images', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--width', type=int, default=1920); ap.add_argument('--height', type=int, default=1200)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--zbuf', type=int, default=480, help='z-buffer width (height scaled to aspect)')
    ap.add_argument('--ztol', type=float, default=0.05, help='depth tolerance (m) for visibility')
    a = ap.parse_args()

    # --- calib from YAML (D4) ---
    R_L2C = load_yaml_mat(a.extr, 'R_lidar_to_cam')
    T_L2C = load_yaml_mat(a.extr, 't_lidar_to_cam').reshape(3)
    K     = load_yaml_mat(a.intr, 'camera_matrix')
    DIST  = load_yaml_mat(a.intr, 'distortion_coefficients').reshape(-1)
    W, H = a.width, a.height
    print("calib loaded. fx=%.1f  T_L2C=%s" % (K[0,0], T_L2C.round(3)))

    # --- cloud (positions in map frame) ---
    import open3d as o3d
    pc = o3d.t.io.read_point_cloud(a.cloud)
    P = pc.point['positions'].numpy().astype(np.float64)   # (N,3) map frame
    N = len(P)
    print("cloud:", N, "points")

    # --- poses (D5: same convention as make_xmp_v2; T_lidar_in_map body->map) ---
    z = np.load(a.poses, allow_pickle=True)
    pos, R_all, ok = z['pos'], z['R'], np.asarray(z['ok'], bool)

    # --- accumulators (D1/D3) ---
    best_dist = np.full(N, np.inf)
    colors = np.zeros((N, 3), np.uint8)   # BGR
    colored_mask = np.zeros(N, bool)

    # z-buffer dims (D2)
    zbw = a.zbuf; zbh = int(round(zbw * H / W))

    frames = {os.path.basename(f): f for f in glob.glob(os.path.join(a.images, '*.png'))}
    order = [i for i in range(len(pos)) if ok[i] and ('img_%05d.png'%i) in frames]
    if a.limit: order = order[:a.limit]
    print("frames to process:", len(order))

    import time; t0=time.time()
    for count, i in enumerate(order):
        img = cv2.imread(frames['img_%05d.png'%i])   # BGR
        if img is None: continue
        R_ml = R_all[i]                                # lidar->map (frame i)
        pos_i = pos[i]
        # world -> lidar(frame i): p_l = R_ml^T @ (P - pos_i)
        Pl = (R_ml.T @ (P - pos_i).T).T
        # lidar -> camera: p_cam = R_L2C @ p_l + T_L2C
        Pc = (R_L2C @ Pl.T).T + T_L2C
        zc = Pc[:,2]
        infront = zc > 0.05
        # project (only in-front, for speed)
        uv = np.full((N,2), -1.0)
        if infront.any():
            proj = cv2.projectPoints(Pc[infront].reshape(-1,1,3), np.zeros(3), np.zeros(3), K, DIST)[0].reshape(-1,2)
            uv[infront] = proj
        u = uv[:,0]; v = uv[:,1]
        inimg = infront & (u>=0)&(u<W)&(v>=0)&(v<H)
        if not inimg.any(): continue
        # --- per-frame z-buffer occlusion (D2) ---
        idx = np.where(inimg)[0]
        bx = np.clip((u[idx]/W*zbw).astype(int), 0, zbw-1)
        by = np.clip((v[idx]/H*zbh).astype(int), 0, zbh-1)
        zbuf = np.full((zbh, zbw), np.inf)
        # nearest depth per z-buffer cell
        order_by_z = np.argsort(zc[idx])
        for j in order_by_z:
            if zc[idx[j]] < zbuf[by[j], bx[j]]:
                zbuf[by[j], bx[j]] = zc[idx[j]]
        visible = zc[idx] <= (zbuf[by, bx] + a.ztol)
        vidx = idx[visible]
        # --- nearest-visible-camera assignment (D3) ---
        Cw = pos_i + R_ml @ (-R_L2C.T @ T_L2C)         # camera center in map
        dist = np.linalg.norm(P[vidx] - Cw, axis=1)
        better = dist < best_dist[vidx]
        take = vidx[better]
        ui = np.clip(u[take].astype(int), 0, W-1); vi = np.clip(v[take].astype(int), 0, H-1)
        colors[take] = img[vi, ui]
        best_dist[take] = dist[better]
        colored_mask[take] = True
        if count % 25 == 0:
            print("  frame %d/%d  colored so far: %d (%.0f%%)  %.1fs" %
                  (count, len(order), colored_mask.sum(), 100*colored_mask.mean(), time.time()-t0))

    print("DONE colorized %d/%d points (%.0f%%) in %.1fs" %
          (colored_mask.sum(), N, 100*colored_mask.mean(), time.time()-t0))
    # write ply (BGR->RGB)
    out = o3d.geometry.PointCloud()
    out.points = o3d.utility.Vector3dVector(P)
    rgb = colors[:, ::-1].astype(np.float64) / 255.0
    out.colors = o3d.utility.Vector3dVector(rgb)
    o3d.io.write_point_cloud(a.out, out)
    print("WROTE", a.out)

if __name__ == '__main__':
    main()
