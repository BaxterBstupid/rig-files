#!/usr/bin/env python3
"""
planar_shell.py  --  RANSAC room-shell reconstructor for the LiDAR-camera rig.

WHY THIS EXISTS
---------------
Poisson (what fuse_to_fbx.py still runs at depth 9) was convicted on our own bench:
it invented surface up to 1556 mm from any measured point = the melt/blob. But our
own analysis also found ~52% of a room cloud is already CLEAN PLANES (walls+floor+
ceiling) at 16 mm thickness -- the L2 sensor limit, no drift smear. This tool stops
blob-meshing those planes. It FITS them (RANSAC) so walls come out flat and corners
come out sharp, and rasterizes each plane's real measured extent so windows and doors
stay as genuine OPENINGS instead of being melted over.

WHY IT'S ROBUST TO OUR CAPTURE WEAKNESS
---------------------------------------
Photogrammetry (RealityScan / Gaussian / Polycam / our photo-first pass) needs camera
PARALLAX -- orbiting a surface. Our captures are often parallax-starved (straight dolly),
which caps every one of those tools. A LiDAR plane does not triangulate across views: the
L2 measures the wall directly from where it stands. So this shell does not care that we
didn't orbit. It only needs the odometry not to have collapsed -- which this tool MEASURES
for you (per-plane thickness = drift/double-wall check; wall orthogonality = rotation-
collapse check). No normals needed. tau-independent (geometry always was).

OUTPUTS (into --out)
  shell.obj         crisp planar shell (flat walls, sharp corners, real openings)
  objects.ply       the non-planar remainder (furniture/objects) as points
  shell_render.png  shaded multi-view preview so you SEE it without a huge transfer
  report.txt        the coherence diagnostic (also printed): planes, thickness,
                    orthogonality, % of cloud explained -- i.e. "is the geometry
                    corrupted, or was it only ever the mesher?"

DEPS: numpy, open3d.  Optional: opencv-python OR pillow (for the PNG).  All in the
Shadow 'fusion' env already.

RUN
  python planar_shell.py --cloud fusioncap_163005.ply --out shell_163005 \
      [--poses posed_163005.npz]        # optional; only used for a parallax read-out
  python planar_shell.py --selftest --out selftest_out   # no operator data needed
"""
import sys, os, argparse, math
import numpy as np


# --------------------------------------------------------------------------- io
def load_cloud(path):
    import open3d as o3d
    pc = o3d.io.read_point_cloud(path)
    P = np.asarray(pc.points, dtype=np.float64)
    P = P[np.isfinite(P).all(axis=1)]
    return P


def to_o3d(P):
    import open3d as o3d
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(np.ascontiguousarray(P))
    return pc


def parallax_readout(poses_path):
    """Informational: does the trajectory have the parallax photogrammetry needs?
    Pure read-out -- the shell does NOT depend on this, but it explains why photo
    pipelines struggled and confirms whether the ratified orbit rule was met."""
    try:
        z = np.load(poses_path, allow_pickle=True)
        pos = np.asarray(z['pos'], float)
        ok = np.asarray(z['ok'], bool) if 'ok' in z else np.ones(len(pos), bool)
        pos = pos[ok]
        span = pos.max(0) - pos.min(0)
        return span, len(pos)
    except Exception as e:
        return None, str(e)


# ------------------------------------------------------------------ plane finder
def extract_planes(P, dist, min_frac, max_planes, ransac_n=3, iters=1000):
    """Iterative RANSAC. Returns list of dicts: model[4], idx(global), thickness_m."""
    import open3d as o3d
    n_total = len(P)
    rest_idx = np.arange(n_total)
    rest = to_o3d(P)
    planes = []
    min_pts = max(int(min_frac * n_total), 200)
    for _ in range(max_planes):
        if len(rest.points) < min_pts:
            break
        model, inl = rest.segment_plane(distance_threshold=dist,
                                        ransac_n=ransac_n, num_iterations=iters)
        if len(inl) < min_pts:
            break
        inl = np.asarray(inl, int)
        gidx = rest_idx[inl]
        Pi = P[gidx]
        a, b, c, d = model
        nrm = np.array([a, b, c], float)
        nl = np.linalg.norm(nrm)
        signed = (Pi @ nrm + d) / (nl + 1e-12)
        planes.append({
            'model': np.array(model, float) / (nl + 1e-12),
            'normal': nrm / (nl + 1e-12),
            'idx': gidx,
            'n': len(gidx),
            'thickness_m': float(signed.std()),
            'centroid': Pi.mean(0),
        })
        keep = np.ones(len(rest_idx), bool); keep[inl] = False
        rest_idx = rest_idx[keep]
        rest = to_o3d(P[rest_idx])
    return planes, rest_idx


# ------------------------------------------------------------- classify + report
def classify(planes, up=np.array([0, 0, 1.0])):
    for pl in planes:
        n = pl['normal']
        vert_align = abs(float(n @ up))          # 1 = horizontal surface, 0 = wall
        if vert_align > 0.85:
            pl['kind'] = 'floor' if pl['centroid'] @ up < 0 else 'ceiling'
        elif vert_align < 0.35:
            pl['kind'] = 'wall'
        else:
            pl['kind'] = 'slanted'
        pl['vert_align'] = vert_align
    # decide floor vs ceiling by relative height among horizontals
    horiz = [p for p in planes if p['kind'] in ('floor', 'ceiling')]
    if len(horiz) >= 2:
        hs = sorted(horiz, key=lambda p: p['centroid'] @ up)
        for p in hs:
            p['kind'] = 'ceiling'
        hs[0]['kind'] = 'floor'
    return planes


def wall_orthogonality(planes):
    """Azimuth of each wall (mod 180). Rectangular room -> two clusters 90 apart.
    Big scatter -> rotation collapse / warp. Returns (azimuths_deg, max_dev_deg)."""
    azs = []
    for p in planes:
        if p['kind'] != 'wall':
            continue
        n = p['normal']
        az = math.degrees(math.atan2(n[1], n[0])) % 180.0
        azs.append(az)
    if len(azs) < 2:
        return azs, None
    # fold every azimuth to its distance from the nearest multiple of 90 of the
    # first wall -- a healthy rectangular room gives ~0 deviation for all walls.
    ref = azs[0]
    devs = []
    for a in azs:
        diff = (a - ref) % 90.0
        devs.append(min(diff, 90.0 - diff))
    return azs, max(devs)


def build_report(planes, rest_idx, n_total, span, span_n):
    L = []
    L.append("=" * 70)
    L.append("PLANAR SHELL -- COHERENCE REPORT")
    L.append("=" * 70)
    explained = sum(p['n'] for p in planes)
    L.append(f"cloud points            : {n_total:,}")
    L.append(f"points on fitted planes : {explained:,} ({100*explained/max(n_total,1):.1f}%)")
    L.append(f"non-planar remainder    : {len(rest_idx):,} ({100*len(rest_idx)/max(n_total,1):.1f}%)")
    L.append(f"planes found            : {len(planes)}")
    L.append("")
    L.append(f"{'#':>2} {'kind':>8} {'pts':>9} {'thick_mm':>9}  drift?")
    for i, p in enumerate(planes):
        tmm = p['thickness_m'] * 1000
        flag = "OK" if tmm < 30 else ("thick" if tmm < 80 else "*** DRIFT/DOUBLE-WALL ***")
        L.append(f"{i:>2} {p['kind']:>8} {p['n']:>9,} {tmm:>9.1f}  {flag}")
    L.append("")
    azs, maxdev = wall_orthogonality(planes)
    if maxdev is None:
        L.append("wall orthogonality      : <2 walls found, cannot judge")
    else:
        verdict = ("HEALTHY (walls square)" if maxdev < 6 else
                   "MILD skew" if maxdev < 15 else
                   "*** NON-ORTHOGONAL -- likely rotation collapse / warp ***")
        L.append(f"wall azimuths (deg)     : {', '.join(f'{a:.1f}' for a in azs)}")
        L.append(f"max deviation from square: {maxdev:.1f} deg -> {verdict}")
    L.append("")
    if span is not None:
        L.append(f"trajectory span (m)     : X={span[0]:.2f} Y={span[1]:.2f} Z={span[2]:.2f}  ({span_n} poses)")
        lat = sorted(span[:2])
        if lat[0] < 0.3:
            L.append("  -> PARALLAX-STARVED path (one lateral axis ~0). This caps every")
            L.append("     PHOTO pipeline (RealityScan/Gaussian/Polycam) -- but NOT this")
            L.append("     shell, which is pure LiDAR geometry. Good.")
        else:
            L.append("  -> trajectory has lateral parallax on both axes.")
    L.append("")
    L.append("READ ME: if thickness is ~16-30mm and walls are square, the GEOMETRY is")
    L.append("sound and Poisson was the whole problem. If a plane is *** DRIFT *** or the")
    L.append("walls are non-orthogonal, the corruption is upstream in odometry (loop")
    L.append("closure / rotation tracking), and no mesher can fix it -- reprocess the raw")
    L.append("LiDAR+IMU first.")
    L.append("=" * 70)
    return "\n".join(L)


# ------------------------------------------------------------------ shell mesher
def plane_basis(n):
    n = n / (np.linalg.norm(n) + 1e-12)
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = a - n * (a @ n); u /= (np.linalg.norm(u) + 1e-12)
    v = np.cross(n, u)
    return u, v


def occupancy_mesh(Pi, n, p0, grid, min_cell, close_iter):
    """Rasterize a plane's measured extent to a flat quad mesh. Openings (windows/
    doors) fall out as genuine holes because no points measured there."""
    u, v = plane_basis(n)
    d = Pi - p0
    s = d @ u; t = d @ v
    smin, tmin = s.min(), t.min()
    ns = int(math.ceil((s.max() - smin) / grid)) + 1
    nt = int(math.ceil((t.max() - tmin) / grid)) + 1
    if ns < 1 or nt < 1 or ns * nt > 8_000_000:
        return None
    si = np.clip(((s - smin) / grid).astype(int), 0, ns - 1)
    ti = np.clip(((t - tmin) / grid).astype(int), 0, nt - 1)
    occ = np.zeros((ns, nt), np.int32)
    np.add.at(occ, (si, ti), 1)
    occ = occ >= min_cell
    for _ in range(close_iter):                 # tiny close: bridge scan-stripe gaps
        occ = _dilate(occ); occ = _erode(occ)
    # node grid corners -> 3D
    ii = np.arange(ns + 1); jj = np.arange(nt + 1)
    S = smin + ii * grid; T = tmin + jj * grid
    SS, TT = np.meshgrid(S, T, indexing='ij')       # (ns+1, nt+1)
    verts = (p0[None, None, :] + SS[..., None] * u[None, None, :]
             + TT[..., None] * v[None, None, :]).reshape(-1, 3)
    def nid(a, b): return a * (nt + 1) + b
    faces = []
    oc = np.argwhere(occ)
    for a, b in oc:
        v00, v10, v11, v01 = nid(a, b), nid(a + 1, b), nid(a + 1, b + 1), nid(a, b + 1)
        faces.append((v00, v10, v11)); faces.append((v00, v11, v01))
    if not faces:
        return None
    return verts, np.array(faces, np.int64)


def _dilate(m):
    o = m.copy()
    o[:-1] |= m[1:]; o[1:] |= m[:-1]; o[:, :-1] |= m[:, 1:]; o[:, 1:] |= m[:, :-1]
    return o
def _erode(m):
    o = m.copy()
    o[:-1] &= m[1:]; o[1:] &= m[:-1]; o[:, :-1] &= m[:, 1:]; o[:, 1:] &= m[:, :-1]
    return o


KIND_COLOR = {'floor': (150, 130, 110), 'ceiling': (200, 205, 215),
              'wall': (170, 175, 185), 'slanted': (150, 120, 150)}


def build_shell(P, planes, grid, min_cell, close_iter):
    allV, allF, allC = [], [], []
    voff = 0
    for p in planes:
        if p['kind'] == 'slanted':
            continue
        Pi = P[p['idx']]
        out = occupancy_mesh(Pi, p['normal'], p['centroid'], grid, min_cell, close_iter)
        if out is None:
            continue
        V, F = out
        allV.append(V); allF.append(F + voff)
        allC.append(np.tile(KIND_COLOR.get(p['kind'], (180, 180, 180)), (len(F), 1)))
        voff += len(V)
    if not allV:
        return None, None, None
    return np.vstack(allV), np.vstack(allF), np.vstack(allC).astype(np.uint8)


def write_obj(path, V, F):
    with open(path, 'w') as f:
        f.write("# planar_shell\n")
        for x, y, z in V:
            f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
        for a, b, c in F:
            f.write(f"f {a+1} {b+1} {c+1}\n")


def write_ply_points(path, P):
    with open(path, 'w') as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(P)}\n")
        f.write("property float x\nproperty float y\nproperty float z\nend_header\n")
        for x, y, z in P:
            f.write(f"{x:.4f} {y:.4f} {z:.4f}\n")


# ------------------------------------------------------------------ numpy render
def render_shell(V, F, C, out_png, W=900, H=650, views=((35, 22), (125, 22),
                                                        (215, 25), (0, 80))):
    """Orthographic z-buffer, flat Lambert headlight shading. Pure numpy."""
    tiles = []
    for az, el in views:
        tiles.append(_render_one(V, F, C, W, H, az, el))
    top = np.concatenate(tiles[:2], axis=1)
    bot = np.concatenate(tiles[2:], axis=1)
    img = np.concatenate([top, bot], axis=0)
    _save_png(img, out_png)


def _render_one(V, F, C, W, H, az, el):
    ar, er = math.radians(az), math.radians(el)
    Rz = np.array([[math.cos(ar), -math.sin(ar), 0],
                   [math.sin(ar), math.cos(ar), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(er), -math.sin(er)],
                   [0, math.sin(er), math.cos(er)]])
    Rm = Rx @ Rz
    Vr = V @ Rm.T
    xs, ys, zs = Vr[:, 0], Vr[:, 1], Vr[:, 2]
    pad = 0.08
    x0, x1 = xs.min(), xs.max(); y0, y1 = ys.min(), ys.max()
    sx = (W * (1 - 2 * pad)) / max(x1 - x0, 1e-6)
    sy = (H * (1 - 2 * pad)) / max(y1 - y0, 1e-6)
    sc = min(sx, sy)
    px = (W * pad + (xs - x0) * sc)
    py = (H - (H * pad + (ys - y0) * sc))            # flip y
    img = np.zeros((H, W, 3), np.float32)
    img[:] = (22, 24, 28)
    zbuf = np.full((H, W), -1e18, np.float32)
    tri = Vr[F]                                       # (m,3,3)
    e1 = tri[:, 1] - tri[:, 0]; e2 = tri[:, 2] - tri[:, 0]
    fn = np.cross(e1, e2)
    fnn = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12)
    shade = 0.30 + 0.70 * np.abs(fnn[:, 2])          # headlight along view z
    Px, Py, Pz = px[F], py[F], zs[F]
    order = np.argsort(tri[:, :, 2].mean(1))          # far first (painter helps ties)
    for k in order:
        ax, ay = Px[k, 0], Py[k, 0]
        bx, by = Px[k, 1], Py[k, 1]
        cx, cy = Px[k, 2], Py[k, 2]
        minx = max(int(math.floor(min(ax, bx, cx))), 0)
        maxx = min(int(math.ceil(max(ax, bx, cx))), W - 1)
        miny = max(int(math.floor(min(ay, by, cy))), 0)
        maxy = min(int(math.ceil(max(ay, by, cy))), H - 1)
        if minx > maxx or miny > maxy:
            continue
        xx, yy = np.meshgrid(np.arange(minx, maxx + 1), np.arange(miny, maxy + 1))
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-9:
            continue
        l1 = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / det
        l2 = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / det
        l3 = 1 - l1 - l2
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not inside.any():
            continue
        zt = l1 * Pz[k, 0] + l2 * Pz[k, 1] + l3 * Pz[k, 2]
        sub = zbuf[miny:maxy + 1, minx:maxx + 1]
        win = inside & (zt > sub)
        if not win.any():
            continue
        col = (C[k].astype(np.float32) * shade[k])
        seg = img[miny:maxy + 1, minx:maxx + 1]
        seg[win] = col
        sub[win] = zt[win]
    return np.clip(img, 0, 255).astype(np.uint8)


def _save_png(img, path):
    try:
        import cv2
        cv2.imwrite(path, img[:, :, ::-1])            # RGB->BGR
        return
    except Exception:
        pass
    from PIL import Image
    Image.fromarray(img).save(path)


# ------------------------------------------------------------------- self-test
def synth_room():
    """Box room: 5x4x2.6 m, 4 walls + floor + ceiling, a window GAP in +X wall,
    plus two furniture boxes. Returns (N,3)."""
    rng = np.random.default_rng(0)
    pts = []
    def rect(o, du, dv, nu, nv, jitter=0.004):
        a = np.linspace(0, 1, nu); b = np.linspace(0, 1, nv)
        A, B = np.meshgrid(a, b)
        Q = o + A[..., None] * du + B[..., None] * dv
        Q = Q.reshape(-1, 3) + rng.normal(0, jitter, (Q.size // 3, 3))
        return Q
    Lx, Ly, Lz = 5.0, 4.0, 2.6
    pts.append(rect([0, 0, 0], [Lx, 0, 0], [0, Ly, 0], 120, 100))       # floor
    pts.append(rect([0, 0, Lz], [Lx, 0, 0], [0, Ly, 0], 120, 100))      # ceiling
    pts.append(rect([0, 0, 0], [Lx, 0, 0], [0, 0, Lz], 120, 70))        # -Y wall
    pts.append(rect([0, Ly, 0], [Lx, 0, 0], [0, 0, Lz], 120, 70))       # +Y wall
    pts.append(rect([0, 0, 0], [0, Ly, 0], [0, 0, Lz], 100, 70))        # -X wall
    # +X wall WITH a window hole (skip a rectangular band)
    w = rect([Lx, 0, 0], [0, Ly, 0], [0, 0, Lz], 100, 70)
    wl = w - [Lx, 0, 0]
    win = (wl[:, 1] > 1.4) & (wl[:, 1] < 2.6) & (wl[:, 2] > 0.9) & (wl[:, 2] < 2.0)
    pts.append(w[~win])
    # furniture
    pts.append(rect([1.0, 1.0, 0], [0.8, 0, 0], [0, 0, 0.5], 30, 20))
    pts.append(rect([1.0, 1.0, 0.5], [0.8, 0, 0], [0, 1.2, 0], 30, 40))
    return np.vstack(pts)


def run_selftest(outdir):
    os.makedirs(outdir, exist_ok=True)
    P = synth_room()
    print(f"[selftest] synthetic room: {len(P):,} points")
    planes, rest = extract_planes(P, dist=0.02, min_frac=0.02, max_planes=12)
    planes = classify(planes)
    rep = build_report(planes, rest, len(P), np.array([5.0, 4.0, 0.1]), 999)
    print(rep)
    kinds = sorted(p['kind'] for p in planes)
    assert 'floor' in kinds, "floor not found"
    assert 'ceiling' in kinds, "ceiling not found"
    assert kinds.count('wall') >= 4, f"expected >=4 walls, got {kinds.count('wall')}"
    _, maxdev = wall_orthogonality(planes)
    assert maxdev is not None and maxdev < 6, f"walls not square: {maxdev}"
    V, F, C = build_shell(P, planes, grid=0.05, min_cell=1, close_iter=0)
    assert V is not None and len(F) > 100, "shell build failed"
    write_obj(os.path.join(outdir, 'shell.obj'), V, F)
    render_shell(V, F, C, os.path.join(outdir, 'shell_render.png'))
    with open(os.path.join(outdir, 'report.txt'), 'w') as f:
        f.write(rep)
    print(f"[selftest] PASS -- {len(V):,} verts / {len(F):,} tris -> {outdir}/shell.obj + shell_render.png")
    return True


# -------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="RANSAC room-shell reconstructor")
    ap.add_argument('--cloud'); ap.add_argument('--poses', default=None)
    ap.add_argument('--out', required=True)
    ap.add_argument('--dist', type=float, default=0.02, help='plane inlier dist (m); ~L2 sensor limit')
    ap.add_argument('--min-frac', type=float, default=0.02, help='stop when a plane is < this frac of cloud')
    ap.add_argument('--max-planes', type=int, default=14)
    ap.add_argument('--grid', type=float, default=0.05, help='shell occupancy cell (m)')
    ap.add_argument('--min-cell', type=int, default=2, help='min pts to call a cell measured')
    ap.add_argument('--close', type=int, default=0, help='tiny close iters to bridge scan-stripes (0=honest/measured)')
    ap.add_argument('--voxel', type=float, default=0.0, help='pre-downsample (m); 0=off')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    if a.selftest:
        run_selftest(a.out); return
    if not a.cloud:
        sys.exit("need --cloud (or --selftest)")

    print("[load]", a.cloud)
    P = load_cloud(a.cloud)
    print(f"[load] {len(P):,} finite points")
    if a.voxel > 0:
        import open3d as o3d
        P = np.asarray(to_o3d(P).voxel_down_sample(a.voxel).points)
        print(f"[load] voxel {a.voxel} -> {len(P):,} points")

    span, span_n = (None, None)
    if a.poses:
        span, span_n = parallax_readout(a.poses)

    print("[ransac] extracting planes ...")
    planes, rest = extract_planes(P, a.dist, a.min_frac, a.max_planes)
    planes = classify(planes)
    rep = build_report(planes, rest, len(P), span, span_n)
    print(rep)
    with open(os.path.join(a.out, 'report.txt'), 'w') as f:
        f.write(rep)

    print("[shell] rasterizing measured extents ...")
    V, F, C = build_shell(P, planes, a.grid, a.min_cell, a.close)
    if V is None:
        sys.exit("[shell] no planar surfaces meshed -- check --dist / cloud")
    write_obj(os.path.join(a.out, 'shell.obj'), V, F)
    write_ply_points(os.path.join(a.out, 'objects.ply'), P[rest])
    print(f"[shell] {len(V):,} verts / {len(F):,} tris -> shell.obj  ({len(rest):,} object pts -> objects.ply)")

    print("[render] shaded preview ...")
    try:
        render_shell(V, F, C, os.path.join(a.out, 'shell_render.png'))
        print("[render] shell_render.png")
    except Exception as e:
        print("[render] skipped:", e)
    print("[done]", a.out)


if __name__ == '__main__':
    main()
