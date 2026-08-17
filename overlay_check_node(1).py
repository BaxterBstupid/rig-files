#!/usr/bin/env python3
"""
overlay_check_node.py  -  DIAGNOSTIC ONLY, WITH SCAN ACCUMULATION
=================================================================
Draws LiDAR points (projected through the calibration loaded from the YAMLs) onto
the camera image, publishing /fusion/overlay_image for rqt viewing.

NEW: accumulates the last N_ACCUM scans into a rolling buffer before drawing, so a
single sparse ~5,390-pt non-repetitive scan becomes a DENSE overlay (~N*5,390 pts)
- matching the density the calibration was verified on. Hold the board STILL while
viewing; accumulation assumes a static scene (same assumption as accumulate_scans.py).

Does NOT modify the colorized fusion node (which feeds RTAB and correctly stays
per-scan). This is purely to SEE color-on-geometry with enough density to judge.

Runs alongside colorized_fusion_node.py.
"""
import os
from collections import deque
import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, PointCloud2
from sensor_msgs_py import point_cloud2
from cv_bridge import CvBridge
import message_filters

EXTRINSIC_YAML  = os.path.expanduser('~/Desktop/extrinsic_20260816.yaml')
INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
SYNC_SLOP_S     = 0.04
SYNC_QUEUE      = 10
N_ACCUM         = 25          # scans to stack for a dense overlay (board must be STILL)


def load_intrinsics(path):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat()
    D = fs.getNode('distortion_coefficients').mat().flatten()
    fs.release()
    if K is None:
        raise RuntimeError("no camera_matrix in %s" % path)
    if K[0, 2] >= 960:
        raise RuntimeError("cx=%.1f >= 960 -> STALE suspect K in %s; refusing" % (K[0, 2], path))
    return K, D


def load_extrinsic(path):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    R = fs.getNode('R_lidar_to_cam').mat()
    t = fs.getNode('t_lidar_to_cam').mat()
    fs.release()
    if R is None or t is None:
        raise RuntimeError("missing R/t in %s" % path)
    return R, t.reshape(3, 1)


class OverlayCheckNode(Node):
    def __init__(self):
        super().__init__('overlay_check_node')
        self.bridge = CvBridge()
        self.K, self.dist_coeffs = load_intrinsics(INTRINSICS_YAML)
        self.R, self.t = load_extrinsic(EXTRINSIC_YAML)
        self.scan_buffer = deque(maxlen=N_ACCUM)   # rolling buffer of recent scans
        self.get_logger().info("Overlay check: loaded cx=%.1f |t|=%.3f, accumulating %d scans" % (
            self.K[0, 2], float(np.linalg.norm(self.t)), N_ACCUM))

        self.image_sub = message_filters.Subscriber(self, Image, '/image_raw')
        self.cloud_sub = message_filters.Subscriber(self, PointCloud2, '/unilidar/cloud')
        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.image_sub, self.cloud_sub], queue_size=SYNC_QUEUE, slop=SYNC_SLOP_S)
        self.sync.registerCallback(self.cb)

        self.pub = self.create_publisher(Image, '/fusion/overlay_image', 10)
        self.get_logger().info(
            "Overlay check node started -> /fusion/overlay_image (hold board STILL; view in rqt)")

    def cb(self, image_msg, cloud_msg):
        image = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding='bgr8')
        h, w = image.shape[:2]

        # this scan's points
        pts = np.array([
            [p[0], p[1], p[2]]
            for p in point_cloud2.read_points(cloud_msg, field_names=('x', 'y', 'z'), skip_nans=True)
        ])
        if pts.shape[0] > 0:
            self.scan_buffer.append(pts)
        if len(self.scan_buffer) == 0:
            return

        # accumulate the rolling buffer into one dense cloud
        points = np.vstack(self.scan_buffer)

        pc = (self.R @ points.T + self.t).T
        in_front = pc[:, 2] > 0
        pc = pc[in_front]
        if pc.shape[0] == 0:
            return
        px, _ = cv2.projectPoints(pc, np.zeros(3), np.zeros(3), self.K, self.dist_coeffs)
        px = px.reshape(-1, 2)
        depths = pc[:, 2]
        dmin, dmax = depths.min(), depths.max()
        drange = max(dmax - dmin, 1e-3)
        for (u, v), d in zip(px, depths):
            u, v = int(round(u)), int(round(v))
            if 0 <= u < w and 0 <= v < h:
                ratio = (d - dmin) / drange
                color = (int(255 * ratio), 0, int(255 * (1 - ratio)))  # near=red, far=blue (BGR)
                cv2.circle(image, (u, v), 1, color, -1)
        # show how many scans are currently stacked
        cv2.putText(image, "accum: %d/%d scans" % (len(self.scan_buffer), N_ACCUM),
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        out = self.bridge.cv2_to_imgmsg(image, encoding='bgr8')
        out.header = image_msg.header
        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = OverlayCheckNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
