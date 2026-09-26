#!/usr/bin/env python3
"""
make_ds_pcd.py  --  voxel-downsample a Point-LIO scans.pcd so it fits a chat upload.
Keeps all 8 fields (x y z intensity nx ny nz curvature) so fuse_pano.py reads it
unchanged. Pure numpy, no open3d. This is a TRANSFER helper only — on a real station
(Tailscale from the Jetson) the full cloud is used directly and this step is skipped.

    python3 make_ds_pcd.py <in.pcd> <out.pcd> [voxel_m=0.04]
"""
import sys, numpy as np

IN  = sys.argv[1]
OUT = sys.argv[2]
VOX = float(sys.argv[3]) if len(sys.argv) > 3 else 0.04

# read binary PCD (8 float32 fields)
with open(IN, 'rb') as f:
    hdr = b''
    while True:
        line = f.readline(); hdr += line
        if line.startswith(b'DATA'):
            break
    raw = np.fromfile(f, dtype=np.float32)
n = raw.size // 8
pts = raw[:n * 8].reshape(n, 8)
print("read %d points" % n)

# voxel downsample: keep first point per occupied voxel
key = np.floor(pts[:, :3] / VOX).astype(np.int64)
# pack 3 int64 voxel coords into one hashable key
k = (key[:, 0] * 73856093) ^ (key[:, 1] * 19349663) ^ (key[:, 2] * 83492791)
_, idx = np.unique(k, return_index=True)
ds = pts[np.sort(idx)]
m = len(ds)
print("kept %d points (voxel %.3f m)" % (m, VOX))

header = ("# .PCD v0.7\nVERSION 0.7\n"
          "FIELDS x y z intensity normal_x normal_y normal_z curvature\n"
          "SIZE 4 4 4 4 4 4 4 4\nTYPE F F F F F F F F\nCOUNT 1 1 1 1 1 1 1 1\n"
          "WIDTH %d\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS %d\nDATA binary\n" % (m, m))
with open(OUT, 'wb') as f:
    f.write(header.encode()); ds.astype(np.float32).tofile(f)
print("wrote", OUT)
