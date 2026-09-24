#!/usr/bin/env python3
"""
check_pan_heading.py  -- READ-ONLY diagnostic.  Nothing is written, no pipeline
tool is touched, the L2 and camera stay off.  It answers ONE question:

    Did capture 114136 actually sweep heading (a real pan), or was the rig
    fixed on one direction the whole recording?

It reads ONLY the /aft_mapped_to_init odometry track from the bag and reports:
  - how far the YAW (heading) swept over the whole recording
  - how far the rig TRANSLATED (parallax) over the whole recording

Why this exists: the 30-frame ebundle we already have all faces 153-154 deg
(a 1 deg spread), and make_extrinsic_bundle.py picks frames spread across the
WHOLE bag -- so if a pan had happened, those frames would show many headings.
They don't.  This confirms, from the full odom track, whether the pan is in
the data at all BEFORE we try to export a "full pan" that may not exist.

Run on the Jetson (the machine with the bag):
    python3 check_pan_heading.py <BAG_DIR>

Reads with the same rosbags/typestore stack the matcher already uses.
"""
import sys
import numpy as np
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

if len(sys.argv) < 2:
    raise SystemExit("usage: python3 check_pan_heading.py <BAG_DIR>")
BAG = sys.argv[1]
ODOM = "/aft_mapped_to_init"

TS = get_typestore(Stores.ROS2_HUMBLE)
yaws, xs, ys, zs, ts = [], [], [], [], []
with AnyReader([Path(BAG)], default_typestore=TS) as r:
    conns = [c for c in r.connections if c.topic == ODOM]
    if not conns:
        raise SystemExit("no %s in %s -- is this the right bag?" % (ODOM, BAG))
    for con, t, raw in r.messages(connections=conns):
        m = r.deserialize(raw, con.msgtype)
        p = m.pose.pose.position
        q = m.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaws.append(np.degrees(np.arctan2(siny, cosy)))
        xs.append(p.x); ys.append(p.y); zs.append(p.z); ts.append(t * 1e-9)

n = len(yaws)
if n == 0:
    raise SystemExit("no odometry messages found in %s" % BAG)

yaws = np.asarray(yaws)
ts = np.asarray(ts) - ts[0]
# angular coverage: largest gap on the heading circle, subtracted from 360
s = np.sort(yaws % 360.0)
gap = np.diff(np.r_[s, s[0] + 360.0])
cov = 360.0 - gap.max()
# translation extent (parallax)
ext = np.array([np.ptp(xs), np.ptp(ys), np.ptp(zs)]) * 100.0  # cm

print("bag:", BAG)
print("odom poses: %d over %.1f s" % (n, ts[-1]))
print("YAW sweep : min=%.0f  max=%.0f  angular COVERAGE=%.0f deg" % (yaws.min(), yaws.max(), cov))
print("TRANSLATION extent (cm): X=%.0f Y=%.0f Z=%.0f" % (ext[0], ext[1], ext[2]))
print("-" * 56)
if cov > 60:
    print("VERDICT: PAN PRESENT (%.0f deg of heading) -- a full-ring photo export IS possible from this bag." % cov)
else:
    print("VERDICT: NO PAN -- heading is fixed (only %.0f deg). This bag holds ONE direction;" % cov)
    print("         a wider colored ring needs a NEW capture that actually rotates the rig.")
