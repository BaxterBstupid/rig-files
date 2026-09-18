#!/usr/bin/env python3
"""
tau_sweep.py -- find the tau that best aligns photo color to LiDAR geometry.
For each tau value: shift camera stamps, colorize the cloud, measure color-coherence
on locally-flat regions (a wall's color should be uniform; smear = high variance).
The tau minimizing smear = the correct camera-LiDAR offset. Confirms tau_solve independently.

Reuses colorize projection. Needs: cloud, poses(orig), extr, intr, frames, and the
per-frame image timestamps (to apply tau BEFORE matching pose per point).

Simpler design: we already have per-frame posed npz. To apply tau we need the pose
at (frame_time - tau). Since re-matching per tau is heavy, we instead pass PRE-MATCHED
pose files (one per tau, from pointlio_pose_matcher --tau X) and just colorize+score each.

USAGE: python tau_sweep.py --cloud C.ply --posedir . --stems posed_163005,posed_163005_TAU \
        --extr E.yaml --intr I.yaml --images F --label none,tau293
"""
import argparse, numpy as np, cv2, os, glob, open3d as o3d

def load_yaml_mat(p,k):
    fs=cv2.FileStorage(p,cv2.FILE_STORAGE_READ); m=fs.getNode(k).mat(); fs.release(); return np.asarray(m)

def colorize(cloud_P, poses_npz, R_L2C,T_L2C,K,DIST,images,W,H):
    z=np.load(poses_npz,allow_pickle=True); pos,R_all,ok=z['pos'],z['R'],np.asarray(z['ok'],bool)
    N=len(cloud_P); best=np.full(N,np.inf); col=np.zeros((N,3),np.uint8); done=np.zeros(N,bool)
    frames={os.path.basename(f):f for f in glob.glob(os.path.join(images,'*.png'))}
    order=[i for i in range(len(pos)) if ok[i] and ('img_%05d.png'%i) in frames]
    for i in order:
        img=cv2.imread(frames['img_%05d.png'%i]); 
        if img is None: continue
        R_ml=R_all[i]; pos_i=pos[i]
        Pc=(R_L2C@(R_ml.T@(cloud_P-pos_i).T)).T+T_L2C; zc=Pc[:,2]; infront=zc>0.05
        uv=np.full((N,2),-1.0)
        if infront.any():
            uv[infront]=cv2.projectPoints(Pc[infront].reshape(-1,1,3),np.zeros(3),np.zeros(3),K,DIST)[0].reshape(-1,2)
        u,v=uv[:,0],uv[:,1]; inimg=infront&(u>=0)&(u<W)&(v>=0)&(v<H)
        vidx=np.where(inimg)[0]
        Cw=pos_i+R_ml@(-R_L2C.T@T_L2C); dist=np.linalg.norm(cloud_P[vidx]-Cw,axis=1)
        better=dist<best[vidx]; take=vidx[better]
        ui=np.clip(u[take].astype(int),0,W-1); vi=np.clip(v[take].astype(int),0,H-1)
        col[take]=img[vi,ui]; best[take]=dist[better]; done[take]=True
    return col,done

def smear_score(P,col,done,knn=12):
    # on colored points, measure local color variance in small neighborhoods.
    # flat surfaces should be ~uniform; tau-smear raises local color variance.
    m=done; Pm=P[m]; Cm=col[m].astype(np.float32)
    if len(Pm)<1000: return None
    pcd=o3d.geometry.PointCloud(); pcd.points=o3d.utility.Vector3dVector(Pm)
    tree=o3d.geometry.KDTreeFlann(pcd)
    import random
    idx=random.sample(range(len(Pm)), min(4000,len(Pm)))
    vs=[]
    for i in idx:
        _,nn,_=tree.search_knn_vector_3d(Pm[i],knn)
        vs.append(Cm[nn].std(0).mean())
    return float(np.median(vs))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--cloud',required=True); ap.add_argument('--posefiles',required=True,help='comma-sep npz paths')
    ap.add_argument('--labels',required=True); ap.add_argument('--extr',required=True); ap.add_argument('--intr',required=True)
    ap.add_argument('--images',required=True); ap.add_argument('--width',type=int,default=1920); ap.add_argument('--height',type=int,default=1200)
    a=ap.parse_args()
    R_L2C=load_yaml_mat(a.extr,'R_lidar_to_cam'); T_L2C=load_yaml_mat(a.extr,'t_lidar_to_cam').reshape(3)
    K=load_yaml_mat(a.intr,'camera_matrix'); DIST=load_yaml_mat(a.intr,'distortion_coefficients').reshape(-1)
    pc=o3d.t.io.read_point_cloud(a.cloud); P=pc.point['positions'].numpy().astype(np.float64)
    print("cloud:",len(P),"points")
    for pf,lab in zip(a.posefiles.split(','),a.labels.split(',')):
        col,done=colorize(P,pf,R_L2C,T_L2C,K,DIST,a.images,a.width,a.height)
        s=smear_score(P,col,done)
        print("  %-10s colored %d (%.0f%%)  smear-score %.2f  (LOWER=sharper)"%(lab,done.sum(),100*done.mean(),s))
