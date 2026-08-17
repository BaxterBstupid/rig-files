#!/usr/bin/env python3
"""
dump_curves_v2.py  -  robust board-position extraction (RANSAC plane segmentation)
==================================================================================
v1's LiDAR tracker took a crude depth-band centroid -> contaminated by background
and yanked around by the L2's non-uniform scan as the board swept edge-to-edge.
Result: noisy LiDAR position signal that wouldn't cross-correlate with the camera.

v2 fix: SEGMENT THE BOARD PLANE with RANSAC (the same robust approach the
calibration used), keep only plane inliers, track THEIR centroid. Rejects
background + stray points -> clean board position.

Camera tracker unchanged (checkerboard corners = already clean).

Outputs ~/Desktop/tau_curves_v2.csv. Progress-printed, downscaled cam detect.

USAGE (Jetson, cold):
  python3 dump_curves_v2.py ~/Desktop/tau_pan_test
"""
import sys, os
import numpy as np
import cv2

INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
EXTRINSIC_YAML  = os.path.expanduser('~/Desktop/extrinsic_20260816.yaml')
CHECKER = (7, 10)
DOWNSCALE = 2
OUT = os.path.expanduser('~/Desktop/tau_curves_v2.csv')

def load_calib():
    fs = cv2.FileStorage(INTRINSICS_YAML, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat(); D = fs.getNode('distortion_coefficients').mat().flatten(); fs.release()
    fs = cv2.FileStorage(EXTRINSIC_YAML, cv2.FILE_STORAGE_READ)
    R = fs.getNode('R_lidar_to_cam').mat(); t = fs.getNode('t_lidar_to_cam').mat().reshape(3,1); fs.release()
    return K, D, R, t

def fit_plane_ransac(pts, thresh=0.01, iters=300, seed=0):
    """Return inlier mask of the dominant plane in pts. Self-contained RANSAC."""
    rng = np.random.default_rng(seed)
    n = len(pts)
    if n < 20: return None
    best_inl = None; best_cnt = 0
    for _ in range(iters):
        idx = rng.choice(n, 3, replace=False)
        p0, p1, p2 = pts[idx]
        v1, v2 = p1 - p0, p2 - p0
        nrm = np.cross(v1, v2)
        nn = np.linalg.norm(nrm)
        if nn < 1e-9: continue
        nrm = nrm / nn
        d = np.abs((pts - p0) @ nrm)
        inl = d < thresh
        c = inl.sum()
        if c > best_cnt:
            best_cnt = c; best_inl = inl
    return best_inl

def cam_board_x(img, K, D):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gs = cv2.resize(g, (g.shape[1]//DOWNSCALE, g.shape[0]//DOWNSCALE)) if DOWNSCALE>1 else g
    ok, corners = cv2.findChessboardCorners(gs, CHECKER,
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok: return None
    return float(np.mean(corners.reshape(-1,2)[:,0])) * DOWNSCALE

def lidar_board_x(xyz, K, D, R, t):
    pc = (R @ xyz.T + t).T
    infront = pc[:,2] > 0
    pc = pc[infront]
    if len(pc) < 40: return None, None, None
    depth = pc[:,2]
    # coarse gate to the board's depth neighborhood (board ~1.5m; keep 0.8-2.2)
    band = pc[(depth > 0.8) & (depth < 2.2)]
    if len(band) < 40: return None, None, None
    # RANSAC-segment the dominant plane (the board) in that band
    inl = fit_plane_ransac(band, thresh=0.02, iters=300)
    if inl is None or inl.sum() < 40: return None, None, None
    board = band[inl]
    # guard: board plane should be a compact patch, not a huge wall. Reject if its
    # lateral extent is implausibly large (a wall) - board is ~0.8x1.0m.
    ext = np.ptp(board, axis=0)
    if max(ext[0], ext[1]) > 1.6:   # >1.6m extent in image-plane axes = not the board
        # fall back: take the sub-cluster nearest the median depth
        d = board[:,2]; med = np.median(d)
        board = board[np.abs(d-med) < 0.10]
        if len(board) < 40: return None, None, None
    ctr = board.mean(0).reshape(3,1)
    px = (K @ ctr).flatten()
    return float(px[0]/px[2]), float(np.median(board[:,2])), len(board)

def main():
    if len(sys.argv) < 2:
        print("usage: python3 dump_curves_v2.py <bag_dir>"); return
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
    rows = []; ni = nc = 0
    while reader.has_next():
        topic, data, ts = reader.read_next()
        if topic == '/image_raw':
            ni += 1
            if ni % 100 == 0: print("  ...%d images" % ni)
            msg = deserialize_message(data, Image)
            img = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            x = cam_board_x(img, K, D)
            if x is not None:
                st = msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9
                rows.append(("CAM", st, x, 0.0))
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

    with open(OUT,'w') as f:
        f.write("kind,stamp,board_x,extra\n")
        for r in rows: f.write("%s,%.6f,%.3f,%.3f\n" % r)
    ncam=sum(1 for r in rows if r[0]=="CAM"); nlid=sum(1 for r in rows if r[0]=="LID")
    print("\nwrote %s : %d CAM, %d LID rows"%(OUT,ncam,nlid))
    print("Send me that file.")

if __name__ == '__main__':
    main()
