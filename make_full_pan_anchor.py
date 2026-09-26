#!/usr/bin/env python3
"""
make_full_pan_anchor.py  --  export a HEADING-SPREAD posed-frame bundle from ONE bag,
for full-360 photo colouring of the LiDAR cloud.

WHY THIS EXISTS
  make_extrinsic_bundle.py selects frames spread by TIME and (on a different, single-
  heading recording) handed us 30 frames all facing 153 deg. This bag (114136) actually
  sweeps 309 deg. This script selects frames spread by HEADING, so the whole ring gets
  colour, and it pulls frames + poses from the SAME bag as the cloud (no cross-capture
  mismatch).

POSE MATH PROVENANCE
  quat_to_R, interpolate_pose (bracketed LERP + short-arc SLERP) and read_bag are copied
  VERBATIM from pointlio_pose_matcher.py v2 (md5 6827341d58e6d25384d07b47713c15bb), the
  gated matcher. Convention: T_lidar_in_map (body->map); the camera<->LiDAR extrinsic is
  applied DOWNSTREAM by per_shot_texture.compose_world_to_cam (never here).

RUN on the Jetson (the machine with the bag; L2 off, camera off, no Point-LIO relaunch --
this only READS the recorded bag):
    python3 make_full_pan_anchor.py <BAG_DIR> [NKEY] [IMAGE_TOPIC]
  NKEY        number of heading-spread keyframes to export (default 40)
  IMAGE_TOPIC auto-detected if omitted (prefers a compressed image topic)
OUTPUT: /tmp/panbundle.tar.gz   -> upload that to the chat.
"""
import sys, os, shutil, tarfile
import numpy as np
from pathlib import Path

# ============================ proven math (verbatim: matcher v2) ============================
def quat_normalize(q):
    q = np.asarray(q, dtype=np.float64); n = np.linalg.norm(q)
    if n < 1e-12: raise ValueError("zero-norm quaternion")
    return q / n

def quat_slerp(q0, q1, u):
    q0 = quat_normalize(q0); q1 = quat_normalize(q1); dot = float(np.dot(q0, q1))
    if dot < 0.0: q1 = -q1; dot = -dot
    dot = min(1.0, max(-1.0, dot)); perp = q1 - dot * q0; sin0 = float(np.linalg.norm(perp))
    if sin0 < 1e-12: return quat_normalize(q0 + u * (q1 - q0))
    theta0 = np.arctan2(sin0, dot)
    return quat_normalize(np.sin((1-u)*theta0)/sin0 * q0 + np.sin(u*theta0)/sin0 * q1)

def quat_to_R(q):
    x, y, z, w = quat_normalize(q)
    return np.array([
        [1-2*(y*y+z*z),   2*(x*y-z*w),   2*(x*z+y*w)],
        [  2*(x*y+z*w), 1-2*(x*x+z*z),   2*(y*z-x*w)],
        [  2*(x*z-y*w),   2*(y*z+x*w), 1-2*(x*x+y*y)]], dtype=np.float64)

def interpolate_pose(odom_t, odom_pos, odom_quat, tq, max_gap=None):
    M = len(odom_t)
    if M == 0 or tq < odom_t[0] or tq > odom_t[-1]: return None, None, False
    j = int(np.searchsorted(odom_t, tq))
    if j < M and odom_t[j] == tq: return odom_pos[j].copy(), quat_normalize(odom_quat[j]), True
    i = j - 1; t0, t1 = odom_t[i], odom_t[i+1]; gap = t1 - t0
    if max_gap is not None and gap > max_gap: return None, None, False
    u = (tq - t0) / gap
    return odom_pos[i] + u*(odom_pos[i+1]-odom_pos[i]), quat_slerp(odom_quat[i], odom_quat[i+1], u), True

def read_bag(bag_path, odom_topic, image_topic):
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore
    odom_ns, opos, oquat, img_ns = [], [], [], []
    _ts = get_typestore(Stores.ROS2_HUMBLE)
    with AnyReader([Path(bag_path)], default_typestore=_ts) as reader:
        conns_o = [c for c in reader.connections if c.topic == odom_topic]
        conns_i = [c for c in reader.connections if c.topic == image_topic]
        if not conns_o: raise RuntimeError("odom topic %s not in bag" % odom_topic)
        if not conns_i: raise RuntimeError("image topic %s not in bag" % image_topic)
        for con, bt, raw in reader.messages(connections=conns_o):
            m = reader.deserialize(raw, con.msgtype)
            odom_ns.append(bt); p = m.pose.pose.position; q = m.pose.pose.orientation
            opos.append([p.x, p.y, p.z]); oquat.append([q.x, q.y, q.z, q.w])
        for con, bt, raw in reader.messages(connections=conns_i):
            img_ns.append(bt)
    odom_ns = np.array(odom_ns, np.int64); img_ns = np.array(img_ns, np.int64)
    t0 = odom_ns.min()
    return (odom_ns-t0)/1e9, np.array(opos), np.array(oquat), (img_ns-t0)/1e9

# ============================ topic auto-detect + decode ============================
def list_image_topics(bag_path):
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore
    with AnyReader([Path(bag_path)], default_typestore=get_typestore(Stores.ROS2_HUMBLE)) as r:
        cnt = {}
        for c in r.connections:
            if 'Image' in c.msgtype:
                cnt[c.topic] = cnt.get(c.topic, 0) + c.msgcount
    return cnt

def decode_selected(bag_path, image_topic, want_order, out_dir):
    """want_order: dict {bag_image_index -> output_rank}. Decodes only those frames."""
    import cv2
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore
    n = 0; done = 0
    with AnyReader([Path(bag_path)], default_typestore=get_typestore(Stores.ROS2_HUMBLE)) as reader:
        conns = [c for c in reader.connections if c.topic == image_topic]
        for con, _, raw in reader.messages(connections=conns):
            if n in want_order:
                m = reader.deserialize(raw, con.msgtype)
                if 'CompressedImage' in con.msgtype:
                    img = cv2.imdecode(np.frombuffer(bytes(m.data), np.uint8), cv2.IMREAD_COLOR)
                else:
                    buf = np.frombuffer(bytes(m.data), np.uint8); enc = m.encoding.lower()
                    if enc in ('bgr8','rgb8'):
                        img = buf.reshape(m.height, m.width, 3)
                        if enc == 'rgb8': img = img[:, :, ::-1]
                    elif enc == 'mono8':
                        img = cv2.cvtColor(buf.reshape(m.height, m.width), cv2.COLOR_GRAY2BGR)
                    elif enc in ('yuv422','uyvy'):
                        img = cv2.cvtColor(buf.reshape(m.height, m.width, 2), cv2.COLOR_YUV2BGR_UYVY)
                    elif enc in ('yuv422_yuy2','yuyv'):
                        img = cv2.cvtColor(buf.reshape(m.height, m.width, 2), cv2.COLOR_YUV2BGR_YUY2)
                    else:
                        raise RuntimeError("unhandled encoding '%s' -- tell Claude" % enc)
                if img is None: raise RuntimeError("frame %d failed to decode" % n)
                cv2.imwrite(os.path.join(out_dir, "img_%03d.jpg" % want_order[n]), img,
                            [cv2.IMWRITE_JPEG_QUALITY, 92])
                done += 1
            n += 1
    return done

# ============================ main ============================
BAG = sys.argv[1] if len(sys.argv) > 1 else None
NKEY = int(sys.argv[2]) if len(sys.argv) > 2 else 40
IMGTOPIC = sys.argv[3] if len(sys.argv) > 3 else None
if not BAG: raise SystemExit("usage: python3 make_full_pan_anchor.py <BAG_DIR> [NKEY] [IMAGE_TOPIC]")

if IMGTOPIC is None:
    cand = list_image_topics(BAG)
    if not cand: raise SystemExit("no Image topics in bag")
    comp = [t for t in cand if 'compress' in t.lower()]
    IMGTOPIC = (comp[0] if comp else max(cand, key=cand.get))
    print("[auto] image topic: %s   (candidates: %s)" % (IMGTOPIC, dict(cand)))

print("[1/5] reading bag:", BAG)
odom_t, opos, oquat, image_t = read_bag(BAG, "/aft_mapped_to_init", IMGTOPIC)
print("      odom %d msgs @ %.0f Hz | images %d over %.1fs"
      % (len(odom_t), len(odom_t)/max(1e-9, odom_t[-1]-odom_t[0]), len(image_t), image_t.max()-image_t.min()))

print("[2/5] matching every frame to a pose")
order = np.argsort(odom_t); odom_t, opos, oquat = odom_t[order], opos[order], oquat[order]
keep = np.concatenate([[True], np.diff(odom_t) > 0]); odom_t, opos, oquat = odom_t[keep], opos[keep], oquat[keep]
pos = np.full((len(image_t),3), np.nan); quat = np.full((len(image_t),4), np.nan); ok = np.zeros(len(image_t), bool)
for k, ti in enumerate(image_t):
    p, q, good = interpolate_pose(odom_t, opos, oquat, ti, max_gap=0.5)
    if good: pos[k] = p; quat[k] = q; ok[k] = True
print("      poseable: %d / %d (%.0f%%)" % (ok.sum(), len(ok), 100*ok.mean()))

print("[3/5] selecting %d frames spread by HEADING" % NKEY)
okidx = np.where(ok)[0]
yaw = np.degrees(np.arctan2(2*(quat[okidx,3]*quat[okidx,2] + quat[okidx,0]*quat[okidx,1]),
                            1 - 2*(quat[okidx,1]**2 + quat[okidx,2]**2))) % 360.0
bins = np.linspace(0, 360, NKEY+1); sel = []
for b in range(NKEY):
    m = (yaw >= bins[b]) & (yaw < bins[b+1])
    if m.any():
        c = (bins[b]+bins[b+1])/2.0
        sel.append(okidx[np.where(m)[0][np.argmin(np.abs(yaw[m]-c))]])
sel = np.array(sorted(set(sel)))
selyaw = np.degrees(np.arctan2(2*(quat[sel,3]*quat[sel,2] + quat[sel,0]*quat[sel,1]),
                               1 - 2*(quat[sel,1]**2 + quat[sel,2]**2))) % 360.0
so = np.argsort(selyaw); sel = sel[so]                 # order output by heading
s = np.sort(selyaw); gap = np.diff(np.r_[s, s[0]+360]); cov = 360 - gap.max()
print("      selected %d frames, heading COVERAGE=%.0f deg" % (len(sel), cov))

print("[4/5] decoding the %d selected frames" % len(sel))
OUT = "/tmp/panbundle"
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT + "/frames")
want = {int(b): i for i, b in enumerate(sel)}
nd = decode_selected(BAG, IMGTOPIC, want, OUT + "/frames")
R = np.array([quat_to_R(quat[i]) for i in sel])
np.savez(OUT + "/poses.npz", pos=pos[sel], R=R, quat=quat[sel],
         ok=np.ones(len(sel), bool), image_t=image_t[sel], sel_bag_idx=sel, sel_yaw=selyaw[so],
         convention="T_lidar_in_map (body->map); full-pan heading-spread for 360 colour; extrinsic applied downstream by per_shot_texture")

print("[5/5] taring")
with tarfile.open("/tmp/panbundle.tar.gz", "w:gz") as t:
    t.add(OUT, arcname="panbundle")
mb = os.path.getsize("/tmp/panbundle.tar.gz")/1e6
print("DONE -> /tmp/panbundle.tar.gz  (%.1f MB)  frames=%d  heading-coverage=%.0f deg" % (mb, nd, cov))
print("Upload /tmp/panbundle.tar.gz to the chat.")
