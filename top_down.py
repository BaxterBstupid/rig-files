#!/usr/bin/env python3
"""
top_down.py -- overhead (floor-plan) render of a Point-LIO scans.pcd, to spot
odometry DRIFT / doubled geometry. Single crisp wall lines = clean cloud; parallel
"ghost" lines / doubled corners = drift (a capture problem, not a fusion one).

Deps: numpy + cv2 only (runs in the rigstation env). No ROS, no open3d.
PCD reader is verbatim from fuse_pano.read_pcd_xyzi (binary float32, 8 fields).

Run (Anaconda Prompt, rigstation):
    python top_down.py <scans.pcd> [OUT_DIR]
Writes OUT_DIR/topdown_walls.png (wall-band only -> clearest for doubling)
   and OUT_DIR/topdown_all.png  (all points -> overall footprint).
"""
import sys, os
import numpy as np
import cv2


def read_pcd_xyzi(path):
    with open(path, 'rb') as f:
        while True:
            line = f.readline()
            if not line or line.startswith(b'DATA'):
                break
        raw = np.fromfile(f, dtype=np.float32)
    n = raw.size // 8                      # x y z intensity nx ny nz curvature
    raw = raw[:n * 8].reshape(n, 8)
    return raw[:, :3].astype(np.float64)


def density_topdown(xy, long_px=1500, pad=0.06):
    """Log-density overhead raster: white structure on black. Walls (vertically
    stacked points) accumulate into bright lines; drift shows as parallel lines."""
    x, y = xy[:, 0], xy[:, 1]
    x0, x1 = np.percentile(x, [0.3, 99.7])
    y0, y1 = np.percentile(y, [0.3, 99.7])
    dx, dy = (x1 - x0) * pad, (y1 - y0) * pad   # margin so walls aren't on the edge
    x0 -= dx; x1 += dx; y0 -= dy; y1 += dy
    sx, sy = x1 - x0, y1 - y0
    if sx <= 0 or sy <= 0:
        return None
    if sx >= sy:
        W = long_px; H = max(1, int(round(long_px * sy / sx)))
    else:
        H = long_px; W = max(1, int(round(long_px * sx / sy)))
    ix = ((x - x0) / sx * (W - 1)).astype(np.int64)
    iy = ((y - y0) / sy * (H - 1)).astype(np.int64)
    m = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    acc = np.zeros((H, W), np.float64)
    np.add.at(acc, (iy[m], ix[m]), 1.0)
    g = np.log1p(acc)
    g = g / (g.max() + 1e-9)
    g = np.power(g, 0.5)                    # gamma lift so faint lines read
    g = (g * 255.0).astype(np.uint8)
    g = cv2.dilate(g, np.ones((2, 2), np.uint8))   # thicken 1px wall lines
    g = cv2.flip(g, 0)                     # +y up, so it reads like a floor plan
    ppm = W / sx
    cv2.putText(g, "%.1f x %.1f m   %.0f px/m" % (sx, sy, ppm),
                (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1, cv2.LINE_AA)
    return g


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python top_down.py <scans.pcd> [OUT_DIR]")
    pcd = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(outdir, exist_ok=True)

    P = read_pcd_xyzi(pcd)
    z = P[:, 2]
    print("points: %d   z-range %.2f..%.2f m" % (len(P), z.min(), z.max()))

    fl, ce = np.percentile(z, 2), np.percentile(z, 98)
    hi = min(fl + 2.0, ce)
    band = (z > fl + 0.3) & (z < hi)
    print("wall band: %.2f..%.2f m  (%d pts)" % (fl + 0.3, hi, int(band.sum())))

    walls = density_topdown(P[band][:, :2])
    allv = density_topdown(P[:, :2])
    if walls is not None:
        cv2.imwrite(os.path.join(outdir, "topdown_walls.png"), walls)
        print("wrote", os.path.join(outdir, "topdown_walls.png"))
    if allv is not None:
        cv2.imwrite(os.path.join(outdir, "topdown_all.png"), allv)
        print("wrote", os.path.join(outdir, "topdown_all.png"))


if __name__ == "__main__":
    main()
