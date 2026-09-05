#!/usr/bin/env python3
# hud_coverage.py — STAGE 2: coverage JUDGMENT (not raw presence).
# Bins the projected LiDAR points into an image grid; colors each cell by hit-density:
#   green = well covered, amber = thin, red = none/near-none. Semi-transparent over the photo.
# HONEST CAVEATS (printed): (1) 2D density is distance-biased — far surfaces look thinner than
#   they were covered. (2) an empty cell = "missed" OR "nothing there" (open door/window) —
#   this version can't distinguish; that's the next refinement.
import sys, os, numpy as np, cv2, re
sys.path.insert(0, os.path.expanduser('~/anchor_test'))
import per_shot_texture as pst

FRAME_IDX = int(sys.argv[1]) if len(sys.argv)>1 else 1100
NPZ='/home/fasterbybaxter/anchor_test/posed_180551.npz'
FRAMES='/home/fasterbybaxter/anchor_test/frames_180551'
PCD='/mnt/rigdata/fusioncap_180551_scans.pcd'
OUT='/home/fasterbybaxter/Desktop/hud_coverage_180551.png'
GX, GY = 32, 20                    # grid cells
DENSE, THIN = 8, 1                 # hits/cell: >=DENSE green, >=THIN amber, else red

d=np.load(NPZ,allow_pickle=True); pos,R,ok=d['pos'],d['R'],d['ok']
img=cv2.imread(os.path.join(FRAMES,f"img_{FRAME_IDX:05d}.png"))
H,W=img.shape[:2]
raw=open(PCD,'rb').read(); hdr=raw[:raw.index(b'DATA')+20].decode('ascii','ignore')
n=int(re.search(r'POINTS (\d+)',hdr).group(1)); c=len(re.search(r'FIELDS (.+)',hdr).group(1).split())
st=raw.index(b'\n',raw.index(b'DATA'))+1
xyz=np.frombuffer(raw[st:st+n*c*4],np.float32).reshape(n,c)[:,:3].astype(np.float64)

Rwc,twc=pst.compose_world_to_cam(R[FRAME_IDX],pos[FRAME_IDX])
Xc=(Rwc@xyz.T).T+twc; Xc=Xc[Xc[:,2]>0.05]
px,_=cv2.projectPoints(Xc.astype(np.float64),np.zeros(3),np.zeros(3),pst.K,pst.DIST)
px=px.reshape(-1,2); u,v=px[:,0],px[:,1]
on=(u>=0)&(u<W)&(v>=0)&(v<H); u,v=u[on],v[on]

# bin into grid, count hits per cell
gx=(u/W*GX).astype(int).clip(0,GX-1); gy=(v/H*GY).astype(int).clip(0,GY-1)
counts=np.zeros((GY,GX),int)
np.add.at(counts,(gy,gx),1)

# build coverage tint overlay
tint=np.zeros_like(img)
cw,ch=W//GX,H//GY
green=np.array([60,190,60]);amber=np.array([40,190,240]);red=np.array([40,40,220])  # BGR
n_green=n_amber=n_red=0
for j in range(GY):
    for i in range(GX):
        cnt=counts[j,i]
        if cnt>=DENSE: col=green; n_green+=1
        elif cnt>=THIN: col=amber; n_amber+=1
        else: col=red; n_red+=1
        cv2.rectangle(tint,(i*cw,j*ch),((i+1)*cw,(j+1)*ch),col.tolist(),-1)
blend=cv2.addWeighted(img,0.6,tint,0.4,0)
# grid lines for legibility
for i in range(GX+1): cv2.line(blend,(i*cw,0),(i*cw,H),(0,0,0),1)
for j in range(GY+1): cv2.line(blend,(0,j*ch),(W,j*ch),(0,0,0),1)
cv2.imwrite(OUT,blend)
tot=GX*GY
print(f"frame {FRAME_IDX}: {on.sum():,} pts on image, grid {GX}x{GY}={tot} cells")
print(f"  GREEN (well covered, >={DENSE}): {n_green} cells ({100*n_green/tot:.0f}%)")
print(f"  AMBER (thin, {THIN}-{DENSE-1}):   {n_amber} cells ({100*n_amber/tot:.0f}%)")
print(f"  RED   (none/near-none, <{THIN}):  {n_red} cells ({100*n_red/tot:.0f}%)")
print(f"WROTE {OUT}")
print("CAVEATS: 2D density is distance-biased (far=artificially thinner); RED = missed OR empty-space (can't yet distinguish).")
