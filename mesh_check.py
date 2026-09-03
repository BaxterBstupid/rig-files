#!/usr/bin/env python3
"""MESH CHECK v2 - instrument mesh via MARCHING CUBES on the voxel occupancy grid.
No Open3D (no aarch64 wheel for the Jetson). Deps: numpy, scipy, scikit-image - all
with cp310 aarch64 wheels (pin numpy<2 on the Jetson to protect ROS's cv_bridge).

Honesty by construction: the surface is exactly the occupied/empty boundary of what
was scanned. Holes cannot be ballooned over - an unscanned patch has no occupied
voxels, so it gets no surface. Blocky at voxel scale, which is correct for an
instrument: it shows what you HAVE, not a beautified guess.

In:  .npy (N,4 float32 x,y,z,hitcount - the server's map snapshot)
Out: <prefix>.ply + <prefix>.meshbin + <prefix>.json
     meshbin: b'RGM1', u32 nv, u32 nf, f32 verts nv*3, f32 colors nv*3, u32 faces nf*3
Colours: RED = thin coverage (walk here again) -> yellow -> GREEN = well-seen."""
import sys, os, time, json, argparse
import numpy as np
from skimage.measure import marching_cubes
from scipy.ndimage import maximum_filter

def log(msg, t0=None):
    print(f"[mesh_check] {msg}" + (f" ({time.time()-t0:.1f}s)" if t0 else ""), flush=True)

def coverage_color(counts):
    t = np.log2(1.0 + counts.astype(np.float64))
    hi = np.quantile(t, 0.95) if len(t) else 1.0
    t = np.clip(t / max(hi, 1e-6), 0, 1)
    red = np.array([1.00,0.20,0.15]); yellow = np.array([1.00,0.85,0.20]); green = np.array([0.20,0.80,0.35])
    c = np.empty((len(t),3))
    lo = t < 0.5; f = (t[lo]/0.5)[:,None];  c[lo]  = red*(1-f)+yellow*f
    f = ((t[~lo]-0.5)/0.5)[:,None];         c[~lo] = yellow*(1-f)+green*f
    return c

def write_ply(path, V, C, F):
    """minimal binary-little-endian PLY, vertex xyz float + rgb uchar, face lists."""
    with open(path, "wb") as f:
        rgb = np.clip(C*255, 0, 255).astype(np.uint8)
        f.write(b"ply\nformat binary_little_endian 1.0\n")
        f.write(f"element vertex {len(V)}\n".encode())
        f.write(b"property float x\nproperty float y\nproperty float z\n")
        f.write(b"property uchar red\nproperty uchar green\nproperty uchar blue\n")
        f.write(f"element face {len(F)}\n".encode())
        f.write(b"property list uchar int vertex_indices\nend_header\n")
        vrec = np.zeros(len(V), dtype=[("xyz","<f4",3),("rgb","u1",3)])
        vrec["xyz"] = V.astype(np.float32); vrec["rgb"] = rgb
        f.write(vrec.tobytes())
        frec = np.zeros(len(F), dtype=[("n","u1"),("idx","<i4",3)])
        frec["n"] = 3; frec["idx"] = F.astype(np.int32)
        f.write(frec.tobytes())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("prefix")
    ap.add_argument("--voxel", type=float, default=0.05, help="must match the map voxel")
    ap.add_argument("--max-dim", type=int, default=900, help="auto-coarsen above this grid size")
    ap.add_argument("--depth", type=int, default=0, help="ignored (v1 compat)")
    a = ap.parse_args()
    T0 = time.time()

    t = time.time()
    arr = np.load(a.input)
    pts, counts = arr[:,:3].astype(np.float64), np.maximum(arr[:,3], 1)
    log(f"loaded {len(pts):,} voxel pts", t)

    # occupancy + counts grids; auto-coarsen so huge captures stay in RAM
    t = time.time()
    voxel = a.voxel
    while True:
        lo = pts.min(0) - 2*voxel
        dims = np.ceil((pts.max(0) + 2*voxel - lo) / voxel).astype(int) + 1
        if dims.max() <= a.max_dim: break
        voxel *= 2.0
    idx = np.floor((pts - lo) / voxel).astype(int)
    occ = np.zeros(dims, bool); cnt = np.zeros(dims, np.float32)
    occ[idx[:,0], idx[:,1], idx[:,2]] = True
    np.maximum.at(cnt, (idx[:,0], idx[:,1], idx[:,2]), counts.astype(np.float32))
    log(f"grid {dims[0]}x{dims[1]}x{dims[2]} @ {voxel:.3f} m ({occ.sum():,} occupied)", t)

    t = time.time()
    V, F, _, _ = marching_cubes(occ.astype(np.float32), level=0.5, spacing=(voxel,)*3)
    V += lo   # back to world metres
    log(f"marching cubes: {len(V):,} v {len(F):,} f", t)

    # colour each vertex by the hit count of its neighbourhood's best-seen voxel
    t = time.time()
    cnt_d = maximum_filter(cnt, size=2)
    vi = np.clip(np.floor((V - lo)/voxel).astype(int), 0, dims-1)
    vc = cnt_d[vi[:,0], vi[:,1], vi[:,2]]
    vc = np.maximum(vc, 1)
    C = coverage_color(vc)
    log("coverage colours", t)

    t = time.time()
    write_ply(a.prefix + ".ply", V, C, F)
    v32 = V.astype(np.float32); c32 = C.astype(np.float32); f32 = F.astype(np.uint32)
    with open(a.prefix + ".meshbin", "wb") as fh:
        fh.write(b"RGM1"); fh.write(np.uint32(len(v32)).tobytes()); fh.write(np.uint32(len(f32)).tobytes())
        fh.write(v32.tobytes()); fh.write(c32.tobytes()); fh.write(f32.tobytes())
    meta = {"verts": int(len(v32)), "faces": int(len(f32)),
            "voxel": round(voxel,4), "seconds": round(time.time()-T0,1), "engine": "marching_cubes"}
    open(a.prefix + ".json","w").write(json.dumps(meta))
    log(f"wrote {a.prefix}.ply/.meshbin/.json {meta}", t)
    log("TOTAL", T0)

if __name__ == "__main__":
    main()
