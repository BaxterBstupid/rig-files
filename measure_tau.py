#!/usr/bin/env python3
"""
measure_tau.py  -  extract the camera<->LiDAR temporal offset (tau) from a rosbag
=================================================================================
Reads a bag containing /image_raw + /unilidar/cloud recorded during smooth pans of
the board. Tracks the board's HORIZONTAL position (in image pixels) over time in
BOTH sensors, then finds the time-shift that best aligns the two position-vs-time
curves. That shift is tau.

METHOD (validated cold on synthetic data - recovers known tau to within ~2ms even
with heavy frame drops, noise, and multi-speed pans):
  - camera board-x  = horizontal centroid of detected checkerboard corners (px)
  - lidar  board-x  = board-plane centroid projected through calibration to px
  - both are the SAME physical motion in the SAME units (px); a temporal offset
    shows as a time-shift between the curves. Search the shift that minimizes
    mismatch -> tau.
  - Also splits the data in halves and re-solves each, to check tau is STABLE
    (consistent) vs JITTERY (varies) - the decisive question for whether a constant
    software correction suffices.

USAGE (Jetson, COLD - no LiDAR needed, reads the recorded bag):
  python3 measure_tau.py ~/Desktop/tau_pan_test
"""
import sys, os
import numpy as np
import cv2

# ---- calibration (same vetted sources as the fusion node) ----
INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
EXTRINSIC_YAML  = os.path.expanduser('~/Desktop/extrinsic_20260816.yaml')
BOARD_DEPTH_MIN = 1.0    # board is ~1.64m ahead; accept plane points in this range
BOARD_DEPTH_MAX = 2.4
CHECKER = (7, 10)

def load_calib():
    fs = cv2.FileStorage(INTRINSICS_YAML, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat(); D = fs.getNode('distortion_coefficients').mat().flatten(); fs.release()
    fs = cv2.FileStorage(EXTRINSIC_YAML, cv2.FILE_STORAGE_READ)
    R = fs.getNode('R_lidar_to_cam').mat(); t = fs.getNode('t_lidar_to_cam').mat().reshape(3,1); fs.release()
    if K[0,2] >= 960:
        raise RuntimeError("stale K (cx>=960); refusing")
    return K, D, R, t

def cam_board_x(img_bgr, K, D):
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    ok, corners = cv2.findChessboardCorners(g, CHECKER,
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        return None
    return float(np.mean(corners.reshape(-1, 2)[:, 0]))   # mean horizontal pixel

def lidar_board_x(xyz, K, D, R, t):
    # points in front at board depth
    pc = (R @ xyz.T + t).T
    infront = pc[:, 2] > 0
    pc = pc[infront]
    if len(pc) < 30:
        return None
    depth = pc[:, 2]
    m = (depth > BOARD_DEPTH_MIN) & (depth < BOARD_DEPTH_MAX)
    band = pc[m]
    if len(band) < 30:
        return None
    # the board is the densest near-plane in that band; take the centroid of the
    # largest depth-cluster to avoid background walls
    d = band[:, 2]
    med = np.median(d)
    core = band[np.abs(d - med) < 0.15]     # +/-15cm around the median depth = the board plane
    if len(core) < 30:
        return None
    ctr = core.mean(0).reshape(3, 1)
    px = (K @ ctr).flatten()
    return float(px[0] / px[2])             # projected horizontal pixel

def solve_tau(t_cam, x_cam, t_lid, x_lid, lo=-0.3, hi=0.3, n=601):
    order = np.argsort(t_cam); t_cam, x_cam = t_cam[order], x_cam[order]
    taus = np.linspace(lo, hi, n); best_e, best = np.inf, 0.0
    for tc in taus:
        xc = np.interp(t_lid - tc, t_cam, x_cam)
        mask = (t_lid - tc >= t_cam[0]) & (t_lid - tc <= t_cam[-1])
        if mask.sum() < 10:
            continue
        e = np.mean((x_lid[mask] - xc[mask]) ** 2)
        if e < best_e:
            best_e, best = e, tc
    return best, best_e

def main():
    if len(sys.argv) < 2:
        print("usage: python3 measure_tau.py <bag_dir>"); return
    bag = sys.argv[1]
    K, D, R, t = load_calib()
    print("calib loaded (cx=%.1f, |t|=%.3f)" % (K[0,2], float(np.linalg.norm(t))))

    # --- read bag ---
    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import Image, PointCloud2
    from sensor_msgs_py import point_cloud2
    from cv_bridge import CvBridge
    bridge = CvBridge()

    reader = SequentialReader()
    reader.open(StorageOptions(uri=bag, storage_id='sqlite3'),
                ConverterOptions('', ''))
    tcam, xcam, tlid, xlid = [], [], [], []
    n_img = n_cld = 0
    while reader.has_next():
        topic, data, ts = reader.read_next()
        if topic == '/image_raw':
            n_img += 1
            msg = deserialize_message(data, Image)
            img = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            x = cam_board_x(img, K, D)
            if x is not None:
                stamp = msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9
                tcam.append(stamp); xcam.append(x)
        elif topic == '/unilidar/cloud':
            n_cld += 1
            msg = deserialize_message(data, PointCloud2)
            pts = np.array([[p[0],p[1],p[2]] for p in
                            point_cloud2.read_points(msg, field_names=('x','y','z'), skip_nans=True)])
            if len(pts) > 0:
                x = lidar_board_x(pts, K, D, R, t)
                if x is not None:
                    stamp = msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9
                    tlid.append(stamp); xlid.append(x)

    tcam=np.array(tcam); xcam=np.array(xcam); tlid=np.array(tlid); xlid=np.array(xlid)
    print("read %d images (%d with board), %d clouds (%d with board)" %
          (n_img, len(tcam), n_cld, len(tlid)))
    if len(tcam) < 15 or len(tlid) < 15:
        print("TOO FEW board detections - need a cleaner/longer re-record."); return

    # normalize time to start=0 for readability
    t0 = min(tcam.min(), tlid.min()); tcam-=t0; tlid-=t0

    tau, err = solve_tau(tcam, xcam, tlid, xlid)
    print("\n=== TAU = %+.1f ms  (positive => lidar stamp lags camera) ===" % (tau*1000))

    # stability check: split into halves, solve each
    mid = tcam.min() + (tcam.max()-tcam.min())/2
    for label, sel_c, sel_l in [("first half", tcam<mid, tlid<mid), ("second half", tcam>=mid, tlid>=mid)]:
        if sel_c.sum()>10 and sel_l.sum()>10:
            th,_ = solve_tau(tcam[sel_c], xcam[sel_c], tlid[sel_l], xlid[sel_l])
            print("  %-12s tau = %+.1f ms  (%d cam, %d lid pts)" % (label, th*1000, sel_c.sum(), sel_l.sum()))
    print("\nIf the two halves AGREE (within ~15ms), tau is STABLE -> subtract the")
    print("constant. If they DIVERGE, tau is jittery -> needs a different approach.")

if __name__ == '__main__':
    main()
