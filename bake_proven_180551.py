#!/usr/bin/env python3
# STEP 2b: PROVEN Poisson bridge on 180551, exported as an ORBITABLE colored .ply.
# Uses per_shot_texture.mesh_cloud (the EXACT Poisson mesher that made pointlio_bridge_realproof.png
# = Image 2, 90.3% crisp). Adds per-vertex texture + PLY export (proven bridge renders 2D; we export mesh).
# HARD downsample toward ~161k (Image-2 size where Poisson worked) to test if segfault is size-specific.
import numpy as np, cv2, time, os, sys
sys.path.insert(0, os.path.expanduser('~/anchor_test'))
import per_shot_texture as pst   # the PROVEN engine: K, DIST, R_L2C, T_L2C, mesh_cloud, compose

NPY    = '/mnt/rigdata/fusioncap_180551_scans.npy'
NPZ    = os.path.expanduser('~/anchor_test/posed_180551.npz')
FRAMES = os.path.expanduser('~/anchor_test/frames_180551')
OUT    = os.path.expanduser('~/Desktop/bake_proven_180551.ply')
TARGET = int(sys.argv[1]) if len(sys.argv)>1 else 161000   # downsample target pts
STRIDE = int(sys.argv[2]) if len(sys.argv)>2 else 150

def quat_to_R(q):
    x,y,z_,w=q; n=x*x+y*y+z_*z_+w*w; s=2.0/n
    return np.array([[1-s*(y*y+z_*z_),s*(x*y-z_*w),s*(x*z_+y*w)],
                     [s*(x*y+z_*w),1-s*(x*x+z_*z_),s*(y*z_-x*w)],
                     [s*(x*z_-y*w),s*(y*z_+x*w),1-s*(x*x+y*y)]])

T0=time.time()
print("=== LOAD + DOWNSAMPLE to ~%d pts ==="%TARGET)
pts=np.load(NPY)[:,:3].astype(np.float64); n0=len(pts)
if n0>TARGET:
    idx=np.random.default_rng(0).choice(n0,TARGET,replace=False); pts=pts[idx]
print(f"  {n0:,} -> {len(pts):,} pts  ({time.time()-T0:.1f}s)")

print("=== PROVEN mesh_cloud (trimmed Poisson d9) — the Image-2 mesher ===")
t=time.time()
mesh=pst.mesh_cloud(pts, trim_quantile=0.05)   # <-- if this segfaults at 161k, crash is cloud-characteristic
V=np.asarray(mesh.vertices); Tr=np.asarray(mesh.triangles)
mesh.compute_vertex_normals(); VN=np.asarray(mesh.vertex_normals)
print(f"  {len(V):,} verts {len(Tr):,} faces  ({time.time()-t:.1f}s)")

print(f"=== TEXTURE — per-vertex facing color, stride {STRIDE} ===")
t=time.time()
z=np.load(NPZ,allow_pickle=True); pos,quat,ok=z['pos'],z['quat'],np.asarray(z['ok'],bool)
K,DIST,W,H=pst.K,pst.DIST,pst.IMG_W,pst.IMG_H; R_L2C,T_L2C=pst.R_L2C,pst.T_L2C
allf=[i for i in range(len(ok)) if ok[i] and os.path.exists(os.path.join(FRAMES,f'img_{i:05d}.png'))]
frames=allf[::STRIDE] if STRIDE>1 else allf
print(f"  {len(allf)} usable -> {len(frames)} frames")
vcolor=np.full((len(V),3),0.5); best=np.full(len(V),-1.0)
for fi in frames:
    R=R_L2C@quat_to_R(quat[fi]).T; tt=T_L2C-R@pos[fi]
    Vc=(R@V.T).T+tt; infront=Vc[:,2]>0.05
    uv=cv2.projectPoints(Vc.astype(np.float64),np.zeros(3),np.zeros(3),K,DIST)[0].reshape(-1,2)
    u,v=uv[:,0],uv[:,1]; inimg=infront&(u>=0)&(u<W)&(v>=0)&(v<H)
    cam=-R.T@tt; view=cam[None,:]-V; view/=(np.linalg.norm(view,axis=1,keepdims=True)+1e-9)
    facing=np.abs((VN*view).sum(1)); score=np.where(inimg,facing,-1.0)
    take=score>best
    if take.any():
        img=cv2.imread(os.path.join(FRAMES,f'img_{fi:05d}.png'))
        ui=np.clip(u[take].astype(int),0,W-1); vi=np.clip(v[take].astype(int),0,H-1)
        vcolor[take]=img[vi,ui][:,::-1]/255.0; best[take]=score[take]; del img
seen=(best>=0).sum()
print(f"  textured {seen:,}/{len(V):,} ({100*seen/len(V):.1f}%)  ({time.time()-t:.1f}s)")

print("=== EXPORT colored PLY ===")
import open3d as o3d
mesh.vertex_colors=o3d.utility.Vector3dVector(vcolor)
o3d.io.write_triangle_mesh(OUT, mesh)
print(f"  wrote {OUT} ({os.path.getsize(OUT)/1e6:.1f}MB)  | total {time.time()-T0:.1f}s")
