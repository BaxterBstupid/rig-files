#!/usr/bin/env python3
# hud_accum_test.py — accumulation-coverage PROXY test on 112949.
# Bins the accumulated cloud by voxel, colors each voxel by POINT DENSITY (proxy for dwell-time),
# writes a MeshLab-viewable .ply (green=dense/dwelt, red=thin/rushed).
# GROUND TRUTH: dwelt ~30s on the MANTEL (should be GREEN), rushed 270deg sweep (should be RED).
# HONEST: density is distance-biased; prints raw density stats so we judge dwell vs proximity.
import sys, os, numpy as np, re

PCD = sys.argv[1] if len(sys.argv)>1 else '/mnt/rigdata/fusioncap_112949_scans.pcd'
OUT = os.path.expanduser('~/Desktop/hud_accum_112949.ply')
VOX = 0.05

raw=open(PCD,'rb').read()
hdr=raw[:raw.index(b'DATA')+20].decode('ascii','ignore')
n=int(re.search(r'POINTS (\d+)',hdr).group(1)); c=len(re.search(r'FIELDS (.+)',hdr).group(1).split())
st=raw.index(b'\n',raw.index(b'DATA'))+1
pts=np.frombuffer(raw[st:st+n*c*4],np.float32).reshape(n,c)[:,:3].astype(np.float64)
print(f"loaded {len(pts):,} pts, extent {(pts.max(0)-pts.min(0)).round(2)}")

# voxelize + COUNT points per voxel (density = observation proxy)
lo=pts.min(0)
idx=np.floor((pts-lo)/VOX).astype(np.int64)
key=idx[:,0]*73856093 ^ idx[:,1]*19349663 ^ idx[:,2]*83492791
uniq,inv,counts=np.unique(key,return_inverse=True,return_counts=True)
centers=np.zeros((len(uniq),3)); np.add.at(centers,inv,pts); centers/=counts[:,None]
print(f"{len(uniq):,} voxels; density per voxel: min {counts.min()} max {counts.max()} median {int(np.median(counts))}")
print(f"  density percentiles 25/50/75/90/99: {[int(np.percentile(counts,p)) for p in (25,50,75,90,99)]}")

# color by density on a red->green ramp, using percentile scaling (relative, per the eye-is-arbiter principle)
t = np.clip((counts - np.percentile(counts,25)) / (np.percentile(counts,90)-np.percentile(counts,25)+1e-9), 0, 1)
def ramp(t):
    R=np.array([220,40,40]); Y=np.array([240,190,40]); G=np.array([50,200,70])
    out=np.where(t[:,None]<0.5, R+(Y-R)*(t[:,None]/0.5), Y+(G-Y)*((t[:,None]-0.5)/0.5))
    return out.astype(np.uint8)
cols=ramp(t)

# write ply (MeshLab-viewable points with color)
with open(OUT,'w') as f:
    f.write("ply\nformat ascii 1.0\n")
    f.write(f"element vertex {len(centers)}\n")
    f.write("property float x\nproperty float y\nproperty float z\n")
    f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    for p,col in zip(centers,cols):
        f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {col[0]} {col[1]} {col[2]}\n")
print(f"WROTE {OUT}")
print("EYEBALL TEST in MeshLab: is the MANTEL region GREEN (dense/dwelt) and the swept walls RED (thin)?")
print("(density is a PROXY for dwell; if mantel is clearly greener than the sweep, the concept holds.)")
