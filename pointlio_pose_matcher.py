#!/usr/bin/env python3
"""
pointlio_pose_matcher.py  —  TEXTURE BRIDGE, PIECE 2 (pose matcher)
===================================================================
Recovers WHERE THE CAMERA WAS, in the Point-LIO map frame, at the instant each
camera image was taken. RTAB used to store that pairing in a .db; Point-LIO does
not, so we reconstruct it from the odometry stream + the images' timestamps.

INPUT  : a ROS2 bag containing
           /aft_mapped_to_init   (nav_msgs/Odometry)  = LiDAR-body pose in map, timestamped
           /image_raw            (sensor_msgs/Image)  = camera frames, timestamped
OUTPUT : posed_images.npz  — for each image: its stamp + the interpolated
           LiDAR-BODY-IN-MAP pose (position + quaternion + 3x3 R), plus a validity mask.

*** CONVENTION — READ THIS (the one handoff line to lock) ***
This matcher outputs T_lidar_in_map  (a.k.a. body->map: takes a point in the LiDAR
body frame and expresses it in the map frame). It does NOT apply the camera<->LiDAR
extrinsic. per_shot_texture.compose_world_to_cam is documented to apply the extrinsic
ITSELF (verified to 1e-16 per the master reference), so applying it here too would
double-apply it. Before wiring into Piece 3, CONFIRM against the real per_shot_texture.py:
  - if best_image_per_face wants the LiDAR-body-in-map pose  -> feed this output as-is.
  - if it wants the CAMERA-in-map pose already               -> set APPLY_EXTRINSIC=True
    below (it composes T_cam_in_map = T_lidar_in_map @ inv(T_lidar_to_cam); note the
    INVERSE — our extrinsic stores lidar->cam, the pose needs cam-in-lidar = its inverse).
This file makes that a ONE-FLAG change, not a rewrite.

The interpolation core (quaternion SLERP + position LERP + bracket search) is
UNIT-TESTED against an analytic constant-velocity trajectory — see selftest().
The bag-reading I/O layer is written but UNVALIDATED until run on a real Point-LIO bag.
"""
import argparse
import json
import os
import numpy as np

# =====================================================================================
# CORE MATH  (pure numpy, no ROS — this is the part proven by selftest())
# =====================================================================================

def quat_normalize(q):
    q = np.asarray(q, dtype=np.float64)
    n = np.linalg.norm(q)
    if n < 1e-12:
        raise ValueError("zero-norm quaternion")
    return q / n


def quat_slerp(q0, q1, u):
    """Shortest-path SLERP between two (x,y,z,w) quaternions at fraction u in [0,1].
    Handles the quaternion double-cover (q and -q are the same rotation) by flipping
    q1 when the dot product is negative, so we always take the short arc."""
    q0 = quat_normalize(q0)
    q1 = quat_normalize(q1)
    dot = float(np.dot(q0, q1))
    if dot < 0.0:            # double-cover: take the short way round
        q1 = -q1
        dot = -dot
    dot = min(1.0, max(-1.0, dot))
    # Well-conditioned angle: |q1 - dot*q0| = sin(theta0) exactly (unit quats), and
    # atan2(sin0, dot) stays accurate for small angles where arccos(dot) would not.
    perp = q1 - dot * q0
    sin0 = float(np.linalg.norm(perp))
    if sin0 < 1e-12:        # GENUINELY parallel (theta~0) -> LERP avoids 0/0 only here.
        return quat_normalize(q0 + u * (q1 - q0))
    theta0 = np.arctan2(sin0, dot)
    s0 = np.sin((1.0 - u) * theta0) / sin0
    s1 = np.sin(u * theta0) / sin0
    return quat_normalize(s0 * q0 + s1 * q1)


def quat_to_R(q):
    """(x,y,z,w) -> 3x3 rotation matrix."""
    x, y, z, w = quat_normalize(q)
    return np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - z*w),     2*(x*z + y*w)],
        [    2*(x*y + z*w), 1 - 2*(x*x + z*z),     2*(y*z - x*w)],
        [    2*(x*z - y*w),     2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ], dtype=np.float64)


def interpolate_pose(odom_t, odom_pos, odom_quat, t_query, max_gap=None):
    """Interpolate the body pose at t_query from a sorted odometry stream.
    odom_t     : (M,)   strictly increasing times (seconds)
    odom_pos   : (M,3)  positions
    odom_quat  : (M,4)  (x,y,z,w) quaternions
    Returns (pos(3,), quat(4,), ok(bool), reason(str)).
      ok=False when t_query is outside the odometry span, or the bracketing gap
      exceeds max_gap (a stale-bracket guard — do NOT texture across a tracking hole)."""
    M = len(odom_t)
    if M == 0:
        return None, None, False, "empty odometry"
    if t_query < odom_t[0] or t_query > odom_t[-1]:
        return None, None, False, "out of odometry time span"
    # exact-hit shortcut
    j = int(np.searchsorted(odom_t, t_query))
    if j < M and odom_t[j] == t_query:
        return odom_pos[j].copy(), quat_normalize(odom_quat[j]), True, "exact"
    i = j - 1                       # bracket [i, i+1]
    t0, t1 = odom_t[i], odom_t[i + 1]
    gap = t1 - t0
    if max_gap is not None and gap > max_gap:
        return None, None, False, "bracket gap %.3fs > max_gap %.3fs" % (gap, max_gap)
    u = (t_query - t0) / gap
    pos = odom_pos[i] + u * (odom_pos[i + 1] - odom_pos[i])          # LERP
    quat = quat_slerp(odom_quat[i], odom_quat[i + 1], u)             # SLERP
    return pos, quat, True, "interp u=%.4f gap=%.3fs" % (u, gap)


def match_images_to_poses(odom_t, odom_pos, odom_quat, image_t, max_gap=None):
    """For each image time, interpolate the body pose. Returns a dict of arrays."""
    order = np.argsort(odom_t)                     # ensure sorted
    odom_t = np.asarray(odom_t, float)[order]
    odom_pos = np.asarray(odom_pos, float)[order]
    odom_quat = np.asarray(odom_quat, float)[order]
    if np.any(np.diff(odom_t) <= 0):
        # collapse exact-duplicate stamps (keep first); reject true non-monotonic
        keep = np.concatenate([[True], np.diff(odom_t) > 0])
        odom_t, odom_pos, odom_quat = odom_t[keep], odom_pos[keep], odom_quat[keep]

    n = len(image_t)
    out_pos = np.full((n, 3), np.nan)
    out_quat = np.full((n, 4), np.nan)
    out_R = np.full((n, 3, 3), np.nan)
    ok = np.zeros(n, bool)
    reasons = []
    for k, ti in enumerate(image_t):
        p, q, good, why = interpolate_pose(odom_t, odom_pos, odom_quat, ti, max_gap)
        reasons.append(why)
        if good:
            out_pos[k] = p
            out_quat[k] = q
            out_R[k] = quat_to_R(q)
            ok[k] = True
    return dict(image_t=np.asarray(image_t, float), pos=out_pos, quat=out_quat,
                R=out_R, ok=ok, reasons=reasons)


# Optional downstream convenience (OFF by default — see the CONVENTION note at top).
APPLY_EXTRINSIC = False

def compose_cam_in_map(R_lidar_in_map, t_lidar_in_map, R_lidar_to_cam, t_lidar_to_cam):
    """T_cam_in_map = T_lidar_in_map @ inv(T_lidar_to_cam).
    Our extrinsic stores lidar->cam; the camera's pose in the lidar frame is its INVERSE."""
    R_cam_in_lidar = R_lidar_to_cam.T
    t_cam_in_lidar = -R_lidar_to_cam.T @ t_lidar_to_cam
    R = R_lidar_in_map @ R_cam_in_lidar
    t = R_lidar_in_map @ t_cam_in_lidar + t_lidar_in_map
    return R, t


# =====================================================================================
# I/O LAYER  (rosbags — WRITTEN, but UNVALIDATED until run on a real Point-LIO bag)
# =====================================================================================

def _stamp_to_sec(stamp):
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)   # integer nanoseconds

def read_bag(bag_path, odom_topic='/aft_mapped_to_init', image_topic='/image_raw'):
    """Read odometry + image stamps from a ROS2 bag. Times are returned in seconds,
    rebased to the first odometry stamp (preserves nanosecond precision as float64)."""
    from rosbags.highlevel import AnyReader
    from pathlib import Path
    odom_ns, opos, oquat, img_ns = [], [], [], []
    with AnyReader([Path(bag_path)]) as reader:
        conns_o = [c for c in reader.connections if c.topic == odom_topic]
        conns_i = [c for c in reader.connections if c.topic == image_topic]
        if not conns_o:
            raise RuntimeError("odom topic %s not in bag (have: %s)"
                               % (odom_topic, sorted({c.topic for c in reader.connections})))
        for con, _, raw in reader.messages(connections=conns_o):
            m = reader.deserialize(raw, con.msgtype)
            odom_ns.append(_stamp_to_sec(m.header.stamp))
            p = m.pose.pose.position
            q = m.pose.pose.orientation
            opos.append([p.x, p.y, p.z])
            oquat.append([q.x, q.y, q.z, q.w])
        for con, _, raw in reader.messages(connections=conns_i):
            m = reader.deserialize(raw, con.msgtype)
            img_ns.append(_stamp_to_sec(m.header.stamp))
    odom_ns = np.array(odom_ns, dtype=np.int64)
    img_ns = np.array(img_ns, dtype=np.int64)
    if len(odom_ns) == 0:
        raise RuntimeError("no odometry messages read")
    t0 = odom_ns.min()
    odom_t = (odom_ns - t0) / 1e9
    image_t = (img_ns - t0) / 1e9
    return odom_t, np.array(opos), np.array(oquat), image_t


# =====================================================================================
# SELFTEST  (proves the CORE math cold — no ROS, no bag, no rig)
# =====================================================================================

def selftest():
    """Proves interpolation + composition against an ANALYTIC constant-velocity
    trajectory, where LERP (straight-line translation) and SLERP (constant-rate
    rotation) are both mathematically EXACT -> correct code recovers ground truth to
    machine precision. Run: python3 pointlio_pose_matcher.py --selftest"""
    def R_to_quat(R):
        t = np.trace(R)
        if t > 0:
            s = np.sqrt(t+1)*2; w=.25*s; x=(R[2,1]-R[1,2])/s; y=(R[0,2]-R[2,0])/s; z=(R[1,0]-R[0,1])/s
        elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
            s = np.sqrt(1+R[0,0]-R[1,1]-R[2,2])*2; w=(R[2,1]-R[1,2])/s; x=.25*s; y=(R[0,1]+R[1,0])/s; z=(R[0,2]+R[2,0])/s
        elif R[1,1] > R[2,2]:
            s = np.sqrt(1+R[1,1]-R[0,0]-R[2,2])*2; w=(R[0,2]-R[2,0])/s; x=(R[0,1]+R[1,0])/s; y=.25*s; z=(R[1,2]+R[2,1])/s
        else:
            s = np.sqrt(1+R[2,2]-R[0,0]-R[1,1])*2; w=(R[1,0]-R[0,1])/s; x=(R[0,2]+R[2,0])/s; y=(R[1,2]+R[2,1])/s; z=.25*s
        return quat_normalize([x, y, z, w])
    def aa(axis, ang):
        a = np.asarray(axis, float); a /= np.linalg.norm(a)
        K = np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]])
        return np.eye(3) + np.sin(ang)*K + (1-np.cos(ang))*(K@K)
    rng = np.random.default_rng(42)
    axis=np.array([.2,.3,1.]); omega=.9; vel=np.array([.4,-.15,.05]); p0=np.array([1.,2.,-.5]); R0=aa([1,.2,0],.3)
    gt = lambda t: (p0+vel*t, R_to_quat(aa(axis, omega*t)@R0))
    ts = np.unique(np.sort(rng.uniform(0,5,300)))
    opos = np.array([gt(t)[0] for t in ts]); oquat = np.array([gt(t)[1] for t in ts])
    tq = rng.uniform(ts[1], ts[-2], 500); pe=[]; qe=[]
    for t in tq:
        p,q,ok,_ = interpolate_pose(ts,opos,oquat,t,max_gap=1.0); pg,qg = gt(t)
        pe.append(np.linalg.norm(p-pg)); d=min(1,abs(np.dot(quat_normalize(q),qg))); qe.append(np.degrees(2*np.arccos(d)))
    assert max(pe)<1e-9 and max(qe)<1e-8, "interpolation not exact"
    print("TEST 1  PASS  const-velocity interp exact (pos %.1e m, rot %.1e deg)" % (max(pe), max(qe)))
    _,_,ok,why = interpolate_pose(ts,opos,oquat,ts[123],max_gap=1.0); assert ok and why=="exact"; print("TEST 2  PASS  exact-stamp hit")
    assert not interpolate_pose(ts,opos,oquat,ts[0]-.1)[2] and not interpolate_pose(ts,opos,oquat,ts[-1]+.1)[2]; print("TEST 3  PASS  out-of-span dropped")
    assert not interpolate_pose(np.array([0,.1,2.,2.1]),np.zeros((4,3)),np.tile([0,0,0,1.],(4,1)),1.0,max_gap=.5)[2]; print("TEST 4  PASS  max_gap guard")
    q0=quat_normalize([0,0,0,1]); q1=quat_normalize([0,0,np.sin(.1),np.cos(.1)])
    assert np.degrees(2*np.arccos(min(1,abs(np.dot(quat_slerp(q0,-q1,.5),quat_slerp(q0,q1,.5))))))<1e-9; print("TEST 5  PASS  SLERP short-arc (double cover)")
    R_l2c=aa([.02,.07,.99],1.49); t_l2c=np.array([.0183,-.0536,-.1596]); R_lim=aa([.1,.9,.2],.7); t_lim=np.array([3.,1.,-2.])
    R_cim,t_cim = compose_cam_in_map(R_lim,t_lim,R_l2c,t_l2c); pw=np.array([1.2,-.4,2.5])
    e6 = np.linalg.norm((R_l2c@(R_lim.T@(pw-t_lim))+t_l2c)-(R_cim.T@(pw-t_cim))); assert e6<1e-12; print("TEST 6  PASS  extrinsic inverse-compose consistent (%.1e)" % e6)
    res = match_images_to_poses(ts,opos,oquat,np.concatenate([rng.uniform(.5,2,20),[ts.max()+1]]),max_gap=.3)
    assert res["ok"][-1]==False; print("TEST 7  PASS  end-to-end match (%d matched, out-of-span dropped)" % int(res["ok"].sum()))
    print("\nALL 7 TESTS PASS.")


def dump_frames(bag_path, image_topic, out_dir):
    """Decode each image message to out_dir/img_{idx:05d}.png, in the SAME order the
    stamps were read, so PNG index == matcher entry index (Piece 3 relies on this).
    Handles sensor_msgs/Image (bgr8/rgb8/mono8) and sensor_msgs/CompressedImage (mjpeg).
    UNVALIDATED until run on a real bag — decode paths are written to spec, not tested."""
    import cv2
    from rosbags.highlevel import AnyReader
    from pathlib import Path
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    with AnyReader([Path(bag_path)]) as reader:
        conns = [c for c in reader.connections if c.topic == image_topic]
        for con, _, raw in reader.messages(connections=conns):
            m = reader.deserialize(raw, con.msgtype)
            if 'CompressedImage' in con.msgtype:
                arr = np.frombuffer(bytes(m.data), np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            else:
                buf = np.frombuffer(bytes(m.data), np.uint8)
                enc = m.encoding.lower()
                if enc in ('bgr8', 'rgb8'):
                    img = buf.reshape(m.height, m.width, 3)
                    if enc == 'rgb8':
                        img = img[:, :, ::-1]
                elif enc in ('mono8',):
                    img = cv2.cvtColor(buf.reshape(m.height, m.width), cv2.COLOR_GRAY2BGR)
                else:
                    raise RuntimeError("unhandled image encoding '%s' — add a decode branch" % enc)
            cv2.imwrite(os.path.join(out_dir, "img_%05d.png" % n), img)
            n += 1
    print("dumped %d frames to %s" % (n, out_dir))
    return n


def main():
    ap = argparse.ArgumentParser(description="Match camera images to Point-LIO poses (Piece 2).")
    ap.add_argument("bag", nargs="?", help="path to the ROS2 bag directory")
    ap.add_argument("--selftest", action="store_true", help="run the built-in math proof and exit")
    ap.add_argument("-o", "--out", default="posed_images.npz")
    ap.add_argument("--odom-topic", default="/aft_mapped_to_init")
    ap.add_argument("--image-topic", default="/image_raw")
    ap.add_argument("--max-gap", type=float, default=0.5,
                    help="reject images whose bracketing odometry gap exceeds this (s)")
    ap.add_argument("--dump-frames", metavar="DIR", default=None,
                    help="also decode the bag's image frames to DIR/img_00000.png ... "
                         "(index-aligned with the matcher output, for Piece 3)")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.bag:
        ap.error("bag path required (or pass --selftest)")

    odom_t, opos, oquat, image_t = read_bag(args.bag, args.odom_topic, args.image_topic)
    print("odometry msgs: %d  span %.2fs @ %.1f Hz" %
          (len(odom_t), odom_t[-1] - odom_t[0], len(odom_t) / max(1e-9, odom_t[-1] - odom_t[0])))
    print("image msgs:    %d  span %.2fs" % (len(image_t), image_t.max() - image_t.min()))

    res = match_images_to_poses(odom_t, opos, oquat, image_t, max_gap=args.max_gap)
    n_ok = int(res["ok"].sum())
    print("matched: %d / %d images (%.0f%%)" % (n_ok, len(image_t), 100 * n_ok / max(1, len(image_t))))
    dropped = np.where(~res["ok"])[0]
    if len(dropped):
        print("dropped %d — first few reasons:" % len(dropped))
        for k in dropped[:5]:
            print("  image[%d] t=%.3fs : %s" % (k, res["image_t"][k], res["reasons"][k]))

    np.savez(args.out, image_t=res["image_t"], pos=res["pos"], quat=res["quat"],
             R=res["R"], ok=res["ok"],
             convention="T_lidar_in_map (body->map); extrinsic applied downstream by per_shot_texture")
    print("wrote", args.out, "(convention: T_lidar_in_map — extrinsic applied downstream)")

    if args.dump_frames:
        ndump = dump_frames(args.bag, args.image_topic, args.dump_frames)
        if ndump != len(image_t):
            print("WARN: dumped %d frames but read %d image stamps — index alignment "
                  "may be off; investigate before texturing." % (ndump, len(image_t)))


if __name__ == "__main__":
    main()
