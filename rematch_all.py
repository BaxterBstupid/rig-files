#!/usr/bin/env python3
"""
rematch_all.py  — RUN ON SHADOW (in fusion env, shadow_bundle folder)
Reads odom_and_stamps.npz (full odometry + all 2200 image timestamps),
interpolates a pose for EVERY frame (SLERP rotation + linear translation),
writes posed_images_ALL.npz in the SAME format the bake expects (pos, quat, R, ok, image_t).
This recovers all 2200 frames (vs the old 210).
"""
import numpy as np
from scipy.spatial.transform import Rotation as Rot, Slerp

D = np.load('odom_and_stamps.npz')
ot, opos, oquat, it = D['odom_t'], D['odom_pos'], D['odom_quat'], D['img_t']
print(f"odom: {len(ot)} poses, span {ot.max()-ot.min():.1f}s")
print(f"images: {len(it)}")

# sort odom by time (safety) and dedupe identical timestamps (Slerp needs strictly increasing)
order = np.argsort(ot)
ot, opos, oquat = ot[order], opos[order], oquat[order]
keep = np.concatenate([[True], np.diff(ot) > 1e-9])
ot, opos, oquat = ot[keep], opos[keep], oquat[keep]
print(f"odom after dedupe: {len(ot)}")

# build interpolators
slerp = Slerp(ot, Rot.from_quat(oquat))   # quat is [x,y,z,w] - scipy convention
# clamp image times into the odom window (they're all inside per the extractor, but be safe)
t_lo, t_hi = ot.min(), ot.max()
ok = (it >= t_lo) & (it <= t_hi)
itc = np.clip(it, t_lo, t_hi)

# interpolate
R_all = slerp(itc).as_matrix()                       # (N,3,3)
quat_all = Rot.from_matrix(R_all).as_quat()          # (N,4) [x,y,z,w]
pos_all = np.column_stack([np.interp(itc, ot, opos[:,k]) for k in range(3)])  # (N,3)

print(f"interpolated {len(it)} frames; ok(in-window): {int(ok.sum())}/{len(it)}")

# save in the SAME KEYS the bake reads: pos, quat, R, ok, image_t
np.savez_compressed('posed_images_ALL.npz',
    image_t=it, pos=pos_all, quat=quat_all, R=R_all, ok=ok,
    convention=np.array('lidar_in_world R_wl,t_wl; same as posed_images.npz'))
import os
print(f"wrote posed_images_ALL.npz ({os.path.getsize('posed_images_ALL.npz')/1e6:.1f}MB) with {len(it)} frames")
