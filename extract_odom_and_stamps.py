#!/usr/bin/env python3
"""
extract_odom_and_stamps.py  —  RUN ON THE JETSON (has ROS2 to read the bag)
Pulls from fusioncap_180551_0.db3:
  (1) the FULL /aft_mapped_to_init odometry stream (poses + timestamps)  [thinned to ~200Hz - plenty]
  (2) all 2200 /image_raw timestamps
Saves a COMPACT odom_and_stamps.npz (a few MB) to bridge to Shadow for re-matching all 2200 frames.

Usage:
  source /opt/ros/humble/setup.bash
  python3 extract_odom_and_stamps.py /mnt/rigdata/fusioncap_180551/fusioncap_180551_0.db3
"""
import sys, numpy as np
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

BAG = sys.argv[1] if len(sys.argv)>1 else '/mnt/rigdata/fusioncap_180551/fusioncap_180551_0.db3'
OUT = 'odom_and_stamps.npz'
ODOM_THIN_HZ = 200.0   # 1.15M poses is overkill; keep ~200Hz (still far denser than 28Hz frames)

ts = get_typestore(Stores.ROS2_HUMBLE)

odom_t=[]; odom_pos=[]; odom_quat=[]
img_t=[]
last_odom_keep = -1.0
min_dt = 1.0/ODOM_THIN_HZ

print("reading bag:", BAG)
with Reader(BAG) as reader:
    conns = {c.topic: c for c in reader.connections}
    for c in reader.connections:
        print(f"  topic {c.topic}: {c.msgcount} msgs")
    for conn, t_ns, raw in reader.messages():
        topic = conn.topic
        if topic == '/aft_mapped_to_init':
            m = ts.deserialize_cdr(raw, conn.msgtype)
            # use the message HEADER stamp if valid, else bag time
            hs = m.header.stamp
            th = hs.sec + hs.nanosec*1e-9
            tb = t_ns*1e-9
            # NOTE: header stamps can be frozen on old bags; keep BOTH, decide on Shadow
            # store bag-time as the reliable clock (matches how images are stamped in the same bag)
            tt = tb
            if tt - last_odom_keep < min_dt:
                continue
            last_odom_keep = tt
            p = m.pose.pose.position; q = m.pose.pose.orientation
            odom_t.append(tt)
            odom_pos.append([p.x, p.y, p.z])
            odom_quat.append([q.x, q.y, q.z, q.w])
        elif topic == '/image_raw':
            # just the timestamp (bag time - same clock as odom above)
            img_t.append(t_ns*1e-9)

odom_t=np.array(odom_t); odom_pos=np.array(odom_pos); odom_quat=np.array(odom_quat)
img_t=np.array(img_t)
print(f"\nODOM kept (thinned to ~{ODOM_THIN_HZ:.0f}Hz): {len(odom_t)}  span {odom_t.max()-odom_t.min():.1f}s")
print(f"IMAGES: {len(img_t)}  span {img_t.max()-img_t.min():.1f}s")
# how many images fall INSIDE the odom window (the recoverable set)?
inwin = ((img_t>=odom_t.min()) & (img_t<=odom_t.max())).sum()
print(f"IMAGES inside odom window: {inwin} / {len(img_t)}  <-- the recoverable count")
np.savez_compressed(OUT, odom_t=odom_t, odom_pos=odom_pos, odom_quat=odom_quat, img_t=img_t)
import os; print(f"\nwrote {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB) - bridge THIS to Shadow")
