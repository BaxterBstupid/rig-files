#!/usr/bin/env python3
"""Inspect a Point-LIO scans.pcd: report dimensions + render orthographic views.
Runs on the Jetson (matplotlib + numpy only, no heavy GUI). Downsamples for speed.
Compares directly to the RTAB failure signature (that map was 3.3 x 9.5 x 13.0m,
the 13m-tall being the rotation-collapse tell)."""
import sys, numpy as np
import matplotlib
matplotlib.use('Agg')  # no display needed, writes PNGs
import matplotlib.pyplot as plt

path = sys.argv[1] if len(sys.argv)>1 else \
    "/home/fasterbybaxter/point_lio_ws/src/point_lio_ros2/PCD/scans.pcd"

# --- minimal PCD reader (handles ascii + binary float32 x,y,z[,intensity]) ---
def read_pcd(fn):
    with open(fn,'rb') as f:
        fields=[]; size=[]; typ=[]; count=[]; npts=0; data_fmt=None; header_len=0
        while True:
            line=f.readline(); header_len+=len(line)
            l=line.decode('ascii','ignore').strip()
            if l.startswith('FIELDS'): fields=l.split()[1:]
            elif l.startswith('SIZE'): size=list(map(int,l.split()[1:]))
            elif l.startswith('TYPE'): typ=l.split()[1:]
            elif l.startswith('COUNT'): count=list(map(int,l.split()[1:]))
            elif l.startswith('POINTS'): npts=int(l.split()[1])
            elif l.startswith('DATA'): data_fmt=l.split()[1]; break
        if data_fmt=='ascii':
            arr=np.loadtxt(f, dtype=np.float32)
            xyz=arr[:,:3]
        else:  # binary
            # build dtype
            tmap={'F':'f','U':'u','I':'i'}
            dt=[]
            for nm,s,t,c in zip(fields,size,typ,count):
                dt.append((nm, tmap[t]+str(s)))
            rec=np.dtype(dt)
            buf=f.read(npts*rec.itemsize)
            arr=np.frombuffer(buf, dtype=rec, count=npts)
            xyz=np.stack([arr['x'],arr['y'],arr['z']],axis=1).astype(np.float32)
    # drop NaN/inf
    m=np.isfinite(xyz).all(axis=1)
    return xyz[m]

print("reading", path, "...")
xyz=read_pcd(path)
print("total finite points: %d"%len(xyz))

# downsample for plotting
if len(xyz)>200000:
    idx=np.random.choice(len(xyz),200000,replace=False)
    xs=xyz[idx]
else:
    xs=xyz

# robust extent (1st-99th percentile, ignores stray outliers)
lo=np.percentile(xyz,1,axis=0); hi=np.percentile(xyz,99,axis=0)
ext=hi-lo
full=xyz.max(0)-xyz.min(0)
print("\n=== DIMENSIONS ===")
print("robust extent (1-99%%): X %.2f  Y %.2f  Z %.2f  m"%(ext[0],ext[1],ext[2]))
print("full extent (min-max):  X %.2f  Y %.2f  Z %.2f  m"%(full[0],full[1],full[2]))
print("\n=== VERDICT REFERENCE ===")
print("RTAB failure was: 3.3 x 9.5 x 13.0m (13m TALL = rotation collapse).")
print("A real room: height (usually Z or one axis) ~2.4-3.0m, footprint a few metres.")
zmin=min(ext)
print("smallest axis (should be the ~2.5-3m ceiling height): %.2f m"%zmin)
if zmin < 3.5:
    print(" -> plausible real room height. GOOD SIGN (not collapsed).")
else:
    print(" -> no axis is room-height; possible distortion. INSPECT.")

# render 3 ortho views
fig=plt.figure(figsize=(16,5))
combos=[(0,1,'X','Y','TOP-DOWN (floorplan)'),
        (0,2,'X','Z','FRONT (X-Z, height)'),
        (1,2,'Y','Z','SIDE (Y-Z, height)')]
for i,(a,b,la,lb,t) in enumerate(combos):
    ax=fig.add_subplot(1,3,i+1)
    ax.scatter(xs[:,a],xs[:,b],s=0.3,c=xs[:,2],cmap='viridis',alpha=0.4)
    ax.set_xlabel(la+' (m)'); ax.set_ylabel(lb+' (m)'); ax.set_title(t,fontsize=10)
    ax.set_aspect('equal'); ax.grid(True,alpha=0.2)
plt.tight_layout()
out="/home/fasterbybaxter/point_lio_ws/pointlio_views.png"
plt.savefig(out,dpi=90,bbox_inches='tight')
print("\nsaved images -> %s"%out)
print("copy it to Desktop to view:  cp %s ~/Desktop/"%out)
