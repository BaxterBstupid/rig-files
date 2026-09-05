#!/usr/bin/env python3
# hud_overlay_coverage.py — the READABLE HUD: coverage painted on the REAL camera photo.
# Projects LiDAR onto a mantel frame (proven per_shot_texture calib), colors projected points by
# LOCAL density (green=covered, red=thin), draws semi-transparent over the photo. You see the
# MANTEL as the mantel, with coverage on it — no abstract-cloud "where am I" ambiguity.
import sys, os, numpy as np, cv2, re, glob
sys.path.insert(0, os.path.expanduser('~/anchor_test'))
import per_shot_texture as pst

BAG_STAMP='121219'
NPZ=os.path.expanduser('~/anchor_test/posed_121219.npz')
FRAMES=os.path.expanduser('~/anchor_test/frames_121219')
PCD='/mnt/rigdata/fusioncap_121219_scans.pcd'
OUT=os.path.expanduser('~/Desktop/hud_overlay_coverage_121219.png')

# NOTE: needs posed_121219.npz + frames_121219 — produced by running the matcher on 121219 first.
d=np.load(NPZ,allow_pickle=True); pos,R,ok=d['pos'],d['R'],d['ok']
n=len(pos); FI=n//2  # mid-capture frame (all mantel anyway)
while FI<n and not ok[FI]: FI+=1
img=cv2.imread(os.path.join(FRAMES,f"img_{FI:05d}.png"))
H,W=img.shape[:2]

raw=open(PCD,'rb').read(); hdr=raw[:raw.index(b'DATA')+20].decode('ascii','ignore')
N=int(re.search(r'POINTS (\d+)',hdr).group(1)); C=len(re.search(r'FIELDS (.+)',hdr).group(1).split())
st=raw.index(b'\n',raw.index(b'DATA'))+1
xyz=np.frombuffer(raw[st:st+N*C*4],np.float32).reshape(N,C)[:,:3].astype(np.float64)

# density per voxel (coverage proxy)
vox=0.05; lo=xyz.min(0); vi=np.floor((xyz-lo)/vox).astype(np.int64)
key=vi[:,0]*73856093^vi[:,1]*19349663^vi[:,2]*83492791
uk,inv,cnt=np.unique(key,return_inverse=True,return_counts=True)
ptdens=cnt[inv]  # each point's voxel density

# project into the frame
Rwc,twc=pst.compose_world_to_cam(R[FI],pos[FI])
Xc=(Rwc@xyz.T).T+twc
front=Xc[:,2]>0.05
Xc_f=Xc[front]; dens_f=ptdens[front]
px,_=cv2.projectPoints(Xc_f.astype(np.float64),np.zeros(3),np.zeros(3),pst.K,pst.DIST); px=px.reshape(-1,2)
u,v=px[:,0],px[:,1]; onim=(u>=0)&(u<W)&(v>=0)&(v<H)
u,v,dd=u[onim].astype(int),v[onim].astype(int),dens_f[onim]

# color by density, relative (percentile) — green=dense/covered, red=thin
t=np.clip((dd-np.percentile(dd,25))/(np.percentile(dd,90)-np.percentile(dd,25)+1e-9),0,1)
ov=img.copy()
for i in range(len(u)):
    ti=t[i]; col=(int(60*(1-ti)+50*ti),int(40*(1-ti)+200*ti),int(220*(1-ti)+70*ti))  # BGR red->green
    cv2.circle(ov,(u[i],v[i]),2,col,-1)
blend=cv2.addWeighted(img,0.5,ov,0.5,0)
cv2.imwrite(OUT,blend)
print(f"frame {FI}: {onim.sum():,} pts on the mantel photo")
print(f"WROTE {OUT}")
print("READ: green = well-covered on the mantel, red = thin. You see the MANTEL, coverage painted on it.")
