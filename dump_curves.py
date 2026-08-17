#!/usr/bin/env python3
"""
dump_curves.py  -  extract the two board-position curves from the bag to a TINY CSV
===================================================================================
Same board-tracking as measure_tau.py, but instead of solving tau, it DUMPS the raw
extracted signals (timestamp, board-x) for camera and lidar to a small text file we
can actually LOOK at, to diagnose why the tau fit failed.

Adds:
  - PROGRESS printing (so we never wonder if it's hung)
  - image DOWNSCALE before checkerboard detect (much faster)
  - dumps to ~/Desktop/tau_curves.csv  (tiny - ~850 rows)

USAGE (Jetson, cold):
  python3 dump_curves.py ~/Desktop/tau_pan_test
Then send me ~/Desktop/tau_curves.csv (it's tiny).
"""
import sys, os
import numpy as np
import cv2

INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
EXTRINSIC_YAML  = os.path.expanduser('~/Desktop/extrinsic_20260816.yaml')
CHECKER = (7, 10)
DOWNSCALE = 2          # detect checkerboard at half-res = ~4x faster
OUT = os.path.expanduser('~/Desktop/tau_curves.csv')

def load_calib():
    fs = cv2.FileStorage(INTRINSICS_YAML, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat(); D = fs.getNode('distortion_coefficients').mat().flatten(); fs.release()
    fs = cv2.FileStorage(EXTRINSIC_YAML, cv2.FILE_STORAGE_READ)
    R = fs.getNode('R_lidar_to_cam').mat(); t = fs.getNode('t_lidar_to_cam').mat().reshape(3,1); fs.release()
    return K, D, R, t

def cam_board_x(img, K, D):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if DOWNSCALE > 1:
        gs = cv2.resize(g, (g.shape[1]//DOWNSCALE, g.shape[0]//DOWNSCALE))
    else:
        gs = g
    ok, corners = cv2.findChessboardCorners(gs, CHECKER,
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        return None, None
    cx = float(np.mean(corners.reshape(-1,2)[:,0])) * DOWNSCALE     # back to full-res px
    # also return spread (corner count sanity / how much of board seen)
    spread = float(np.ptp(corners.reshape(-1,2)[:,0])) * DOWNSCALE
    return cx, spread

def lidar_board_x(xyz, K, D, R, t):
    pc = (R @ xyz.T + t).T
    infront = pc[:,2] > 0
    pc = pc[infront]
    if len(pc) < 30: return None, None, None
    depth = pc[:,2]
    m = (depth > 1.0) & (depth < 2.4)
    band = pc[m]
    if len(band) < 30: return None, None, None
    d = band[:,2]; med = np.median(d)
    core = band[np.abs(d-med) < 0.15]
    if len(core) < 30: return None, None, None
    ctr = core.mean(0).reshape(3,1)
    px = (K @ ctr).flatten()
    return float(px[0]/px[2]), float(med), len(core)   # board-x, board depth, #pts

def main():
    if len(sys.argv) < 2:
        print("usage: python3 dump_curves.py <bag_dir>"); return
    bag = sys.argv[1]
    K, D, R, t = load_calib()
    print("calib loaded (cx=%.1f)" % K[0,2])

    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import Image, PointCloud2
    from sensor_msgs_py import point_cloud2
    from cv_bridge import CvBridge
    bridge = CvBridge()

    reader = SequentialReader()
    reader.open(StorageOptions(uri=bag, storage_id='sqlite3'), ConverterOptions('',''))

    rows = []   # (kind, stamp, x, extra)
    ni = nc = 0
    while reader.has_next():
        topic, data, ts = reader.read_next()
        if topic == '/image_raw':
            ni += 1
            if ni % 50 == 0: print("  ...%d images" % ni)
            msg = deserialize_message(data, Image)
            img = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            x, spread = cam_board_x(img, K, D)
            if x is not None:
                st = msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9
                rows.append(("CAM", st, x, spread))
        elif topic == '/unilidar/cloud':
            nc += 1
            if nc % 30 == 0: print("  ...%d clouds" % nc)
            msg = deserialize_message(data, PointCloud2)
            pts = np.array([[p[0],p[1],p[2]] for p in
                            point_cloud2.read_points(msg, field_names=('x','y','z'), skip_nans=True)])
            if len(pts) > 0:
                x, depth, npts = lidar_board_x(pts, K, D, R, t)
                if x is not None:
                    st = msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9
                    rows.append(("LID", st, x, depth))

    with open(OUT, 'w') as f:
        f.write("kind,stamp,board_x,extra\n")
        for r in rows:
            f.write("%s,%.6f,%.3f,%.3f\n" % r)
    ncam = sum(1 for r in rows if r[0]=="CAM")
    nlid = sum(1 for r in rows if r[0]=="LID")
    print("\nwrote %s : %d CAM rows, %d LID rows" % (OUT, ncam, nlid))
    print("Send me that file (it's tiny).")

if __name__ == '__main__':
    main()
