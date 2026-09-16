#!/usr/bin/env python3
"""
bake_shadow_good.py -- RUN ON SHADOW (fusion env, shadow_bundle). ALL PROCESSING ON SHADOW.
GOOD poses (posed_180551_GOOD.npz, 27.6deg pitch) + FIXED clean-normal mesher (de-shred, NOT the
shredding orient-toward-[0,0,0]). Per-vertex facing color = NO xatlas = no segfault.
Outputs colored .ply to LOOK AT + self-reports coverage %.
  python bake_shadow_good.py            # full, all frames
  python bake_shadow_good.py 800000 4   # target pts, frame stride (faster first look)
"""
import numpy as np, cv2, time, os, sys
sys.path.insert(0,'.')
import per_shot_texture as pst
import open3d as o3d

PCD    = 'fusioncap_180551_scans.pcd'
NPZ    = 'posed_180551_GOOD.npz'
FRAMES = os.path.join(os.path.expanduser('~'),'Desktop','frames_180551')
OUT    = 'bake_180551_GOOD.ply'
TARGET = int(sys.argv[1]) if len(sys.argv)>1 else 800000
STRIDE = int(sys.argv[2]) if len(sys.argv)>2 else 1

def quat_to_R(q):
    x,y,z_,w=q; n=x*x+y*y+z_*z_+w*w; s=2.0/n
    return np.array([[1-s*(y*y+z_*z_),s*(x*y-z_*w),s*(x*z_+y*w)],
                     [s*(x*y+z_*w),1-s*(x*x+z_*z_),s*(y*z_-x*w)],
                     [s*(x*z_-y*w),s*(y*z_+x*w),1-s*(x*x+y*y)]])

def mesh_cloud_clean(xyz):
    """FIXED mesher (Master 50 bake_clean method): consistent-tangent normals (NOT toward [0,0,0]),
    Poisson depth 10, de-shred (drop tiny clusters), harder density trim, NO neighbor-fill (no blobs)."""
    pcd=o3d.geometry.PointCloud(); pcd.points=o3d.utility.Vector3dVector(xyz)
    pcd,_=pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.10, max_nn=40))
    pcd.orient_normals_consistent_tangent_plane(50)          # <-- THE FIX (correct for a walk)
    mesh,dens=o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=10)
    dens=np.asarray(dens)
    mesh.remove_vertices_by_mask(dens < np.quantile(dens, 0.06))   # harder density trim
    mesh.remove_degenerate_triangles(); mesh.remove_duplicated_vertices(); mesh.remove_unreferenced_vertices()
    # de-shred: keep only the big connected clusters
    ti,nt,_=mesh.cluster_connected_triangles()
    ti=np.asarray(ti); nt=np.asarray(nt)
    if len(nt)>0:
        keep_big=nt >= max(200, int(0.001*nt.max()))
        drop=np.isin(ti, np.where(~keep_big)[0])
        mesh.remove_triangles_by_mask(drop); mesh.remove_unreferenced_vertices()
    mesh.compute_vertex_normals()
    return mesh

T0=time.time()
print("=== LOAD CLOUD + DOWNSAMPLE to ~%d pts ==="%TARGET)
pc=o3d.io.read_point_cloud(PCD)
pts=np.asarray(pc.points).astype(np.float64); n0=len(pts)
if n0>TARGET:
    idx=np.random.default_rng(0).choice(n0,TARGET,replace=False); pts=pts[idx]
print(f"  {n0:,} -> {len(pts):,} pts  ({time.time()-T0:.1f}s)")

print("=== CLEAN mesher (consistent-tangent normals + de-shred) ===")
t=time.time()
mesh=mesh_cloud_clean(pts)
V=np.asarray(mesh.vertices); Tr=np.asarray(mesh.triangles)
VN=np.asarray(mesh.vertex_normals)
print(f"  {len(V):,} verts {len(Tr):,} faces  ({time.time()-t:.1f}s)")

z=np.load(NPZ,allow_pickle=True); pos,quat,ok=z['pos'],z['quat'],np.asarray(z['ok'],bool)
from scipy.spatial.transform import Rotation as Rot
pitch=np.ptp(Rot.from_quat(quat).as_euler('xyz',degrees=True)[:,1])
print(f"  POSES {NPZ}: pitch span {pitch:.1f}deg -> {'GOOD' if pitch>10 else 'BAD-ABORT'}")
assert pitch>10, "poses degenerate"

print(f"=== TEXTURE — per-vertex facing color, stride {STRIDE} ===")
t=time.time()
K,DIST,W,H=pst.K,pst.DIST,pst.IMG_W,pst.IMG_H; R_L2C,T_L2C=pst.R_L2C,pst.T_L2C
allf=[i for i in range(len(ok)) if ok[i] and os.path.exists(os.path.join(FRAMES,f'img_{i:05d}.png'))]
frames=allf[::STRIDE] if STRIDE>1 else allf
print(f"  {len(allf)} usable -> {len(frames)} frames")
vcolor=np.full((len(V),3),0.5); best=np.full(len(V),-1.0)
for k,fi in enumerate(frames):
    R=R_L2C@quat_to_R(quat[fi]).T; tt=T_L2C-R@pos[fi]
    Vc=(R@V.T).T+tt; infront=Vc[:,2]>0.05
    uv=cv2.projectPoints(Vc.astype(np.float64),np.zeros(3),np.zeros(3),K,DIST)[0].reshape(-1,2)
    u,v=uv[:,0],uv[:,1]; inimg=infront&(u>=0)&(u<W)&(v>=0)&(v<H)
    cam=-R.T@tt; view=cam[None,:]-V; view/=(np.linalg.norm(view,axis=1,keepdims=True)+1e-9)
    facing=np.abs((VN*view).sum(1)); score=np.where(inimg,facing,-1.0)
    take=score>best
    if take.any():
        img=cv2.imread(os.path.join(FRAMES,f'img_{fi:05d}.png'))
        if img is None: continue
        ui=np.clip(u[take].astype(int),0,W-1); vi=np.clip(v[take].astype(int),0,H-1)
        vcolor[take]=img[vi,ui][:,::-1]/255.0; best[take]=score[take]; del img
    if (k+1)%300==0: print(f"    {k+1}/{len(frames)} frames")
seen=(best>=0).sum()
print(f"  *** TEXTURED {seen:,}/{len(V):,} = {100*seen/len(V):.1f}% *** ({time.time()-t:.1f}s)")

print("=== EXPORT colored PLY ===")
mesh.vertex_colors=o3d.utility.Vector3dVector(vcolor)
o3d.io.write_triangle_mesh(OUT, mesh)
print(f"  wrote {OUT} ({os.path.getsize(OUT)/1e6:.1f}MB)  | total {time.time()-T0:.1f}s")
print("  Open bake_180551_GOOD.ply and LOOK. Clean surface + ~80% color = good poses + fixed normals working.")
