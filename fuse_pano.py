#!/usr/bin/env python3
"""
fuse_pano.py  --  CANONICAL full-ring 360 render (station / sandbox side).

Projects a heading-spread posed-frame bundle onto a LiDAR cloud (occlusion-gated,
best-camera per point) and renders one equirectangular 360 PNG. Real photo colour
where a camera saw a surface; LiDAR intensity grayscale elsewhere.

This is the step that PASSED the visual gate on capture 114136 (2026-09-24):
77.7% of the cloud coloured, 306 deg heading coverage, 35 frames.

Calibration is EMBEDDED (below) so the render is self-contained and reproducible.
Values are verbatim from per_shot_texture.py. Convention: poses are T_lidar_in_map
(body->map); the camera<->LiDAR extrinsic is applied HERE, exactly once, in
compose_world_to_cam -- never in the matcher/exporter.

Run (station or sandbox, NOT the Jetson):
    python3 fuse_pano.py --cloud scans.pcd --bundle panbundle --out pano_full.png
  --cloud   binary PCD with fields: x y z intensity [...]   (Point-LIO scans.pcd)
  --bundle  dir with poses.npz (R,pos, T_lidar_in_map) + frames/img_000.jpg ...
            (produced by make_full_pan_anchor.py)
  --out     output equirectangular PNG (default pano_full.png)
"""
import argparse, os
import numpy as np, cv2

# ---- EMBEDDED CALIBRATION (verbatim from per_shot_texture.py) ----
K = np.array([[848.759, 0, 921.002],
              [0, 849.231, 565.962],
              [0, 0, 1]], dtype=np.float64)
DIST = np.array([-0.014979, -0.013547, -0.001997, 0.000698, 0.003842])
R_L2C = np.array([
    [0.079231956747140869, 0.99456000522703925, -0.067621690549788172],
    [-0.98716139340257103, 0.087718305377614436, 0.13348364048516903],
    [0.13868915028045117, 0.056177352237994721, 0.9887413335600036]])
T_L2C = np.array([0.018336757321533628, -0.053568141733719279, -0.15964461058920226])
IMG_W, IMG_H = 1920, 1200

def compose_world_to_cam(R_wl, t_wl):
    """T_lidar_in_map (body->map) -> world-to-camera. Extrinsic applied ONCE, here."""
    R = R_L2C @ R_wl.T
    t = T_L2C - R @ t_wl
    return R, t

def read_pcd_xyzi(path):
    with open(path, 'rb') as f:
        while True:
            line = f.readline()
            if line.startswith(b'DATA'):
                break
        raw = np.fromfile(f, dtype=np.float32)
    n = raw.size // 8              # x y z intensity nx ny nz curvature
    raw = raw[:n * 8].reshape(n, 8)
    return raw[:, :3].astype(np.float64), raw[:, 3].copy()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", default="pano_full.png")
    ap.add_argument("--width", type=int, default=2600)
    ap.add_argument("--rmax", type=float, default=25.0)
    args = ap.parse_args()

    P, inten = read_pcd_xyzi(args.cloud)
    d = np.load(os.path.join(args.bundle, "poses.npz"), allow_pickle=True)
    Rs, Ts = d['R'], d['pos']; NC = len(Rs)
    imgs = [cv2.imread(os.path.join(args.bundle, "frames", "img_%03d.jpg" % i)) for i in range(NC)]
    if any(im is None for im in imgs):
        raise SystemExit("missing frame(s) in %s/frames" % args.bundle)
    print("cloud pts %d | frames %d" % (len(P), NC))

    W, H = IMG_W, IMG_H
    col = np.zeros((len(P), 3), np.float32); best = np.full(len(P), -1.0)
    cx, cy, diag = W / 2, H / 2, np.hypot(W / 2, H / 2)
    OS = 0.5; w2, h2 = int(W * OS), int(H * OS)
    for i in range(NC):
        R_cw, t_cw = compose_world_to_cam(Rs[i], Ts[i])
        pc = (R_cw @ P.T + t_cw.reshape(3, 1)).T
        z = pc[:, 2]; infront = z > 0.15
        px = cv2.projectPoints(pc, np.zeros(3), np.zeros(3), K, DIST)[0].reshape(-1, 2)
        u, v = px[:, 0], px[:, 1]
        inframe = infront & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        idx = np.where(inframe)[0]
        if not len(idx):
            continue
        ui = np.clip((u * OS).astype(int), 0, w2 - 1); vi = np.clip((v * OS).astype(int), 0, h2 - 1)
        zb = np.full((h2, w2), 1e9, np.float32)
        np.minimum.at(zb, (vi[idx], ui[idx]), z[idx].astype(np.float32))
        visible = inframe & (z <= zb[vi, ui] * 1.03 + 0.05)
        centered = 1.0 - np.hypot(u - cx, v - cy) / diag
        score = np.where(visible, centered, -1.0)
        take = visible & (score > best); ti = np.where(take)[0]
        col[ti] = imgs[i][np.clip(v[ti].astype(int), 0, H - 1), np.clip(u[ti].astype(int), 0, W - 1)]
        best[ti] = score[ti]
    pct = 100.0 * (best > 0).mean()
    print("photo-coloured: %.1f%% of cloud" % pct)

    lo, hi = np.percentile(inten, [2, 98]); g = np.clip((inten - lo) / (hi - lo + 1e-9), 0, 1)
    gray = (255 * np.power(g, 0.6)).astype(np.uint8)
    colored = best > 0
    BGR = np.empty((len(P), 3), np.uint8)
    BGR[~colored] = np.stack([gray[~colored]] * 3, 1)
    BGR[colored] = np.clip(col[colored], 0, 255).astype(np.uint8)

    center = Ts.mean(0); vv = P - center; r = np.linalg.norm(vv, axis=1)
    keep = (r > 0.15) & (r < args.rmax); vv = vv[keep]; r = r[keep]; C = BGR[keep]
    az = np.arctan2(vv[:, 1], vv[:, 0]); el = np.arcsin(np.clip(vv[:, 2] / r, -1, 1))
    Wp = args.width; Hp = Wp // 2
    u = np.clip(((az + np.pi) / (2 * np.pi) * (Wp - 1)).astype(int), 0, Wp - 1)
    vr = np.clip(((1 - (el + np.pi / 2) / np.pi) * (Hp - 1)).astype(int), 0, Hp - 1)
    zbuf = np.full((Hp, Wp), 1e9, np.float32); img = np.zeros((Hp, Wp, 3), np.uint8)
    o = np.argsort(-r); uu, vrr, cc, rr = u[o], vr[o], C[o], r[o]
    for du in (-1, 0, 1):
        for dv in (-1, 0, 1):
            U = np.clip(uu + du, 0, Wp - 1); Vr = np.clip(vrr + dv, 0, Hp - 1)
            m = rr < zbuf[Vr, U]; img[Vr[m], U[m]] = cc[m]; zbuf[Vr[m], U[m]] = rr[m]
    cv2.imwrite(args.out, img)
    print("wrote %s  (%.1f%% coloured)" % (args.out, pct))

if __name__ == "__main__":
    main()
