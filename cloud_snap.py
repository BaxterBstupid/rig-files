#!/usr/bin/env python3
"""
cloud_snap.py  v1 (2026-10-09) -- flatten the PLANAR surfaces of a Point-LIO cloud before RealityScan imports it.

WHY: the eye FAIL of 2026-10-09 (Master 20.13.81 XII) traced both halves -- rippled geometry AND smeared
texture -- to the cloud's surface noise. planar_shell measured the walls/floor/ceiling of 130955 at ~11 mm
"thickness" inside a +/-20 mm band (i.e. the band is saturated: the noise is AT LEAST +/-2 cm), square to
3 deg. The poses are sound; the surfaces are fuzzy. RealityScan meshes the fuzz faithfully and the photos
then cannot land on it. This tool projects every point that belongs to a fitted plane ONTO that plane
(zero thickness, colours kept, point order kept) and leaves everything else -- furniture, frames, lamps,
curtains -- exactly as measured. It also MEASURES the wall thickness properly (a wide band, percentiles),
so the "thick wall" question is answered with numbers, not a saturated std.

    python cloud_snap.py --cloud C:\\rig\\rs\\rsbundle_130955_v3\\cloud_color.ply --out C:\\rig\\rs\\snap_130955
    python cloud_snap.py --selftest --out selftest_snap

    --dist 0.02       RANSAC inlier distance (m) = points this close to a plane are snapped          [planar_shell default]
    --band 0.08       measurement band (m): the thickness report looks this far either side of each plane
    --snap-band D     snap everything within D of a plane instead of --dist (use when the report shows the
                      2-8 cm shell is noise, not objects; default = --dist)
    --min-frac 0.02   stop when a plane holds < this fraction of the cloud        --max-planes 14
    --sor K S         statistical outlier removal on the NON-planar remainder (K neighbours, S std); default off
    --voxel V         pre-downsample for plane FINDING only (m); the output cloud keeps every point. default 0.02
                      (5.3 M points: RANSAC on a 2 cm voxel copy takes ~1 min instead of ~10)

OUTPUT (into --out): cloud_snapped.ply (binary little-endian, float xyz + uchar rgb -- the exact format
rs_bundle writes and RealityScan's LiDAR Scan import reads), report.txt, planes.json.
Then: rs_bundle (or copy the bundle and replace cloud_color.ply) -> rs_merge.py align / lidar --merge-georef
/ mesh --texture-from photos on a fresh tag -> the eye.

DEPS: numpy, open3d (segment_plane). Shadow env: fusion.
"""
import sys, os, json, argparse, time
import numpy as np

UP = np.array([0.0, 0.0, 1.0])

# ------------------------------------------------------------------------------------------------- PLY io
PLY_DT = np.dtype([('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('r', 'u1'), ('g', 'u1'), ('b', 'u1')])

def read_ply(path):
    """xyz (float64, N x 3), rgb (uint8, N x 3). Fast path for the rs_bundle layout; open3d for anything else."""
    with open(path, 'rb') as f:
        hdr = b""
        while not hdr.endswith(b"end_header\n"):
            line = f.readline()
            if not line: raise ValueError("not a PLY: " + path)
            hdr += line
        text = hdr.decode("ascii", "replace")
        props = [l.split()[2] for l in text.splitlines() if l.startswith("property")]
        n = int([l for l in text.splitlines() if l.startswith("element vertex")][0].split()[2])
        if "binary_little_endian" in text and props == ['x', 'y', 'z', 'red', 'green', 'blue'] and \
           all(("property float " + k) in text for k in "xyz") and "property uchar red" in text:
            arr = np.fromfile(f, dtype=PLY_DT, count=n)
            P = np.stack([arr['x'], arr['y'], arr['z']], 1).astype(np.float64)
            rgb = np.stack([arr['r'], arr['g'], arr['b']], 1)
            return P, rgb
    import open3d as o3d
    pc = o3d.io.read_point_cloud(path)
    P = np.asarray(pc.points, dtype=np.float64)
    rgb = (np.asarray(pc.colors) * 255 + 0.5).astype(np.uint8) if pc.has_colors() else np.full((len(P), 3), 128, np.uint8)
    return P, rgb

def write_ply(path, P, rgb):
    n = len(P)
    hdr = ("ply\nformat binary_little_endian 1.0\nelement vertex %d\n"
           "property float x\nproperty float y\nproperty float z\n"
           "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % n).encode()
    arr = np.empty(n, PLY_DT)
    arr['x'], arr['y'], arr['z'] = P[:, 0], P[:, 1], P[:, 2]
    arr['r'], arr['g'], arr['b'] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    with open(path, 'wb') as f:
        f.write(hdr); arr.tofile(f)

# ---------------------------------------------------------------------------------------------- planes
def fit_plane_lsq(Pi):
    """least-squares plane through points: unit normal n, offset d with n.p + d = 0"""
    c = Pi.mean(0)
    _, _, vt = np.linalg.svd(Pi - c, full_matrices=False)
    n = vt[-1]
    return n, float(-(n @ c)), c

def merge_parallel(planes, merge_dist):
    """a plane parallel to a bigger one and within merge_dist of it is a second surface of the SAME wall
    (pose jitter / double pass): drop it, so its points are measured and reported against the main plane."""
    planes = sorted(planes, key=lambda p: -p['n_vox']); kept = []; merged = []
    for p in planes:
        dup = next((q for q in kept if abs(float(p['normal'] @ q['normal'])) > 0.995 and abs(float(q['normal'] @ p['centroid'] + q['d'])) <= merge_dist), None)
        if dup is None: kept.append(p)
        else: merged.append((p, dup, float(q_off) if (q_off := (dup['normal'] @ p['centroid'] + dup['d'])) is not None else 0.0))
    return kept, merged

def find_planes(P, dist, min_frac, max_planes, voxel, merge_dist=0.06):
    """iterative RANSAC (open3d) on a voxel copy, each plane refined by least squares on its inliers.
    Returns list of dict(normal, d, centroid, kind, n_vox)."""
    import open3d as o3d
    o3d.utility.random.seed(0)
    pc = o3d.geometry.PointCloud(); pc.points = o3d.utility.Vector3dVector(np.ascontiguousarray(P))
    if voxel > 0: pc = pc.voxel_down_sample(voxel)
    V = np.asarray(pc.points); n_total = len(V)
    rest_idx = np.arange(n_total); planes = []
    min_pts = max(int(min_frac * n_total), 200)
    for _ in range(max_planes):
        if len(rest_idx) < min_pts: break
        sub = o3d.geometry.PointCloud(); sub.points = o3d.utility.Vector3dVector(np.ascontiguousarray(V[rest_idx]))
        model, inl = sub.segment_plane(distance_threshold=dist, ransac_n=3, num_iterations=1000)
        if len(inl) < min_pts: break
        inl = np.asarray(inl, int); gidx = rest_idx[inl]
        n, d, c = fit_plane_lsq(V[gidx])
        planes.append(dict(normal=n, d=d, centroid=c, n_vox=int(len(gidx))))
        keep = np.ones(len(rest_idx), bool); keep[inl] = False; rest_idx = rest_idx[keep]
    planes, merged = merge_parallel(planes, merge_dist)
    classify(planes)
    return planes, n_total, merged

def classify(planes):
    for pl in planes:
        va = abs(float(pl['normal'] @ UP))
        pl['kind'] = ('floor' if pl['centroid'] @ UP < 0 else 'ceiling') if va > 0.85 else ('wall' if va < 0.35 else 'slanted')
        pl['vert_align'] = va
    horiz = sorted([p for p in planes if p['kind'] in ('floor', 'ceiling')], key=lambda p: p['centroid'] @ UP)
    if len(horiz) >= 2:
        for p in horiz: p['kind'] = 'ceiling'
        horiz[0]['kind'] = 'floor'
    return planes

def wall_azimuths(planes):
    az = []
    for p in planes:
        if p['kind'] == 'wall':
            a = np.degrees(np.arctan2(p['normal'][1], p['normal'][0])) % 180.0
            az.append(a)
    if len(az) < 2: return az, 0.0
    dev = max(min(abs(((a - b) % 180) - k) for k in (0, 90, 180)) for a in az for b in az)
    return az, float(dev)

# ------------------------------------------------------------------------------------------ snap + report
def snap(P, rgb, planes, dist, band, snap_band):
    """assign each point to the nearest plane within snap_band, project it; measure the band first."""
    N = len(P)
    S = np.stack([(P @ pl['normal'] + pl['d']).astype(np.float32) for pl in planes], 1) if planes else np.zeros((N, 0), np.float32)
    A = np.abs(S); nearest = A.argmin(1) if planes else np.full(N, -1)
    best_d = np.full(N, np.inf); best_k = np.full(N, -1, int)
    report = []
    for k, pl in enumerate(planes):
        s = S[:, k].astype(np.float64)                        # signed distance
        a = A[:, k]
        inband = (a <= band) & (nearest == k)                 # this plane is the point's nearest: corners of adjacent walls stay out
        if inband.any():
            ab = a[inband]
            q = np.percentile(ab, [50, 90, 99])
            frac_core = float((ab <= dist).mean()); frac_shell = float(((ab > dist) & (ab <= 2 * dist)).mean()); frac_far = float((ab > 2 * dist).mean())
            # two-sided: a double wall shows as a second mode on one side
            sb = s[inband]; pos, neg = sb[sb > dist], sb[sb < -dist]
            second = max(len(pos), len(neg)) / max(1, len(sb))
        else:
            q = [np.nan] * 3; frac_core = frac_shell = frac_far = second = float('nan')
        report.append(dict(kind=pl['kind'], n_band=int(inband.sum()), p50_mm=float(q[0] * 1000), p90_mm=float(q[1] * 1000), p99_mm=float(q[2] * 1000),
                           frac_within_dist=frac_core, frac_dist_to_2dist=frac_shell, frac_beyond_2dist=frac_far, one_sided_shell=float(second)))
        closer = (a < best_d) & (a <= snap_band)
        best_d[closer] = a[closer]; best_k[closer] = k
    moved = best_k >= 0
    Q = P.copy()
    for k, pl in enumerate(planes):
        m = best_k == k
        if m.any():
            s = Q[m] @ pl['normal'] + pl['d']
            Q[m] -= s[:, None] * pl['normal'][None, :]
        report[k]['n_snapped'] = int(m.sum())
    return Q, moved, report

def thickness_after(Q, planes, dist, band):
    """std of signed distance over the points whose nearest plane this is, within the band, AFTER snapping:
    the snapped core contributes 0; what remains is the unsnapped shell (objects, second surfaces)"""
    out = []
    if not planes: return out
    S = np.stack([(Q @ pl['normal'] + pl['d']).astype(np.float32) for pl in planes], 1); A = np.abs(S); nearest = A.argmin(1)
    for k in range(len(planes)):
        m = (A[:, k] <= dist) & (nearest == k)
        out.append(float(np.std(S[m, k]) * 1000) if m.any() else float('nan'))
    return out

def sor_remainder(Q, rgb, moved, k, std):
    import open3d as o3d
    idx = np.where(~moved)[0]
    if len(idx) == 0: return np.ones(len(Q), bool), 0
    pc = o3d.geometry.PointCloud(); pc.points = o3d.utility.Vector3dVector(np.ascontiguousarray(Q[idx]))
    _, keep_local = pc.remove_statistical_outlier(nb_neighbors=k, std_ratio=std)
    keep = np.ones(len(Q), bool); drop = np.ones(len(idx), bool); drop[np.asarray(keep_local, int)] = False
    keep[idx[drop]] = False
    return keep, int(drop.sum())

def run(P, rgb, out, dist, band, snap_band, min_frac, max_planes, voxel, sor, tag=""):
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    planes, n_vox, merged = find_planes(P, dist, min_frac, max_planes, voxel)
    lines = ["CLOUD SNAP %s-- %d points, %d planes (RANSAC on %d voxel points, dist %.3f m, band %.3f m, snap band %.3f m)" % (tag, len(P), len(planes), n_vox, dist, band, snap_band)]
    for p, q, off in merged:
        lines.append("   merged a parallel plane (%d voxel pts) %.1f mm from a bigger %s plane -> treated as a second surface of it" % (p['n_vox'], off * 1000, q['kind'] if 'kind' in q else '?'))
    Q, moved, rep = snap(P, rgb, planes, dist, band, snap_band)
    after = thickness_after(Q, planes, dist, band)
    lines.append(" #   kind     in-band   p50   p90   p99 mm  <=dist  dist..2d  >2d  one-side  snapped   after_std_mm")
    for k, (pl, r) in enumerate(zip(planes, rep)):
        lines.append("%2d %8s %9d %5.1f %5.1f %5.1f    %4.0f%%   %4.0f%%   %4.0f%%   %4.0f%%  %9d   %6.2f" % (
            k, r['kind'], r['n_band'], r['p50_mm'], r['p90_mm'], r['p99_mm'], 100 * r['frac_within_dist'], 100 * r['frac_dist_to_2dist'],
            100 * r['frac_beyond_2dist'], 100 * r['one_sided_shell'], r['n_snapped'], after[k]))
    az, dev = wall_azimuths(planes)
    lines.append("walls: azimuths %s deg, max deviation from square %.1f deg -> %s" % (", ".join("%.1f" % a for a in az), dev, "square" if dev <= 5 else "NOT square (solve problem, not noise)"))
    lines.append("snapped %d of %d points (%.1f%%) onto %d planes; %d left as measured" % (moved.sum(), len(P), 100 * moved.mean() if len(P) else 0, len(planes), (~moved).sum()))
    keep = np.ones(len(Q), bool); dropped = 0
    if sor:
        keep, dropped = sor_remainder(Q, rgb, moved, int(sor[0]), float(sor[1]))
        lines.append("statistical outlier removal on the remainder (k=%d, std=%.1f): dropped %d points" % (int(sor[0]), float(sor[1]), dropped))
    lines.append("READ: p90 <= ~15 mm with <=dist >= 80%% = sensor noise, snapping is the whole fix. A one-sided shell >= 20%% at dist..2d on a WALL = a second")
    lines.append("      surface (pose jitter / double pass): re-run with --snap-band %.3f, or go back to the solve if it is >= 4 cm. Objects never move." % (2 * dist))
    lines.append("%.1f s" % (time.time() - t0))
    text = "\n".join(lines); print(text)
    open(os.path.join(out, "report.txt"), "w").write(text + "\n")
    json.dump([dict(kind=p['kind'], normal=p['normal'].tolist(), d=p['d'], centroid=p['centroid'].tolist(), n_vox=p['n_vox']) for p in planes], open(os.path.join(out, "planes.json"), "w"), indent=1)
    write_ply(os.path.join(out, "cloud_snapped.ply"), Q[keep], rgb[keep])
    print("-> %s" % os.path.join(out, "cloud_snapped.ply"))
    return planes, rep, after, moved, keep

# ------------------------------------------------------------------------------------------------ selftest
def synth_room(seed=0, n_wall=60000, sigma=0.006, ghost=True):
    rs = np.random.RandomState(seed)
    W, D, H = 5.0, 4.0, 2.6
    parts = []
    def sheet(n, fn):
        u, v = rs.rand(n), rs.rand(n); parts.append(fn(u, v))
    sheet(n_wall, lambda u, v: np.stack([u * W, np.zeros(n_wall), v * H], 1))            # wall y=0
    sheet(n_wall, lambda u, v: np.stack([u * W, np.full(n_wall, D), v * H], 1))          # wall y=D
    sheet(n_wall, lambda u, v: np.stack([np.zeros(n_wall), u * D, v * H], 1))            # wall x=0
    sheet(n_wall, lambda u, v: np.stack([np.full(n_wall, W), u * D, v * H], 1))          # wall x=W
    sheet(n_wall, lambda u, v: np.stack([u * W, v * D, np.zeros(n_wall)], 1))            # floor
    sheet(n_wall, lambda u, v: np.stack([u * W, v * D, np.full(n_wall, H)], 1))          # ceiling
    P = np.concatenate(parts); kinds = np.repeat(np.arange(6), n_wall)
    P += rs.randn(*P.shape) * sigma
    # a box object (mantel-like) proud of wall y=0 by 0.30 m -- must NOT be flattened
    nb = 8000; box = np.stack([1.0 + rs.rand(nb) * 1.5, rs.rand(nb) * 0.30, 0.9 + rs.rand(nb) * 0.4], 1); box[:, 1] = np.where(rs.rand(nb) < 0.5, 0.30, box[:, 1])
    P = np.concatenate([P, box]); kinds = np.concatenate([kinds, np.full(nb, 9)])
    if ghost:   # a second surface 3 cm inside wall x=W (pose-jitter double wall), 20 % of that wall's density
        ng = n_wall // 5; g = np.stack([np.full(ng, W - 0.03), rs.rand(ng) * D, rs.rand(ng) * H], 1) + rs.randn(ng, 3) * sigma
        P = np.concatenate([P, g]); kinds = np.concatenate([kinds, np.full(ng, 8)])
    rgb = (rs.rand(len(P), 3) * 255).astype(np.uint8)
    # centre the room so floor is z<0 side like the real cloud (classify uses centroid sign)
    P = P - np.array([W / 2, D / 2, H / 2])
    return P, rgb, kinds

def selftest(out):
    ok = True
    def check(c, msg):
        nonlocal ok; ok &= bool(c); print("  [%s] %s" % ("ok" if c else "FAIL", msg))
    P, rgb, kinds = synth_room()
    src = os.path.join(out, "synth.ply"); os.makedirs(out, exist_ok=True); write_ply(src, P, rgb)
    P2, rgb2 = read_ply(src)
    check(np.allclose(P, P2, atol=1e-6) and np.array_equal(rgb, rgb2), "PLY round trip (binary LE, float xyz, uchar rgb)")
    planes, rep, after, moved, keep = run(P2, rgb2, out, dist=0.02, band=0.08, snap_band=0.02, min_frac=0.02, max_planes=14, voxel=0.0, sor=None, tag="selftest ")
    kinds_found = sorted(p['kind'] for p in planes)
    check(kinds_found.count('wall') == 4 and 'floor' in kinds_found and 'ceiling' in kinds_found, "6 room planes found (4 walls, floor, ceiling): %s" % kinds_found)
    check(all(a < 0.5 for a in after), "after snapping, std within dist < 0.5 mm on every plane: %s" % ["%.2f" % a for a in after])
    box = kinds == 9
    check(moved[box].mean() < 0.3, "the proud object stayed put (only its wall-touching face may snap): %.0f%% moved" % (100 * moved[box].mean()))
    Q, _ = read_ply(os.path.join(out, "cloud_snapped.ply"))
    check(len(Q) == len(P) and np.abs(Q[box] - P[box])[~moved[box]].max() < 1e-6, "untouched points are byte-identical in the output")
    ghost = kinds == 8
    wallW = [r for p, r in zip(planes, rep) if p['kind'] == 'wall' and abs(p['centroid'][0] - 2.5) < 0.2]
    check(wallW and wallW[0]['one_sided_shell'] >= 0.10, "the 3 cm ghost wall shows up as a one-sided shell on wall x=W: %s" % (["%.0f%%" % (100 * w['one_sided_shell']) for w in wallW]))
    check(moved[ghost].mean() < 0.15, "ghost points beyond dist are NOT snapped by default (only its noise tail inside dist moves): %.0f%% moved" % (100 * moved[ghost].mean()))
    planes2, rep2, after2, moved2, _ = run(P2, rgb2, os.path.join(out, "wide"), dist=0.02, band=0.08, snap_band=0.04, min_frac=0.02, max_planes=14, voxel=0.0, sor=None, tag="selftest wide ")
    check(moved2[ghost].mean() > 0.9, "--snap-band 0.04 folds the ghost onto the wall: %.0f%% moved" % (100 * moved2[ghost].mean()))
    _, _, _, moved3, keep3 = run(P2, rgb2, os.path.join(out, "sor"), dist=0.02, band=0.08, snap_band=0.02, min_frac=0.02, max_planes=14, voxel=0.0, sor=(20, 2.0), tag="selftest sor ")
    check(keep3.sum() < len(P2) and keep3[moved3].all(), "SOR drops some remainder points and never touches snapped ones")
    print("SELFTEST", "PASS" if ok else "FAIL"); return 0 if ok else 1

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cloud"); ap.add_argument("--out", required=True)
    ap.add_argument("--dist", type=float, default=0.02); ap.add_argument("--band", type=float, default=0.08); ap.add_argument("--snap-band", type=float, default=None)
    ap.add_argument("--min-frac", type=float, default=0.02); ap.add_argument("--max-planes", type=int, default=14); ap.add_argument("--voxel", type=float, default=0.02)
    ap.add_argument("--sor", nargs=2, type=float, default=None, metavar=("K", "STD")); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: sys.exit(selftest(a.out))
    if not a.cloud: ap.error("--cloud required")
    print("[load] %s" % a.cloud); P, rgb = read_ply(a.cloud); fin = np.isfinite(P).all(1); P, rgb = P[fin], rgb[fin]
    print("[load] %d finite points" % len(P))
    run(P, rgb, a.out, a.dist, a.band, a.snap_band if a.snap_band is not None else a.dist, a.min_frac, a.max_planes, a.voxel, a.sor)

if __name__ == "__main__":
    main()
