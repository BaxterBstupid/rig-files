#!/usr/bin/env python3
"""
pointlio_pose_matcher.py  —  TEXTURE BRIDGE, PIECE 2 (pose matcher)   [v2 — GATED]
===================================================================
Recovers WHERE THE CAMERA WAS, in the Point-LIO map frame, at the instant each
camera image was taken. RTAB used to store that pairing in a .db; Point-LIO does
not, so we reconstruct it from the odometry stream + the images' timestamps.

v2 CHANGE (2026-09-23, ADR-002):  a FAIL-CLOSED TEXTURE-COVERAGE GATE.
  The interpolation MATH is unchanged (proven exact by selftest, 9e-9 m). What v1
  did wrong was write its .npz even at 42% coverage — the baker would then paint a
  patchy room onto perfect geometry (the fusioncap_130955 blocking defect). v2
  evaluates coverage AFTER matching and, on failure, prints a verdict and REFUSES to
  write the pose set (exit 2). Pass --force for a deliberate partial bake.
  Gate fails if: matched% < --min-match, OR images fall outside the odom span, OR an
  in-run odom hole exceeds --max-hole. A raw-recorded (odom-starved) bag fails here.

INPUT  : a ROS2 bag containing
           /aft_mapped_to_init   (nav_msgs/Odometry)  = LiDAR-body pose in map, timestamped
           <image topic>         (sensor_msgs/Image OR .../CompressedImage), timestamped
OUTPUT : posed_images.npz  — for each image: its stamp + the interpolated
           LiDAR-BODY-IN-MAP pose (position + quaternion + 3x3 R), plus a validity mask.
           (Only written if the coverage gate passes, or --force is given.)

*** CONVENTION — READ THIS (the one handoff line to lock) ***
This matcher outputs T_lidar_in_map  (a.k.a. body->map). It does NOT apply the
camera<->LiDAR extrinsic. per_shot_texture.compose_world_to_cam is documented to apply
the extrinsic ITSELF, so applying it here too would double-apply it. Before wiring into
Piece 3, CONFIRM against the real per_shot_texture.py (ADR-001 open item — the extrinsic
must be applied EXACTLY once across matcher->baker):
  - if best_image_per_face wants the LiDAR-body-in-map pose  -> feed this output as-is.
  - if it wants the CAMERA-in-map pose already               -> set APPLY_EXTRINSIC=True.
"""
import argparse
import json
import os
import sys
import numpy as np

# =====================================================================================
# CORE MATH  (pure numpy, no ROS — this is the part proven by selftest())  [UNCHANGED]
# =====================================================================================

def quat_normalize(q):
    q = np.asarray(q, dtype=np.float64)
    n = np.linalg.norm(q)
    if n < 1e-12:
        raise ValueError("zero-norm quaternion")
    return q / n


def quat_slerp(q0, q1, u):
    """Shortest-path SLERP between two (x,y,z,w) quaternions at fraction u in [0,1]."""
    q0 = quat_normalize(q0)
    q1 = quat_normalize(q1)
    dot = float(np.dot(q0, q1))
    if dot < 0.0:            # double-cover: take the short way round
        q1 = -q1
        dot = -dot
    dot = min(1.0, max(-1.0, dot))
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
    """Interpolate the body pose at t_query from a sorted odometry stream."""
    M = len(odom_t)
    if M == 0:
        return None, None, False, "empty odometry"
    if t_query < odom_t[0] or t_query > odom_t[-1]:
        return None, None, False, "out of odometry time span"
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
    R_cam_in_lidar = R_lidar_to_cam.T
    t_cam_in_lidar = -R_lidar_to_cam.T @ t_lidar_to_cam
    R = R_lidar_in_map @ R_cam_in_lidar
    t = R_lidar_in_map @ t_cam_in_lidar + t_lidar_in_map
    return R, t


# =====================================================================================
# COVERAGE GATE  (v2, ADR-002) — fail-closed BEFORE handing a pose set to the baker
# =====================================================================================

def evaluate_coverage(res, image_t, odom_t, min_match=90.0, max_hole=0.5):
    """Return (passed: bool, lines: list[str]).
    A capture that fails this MUST NOT reach the baker: a starved pose set paints a
    patchy room on perfect geometry (the 2026-09-23 blocking defect). Fails if
    matched% < min_match, images fall outside the odom span, or an in-run odom hole
    exceeds max_hole (bag-record time)."""
    n = len(image_t)
    n_ok = int(res["ok"].sum())
    pct = 100.0 * n_ok / max(1, n)
    ot = np.sort(np.asarray(odom_t, float))
    lo, hi = (ot[0], ot[-1]) if len(ot) else (0.0, 0.0)
    head = int((np.asarray(image_t, float) < lo).sum())
    tail = int((np.asarray(image_t, float) > hi).sum())
    gaps = np.diff(ot) if len(ot) > 1 else np.array([0.0])
    biggest = float(gaps.max()) if len(gaps) else 0.0

    L = ["=" * 66, "TEXTURE-COVERAGE GATE  (ADR-002, fail-closed)", "=" * 66]
    L.append("images                 : %d" % n)
    L.append("poseable (matched)     : %d  (%.1f%%)      [need >= %.0f%%]" % (n_ok, pct, min_match))
    L.append("out-of-span head/tail  : %d / %d              [odom must bracket the images]" % (head, tail))
    L.append("largest odom hole      : %.2fs             [max allowed %.2fs]" % (biggest, max_hole))

    fails = []
    if pct < min_match:
        fails.append("coverage %.1f%% < %.0f%%" % (pct, min_match))
    if head or tail:
        fails.append("%d frames outside odom span" % (head + tail))
    if biggest > max_hole:
        fails.append("odom hole %.2fs > %.2fs" % (biggest, max_hole))

    L.append("")
    if fails:
        L.append("VERDICT: *** FAIL ***  —  " + "; ".join(fails))
        L.append("  A starved pose set would paint a patchy room on clean geometry.")
        L.append("  NOT writing the pose set. Fix capture (record COMPRESSED images so the")
        L.append("  recorder keeps up and odom stays dense), or pass --force for a partial bake.")
        L.append("=" * 66)
        return False, L
    L.append("VERDICT: GREEN  —  coverage sound, poses handed off to the baker.")
    L.append("=" * 66)
    return True, L


# =====================================================================================
# I/O LAYER  (rosbags)
# =====================================================================================

def _stamp_to_sec(stamp):
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

def read_bag(bag_path, odom_topic='/aft_mapped_to_init', image_topic='/image_raw'):
    """Read odometry + image stamps from a ROS2 bag. Times in seconds, rebased to the
    first odometry stamp (preserves ns precision as float64). Handles raw Image and
    CompressedImage image topics alike (only their bag-record stamps are used here)."""
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore
    from pathlib import Path
    odom_ns, opos, oquat, img_ns = [], [], [], []
    _ts = get_typestore(Stores.ROS2_HUMBLE)
    with AnyReader([Path(bag_path)], default_typestore=_ts) as reader:
        conns_o = [c for c in reader.connections if c.topic == odom_topic]
        conns_i = [c for c in reader.connections if c.topic == image_topic]
        if not conns_o:
            raise RuntimeError("odom topic %s not in bag (have: %s)"
                               % (odom_topic, sorted({c.topic for c in reader.connections})))
        if not conns_i:
            raise RuntimeError("image topic %s not in bag (have: %s)"
                               % (image_topic, sorted({c.topic for c in reader.connections})))
        for con, bt, raw in reader.messages(connections=conns_o):
            m = reader.deserialize(raw, con.msgtype)
            odom_ns.append(bt)
            p = m.pose.pose.position
            q = m.pose.pose.orientation
            opos.append([p.x, p.y, p.z])
            oquat.append([q.x, q.y, q.z, q.w])
        for con, bt, raw in reader.messages(connections=conns_i):
            img_ns.append(bt)          # only the record stamp is needed here (no decode)
    odom_ns = np.array(odom_ns, dtype=np.int64)
    img_ns = np.array(img_ns, dtype=np.int64)
    if len(odom_ns) == 0:
        raise RuntimeError("no odometry messages read")
    t0 = odom_ns.min()
    odom_t = (odom_ns - t0) / 1e9
    image_t = (img_ns - t0) / 1e9
    return odom_t, np.array(opos), np.array(oquat), image_t


# =====================================================================================
# SELFTEST  (proves the CORE math cold — no ROS, no bag, no rig)  [UNCHANGED + gate test]
# =====================================================================================

def selftest():
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
    assert max(pe)<1e-9 and max(qe)<1e-4, "interpolation not exact"
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
    # --- gate tests (v2) ---
    dense = np.arange(0, 220, 1/200.0)
    P = np.zeros((len(dense),3)); Q = np.tile([0,0,0,1.], (len(dense),1))
    imgs = np.arange(0, 220, 1/28.0)
    clean = match_images_to_poses(dense, P, Q, imgs, max_gap=0.5)
    ok8,_ = evaluate_coverage(clean, imgs, dense, min_match=90, max_hole=0.5); assert ok8; print("TEST 8  PASS  gate GREEN on clean dense odom")
    holed_t = dense[~((dense > 9.7) & (dense < 137.0))]           # 127s hole like fusioncap_130955
    Ph = np.zeros((len(holed_t),3)); Qh = np.tile([0,0,0,1.], (len(holed_t),1))
    starved = match_images_to_poses(holed_t, Ph, Qh, imgs, max_gap=0.5)
    ok9,_ = evaluate_coverage(starved, imgs, holed_t, min_match=90, max_hole=0.5); assert not ok9; print("TEST 9  PASS  gate FAIL on a 127s odom hole (the 130955 case)")
    print("\nALL 9 TESTS PASS.")


def dump_frames(bag_path, image_topic, out_dir):
    """Decode each image message to out_dir/img_{idx:05d}.png, in bag order (PNG index ==
    matcher entry index). Handles sensor_msgs/Image (bgr8/rgb8/mono8/yuv422) and
    sensor_msgs/CompressedImage (mjpeg)."""
    import cv2
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore
    from pathlib import Path
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    _ts = get_typestore(Stores.ROS2_HUMBLE)
    with AnyReader([Path(bag_path)], default_typestore=_ts) as reader:
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
                elif enc in ('yuv422', 'yuv422_yuy2', 'uyvy'):
                    yuv = buf.reshape(m.height, m.width, 2)
                    code = cv2.COLOR_YUV2BGR_UYVY if enc in ('yuv422', 'uyvy') else cv2.COLOR_YUV2BGR_YUY2
                    img = cv2.cvtColor(yuv, code)
                else:
                    raise RuntimeError("unhandled image encoding '%s' — add a decode branch" % enc)
            cv2.imwrite(os.path.join(out_dir, "img_%05d.png" % n), img)
            n += 1
    print("dumped %d frames to %s" % (n, out_dir))
    return n


def main():
    ap = argparse.ArgumentParser(description="Match camera images to Point-LIO poses (Piece 2, gated).")
    ap.add_argument("bag", nargs="?", help="path to the ROS2 bag directory")
    ap.add_argument("--selftest", action="store_true", help="run the built-in math+gate proof and exit")
    ap.add_argument("-o", "--out", default="posed_images.npz")
    ap.add_argument("--odom-topic", default="/aft_mapped_to_init")
    ap.add_argument("--image-topic", default="/image_raw",
                    help="e.g. /camera/image_raw/compressed for a compressed-recorded bag")
    ap.add_argument("--max-gap", type=float, default=0.5,
                    help="reject images whose bracketing odometry gap exceeds this (s)")
    # --- v2 coverage gate ---
    ap.add_argument("--min-match", type=float, default=90.0,
                    help="GATE: fail if matched %% is below this (default 90)")
    ap.add_argument("--max-hole", type=float, default=None,
                    help="GATE: fail if any in-run odom hole exceeds this (s); default = --max-gap")
    ap.add_argument("--force", action="store_true",
                    help="bypass the coverage gate and write anyway (deliberate partial bake)")
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

    # ---- COVERAGE GATE (fail-closed) ----
    max_hole = args.max_hole if args.max_hole is not None else args.max_gap
    passed, lines = evaluate_coverage(res, image_t, odom_t, args.min_match, max_hole)
    print("\n" + "\n".join(lines))
    if not passed and not args.force:
        print("\nGATE FAILED — no pose set written. (Use --force to override.)")
        sys.exit(2)
    if not passed and args.force:
        print("\n--force: writing a KNOWN-PARTIAL pose set anyway.")

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
