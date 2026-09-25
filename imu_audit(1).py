#!/usr/bin/env python3
"""
imu_audit.py  --  full audit of the Point-LIO IMU + config chain for one bag.
Dumps the capture launcher + Point-LIO config + driver config, then runs decisive
tests on the recorded /unilidar/imu. READ-ONLY.

    python3 imu_audit.py <BAG_DIR>

Tests (each is a smoking-gun candidate for pan-drift):
  1. accel |a| magnitude  -> ~9.8 = m/s^2 (correct for ROS/Point-LIO); ~1.0 = g units (BUG)
  2. IMU rate + dropouts   -> starved/low-rate IMU can't hold heading through rotation
  3. stamp monotonicity/jitter -> bad IMU clock -> bad rotation integration
  4. integrate each gyro axis -> net rotation deg; the pan axis should read ~+/-275 deg.
     if NO axis integrates near the physical pan, the gyro is mis-scaled/dropping = root cause.
  5. gyro vs odom net yaw   -> do IMU and Point-LIO agree on how far we turned?
"""
import sys, os, glob
import numpy as np
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

BAG = sys.argv[1]
TS = get_typestore(Stores.ROS2_HUMBLE)
HOME = os.path.expanduser('~')

def dump(title, path, maxlines=200):
    print("\n===== %s :: %s =====" % (title, path))
    try:
        txt = open(path).read().splitlines()
        print("\n".join(txt[:maxlines]))
        if len(txt) > maxlines:
            print("... (%d more lines)" % (len(txt) - maxlines))
    except Exception as e:
        print("(could not read: %s)" % e)

print("########################## CONFIG DUMP ##########################")
seen = set()
def find_dump(title, patterns, limit=2):
    hits = []
    for pat in patterns:
        for p in glob.glob(os.path.join(HOME, pat), recursive=True):
            if p not in seen and os.path.isfile(p):
                seen.add(p); hits.append(p)
    for p in hits[:limit]:
        dump(title, p)
    if not hits:
        print("\n===== %s :: NONE FOUND (%s) =====" % (title, patterns))

find_dump("CAPTURE LAUNCHER", ["Downloads/capture_pointlio_texture.sh", "**/capture_pointlio_texture.sh"], 1)
find_dump("POINT-LIO LAUNCH", ["**/mapping_unilidar*.launch.py"], 2)
find_dump("POINT-LIO CONFIG (IMU extrinsic/cov/time-sync live here)",
          ["**/point_lio*/config/*.yaml", "**/point_lio/**/*.yaml", "**/config/*unilidar*.yaml"], 3)
find_dump("UNITREE DRIVER CONFIG (IMU rate/topic)",
          ["**/unitree_lidar_ros2/**/*.yaml", "**/unilidar*/**/config/*.yaml"], 3)

print("\n########################## IMU AUDIT ##########################")
t = []; G = [[], [], []]; A = [[], [], []]
topics_present = set()
with AnyReader([Path(BAG)], default_typestore=TS) as r:
    topics_present = {c.topic for c in r.connections}
    conns = [c for c in r.connections if c.topic == '/unilidar/imu']
    if not conns:
        # try any Imu topic
        conns = [c for c in r.connections if 'Imu' in c.msgtype]
    for con, bt, raw in r.messages(connections=conns):
        m = r.deserialize(raw, con.msgtype)
        s = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        t.append(s)
        g = m.angular_velocity; a = m.linear_acceleration
        G[0].append(g.x); G[1].append(g.y); G[2].append(g.z)
        A[0].append(a.x); A[1].append(a.y); A[2].append(a.z)

print("bag topics:", sorted(topics_present))
t = np.array(t); n = len(t)
if n < 10:
    print("IMU messages: %d  -- TOO FEW / MISSING. This alone would break Point-LIO." % n)
    sys.exit(0)

dt = np.diff(t); med = np.median(dt)
dur = t[-1] - t[0]
print("IMU msgs: %d over %.2fs  ->  rate = %.1f Hz  (L2 IMU nominal ~250 Hz)" % (n, dur, n / dur))
print("dt: median=%.4fs (%.0f Hz)  max=%.4fs  gaps>3x median: %d  (dropouts starve rotation)"
      % (med, 1.0 / med, dt.max(), int((dt > 3 * med).sum())))
print("stamps monotonic: %s  (non-increasing dt count: %d)" % (bool(np.all(dt > 0)), int((dt <= 0).sum())))

G = [np.array(x) for x in G]; A = [np.array(x) for x in A]
amag = np.sqrt(A[0]**2 + A[1]**2 + A[2]**2)
print("\naccel |a| mean = %.3f   >>> 9.8 = m/s^2 (CORRECT) ; ~1.0 = g units (BUG: Point-LIO expects m/s^2)"
      % amag.mean())
print("accel per-axis mean (m/s^2?): x=%.2f y=%.2f z=%.2f  (one axis ~+/-9.8 = gravity down)"
      % (A[0].mean(), A[1].mean(), A[2].mean()))
print("gyro range rad/s: x[% .2f,% .2f] y[% .2f,% .2f] z[% .2f,% .2f]"
      % (G[0].min(), G[0].max(), G[1].min(), G[1].max(), G[2].min(), G[2].max()))

print("\nINTEGRATED GYRO (net rotation over the capture) -- the pan swept ~275 deg physically:")
for nm, g in zip('xyz', G):
    ang = np.degrees(np.trapz(g, t))
    flag = "  <-- pan axis?" if abs(abs(ang) - 275) < 60 else ""
    print("   axis %s: % 7.0f deg%s" % (nm, ang, flag))
print("If NO axis lands near +/-275, the gyro is mis-scaled or dropping samples = the drift source.")

# cross-check vs odom net yaw
oq = []
with AnyReader([Path(BAG)], default_typestore=TS) as r:
    conns = [c for c in r.connections if c.topic == '/aft_mapped_to_init']
    for con, bt, raw in r.messages(connections=conns):
        m = r.deserialize(raw, con.msgtype); q = m.pose.pose.orientation
        oq.append((q.x, q.y, q.z, q.w))
if oq:
    oq = np.array(oq)
    yaw = np.degrees(np.arctan2(2 * (oq[:, 3] * oq[:, 2] + oq[:, 0] * oq[:, 1]),
                                1 - 2 * (oq[:, 1]**2 + oq[:, 2]**2)))
    uw = np.unwrap(np.radians(yaw)); net = np.degrees(uw[-1] - uw[0])
    print("\nPoint-LIO odom NET yaw (unwrapped start->end): %.0f deg" % net)
    print("Compare to the gyro pan-axis integral above: if they DISAGREE, Point-LIO is not")
    print("tracking the IMU's rotation (fusion/extrinsic/time-sync fault, not the raw gyro).")
