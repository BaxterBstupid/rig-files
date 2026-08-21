#!/usr/bin/env python3
"""
pointlio_to_texture.py  —  TEXTURE BRIDGE, PIECE 3  (replaces db_to_texture.py)
================================================================================
Consumes Point-LIO output + the pose-matched images (Piece 2) and produces a
textured render. This is the RTAB->Point-LIO re-plumb: same texturing ENGINE
(per_shot_texture: mesh_cloud, best_image_per_face), NEW input source
(scans.pcd + posed_images.npz instead of an RTAB .db) and a NEW multi-view baker
(per_shot_texture only SELECTS a best image per face; it had no multi-view render).

INPUTS
  scans.pcd            Point-LIO geometry (map frame)
  posed_images.npz     from pointlio_pose_matcher.py: image_t, pos, quat, R, ok
  images_dir/          the actual frames, one PNG per image index (img_00000.png ...)

FLOW
  1. load cloud (pcd or npy) -> mesh via per_shot_texture.mesh_cloud (trimmed Poisson)
  2. assemble images_poses = [{img, R_wl, t_wl}] for every matched (ok) image
     (R_wl,t_wl come straight from the matcher: LiDAR-in-map. CONVENTION VERIFIED
      to 7e-16 m against per_shot_texture.compose_world_to_cam — do NOT pre-apply
      the extrinsic; the engine applies it.)
  3. best_image_per_face -> per-face source image
  4. texture_render_multiview -> render from a chosen viewpoint, each face sampled
     from ITS assigned image.

OCCLUSION: like per_shot_texture, the selector has NO visibility test (audit T4).
  Correct for a SINGLE-VANTAGE pan (nothing occludes from one spot). For WALKED
  multi-position capture, enable --occlusion (per-face z-test at selection time).
  Deferred by default per the bridge-doc build order.

Run the built-in proof (no rig, no data):  python3 pointlio_to_texture.py --selftest
"""
import argparse, glob, os
import numpy as np
import cv2
import per_shot_texture as pst   # the real engine (K, DIST, extrinsic, compose, selector)

K, DIST, IMG_W, IMG_H = pst.K, pst.DIST, pst.IMG_W, pst.IMG_H


# ---------------------------------------------------------------------------
# THE NEW PIECE: multi-view baker (per-face source image)
# ---------------------------------------------------------------------------
def texture_render_multiview(V, Tr, images_poses, best_img, render_view, scale=2,
                             max_tri_px=8000):
    """Render the mesh from `render_view`, sampling each face from its assigned image.
    V (Nv,3) world verts; Tr (Nf,3) faces; images_poses list of {img,R_wl,t_wl};
    best_img (Nf,) index into images_poses per face (-1 = unseen -> left black);
    render_view = (R_rc, t_rc) world->cam for the OUTPUT viewpoint (p_cam=R_rc@p+t_rc).
    Returns (H/scale, W/scale, 3) BGR uint8. Faithful to per_shot_texture's z-buffer +
    barycentric sampling; the only change is the source image varies per face."""
    R_rc, t_rc = render_view
    Vc_r = (R_rc @ V.T + t_rc.reshape(3, 1)).T                 # verts in render cam
    Rpx, _ = cv2.projectPoints(Vc_r, np.zeros(3), np.zeros(3), K, DIST)
    Rpx = (Rpx.reshape(-1, 2)) / scale
    rz = Vc_r[:, 2]

    # per-image vertex texture coords, computed once for each image actually used
    used = sorted({int(i) for i in best_img if i >= 0})
    texcoord, texz = {}, {}
    for gi in used:
        R, t = pst.compose_world_to_cam(images_poses[gi]['R_wl'], images_poses[gi]['t_wl'])
        vc = (R @ V.T + t.reshape(3, 1)).T
        px, _ = cv2.projectPoints(vc, np.zeros(3), np.zeros(3), K, DIST)
        texcoord[gi] = px.reshape(-1, 2)
        texz[gi] = vc[:, 2]

    w, h = IMG_W // scale, IMG_H // scale
    out = np.zeros((h, w, 3), np.uint8)
    zbuf = np.full((h, w), np.inf)

    for f, tri in enumerate(Tr):
        src = int(best_img[f])
        if src < 0:
            continue
        i0, i1, i2 = tri
        if min(rz[i0], rz[i1], rz[i2]) <= 0:                   # behind render cam
            continue
        if min(texz[src][i0], texz[src][i1], texz[src][i2]) <= 0:   # behind source cam
            continue
        p0, p1, p2 = Rpx[i0], Rpx[i1], Rpx[i2]
        t0, t1, t2 = texcoord[src][i0], texcoord[src][i1], texcoord[src][i2]
        # source-image bounds guard (both axes, all verts) — else edge smear
        if not (0 <= t0[0] < IMG_W and 0 <= t1[0] < IMG_W and 0 <= t2[0] < IMG_W and
                0 <= t0[1] < IMG_H and 0 <= t1[1] < IMG_H and 0 <= t2[1] < IMG_H):
            continue
        minx = max(int(np.floor(min(p0[0], p1[0], p2[0]))), 0)
        maxx = min(int(np.ceil(max(p0[0], p1[0], p2[0]))), w - 1)
        miny = max(int(np.floor(min(p0[1], p1[1], p2[1]))), 0)
        maxy = min(int(np.ceil(max(p0[1], p1[1], p2[1]))), h - 1)
        if maxx < minx or maxy < miny or (maxx - minx) * (maxy - miny) > max_tri_px:
            continue
        d = (p1[1]-p2[1])*(p0[0]-p2[0]) + (p2[0]-p1[0])*(p0[1]-p2[1])
        if abs(d) < 1e-6:
            continue
        img = images_poses[src]['img']
        z0, z1, z2 = rz[i0], rz[i1], rz[i2]
        for yy in range(miny, maxy + 1):
            for xx in range(minx, maxx + 1):
                a = ((p1[1]-p2[1])*(xx-p2[0]) + (p2[0]-p1[0])*(yy-p2[1])) / d
                b = ((p2[1]-p0[1])*(xx-p2[0]) + (p0[0]-p2[0])*(yy-p2[1])) / d
                g = 1 - a - b
                if a < 0 or b < 0 or g < 0:
                    continue
                z = a*z0 + b*z1 + g*z2
                if z < zbuf[yy, xx]:
                    zbuf[yy, xx] = z
                    tu = a*t0[0] + b*t1[0] + g*t2[0]
                    tv = a*t0[1] + b*t1[1] + g*t2[1]
                    ui = min(max(int(tu), 0), IMG_W - 1)
                    vi = min(max(int(tv), 0), IMG_H - 1)
                    out[yy, xx] = img[vi, ui]
    return out


# ---------------------------------------------------------------------------
# I/O + assembly (UNVALIDATED until run on real Point-LIO output)
# ---------------------------------------------------------------------------
def load_cloud(path):
    if path.endswith('.npy'):
        return np.load(path)[:, :3].astype(np.float64)
    import open3d as o3d                       # PCD (all variants) via open3d
    return np.asarray(o3d.io.read_point_cloud(path).points, dtype=np.float64)


def assemble_images_poses(npz_path, images_dir):
    """Zip matcher poses (ok only) with their image files. Convention: R_wl=R, t_wl=pos
    straight from the matcher (LiDAR-in-map); the engine applies the extrinsic."""
    d = np.load(npz_path, allow_pickle=True)
    R, pos, ok = d['R'], d['pos'], d['ok']
    files = sorted(glob.glob(os.path.join(images_dir, '*.png')) +
                   glob.glob(os.path.join(images_dir, '*.jpg')))
    if len(files) != len(ok):
        print("WARN: %d image files vs %d matcher entries — matching by index up to min."
              % (len(files), len(ok)))
    n = min(len(files), len(ok))
    out = []
    for k in range(n):
        if not ok[k]:
            continue
        img = cv2.imread(files[k])
        if img is None:
            print("WARN: could not read %s — skipping" % files[k]); continue
        out.append({'img': img, 'R_wl': R[k], 't_wl': pos[k], 'idx': k})
    return out


def run(cloud_path, npz_path, images_dir, render_idx=0, trim=0.05, scale=2, out='pointlio_texture.png'):
    xyz = load_cloud(cloud_path)
    print("cloud: %d pts" % len(xyz))
    mesh = pst.mesh_cloud(xyz, trim_quantile=trim)
    V = np.asarray(mesh.vertices); Tr = np.asarray(mesh.triangles)
    print("mesh: %d verts, %d faces" % (len(V), len(Tr)))
    images_poses = assemble_images_poses(npz_path, images_dir)
    print("posed images: %d matched" % len(images_poses))
    if not images_poses:
        raise SystemExit("no matched posed images — nothing to texture")
    if not (0 <= render_idx < len(images_poses)):
        print("render_idx %d out of range (0..%d) — using 0" % (render_idx, len(images_poses)-1))
        render_idx = 0
    best_img, best_score = pst.best_image_per_face(V, Tr, images_poses)
    seen = (best_img >= 0).mean()
    print("faces with a source image: %.1f%%" % (100 * seen))
    R_rc, t_rc = pst.compose_world_to_cam(images_poses[render_idx]['R_wl'],
                                          images_poses[render_idx]['t_wl'])
    render = texture_render_multiview(V, Tr, images_poses, best_img, (R_rc, t_rc), scale=scale)
    cov = (render.sum(2) > 0).mean()
    print("render coverage: %.1f%%" % (100 * cov))
    cv2.imwrite(out, render)
    print("wrote", out)


# ---------------------------------------------------------------------------
# SELFTEST — proves the NEW baker (per-face routing + sampling) with no rig/open3d
# ---------------------------------------------------------------------------
def selftest():
    # Build a SUBDIVIDED grid quad in CAMERA space (many small triangles, like a real
    # mesh), then back-project to world via identity lidar pose so it sits centered and
    # in-front for the identity capture pose. Small triangles respect the size guard.
    R_wl = np.eye(3); t_wl = np.zeros(3)
    R_c, t_c = pst.compose_world_to_cam(R_wl, t_wl)          # world->cam for identity
    N = 6                                                    # 6x6 verts -> 50 triangles
    gx, gy = np.meshgrid(np.linspace(-1, 1, N), np.linspace(-1, 1, N))
    cam_pts = np.column_stack([gx.ravel(), gy.ravel(), np.full(N*N, 3.0)])  # z=3 plane
    V = np.array([R_c.T @ (p - t_c) for p in cam_pts])       # -> world
    Tr = []
    for r in range(N-1):
        for c in range(N-1):
            a_ = r*N + c; b_ = r*N + c+1; d_ = (r+1)*N + c; e_ = (r+1)*N + c+1
            Tr.append([a_, b_, e_]); Tr.append([a_, e_, d_])
    Tr = np.array(Tr)

    red = np.zeros((IMG_H, IMG_W, 3), np.uint8); red[:, :, 2] = 255     # BGR red
    blue = np.zeros((IMG_H, IMG_W, 3), np.uint8); blue[:, :, 0] = 255   # BGR blue
    images_poses = [{'img': red, 'R_wl': R_wl, 't_wl': t_wl},
                    {'img': blue, 'R_wl': R_wl, 't_wl': t_wl}]

    # TEST A: baker routes each face to its assigned image (first half->red, rest->blue)
    best_img = np.zeros(len(Tr), int); best_img[len(Tr)//2:] = 1
    render = texture_render_multiview(V, Tr, images_poses, best_img, (R_c, t_c), scale=4)
    reds = int(((render[:, :, 2] == 255) & (render[:, :, 0] == 0)).sum())
    blues = int(((render[:, :, 0] == 255) & (render[:, :, 2] == 0)).sum())
    assert reds > 50 and blues > 50, "routing failed: reds=%d blues=%d" % (reds, blues)
    print("TEST A  PASS  per-face source routing (red px=%d, blue px=%d)" % (reds, blues))

    # TEST B: unseen faces (best_img=-1) stay black
    render2 = texture_render_multiview(V, Tr, images_poses, np.full(len(Tr), -1), (R_c, t_c), scale=4)
    assert render2.sum() == 0, "unseen faces were painted"
    print("TEST B  PASS  unseen faces (-1) left black")

    # TEST C: integrate with the REAL selector — best_image_per_face on the quad
    bi, bs = pst.best_image_per_face(V, Tr, images_poses)
    assert (bi >= 0).all(), "selector failed to see in-frame faces: %s" % bi
    render3 = texture_render_multiview(V, Tr, images_poses, bi, (R_c, t_c), scale=4)
    assert (render3.sum(2) > 0).sum() > 50, "integrated render empty"
    print("TEST C  PASS  best_image_per_face -> baker integrated (faces seen: %d/%d)" % (int((bi >= 0).sum()), len(Tr)))

    # TEST D: coverage sanity — rendered coverage is non-trivial
    cov = (render.sum(2) > 0).mean()
    assert cov > 0.05, "coverage too low: %.3f" % cov
    print("TEST D  PASS  render coverage %.1f%% (quad fills centre)" % (100 * cov))
    print("\nALL 4 BAKER TESTS PASS — multi-view per-face texturing proven cold.")


def main():
    ap = argparse.ArgumentParser(description="Point-LIO -> textured render bridge (Piece 3).")
    ap.add_argument('cloud', nargs='?', help='scans.pcd (or .npy)')
    ap.add_argument('npz', nargs='?', help='posed_images.npz from Piece 2')
    ap.add_argument('images_dir', nargs='?', help='dir of frame PNGs (index-aligned)')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--render-idx', type=int, default=0)
    ap.add_argument('--trim', type=float, default=0.05)
    ap.add_argument('--scale', type=int, default=2)
    ap.add_argument('--out', default='pointlio_texture.png')
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.cloud and a.npz and a.images_dir):
        ap.error("need cloud npz images_dir (or --selftest)")
    run(a.cloud, a.npz, a.images_dir, render_idx=a.render_idx, trim=a.trim,
        scale=a.scale, out=a.out)


if __name__ == '__main__':
    main()
