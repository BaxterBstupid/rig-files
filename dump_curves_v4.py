#!/usr/bin/env python3
"""
dump_curves_v4.py  -  PER-POINT-TIME corrected board timing
============================================================
KEY FIX: the L2 cloud has a per-point 'time' field (0..0.083s within each scan).
Previous versions used only the HEADER stamp for the whole cloud, ignoring WHERE
in the 83ms sweep the board points actually fell -> a motion-dependent timing error
of up to +-83ms that corrupted tau (unstable halves, broad plateau).

v4: for the board points in each scan, compute their TRUE observation time =
header_stamp + mean(per-point time of the board points). This gives the board's
actual instant, not a smeared header stamp.

Also records header stamp separately so we can test scan-start vs scan-end convention.

Outputs ~/Desktop/tau_curves_v4.csv:
  CAM,stamp,board_x,0
  LID,true_time,board_x,header_stamp     <- true_time uses per-point time
  IMU,stamp,wx,wy,wz

USAGE (Jetson, cold):
  python3 dump_curves_v4.py ~/Desktop/tau_pan_v3
"""
import sys, os
import numpy as np
import cv2

INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
EXTRINSIC_YAML  = os.path.expanduser('~/Desktop/extrinsic_20260816.yaml')
CHECKER = (7, 10)
DOWNSCALE = 2
OUT = os.path.expanduser('~/Desktop/tau_curves_v4.csv')

def load_calib():
    fs = cv2.FileStorage(INTRINSICS_YAML, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat(); D = fs.getNode('distortion_coefficients').mat().flatten(); fs.release()
    fs = cv2.FileStorage(EXTRINSIC_YAML, cv2.FILE_STORAGE_READ)
    R = fs.getNode('R_lidar_to_cam').mat(); t = fs.getNode('t_lidar_to_cam').mat().reshape(3,1); fs.release()
    return K, D, R, t

def fit_plane_ransac(pts, thresh=0.02, iters=300, seed=0):
    rng=np.random.default_rng(seed); n=len(pts)
    if n<20: return None
    best=None; bc=0
    for _ in range(iters):
        idx=rng.choice(n,3,replace=False); p0,p1,p2=pts[idx]
        nrm=np.cross(p1-p0,p2-p0); nn=np.linalg.norm(nrm)
        if nn<1e-9: continue
        nrm/=nn; d=np.abs((pts-p0)@nrm); inl=d<thresh; c=inl.sum()
        if c>bc: bc=c; best=inl
    return best

def cam_board_x(img, K, D):
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    gs=cv2.resize(g,(g.shape[1]//DOWNSCALE,g.shape[0]//DOWNSCALE)) if DOWNSCALE>1 else g
    ok,c=cv2.findChessboardCorners(gs,CHECKER,cv2.CALIB_CB_ADAPTIVE_THRESH|cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok: return None
    return float(np.mean(c.reshape(-1,2)[:,0]))*DOWNSCALE

def lidar_board(xyz, ptime, K, D, R, t):
    """Return (board_x_px, mean_pointtime_of_board_points)."""
    pc_cam=(R@xyz.T+t).T
    infront=pc_cam[:,2]>0
    xyz=xyz[infront]; pc_cam=pc_cam[infront]; ptime=ptime[infront]
    if len(pc_cam)<40: return None,None
    depth=pc_cam[:,2]
    band=(depth>0.4)&(depth<1.2)
    xyzb=pc_cam[band]; ptb=ptime[band]
    if len(xyzb)<40: return None,None
    inl=fit_plane_ransac(xyzb)
    if inl is None or inl.sum()<40: return None,None
    board=xyzb[inl]; board_pt=ptb[inl]
    ext=np.ptp(board,axis=0)
    if max(ext[0],ext[1])>1.2:
        d=board[:,2]; med=np.median(d); m=np.abs(d-med)<0.08
        board=board[m]; board_pt=board_pt[m]
        if len(board)<40: return None,None
    ctr=board.mean(0).reshape(3,1); px=(K@ctr).flatten()
    return float(px[0]/px[2]), float(board_pt.mean())   # board-x, and its mean per-point time

def main():
    if len(sys.argv)<2:
        print("usage: python3 dump_curves_v4.py <bag_dir>"); return
    bag=sys.argv[1]
    K,D,R,t=load_calib()
    print("calib loaded (cx=%.1f)"%K[0,2])

    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import Image, PointCloud2, Imu
    from sensor_msgs_py import point_cloud2
    from cv_bridge import CvBridge
    bridge=CvBridge()

    reader=SequentialReader()
    reader.open(StorageOptions(uri=bag,storage_id='sqlite3'),ConverterOptions('',''))
    rows=[]; ni=nc=0
    while reader.has_next():
        topic,data,ts=reader.read_next()
        if topic=='/image_raw':
            ni+=1
            if ni%100==0: print("  ...%d images"%ni)
            msg=deserialize_message(data,Image)
            img=bridge.imgmsg_to_cv2(msg,desired_encoding='bgr8')
            x=cam_board_x(img,K,D)
            if x is not None:
                st=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
                rows.append(("CAM","%.6f"%st,"%.3f"%x,"0"))
        elif topic=='/unilidar/cloud':
            nc+=1
            if nc%50==0: print("  ...%d clouds"%nc)
            msg=deserialize_message(data,PointCloud2)
            hdr=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
            pts=list(point_cloud2.read_points(msg,field_names=('x','y','z','time'),skip_nans=True))
            if len(pts)==0: continue
            arr=np.array([[p[0],p[1],p[2],p[3]] for p in pts])
            xyz=arr[:,:3]; ptime=arr[:,3]
            bx,meanpt=lidar_board(xyz,ptime,K,D,R,t)
            if bx is not None:
                true_time=hdr+meanpt   # header + per-point offset = true board obs time
                rows.append(("LID","%.6f"%true_time,"%.3f"%bx,"%.6f"%hdr))
        elif topic=='/unilidar/imu':
            msg=deserialize_message(data,Imu)
            st=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
            w=msg.angular_velocity
            rows.append(("IMU","%.6f"%st,"%.5f"%w.x,"%.5f"%w.y))  # wx,wy enough

    with open(OUT,'w') as f:
        f.write("kind,stamp,a,b\n")
        for r in rows:
            if r[0]=="IMU": f.write("%s,%s,%s,%s\n"%r)
            else: f.write("%s,%s,%s,%s\n"%r)
    ncam=sum(1 for r in rows if r[0]=="CAM"); nlid=sum(1 for r in rows if r[0]=="LID"); nimu=sum(1 for r in rows if r[0]=="IMU")
    print("\nwrote %s : %d CAM, %d LID, %d IMU"%(OUT,ncam,nlid,nimu))
    print("Send me that file.")

if __name__=='__main__':
    main()
