#!/usr/bin/env python3
"""make_rgbd.py — emit one RGBD pair per matched frame (the pixel-unified pipeline unit).
Usage:
    python3 make_rgbd.py <scans.pcd> <posed_images.npz> <frames_dir> <out_dir>
For every matched frame i (npz ok mask): compute world->cam (engine composition),
project the cloud with the vetted K+DIST, z-buffer nearest depth per pixel, save
depth_{i:05d}.png as uint16 MILLIMETERS (0 = no measurement; Kinect/Open3D
convention) beside the existing img_{i:05d} RGB. Prints per-run fill statistics.
Constants are the vetted 2026-08 calibration (1920x1200).
"""
import sys, glob, re
from pathlib import Path
import numpy as np, cv2

K = np.array([[848.75887098286523,0,921.00150062572425],
              [0,849.23113758207739,565.96150750753168],[0,0,1]])
DIST = np.array([-0.014979,-0.013547,-0.001997,0.000698,0.003842])
R_L2C = np.array([[0.079231956747140869,0.99456000522703925,-0.067621690549788172],
                  [-0.98716139340257103,0.087718305377614436,0.13348364048516903],
                  [0.13868915028045117,0.056177352237994721,0.9887413335600036]])
T_L2C = np.array([0.018336757321533628,-0.053568141733719279,-0.15964461058920226])
W,H = 1920,1200

def quat_to_R(q):
    x,y,z,w=q; s=2.0/(x*x+y*y+z*z+w*w)
    return np.array([[1-s*(y*y+z*z),s*(x*y-z*w),s*(x*z+y*w)],
                     [s*(x*y+z*w),1-s*(x*x+z*z),s*(y*z-x*w)],
                     [s*(x*z-y*w),s*(y*z+x*w),1-s*(x*x+y*y)]])

def main():
    if len(sys.argv)!=5: print(__doc__); sys.exit(1)
    pcd_path,npz_path,frames_dir,out = sys.argv[1:5]
    outp=Path(out); outp.mkdir(exist_ok=True)
    import open3d as o3d
    pts=np.asarray(o3d.io.read_point_cloud(pcd_path).points)
    z=np.load(npz_path,allow_pickle=True)
    ok=np.asarray(z['ok'],bool); pos=np.asarray(z['pos']); quat=np.asarray(z['quat'])
    Rall=np.asarray(z['R']) if 'R' in z else None   # matcher's own rotations = ground truth
    rows=np.where(ok)[0]
    import glob as _g
    missing=[int(i) for i in rows if not (_g.glob(f"{frames_dir}/img_{i:05d}.jpg")+_g.glob(f"{frames_dir}/img_{i:05d}.png"))]
    if missing: print(f"WARN: {len(missing)} matched rows have NO frame file in {frames_dir}: {missing[:8]}...")
    print(f"cloud: {len(pts):,} pts | matched frames: {len(rows)} | frame files verified: {len(rows)-len(missing)}")
    fills=[]
    for n,i in enumerate(rows):
        R_wl = Rall[i] if Rall is not None else quat_to_R(quat[i])
        R=R_L2C@R_wl.T; t=T_L2C-R@pos[i]
        pc=(R@pts.T).T+t
        m=pc[:,2]>0.05; pcv=pc[m]
        uv=cv2.projectPoints(pcv,np.zeros(3),np.zeros(3),K,DIST)[0].reshape(-1,2)
        inb=(uv[:,0]>=0)&(uv[:,0]<W)&(uv[:,1]>=0)&(uv[:,1]<H)
        u=uv[inb,0].astype(np.int64); v=uv[inb,1].astype(np.int64); d=pcv[inb,2]
        # vectorized z-buffer: nearest depth wins per pixel
        D=np.full(H*W,np.inf,np.float32)
        np.minimum.at(D, v*W+u, d.astype(np.float32))
        D=D.reshape(H,W)
        Dmm=np.where(np.isfinite(D),np.clip(D*1000.0,0,65535),0).astype(np.uint16)
        cv2.imwrite(str(outp/f"depth_{i:05d}.png"), Dmm)
        fills.append((Dmm>0).mean())
        if n%40==0: print(f"  [{n+1}/{len(rows)}] frame {i}: fill {100*fills[-1]:.2f}%")
    fills=np.array(fills)
    print(f"DONE: {len(rows)} depth maps -> {out}")
    print(f"fill: mean {100*fills.mean():.2f}% | min {100*fills.min():.2f}% | max {100*fills.max():.2f}%")

def rgbd_to_cloud(rgb_path, depth_path):
    """THE CORRECT BACK-PROJECTION (consumer side). Depth pixels live in the
    DISTORTED image grid (aligned with RGB); back-projecting MUST undistort:
    naive pinhole inverse errs up to ~195mm at frame corners on this lens
    (measured); undistortPoints reduces it to ~0.004mm. Returns (Nx3 xyz in
    CAMERA frame, Nx3 rgb 0-1)."""
    im=cv2.imread(rgb_path)[:,:,::-1]
    Dmm=cv2.imread(depth_path,cv2.IMREAD_UNCHANGED)
    v,u=np.nonzero(Dmm); zc=Dmm[v,u].astype(np.float64)/1000.0
    und=cv2.undistortPoints(np.c_[u,v].astype(np.float64).reshape(-1,1,2),K,DIST).reshape(-1,2)
    xyz=np.c_[und[:,0]*zc, und[:,1]*zc, zc]
    return xyz, im[v,u]/255.0

if __name__=="__main__": main()
