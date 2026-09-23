#!/usr/bin/env python3
"""
rig_camera_compressed.py — publish the camera's NATIVE MJPEG as sensor_msgs/CompressedImage
============================================================================================
WHY THIS EXISTS (ADR-002, 2026-09-23)
  gscam publishes RAW sensor_msgs/Image only — it cannot emit a CompressedImage topic. The
  raw path is what choked the recorder (40 GiB / 3.6 min, ~190 MB/s) and dropped 127 s of
  odometry on fusioncap_130955. This node replaces gscam FOR CAPTURE and does the one thing
  we actually want: it takes the camera's already-JPEG frames and republishes them, wrapped
  as CompressedImage, with NO decode and NO re-encode.

WHAT IT BUYS (vs the two alternatives)
  - vs recording raw /image_raw : bag ~1-5 GB not ~42 GB; recorder keeps up; odom stays dense.
  - vs image_transport re-encode : ZERO CPU spent on encode -> does NOT compete with Point-LIO
    (which is CPU-bound) during the coexistence-critical window.
  - BONUS: it never touches nvv4l2decoder/NVJPG, so it also sidesteps the NVMM ring-buffer
    starvation that killed the camera on 2026-09-22 (the Firefox/ENOMEM scar).

TOPIC: publishes exactly /camera/image_raw/compressed — the topic capture_pointlio_texture.sh
  already prefers, so that script auto-selects it with no change.

============================================================================================
SANDBOX-VALIDATED (2026-09-23, in the cloud, NOT on the rig):
  [x] a 1920x1200 JPEG decodes byte-exact through the matcher's CompressedImage branch
      (cv2.imdecode) — the data path is sound.
  [x] gst-launch  videotestsrc ! video/x-raw,1920x1200 ! jpegenc ! <sink>  yields valid,
      matcher-decodable JPEGs (~183 KB/frame -> ~1 GB bag for 220 s).
  [x] the JPEG framing (SOI FFD8 .. EOI FFD9) is intact, which CompressedImage requires.

MUST BE VERIFIED LIVE ON THE JETSON (cannot be tested off-rig — different elements/HW):
  [ ] the camera actually delivers image/jpeg at 1920x1200@30 on /dev/video0 (it does today —
      the current gscam line already uses image/jpeg, same caps).
  [ ] this node's rclpy + gi(Gst) integration runs on the Jetson's ROS2 Humble.
  [ ] `ros2 topic hz /camera/image_raw/compressed` shows ~15-30 Hz, steady.
  [ ] capture_pointlio_texture.sh selects the compressed topic (its step-2 check) and its
      step-3 liveness gate passes.
  [ ] a ~20 s stationary test bag comes out MUCH smaller than raw AND /aft_mapped_to_init is
      dense (no hole) — the whole point.
  [ ] later: pose matcher --image-topic /camera/image_raw/compressed --dump-frames ... decodes
      every frame (its CompressedImage branch), and the coverage GATE passes.
============================================================================================
RUN (once the LiDAR driver is up; this REPLACES the gscam camera start — see the wiring note):
  python3 rig_camera_compressed.py
  # or with params:
  ros2 run <pkg> rig_camera_compressed --ros-args -p device:=/dev/video0 -p width:=1920 \
      -p height:=1200 -p framerate:=30 -p topic:=/camera/image_raw/compressed
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


class CompressedCam(Node):
    def __init__(self):
        super().__init__('rig_camera_compressed')
        self.declare_parameter('device', '/dev/video0')
        self.declare_parameter('width', 1920)
        self.declare_parameter('height', 1200)
        self.declare_parameter('framerate', 30)
        self.declare_parameter('topic', '/camera/image_raw/compressed')
        self.declare_parameter('frame_id', 'camera')

        dev = self.get_parameter('device').value
        w   = int(self.get_parameter('width').value)
        h   = int(self.get_parameter('height').value)
        fr  = int(self.get_parameter('framerate').value)
        topic = self.get_parameter('topic').value
        self.frame_id = self.get_parameter('frame_id').value

        # RELIABLE so the recorder gets every frame (payload is small now -> no backpressure).
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                         history=HistoryPolicy.KEEP_LAST)
        self.pub = self.create_publisher(CompressedImage, topic, qos)

        Gst.init(None)
        # jpegparse frames each buffer to one complete JPEG (SOI..EOI) — required so every
        # CompressedImage is exactly one decodable frame. NO nvv4l2decoder: we keep the JPEG.
        pipe = (
            "v4l2src device=%s do-timestamp=true ! "
            "image/jpeg,width=%d,height=%d,framerate=%d/1 ! "
            "jpegparse ! "
            "appsink name=sink emit-signals=false max-buffers=30 drop=false sync=false"
            % (dev, w, h, fr)
        )
        self.pipeline = Gst.parse_launch(pipe)
        self.sink = self.pipeline.get_by_name('sink')
        rc = self.pipeline.set_state(Gst.State.PLAYING)
        if rc == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("gstreamer pipeline failed to start — check the camera / caps")

        # Drain the appsink on a ROS timer (all publishing stays on the executor thread =
        # thread-safe; no publishing from the gstreamer streaming thread). Poll > framerate.
        self.count = 0
        self.timer = self.create_timer(1.0 / max(1, fr) * 0.5, self._drain)
        self.get_logger().info(
            "publishing NATIVE JPEG -> %s  (%dx%d@%d, %s)" % (topic, w, h, fr, dev))

    def _drain(self):
        # try-pull-sample with a 0 ns timeout = non-blocking; loop drains everything queued.
        while True:
            sample = self.sink.emit('try-pull-sample', 0)
            if sample is None:
                return
            buf = sample.get_buffer()
            ok, m = buf.map(Gst.MapFlags.READ)
            if not ok:
                continue
            try:
                msg = CompressedImage()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.header.frame_id = self.frame_id
                msg.format = 'jpeg'
                msg.data = bytes(m.data)          # one complete JPEG frame
                self.pub.publish(msg)
                self.count += 1
                if self.count % 60 == 0:
                    self.get_logger().info("...%d frames published" % self.count)
            finally:
                buf.unmap(m)

    def destroy_node(self):
        try:
            self.pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = CompressedCam()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
