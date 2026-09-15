#!/usr/bin/env python3
# CLEANER mesh: fixes shredding via better normals + tuned Poisson, fills gaps (Poisson interpolates)
# Same fusion, same 2200 frames - just better surface reconstruction.
import numpy as np, cv2, time, os, sys, open3d as o3d
import per_shot_texture as pst

PCD='fusioncap_180551_scans.pcd'; NPZ='posed_images.npz'
FRAMES=os.path.join(os.path.expanduser('~'),'Desktop','frames_180551')
OUT='fusion_180551_CLEAN.ply'
DEPTH=int(sys.argv[1]) if len(sys.argv)>1 else 10   # 10 = finer than the old 9
TRIM=float(sys.argv[2]) if len(sys.argv)>2 else 0.02  # 2% trim (less aggressive than 5%)

def quat_to_R(q):
    x,y,z_,w=q; n=x*x+y*y+z_*z_+w*w; s=2.0/n
    return np.array([[1-s*(y*y+z_*z_),s*(x*y-z_*w),s*(x*z_+y*w)],
                     [s*(x*y+z_*w),1-s*(x*x+z_*z_),s*(y*z_-x*w)],
                     [s*(x*z_-y*w),s*(y*z_+x*w),1-s*(x*x+y*y)]])

T0=time.time()
print(f"=== LOAD full cloud ===")
pcd=o3d.io.read_point_cloud(PCD)
print(f"  {len(pcd.points):,} pts")

print(f"=== CLEAN MESH: better normals + Poisson depth {DEPTH}, trim {TRIM} ===")
t=time.time()
pcd,_=pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
# BIGGER normal radius (10cm) for stable normals on uneven walk-cloud density
pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=40))
# CONSISTENT orientation (propagate across tangent planes) - NOT toward-origin (wrong for a walk)
pcd.orient_normals_consistent_tangent_plane(50)
mesh,dens=o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=DEPTH)
dens=np.asarray(dens)
mesh.remove_vertices_by_mask(dens < np.quantile(dens, TRIM))
# clean up: remove tiny disconnected junk fragments (the shredding), keep the big surface
mesh.remove_degenerate_triangles(); mesh.remove_duplicated_vertices()
tri_clusters, cluster_n, _ = mesh.cluster_connected_triangles()
tri_clusters=np.asarray(tri_clusters); cluster_n=np.asarray(cluster_n)
if len(cluster_n)>0:
    big = cluster_n[tri_clusters] > max(200, 0.001*cluster_n.max())  # drop islands <0.1% of biggest
    mesh.remove_triangles_by_mask(~big); mesh.remove_unreferenced_vertices()
mesh.compute_vertex_normals()
V=np.asarray(mesh.vertices); Tr=np.asarray(mesh.triangles); VN=np.asarray(mesh.vertex_normals)
print(f"  {len(V):,} verts {len(Tr):,} faces (after de-shred)  ({time.time()-t:.1f}s)")

print(f"=== TEXTURE with all frames ===")
t=time.time()
z=np.load(NPZ,allow_pickle=True); pos,quat,ok=z['pos'],z['quat'],np.asarray(z['ok'],bool)
K,DIST,W,H=pst.K,pst.DIST,pst.IMG_W,pst.IMG_H; R_L2C,T_L2C=pst.R_L2C,pst.T_L2C
allf=[i for i in range(len(ok)) if ok[i] and os.path.exists(os.path.join(FRAMES,f'img_{i:05d}.png'))]
vcolor=np.full((len(V),3),0.5); best=np.full(len(V),-1.0)
for fi in allf:
    R=R_L2C@quat_to_R(quat[fi]).T; tt=T_L2C-R@pos[fi]
    Vc=(R@V.T).T+tt; infront=Vc[:,2]>0.05
    uv=cv2.projectPoints(Vc.astype(np.float64),np.zeros(3),np.zeros(3),K,DIST)[0].reshape(-1,2)
    u,v=uv[:,0],uv[:,1]; inimg=infront&(u>=0)&(u<W)&(v>=0)&(v<H)
    cam=-R.T@tt; view=cam[None,:]-V; view/=(np.linalg.norm(view,axis=1,keepdims=True)+1e-9)
    facing=np.abs((VN*view).sum(1)); score=np.where(inimg,facing,-1.0); take=score>best
    if take.any():
        img=cv2.imread(os.path.join(FRAMES,f'img_{fi:05d}.png'))
        if img is None: continue
        ui=np.clip(u[take].astype(int),0,W-1); vi=np.clip(v[take].astype(int),0,H-1)
        vcolor[take]=img[vi,ui][:,::-1]/255.0; best[take]=score[take]; del img
seen=(best>=0).sum()
print(f"  textured {seen:,}/{len(V):,} ({100*seen/len(V):.1f}%)  ({time.time()-t:.1f}s)")

# FILL GAPS: untextured verts get color interpolated from nearest textured neighbors
print("=== FILL untextured verts from neighbors ===")
untx=best<0
if untx.any() and (~untx).any():
    from scipy.spatial import cKDTree
    tree=cKDTree(V[~untx]); _,nn=tree.query(V[untx],k=3)
    vcolor[untx]=vcolor[~untx][nn].mean(1)
    print(f"  filled {untx.sum():,} untextured verts from neighbors")

mesh.vertex_colors=o3d.utility.Vector3dVector(vcolor)
o3d.io.write_triangle_mesh(OUT,mesh)
print(f"=== wrote {OUT} ({os.path.getsize(OUT)/1e6:.1f}MB) | total {time.time()-T0:.1f}s ===")
