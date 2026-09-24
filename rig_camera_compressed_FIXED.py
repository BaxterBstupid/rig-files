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

  IMAGE-QUALITY NOTE (measured 2026-09-24, ADR-003): keeping the native JPEG adds ZERO loss
  vs the old raw path — the sensor already emits MJPEG, so both paths carry exactly one JPEG
  generation. Measured on real frames: the Arducam MJPEG is ~Q88, 4:2:0 chroma. That 4:2:0 is
  the texture ceiling; if the camera can be set to higher quality / 4:2:2 / 4:4:4, do it (the
  bag is small now, we have headroom). This node does not change that ceiling either way.

WHAT IT BUYS (vs the two alternatives)
  - vs recording raw /image_raw : bag ~1-5 GB not ~42 GB; recorder keeps up; odom stays dense.
  - vs image_transport re-encode : ZERO CPU spent on encode -> does NOT compete with Point-LIO.
  - BONUS: never touches nvv4l2decoder/NVJPG, so it sidesteps the NVMM ring-buffer starvation
    that killed the camera on 2026-09-22 (the Firefox/ENOMEM scar).

============================================================================================
*** TIMESTAMP FIX (ADR-003 conflict #1, 2026-09-24) — READ THIS ***
  THE BUG (old version): the header stamp was set to `self.get_clock().now()` at DRAIN time,
  i.e. when the ROS timer happened to pull the frame out of the appsink queue. That injects
  the queue wait + timer phase (tens of ms, JITTERY) into every camera timestamp. Our own
  post-mortem + FUSION_SOLUTION say the camera->LiDAR time offset tau (~150-200 ms) is
  mandatory to correct, and that at walking speed 150-200 ms = 18-25 cm of camera-position
  error -> ghosted/doubled texture. Stamping at drain made tau LARGER and, worse, UNSTABLE
  frame-to-frame (a moving target you cannot calibrate out).

  THE FIX: stamp from the BUFFER PTS. `v4l2src do-timestamp=true` stamps each buffer with the
  pipeline (monotonic) clock at capture on the src pad — the earliest in-band time we have.
  We anchor ONCE (first valid buffer: remember its pts and the ROS time at that instant) and
  then every frame's stamp = anchor_ros + (pts - anchor_pts). Result:
    - INTER-FRAME spacing is now driven by the capture clock (PTS), JITTER-FREE — the thing
      the matcher and any de-skew care about.
    - the one constant anchor offset (first-frame latency) is a CONSTANT bias, which is
      exactly what tau calibration measures and removes. So we lose nothing and gain stability.
  PTS still is NOT true photon time (it is set after USB transfer) -> tau still exists and must
  still be measured (motion cross-correlation, per the post-mortem). This fix makes tau a
  stable constant instead of per-frame noise; it does not replace tau.

  UP/DOWN-PIPELINE EFFECTS (traced, per the project's discipline):
    - matcher (pointlio_pose_matcher): matches image_t against odom_t. Jitter-free image_t ->
      correct nearest-odom association; a constant bias is absorbed once tau is applied
      (t_cam_corrected = t_cam - tau) BEFORE matching. NO code change needed there.
    - coverage GATE (max-hole/max-gap): operates on ODOM timestamps -> unaffected.
    - capture_autopsy: reads odom POSITIONS -> unaffected.
    - Point-LIO: consumes LiDAR per-point time + IMU, not this topic -> unaffected.
  Fallback: if a buffer's pts is invalid (GST_CLOCK_TIME_NONE) or --stamp-source now, we stamp
  with ROS now() (old behavior) so the node never crashes on a weird driver.
============================================================================================
SANDBOX-VALIDATED (2026-09-23/24, in the cloud, NOT on the rig):
  [x] a 1920x1200 JPEG decodes byte-exact through the matcher's CompressedImage branch.
  [x] the JPEG framing (SOI FFD8 .. EOI FFD9) is intact (CompressedImage requires it).
  [x] pts_anchor_map() unit-tested: PTS-driven spacing is preserved under drain jitter
      (test_rig_camera_timestamp.py, all cases pass).

MUST BE VERIFIED LIVE ON THE JETSON (cannot be tested off-rig — different elements/HW):
  [ ] camera delivers image/jpeg @1920x1200@30 on /dev/video0 (current gscam line already does).
  [ ] this node's rclpy + gi(Gst) integration runs on the Jetson's ROS2 Humble.
  [ ] `ros2 topic hz /camera/image_raw/compressed` ~15-30 Hz, steady.
  [ ] buffers carry a valid PTS (log line "anchored capture clock" appears once, no
      "pts invalid -> now()" spam). If PTS is missing, the fallback keeps it running but tau
      goes back to being jittery -> tell Claude.
  [ ] capture_pointlio_texture.sh selects the compressed topic; liveness gate passes.
  [ ] a ~20 s stationary test bag << raw AND /aft_mapped_to_init dense (no hole).
  [ ] tau: record the jerky "sync clapper" bag; cross-correlate; confirm the peak is SHARP and
      tau STABLE across bags (spread < ~1 frame). This is the payoff of the stamp fix.
============================================================================================
RUN (once the LiDAR driver is up; this REPLACES the gscam camera start):
  python3 rig_camera_compressed.py
  ros2 run <pkg> rig_camera_compressed --ros-args -p device:=/dev/video0 -p width:=1920 \
      -p height:=1200 -p framerate:=30 -p topic:=/camera/image_raw/compressed \
      -p stamp_source:=capture
"""
import sys

GST_CLOCK_TIME_NONE = 0xFFFFFFFFFFFFFFFF  # 2**64-1, GStreamer's "no timestamp" sentinel


def pts_anchor_map(pts_ns, anchor_pts_ns, anchor_ros_ns):
    """PURE, UNIT-TESTABLE core of the timestamp fix.

    Map a GStreamer buffer PTS (monotonic capture clock, nanoseconds) to a ROS
    epoch nanosecond stamp, using a single anchor pair captured on the first
    valid frame. Inter-frame spacing comes entirely from the PTS deltas (so it
    is jitter-free w.r.t. when we happened to drain the appsink); the absolute
    offset comes from the one anchor (its constant first-frame bias is absorbed
    by tau downstream).

    Returns an int ns stamp, or None if pts is invalid (caller falls back to now()).
    """
    if pts_ns is None or pts_ns == GST_CLOCK_TIME_NONE or pts_ns < 0:
        return None
    return int(anchor_ros_ns) + (int(pts_ns) - int(anchor_pts_ns))


# ---- the ROS node (only imported/constructed on the rig) ------------------
def _build_node_class():
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
            self.declare_parameter('stamp_source', 'capture')  # 'capture' (PTS) | 'now'

            dev = self.get_parameter('device').value
            w   = int(self.get_parameter('width').value)
            h   = int(self.get_parameter('height').value)
            fr  = int(self.get_parameter('framerate').value)
            topic = self.get_parameter('topic').value
            self.frame_id = self.get_parameter('frame_id').value
            self.stamp_source = self.get_parameter('stamp_source').value

            # anchor state for the PTS->ROS mapping (set on first valid buffer)
            self._anchor_pts = None
            self._anchor_ros = None
            self._pts_warned = False

            qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                             history=HistoryPolicy.KEEP_LAST)
            self.pub = self.create_publisher(CompressedImage, topic, qos)

            Gst.init(None)
            # do-timestamp=true -> v4l2src stamps each buffer PTS at capture (src pad).
            # jpegparse frames each buffer to one complete JPEG (SOI..EOI). NO decoder.
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
                raise RuntimeError("gstreamer pipeline failed to start — check camera / caps")

            self.count = 0
            self.timer = self.create_timer(1.0 / max(1, fr) * 0.5, self._drain)
            self.get_logger().info(
                "publishing NATIVE JPEG -> %s  (%dx%d@%d, %s, stamp=%s)"
                % (topic, w, h, fr, dev, self.stamp_source))

        def _stamp_ns(self, buf):
            """Return the ns stamp for this buffer per the fix (or now() fallback)."""
            now_ns = self.get_clock().now().nanoseconds
            if self.stamp_source != 'capture':
                return now_ns
            pts = buf.pts
            # anchor on first valid pts
            if self._anchor_pts is None:
                mapped = pts_anchor_map(pts, pts, now_ns)  # anchor to itself
                if mapped is None:
                    if not self._pts_warned:
                        self.get_logger().warn(
                            "buffer pts invalid -> falling back to now() (tau will be "
                            "jittery; check do-timestamp / driver)")
                        self._pts_warned = True
                    return now_ns
                self._anchor_pts = pts
                self._anchor_ros = now_ns
                self.get_logger().info("anchored capture clock (pts0=%d, ros0=%d)"
                                       % (self._anchor_pts, self._anchor_ros))
                return mapped
            mapped = pts_anchor_map(pts, self._anchor_pts, self._anchor_ros)
            if mapped is None:
                if not self._pts_warned:
                    self.get_logger().warn("buffer pts invalid mid-stream -> now() fallback")
                    self._pts_warned = True
                return now_ns
            return mapped

        def _drain(self):
            while True:
                sample = self.sink.emit('try-pull-sample', 0)
                if sample is None:
                    return
                buf = sample.get_buffer()
                ok, m = buf.map(Gst.MapFlags.READ)
                if not ok:
                    continue
                try:
                    stamp_ns = self._stamp_ns(buf)
                    msg = CompressedImage()
                    msg.header.stamp.sec = int(stamp_ns // 1_000_000_000)
                    msg.header.stamp.nanosec = int(stamp_ns % 1_000_000_000)
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

    return rclpy, CompressedCam


def main():
    rclpy, CompressedCam = _build_node_class()
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
