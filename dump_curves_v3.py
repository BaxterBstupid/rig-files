#!/usr/bin/env python3
"""
dump_curves_v3.py  -  extract THREE signals for tau: cam board-x, lidar board-x, IMU
====================================================================================
Board now at 0.7m (Zhou density fix -> denser board points per single scan).
Also records IMU angular velocity (density-independent, literature-standard signal).

Dumps to ~/Desktop/tau_curves_v3.csv:
  CAM,stamp,board_x,0            <- checkerboard centroid (px)
  LID,stamp,board_x,depth        <- board-plane centroid (px), via RANSAC
  IMU,stamp,wx,wy,wz             <- angular velocity 3 axes (rad/s); we'll pick the
                                    axis showing the pan

Two independent roads to tau (cam-vs-lidar-position, cam-vs-IMU) that cross-check.

USAGE (Jetson, cold):
  python3 dump_curves_v3.py ~/Desktop/tau_pan_v2
"""
import sys, os
import numpy as np
import cv2

INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
EXTRINSIC_YAML  = os.path.expanduser('~/Desktop/extrinsic_20260816.yaml')
CHECKER = (7, 10)
DOWNSCALE = 2
OUT = os.path.expanduser('~/Desktop/tau_curves_v3.csv')

def load_calib():
    fs = cv2.FileStorage(INTRINSICS_YAML, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat(); D = fs.getNode('distortion_coefficients').mat().flatten(); fs.release()
    fs = cv2.FileStorage(EXTRINSIC_YAML, cv2.FILE_STORAGE_READ)
    R = fs.getNode('R_lidar_to_cam').mat(); t = fs.getNode('t_lidar_to_cam').mat().reshape(3,1); fs.release()
    return K, D, R, t

def fit_plane_ransac(pts, thresh=0.02, iters=300, seed=0):
    rng = np.random.default_rng(seed); n = len(pts)
    if n < 20: return None
    best=None; bc=0
    for _ in range(iters):
        idx = rng.choice(n,3,replace=False); p0,p1,p2 = pts[idx]
        nrm = np.cross(p1-p0,p2-p0); nn=np.linalg.norm(nrm)
        if nn<1e-9: continue
        nrm/=nn; d=np.abs((pts-p0)@nrm); inl=d<thresh; c=inl.sum()
        if c>bc: bc=c; best=inl
    return best

def cam_board_x(img, K, D):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gs = cv2.resize(g,(g.shape[1]//DOWNSCALE,g.shape[0]//DOWNSCALE)) if DOWNSCALE>1 else g
    ok,c = cv2.findChessboardCorners(gs,CHECKER,cv2.CALIB_CB_ADAPTIVE_THRESH|cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok: return None
    return float(np.mean(c.reshape(-1,2)[:,0]))*DOWNSCALE

def lidar_board_x(xyz, K, D, R, t):
    pc = (R@xyz.T+t).T; pc=pc[pc[:,2]>0]
    if len(pc)<40: return None,None
    depth=pc[:,2]
    # board now ~0.7m; gate 0.4-1.2m
    band=pc[(depth>0.4)&(depth<1.2)]
    if len(band)<40: return None,None
    inl=fit_plane_ransac(band)
    if inl is None or inl.sum()<40: return None,None
    board=band[inl]; ext=np.ptp(board,axis=0)
    if max(ext[0],ext[1])>1.2:
        d=board[:,2];med=np.median(d);board=board[np.abs(d-med)<0.08]
        if len(board)<40: return None,None
    ctr=board.mean(0).reshape(3,1); px=(K@ctr).flatten()
    return float(px[0]/px[2]), float(np.median(board[:,2]))

def main():
    if len(sys.argv)<2:
        print("usage: python3 dump_curves_v3.py <bag_dir>"); return
    bag=sys.argv[1]
    K,D,R,t = load_calib()
    print("calib loaded (cx=%.1f)"%K[0,2])

    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import Image, PointCloud2, Imu
    from sensor_msgs_py import point_cloud2
    from cv_bridge import CvBridge
    bridge=CvBridge()

    reader=SequentialReader()
    reader.open(StorageOptions(uri=bag,storage_id='sqlite3'),ConverterOptions('',''))
    rows=[]; ni=nc=nm=0
    while reader.has_next():
        topic,data,ts = reader.read_next()
        if topic=='/image_raw':
            ni+=1
            if ni%100==0: print("  ...%d images"%ni)
            msg=deserialize_message(data,Image)
            img=bridge.imgmsg_to_cv2(msg,desired_encoding='bgr8')
            x=cam_board_x(img,K,D)
            if x is not None:
                st=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
                rows.append(("CAM",st,"%.3f"%x,"0","0"))
        elif topic=='/unilidar/cloud':
            nc+=1
            if nc%50==0: print("  ...%d clouds"%nc)
            msg=deserialize_message(data,PointCloud2)
            pts=np.array([[p[0],p[1],p[2]] for p in
                          point_cloud2.read_points(msg,field_names=('x','y','z'),skip_nans=True)])
            if len(pts)>0:
                x,depth=lidar_board_x(pts,K,D,R,t)
                if x is not None:
                    st=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
                    rows.append(("LID",st,"%.3f"%x,"%.3f"%depth,"0"))
        elif topic=='/unilidar/imu':
            nm+=1
            msg=deserialize_message(data,Imu)
            st=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
            w=msg.angular_velocity
            rows.append(("IMU",st,"%.5f"%w.x,"%.5f"%w.y,"%.5f"%w.z))

    with open(OUT,'w') as f:
        f.write("kind,stamp,a,b,c\n")
        for r in rows: f.write("%s,%.6f,%s,%s,%s\n"%r)
    ncam=sum(1 for r in rows if r[0]=="CAM"); nlid=sum(1 for r in rows if r[0]=="LID"); nimu=sum(1 for r in rows if r[0]=="IMU")
    print("\nwrote %s : %d CAM, %d LID, %d IMU rows"%(OUT,ncam,nlid,nimu))
    print("Send me that file.")

if __name__=='__main__':
    main()
