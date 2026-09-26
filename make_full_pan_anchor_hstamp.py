#!/usr/bin/env python3
"""
make_full_pan_anchor_hstamp.py -- HEADER.STAMP build (2026-09-25).

WHY THIS EXISTS (supersedes the tau build for this test):
  ts_probe on plio_texcap_20260924_141733 measured the camera's
  (bag_receive_time - header.stamp) at +16..+42 s, GROWING through the capture
  (std 7.97s, spread 25.58s), while odom/IMU were sub-100ms and tight. The old
  read_bag associated frames->poses on BAG time -> every photo was matched to a
  pose 16-42 s away = near-random. That, not drift or extrinsic, is what wrecked
  the 141733 texture.

  The growing offset is a DELIVERY backlog (compressed camera ~25% behind real
  time), which means header.stamp is almost certainly the TRUE capture time on the
  same clock as odom. So this build associates on header.stamp and can RECOVER the
  existing bag with no re-capture.

  A constant tau CANNOT fix a 25 s spread, so tau defaults to 0.0 here (change ONE
  thing: prove header.stamp alone recovers the image). Layer the ~0.18 s hardware
  tau back on AFTER, via PAN_TAU_S, once header.stamp is proven.

SELF-VALIDATION: before it trusts anything, it prints, for camera and odom:
  (bag-header) stats [reproduces the probe], epoch sanity, header monotonicity,
  and the camera-header vs odom-header time OVERLAP. If header.stamp looks wrong
  (non-monotonic, wrong epoch, or ~0% overlap) it WARNS and, only if you ask
  (ASSOC=bag), falls back to bag time. Default assoc = header.stamp.

RUN on the Jetson (reads the bag only; L2 off; no Point-LIO):
    python3 make_full_pan_anchor_hstamp.py <BAG_DIR> [NKEY] [IMAGE_TOPIC]
    ASSOC=bag python3 ...        # force old bag-time behaviour (A/B)
    PAN_TAU_S=0.18 python3 ...   # add the hardware tau on top of header.stamp
OUTPUT: /tmp/panbundle.tar.gz  -> upload to chat, then fuse_pano on the station.
"""
import sys, os, shutil, tarfile
import numpy as np
from pathlib import Path

TAU   = float(os.environ.get("PAN_TAU_S", "0.0"))     # 0 for the clean header.stamp test
ASSOC = os.environ.get("ASSOC", "header").lower()      # 'header' (default) or 'bag'

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

def _stamp_s(m):
    return m.header.stamp.sec + m.header.stamp.nanosec * 1e-9

def read_bag(bag_path, odom_topic, image_topic):
    """Return BOTH clocks (raw seconds, not rebased): header.stamp and bag time."""
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore
    odom_hs, odom_bt, opos, oquat = [], [], [], []
    img_hs, img_bt = [], []
    _ts = get_typestore(Stores.ROS2_HUMBLE)
    with AnyReader([Path(bag_path)], default_typestore=_ts) as reader:
        conns_o = [c for c in reader.connections if c.topic == odom_topic]
        conns_i = [c for c in reader.connections if c.topic == image_topic]
        if not conns_o: raise RuntimeError("odom topic %s not in bag" % odom_topic)
        if not conns_i: raise RuntimeError("image topic %s not in bag" % image_topic)
        for con, bt, raw in reader.messages(connections=conns_o):
            m = reader.deserialize(raw, con.msgtype)
            odom_bt.append(bt * 1e-9); odom_hs.append(_stamp_s(m))
            p = m.pose.pose.position; q = m.pose.pose.orientation
            opos.append([p.x, p.y, p.z]); oquat.append([q.x, q.y, q.z, q.w])
        for con, bt, raw in reader.messages(connections=conns_i):
            m = reader.deserialize(raw, con.msgtype)   # need the header now
            img_bt.append(bt * 1e-9); img_hs.append(_stamp_s(m))
    return (np.array(odom_hs), np.array(odom_bt), np.array(opos), np.array(oquat),
            np.array(img_hs), np.array(img_bt))

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
                        raise RuntimeError("unhandled encoding '%s'" % enc)
                if img is None: raise RuntimeError("frame %d failed to decode" % n)
                cv2.imwrite(os.path.join(out_dir, "img_%03d.jpg" % want_order[n]), img,
                            [cv2.IMWRITE_JPEG_QUALITY, 92])
                done += 1
            n += 1
    return done

def _stats(name, d):
    print("   %-7s n=%-5d median=%+.4f mean=%+.4f std=%.4f min=%+.4f max=%+.4f spread=%.4f"
          % (name, len(d), np.median(d), d.mean(), d.std(), d.min(), d.max(), d.max()-d.min()))

# ============================ main ============================
BAG = sys.argv[1] if len(sys.argv) > 1 else None
NKEY = int(sys.argv[2]) if len(sys.argv) > 2 else 40
IMGTOPIC = sys.argv[3] if len(sys.argv) > 3 else None
if not BAG: raise SystemExit("usage: python3 make_full_pan_anchor_hstamp.py <BAG_DIR> [NKEY] [IMAGE_TOPIC]")

if IMGTOPIC is None:
    cand = list_image_topics(BAG)
    if not cand: raise SystemExit("no Image topics in bag")
    comp = [t for t in cand if 'compress' in t.lower()]
    IMGTOPIC = (comp[0] if comp else max(cand, key=cand.get))
    print("[auto] image topic: %s   (candidates: %s)" % (IMGTOPIC, dict(cand)))

print("[1/6] reading bag (both clocks):", BAG)
odom_hs, odom_bt, opos, oquat, img_hs, img_bt = read_bag(BAG, "/aft_mapped_to_init", IMGTOPIC)

print("[2/6] CLOCK VALIDATION  (assoc mode = %s ; tau = %+.3fs)" % (ASSOC, TAU))
_stats("CAM b-h", img_bt - img_hs)
_stats("ODM b-h", odom_bt - odom_hs)
cam_epoch_ok = bool(1.0e9 < np.median(img_hs) < 2.0e9)
mono = bool(np.all(np.diff(np.sort(img_hs)) >= 0))
ov_lo = max(img_hs.min(), odom_hs.min()); ov_hi = min(img_hs.max(), odom_hs.max())
overlap = max(0.0, ov_hi - ov_lo)
in_win = int(((img_hs >= odom_hs.min()) & (img_hs <= odom_hs.max())).sum())
print("   camera header epoch ~unix: %s | header monotonic: %s" % (cam_epoch_ok, mono))
print("   odom header range:   %.1f .. %.1f  (%.1fs)" % (odom_hs.min(), odom_hs.max(), odom_hs.max()-odom_hs.min()))
print("   camera header range: %.1f .. %.1f  (%.1fs)" % (img_hs.min(), img_hs.max(), img_hs.max()-img_hs.min()))
print("   header/header OVERLAP: %.1fs | camera frames inside odom window: %d/%d" % (overlap, in_win, len(img_hs)))
if ASSOC == "header" and (not cam_epoch_ok or not mono or in_win == 0):
    print("   !! WARNING: camera header.stamp looks UNTRUSTWORTHY (epoch/mono/overlap).")
    print("   !! Not falling back automatically. Re-run with ASSOC=bag to compare, and tell Claude.")

# choose association clock
if ASSOC == "bag":
    img_t_raw, odom_t_raw = img_bt, odom_bt
else:
    img_t_raw, odom_t_raw = img_hs, odom_hs
t0 = odom_t_raw.min()
image_t = img_t_raw - t0
odom_t  = odom_t_raw - t0
print("      odom %d msgs @ %.0f Hz | images %d over %.1fs"
      % (len(odom_t), len(odom_t)/max(1e-9, odom_t[-1]-odom_t[0]), len(image_t), image_t.max()-image_t.min()))

print("[3/6] matching every frame to a pose on %s clock (+tau %+.3fs)" % (ASSOC, TAU))
order = np.argsort(odom_t); odom_t, opos, oquat = odom_t[order], opos[order], oquat[order]
keep = np.concatenate([[True], np.diff(odom_t) > 0]); odom_t, opos, oquat = odom_t[keep], opos[keep], oquat[keep]
pos = np.full((len(image_t),3), np.nan); quat = np.full((len(image_t),4), np.nan); ok = np.zeros(len(image_t), bool)
for k, ti in enumerate(image_t):
    p, q, good = interpolate_pose(odom_t, opos, oquat, ti + TAU, max_gap=0.5)
    if good: pos[k] = p; quat[k] = q; ok[k] = True
print("      poseable: %d / %d (%.0f%%)   [old bag-assoc on this bag ~ near-random]" % (ok.sum(), len(ok), 100*ok.mean()))
if ok.sum() < 8:
    print("   !! too few poseable frames -- header.stamp assoc did not land in the odom window.")
    print("   !! inspect the CLOCK VALIDATION block above and tell Claude before trusting any render.")

print("[4/6] selecting %d frames spread by HEADING" % NKEY)
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
so = np.argsort(selyaw); sel = sel[so]
s = np.sort(selyaw); gap = np.diff(np.r_[s, s[0]+360]); cov = 360 - gap.max()
print("      selected %d frames, heading COVERAGE=%.0f deg" % (len(sel), cov))

print("[5/6] decoding the %d selected frames" % len(sel))
OUT = "/tmp/panbundle"
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT + "/frames")
want = {int(b): i for i, b in enumerate(sel)}
nd = decode_selected(BAG, IMGTOPIC, want, OUT + "/frames")
R = np.array([quat_to_R(quat[i]) for i in sel])
np.savez(OUT + "/poses.npz", pos=pos[sel], R=R, quat=quat[sel],
         ok=np.ones(len(sel), bool), image_t=image_t[sel], sel_bag_idx=sel, sel_yaw=selyaw[so],
         assoc=ASSOC, tau_s=TAU,
         convention="T_lidar_in_map (body->map); assoc on %s clock; extrinsic downstream" % ASSOC)

print("[6/6] taring")
with tarfile.open("/tmp/panbundle.tar.gz", "w:gz") as t:
    t.add(OUT, arcname="panbundle")
mb = os.path.getsize("/tmp/panbundle.tar.gz")/1e6
print("DONE -> /tmp/panbundle.tar.gz  (%.1f MB)  frames=%d  coverage=%.0f deg  assoc=%s  tau=%+.3fs"
      % (mb, nd, cov, ASSOC, TAU))
print("Upload /tmp/panbundle.tar.gz to the chat; then fuse_pano on the station.")
