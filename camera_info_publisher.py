#!/usr/bin/env python3
"""
camera_info_publisher.py  —  publishes sensor_msgs/CameraInfo for RTAB-Map (Way B)
==================================================================================
WHY: RTAB-Map's camera-projection colouring (Way B) needs the camera INTRINSICS as a
sensor_msgs/CameraInfo TOPIC, matched to /image_raw. The B0578 UVC driver does NOT
publish camera_info, and the fusion node only loads intrinsics internally. This node
fills that gap.

WHAT IT DOES: loads the VETTED intrinsics from calib_intrinsics_20260813.yaml and
publishes CameraInfo on /camera/camera_info, re-stamped to match each /image_raw frame
(subscribes to /image_raw purely to copy its header stamp+frame_id, so the pair is
time-aligned for RTAB-Map's exact/approx sync).

STALE-K GUARD: refuses to load if cx >= 960 (the known stale-K tell; good cx≈921).

Run:  python3 camera_info_publisher.py
Topic out: /camera/camera_info  (sensor_msgs/CameraInfo)
"""
import os
import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo

INTRINSICS_YAML = os.path.expanduser('~/Desktop/calib_intrinsics_20260813.yaml')
IMAGE_TOPIC     = '/image_raw'
CAMERA_INFO_TOPIC = '/camera/camera_info'


def load_intrinsics(path):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_READ)
    K = fs.getNode('camera_matrix').mat()
    D = fs.getNode('distortion_coefficients').mat().flatten()
    w = int(fs.getNode('image_width').real())
    h = int(fs.getNode('image_height').real())
    fs.release()
    if K is None:
        raise RuntimeError("no camera_matrix in %s" % path)
    if K[0, 2] >= 960:
        raise RuntimeError("cx=%.1f >= 960 -> STALE suspect K in %s; refusing" % (K[0, 2], path))
    return K, D, w, h


class CameraInfoPublisher(Node):
    def __init__(self):
        super().__init__('camera_info_publisher')
        self.K, self.D, self.w, self.h = load_intrinsics(INTRINSICS_YAML)
        self.get_logger().info(
            "Loaded intrinsics cx=%.1f cy=%.1f (%dx%d) from %s" % (
                self.K[0, 2], self.K[1, 2], self.w, self.h, os.path.basename(INTRINSICS_YAML)))

        # Pre-build the constant parts of the CameraInfo message
        self.ci = CameraInfo()
        self.ci.width = self.w
        self.ci.height = self.h
        self.ci.distortion_model = 'plumb_bob'   # Brown-Conrady = plumb_bob in ROS
        self.ci.d = [float(x) for x in self.D]    # k1,k2,p1,p2,k3
        self.ci.k = [float(x) for x in self.K.flatten()]          # 3x3 row-major
        # No stereo rectification: R = identity, P = [K|0]
        self.ci.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        self.ci.p = [self.K[0, 0], 0.0, self.K[0, 2], 0.0,
                     0.0, self.K[1, 1], self.K[1, 2], 0.0,
                     0.0, 0.0, 1.0, 0.0]

        self.pub = self.create_publisher(CameraInfo, CAMERA_INFO_TOPIC, 10)
        # Subscribe to image ONLY to copy its header (stamp + frame_id) so camera_info
        # is time-aligned + frame-aligned with the image RTAB-Map will sync against.
        self.sub = self.create_subscription(Image, IMAGE_TOPIC, self.on_image, 10)
        self.get_logger().info("Publishing CameraInfo on %s, stamped to match %s" % (
            CAMERA_INFO_TOPIC, IMAGE_TOPIC))

    def on_image(self, img_msg):
        self.ci.header = img_msg.header   # same stamp AND same frame_id as the image
        self.pub.publish(self.ci)


def main(args=None):
    rclpy.init(args=args)
    node = CameraInfoPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
