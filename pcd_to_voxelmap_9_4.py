#!/usr/bin/env python3
# pcd_to_voxelmap.py — voxelize a dense PCD into the [x,y,z,count] .npy that mesh_check.py wants.
# Memory-safe: voxel-downsamples first (dense cloud -> sparse voxel centers), never holds a big grid.
import sys, numpy as np, re
def load_pcd(path):
    raw = open(path,'rb').read()
    hdr = raw[:raw.index(b'DATA')+20].decode('ascii','ignore')
    n = int(re.search(r'POINTS (\d+)',hdr).group(1))
    fields = re.search(r'FIELDS (.+)',hdr).group(1).split()
    c = len(fields)
    binary = 'binary' in hdr
    start = raw.index(b'\n', raw.index(b'DATA'))+1
    if binary:
        pts = np.frombuffer(raw[start:start+n*c*4], np.float32).reshape(n,c)[:,:3].astype(np.float64)
    else:
        pts = np.loadtxt(path, skiprows=hdr.count('\n'))[:,:3]
    return pts
def main():
    pcd, out, voxel = sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv)>3 else 0.05
    pts = load_pcd(pcd)
    print(f"loaded {len(pts):,} pts, extent {(pts.max(0)-pts.min(0)).round(2)}")
    # voxel-downsample: hash to voxel index, count hits per voxel (this IS the coverage count)
    lo = pts.min(0)
    idx = np.floor((pts-lo)/voxel).astype(np.int64)
    key = idx[:,0]*73856093 ^ idx[:,1]*19349663 ^ idx[:,2]*83492791
    uniq, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
    # voxel center = mean of pts in that voxel; count = hits
    centers = np.zeros((len(uniq),3)); np.add.at(centers, inv, pts); centers /= counts[:,None]
    arr = np.hstack([centers, counts[:,None].astype(np.float64)])
    np.save(out, arr)
    print(f"wrote {out}: {len(arr):,} voxels @ {voxel}m (from {len(pts):,} pts)")
if __name__=='__main__': main()
