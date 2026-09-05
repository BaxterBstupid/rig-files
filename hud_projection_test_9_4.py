#!/usr/bin/env python3
# hud_projection_test.py — STAGE 1 of the "did I get it?" HUD.
# Proves the LiDAR->camera projection is HONEST on ONE real 180551 frame,
# by REUSING per_shot_texture's own calibration + compose_world_to_cam + cv2.projectPoints.
# Output: one overlay PNG = the real photo with LiDAR points drawn on it, colored by range.
# HONEST TEST: a point on the doorway must land on the doorway. If it does, the HUD foundation works.
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.expanduser('~/anchor_test'))
import per_shot_texture as pst   # reuse the PROVEN engine: K, DIST, compose_world_to_cam

FRAME_IDX = int(sys.argv[1]) if len(sys.argv)>1 else 1100   # a mid-walk frame by default
NPZ   = os.path.expanduser('~/anchor_test/posed_180551.npz')
FRAMES= os.path.expanduser('~/anchor_test/frames_180551')
PCD   = '/mnt/rigdata/fusioncap_180551_scans.pcd'
OUT   = os.path.expanduser('~/Desktop/hud_overlay_180551.png')

d = np.load(NPZ, allow_pickle=True)
pos, R, ok = d['pos'], d['R'], d['ok']
n = len(pos)
if not (0 <= FRAME_IDX < n): FRAME_IDX = n//2
print(f"frame {FRAME_IDX}/{n}, ok={bool(ok[FRAME_IDX])}, pose pos={pos[FRAME_IDX].round(2)}")

# load the frame image (dumped as img_NNNNN.png)
img_path = os.path.join(FRAMES, f"img_{FRAME_IDX:05d}.png")
if not os.path.exists(img_path):
    # find nearest existing dumped frame
    import glob
    cands = sorted(glob.glob(os.path.join(FRAMES,'img_*.png')))
    print(f"exact frame not dumped; {len(cands)} frames available, using first: {cands[0] if cands else 'NONE'}")
    img_path = cands[len(cands)//2] if cands else None
    FRAME_IDX = int(os.path.basename(img_path).split('_')[1].split('.')[0])
img = cv2.imread(img_path)
print(f"image {img_path}: {img.shape if img is not None else 'FAILED TO LOAD'}")

# load the world cloud, transform into THIS frame's camera coords via the proven engine
xyz = pst.load_cloud(PCD)
print(f"cloud: {len(xyz):,} pts")
Rwc, twc = pst.compose_world_to_cam(R[FRAME_IDX], pos[FRAME_IDX])
Xc = (Rwc @ xyz.T).T + twc          # world -> camera frame
infront = Xc[:,2] > 0.05            # keep points in front of the camera
Xc = Xc[infront]
print(f"points in front of camera: {len(Xc):,}")

# project to pixels using the REAL K/DIST (rvec/tvec zero because Xc is already camera-frame)
rvec = np.zeros(3); tvec = np.zeros(3)
px,_ = cv2.projectPoints(Xc.astype(np.float64), rvec, tvec, pst.K, pst.DIST)
px = px.reshape(-1,2)
H,W = img.shape[:2]
u,v = px[:,0], px[:,1]
onscreen = (u>=0)&(u<W)&(v>=0)&(v<H)
print(f"points landing ON the {W}x{H} image: {onscreen.sum():,}  ({100*onscreen.mean():.1f}% of in-front)")

# color by range (near=warm, far=cool) and draw
rng = np.linalg.norm(Xc[onscreen], axis=1)
t = np.clip((rng - rng.min())/(np.ptp(rng)+1e-6), 0, 1)
overlay = img.copy()
uu,vv = u[onscreen].astype(int), v[onscreen].astype(int)
for i in range(len(uu)):
    c = (int(255*(1-t[i])), int(180), int(255*t[i]))  # BGR: near=blue-ish, far=red-ish
    cv2.circle(overlay, (uu[i],vv[i]), 1, c, -1)
blend = cv2.addWeighted(img, 0.45, overlay, 0.55, 0)
cv2.imwrite(OUT, blend)
print(f"WROTE {OUT}")
print("EYEBALL TEST: do the LiDAR dots sit on the matching real features (doorway on doorway, wall on wall)?")
