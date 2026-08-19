#!/usr/bin/env python3
"""
colorized_fusion_node.py  (v2 - loads calibration from YAML, timestamp-synchronized)
====================================================================================
Replaces the previous version which HARDCODED stale calibration and paired camera/
LiDAR by unguarded latest-grab. This version:
  1. LOADS intrinsics (K, dist) from calib_intrinsics_20260813.yaml
  2. LOADS extrinsic (R, t)     from extrinsic_20260816.yaml
     -> single sources of truth; no hardcoded numbers; stale-K guard on load.
  3. PAIRS image+cloud with message_filters.ApproximateTimeSynchronizer (tight
     slop) instead of latest-grab -> bounds temporal skew, and STAMPS OUTPUT with
     the matched pair's time so downstream (and tau measurement) is honest.

Note on tau: the synchronizer bounds SOFTWARE skew to <= slop. It does NOT remove
the true hardware exposure-vs-sensor-time offset (tau) - that still needs a
constant-velocity-pan measurement. But it makes the residual skew bounded and
measurable, which the latest-grab version did not.
"""
import os
import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header
from cv_bridge import CvBridge
import message_filters

# ---- calibration file paths (edit if you move the YAMLs) ----
EXTRINSIC_YAML  = os.path.expanduser('~/Desktop/extrinsic_20260816.yaml')
INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
SYNC_SLOP_S     = 0.04    # max tolerated stamp difference when pairing (~1 frame @ 11Hz)
SYNC_QUEUE      = 10


def load_intrinsics(path):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat()
    D = fs.getNode('distortion_coefficients').mat().flatten()
    fs.release()
    if K is None:
        raise RuntimeError("no camera_matrix in %s" % path)
    if K[0, 2] >= 960:
        raise RuntimeError("cx=%.1f >= 960 -> STALE suspect K in %s; refusing to load" % (K[0, 2], path))
    return K, D


def load_extrinsic(path):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    R = fs.getNode('R_lidar_to_cam').mat()
    t = fs.getNode('t_lidar_to_cam').mat()
    paired = fs.getNode('paired_intrinsics').string()
    fs.release()
    if R is None or t is None:
        raise RuntimeError("missing R/t in %s" % path)
    return R, t.reshape(3, 1), paired


class ColorizedFusionNode(Node):
    def __init__(self):
        super().__init__('colorized_fusion_node')
        self.bridge = CvBridge()

        # ---- load calibration from artifacts (single source of truth) ----
        self.K, self.dist_coeffs = load_intrinsics(INTRINSICS_YAML)
        self.R, self.t, paired = load_extrinsic(EXTRINSIC_YAML)
        self.get_logger().info(
            "Loaded intrinsics (cx=%.1f) from %s" % (self.K[0, 2], os.path.basename(INTRINSICS_YAML)))
        self.get_logger().info(
            "Loaded extrinsic |t|=%.3f from %s (paired_intrinsics=%s)" % (
                float(np.linalg.norm(self.t)), os.path.basename(EXTRINSIC_YAML), paired))
        # provenance sanity: the extrinsic names the intrinsics it was solved with
        if paired and paired not in os.path.basename(INTRINSICS_YAML):
            self.get_logger().warn(
                "extrinsic paired_intrinsics=%s but loading %s - verify these match!" % (
                    paired, os.path.basename(INTRINSICS_YAML)))

        # ---- timestamp-synchronized subscription (replaces latest-grab) ----
        self.image_sub = message_filters.Subscriber(self, Image, '/image_raw')
        self.cloud_sub = message_filters.Subscriber(self, PointCloud2, '/unilidar/cloud')
        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.image_sub, self.cloud_sub], queue_size=SYNC_QUEUE, slop=SYNC_SLOP_S)
        self.sync.registerCallback(self.synced_callback)

        self.colorized_pub = self.create_publisher(PointCloud2, '/fusion/colorized_cloud', 10)
        # time-field autodetect: resolved on first cloud (name may be time/t/timestamp/stamps)
        self._time_field = None      # the detected field name, or '' if none
        self._logged_fields = False
        self.get_logger().info(
            "Colorized fusion node v3 started (sync slop=%.3fs, queue=%d). "
            "Will autodetect per-point time field on first cloud." % (SYNC_SLOP_S, SYNC_QUEUE))

    def _resolve_time_field(self, cloud_msg):
        """On first cloud, find which time-like field exists. Log all fields once."""
        names = [f.name for f in cloud_msg.fields]
        if not self._logged_fields:
            self.get_logger().info("Raw cloud fields: %s" % names)
            self._logged_fields = True
        for cand in ('time', 't', 'timestamp', 'stamps'):
            if cand in names:
                self.get_logger().info("Using per-point time field: '%s'" % cand)
                return cand
        self.get_logger().warn(
            "NO per-point time field found in %s. Publishing WITHOUT time; RTAB "
            "deskewing must be disabled (deskewing:=false) or odometry will abort." % names)
        return ''

    def synced_callback(self, image_msg, cloud_msg):
        # both messages are timestamp-matched within slop
        image = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding='bgr8')
        h, w = image.shape[:2]

        # Resolve the time-field name once (autodetect: time/t/timestamp/stamps or none).
        if self._time_field is None:
            self._time_field = self._resolve_time_field(cloud_msg)

        # READ x,y,z AND the per-point time field if it exists (RTAB deskewing needs it).
        if self._time_field:
            raw = np.array([
                [p[0], p[1], p[2], p[3]]
                for p in point_cloud2.read_points(
                    cloud_msg, field_names=('x', 'y', 'z', self._time_field), skip_nans=True)
            ])
            if raw.shape[0] == 0:
                return
            points = raw[:, :3]
            times = raw[:, 3]
        else:
            # no time field available: read xyz only, use zeros for time (deskew must be off)
            points = np.array([
                [p[0], p[1], p[2]]
                for p in point_cloud2.read_points(
                    cloud_msg, field_names=('x', 'y', 'z'), skip_nans=True)
            ])
            if points.shape[0] == 0:
                return
            times = np.zeros(len(points))

        points_cam = (self.R @ points.T + self.t).T
        in_front = points_cam[:, 2] > 0
        points_lidar_frame = points[in_front]
        times_front = times[in_front]
        points_cam = points_cam[in_front]
        if points_cam.shape[0] == 0:
            return

        pixels, _ = cv2.projectPoints(
            points_cam, rvec=np.zeros(3), tvec=np.zeros(3),
            cameraMatrix=self.K, distCoeffs=self.dist_coeffs)
        pixels = pixels.reshape(-1, 2)

        # KEEP_ALL switch:
        #   False (default) = ORIGINAL behaviour: keep only points that land in the
        #     image (coloured subset). For a MOVING capture the camera sweeps and the
        #     accumulated map still fills in with colour. Fewer points per frame.
        #   True = keep EVERY in-front point; colour the ones in-image, leave the rest
        #     grey (0). Full geometry preserved for stronger ICP odometry. Use this if
        #     odometry drifts on the coloured subset.
        KEEP_ALL = False

        colorized_points = []
        for (u, v), (x, y, z), tt in zip(pixels, points_lidar_frame, times_front):
            u_i, v_i = int(round(u)), int(round(v))
            if 0 <= u_i < w and 0 <= v_i < h:
                b, g, r = image[v_i, u_i]
                rgba_int = (0xFF << 24) | (int(r) << 16) | (int(g) << 8) | int(b)
                colorized_points.append([x, y, z, rgba_int, float(tt)])
            elif KEEP_ALL:
                colorized_points.append([x, y, z, 0, float(tt)])  # grey, kept for geometry
        if len(colorized_points) == 0:
            return

        # OUTPUT fields: x,y,z (f32), rgb (u32), time (f32). RTAB reads 'time' for deskew.
        fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='rgb', offset=12, datatype=PointField.UINT32, count=1),
            PointField(name='time', offset=16, datatype=PointField.FLOAT32, count=1),
        ]
        header = Header()
        # stamp with the CLOUD's time; the pair is matched within slop so this is honest
        header.stamp = cloud_msg.header.stamp
        header.frame_id = cloud_msg.header.frame_id
        cloud_out = point_cloud2.create_cloud(header, fields, colorized_points)
        self.colorized_pub.publish(cloud_out)


def main(args=None):
    rclpy.init(args=args)
    node = ColorizedFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
