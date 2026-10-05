#!/usr/bin/env python3
"""
rs_bundle.py -- build the RealityScan 2.2 input bundle from (a) the ORIGINAL capture bag
(compressed camera frames) + (b) the OFFLINE RE-SOLVED odometry bag + (c) the re-solved scans.pcd.
Station side (Shadow, rigstation env). FORWARD_PLAN step 5 / stage B2.

OUTPUT  <out>/
   images/img_<headerstamp_ns>.jpg   undistorted frames (K unchanged, DIST removed), ns stamp in the name
   images/img_<headerstamp_ns>.xmp   RealityScan XMP sidecar: locked/exact CAMERA pose prior, CV convention
   cloud_color.ply                   the re-solved cloud, photo-coloured (binary PLY, uint8 RGB) -> Mobile LiDAR, Color
   manifest.csv                      frame, stamp, pose, sharpness, heading
   README_RS.txt                     the RealityScan click sequence for this bundle

CONVENTIONS (the handoff that bit us before -- ADR-003 #3, pose_xmp_roundtrip):
  * poses from the odom bag are T_lidar_in_map (body->map). The camera<->LiDAR extrinsic is applied
    EXACTLY ONCE here, via the same compose_world_to_cam as fuse_pano.py (values embedded, verbatim).
  * xcr:Rotation = world->camera rotation, ROW-MAJOR, camera axes x right / y down / z into the scene
    (RealityScan coordinate-systems reference, 2026-06-08). xcr:Position = camera centre C = -R^T t.
  * xcr:FocalLength35mm = 36 * fx / W   (= 15.914228 for our K -- matches the ratified recipe prior)
    xcr:AspectRatio = fy / fx ; PrincipalPointU = (cx - W/2)/W ; PrincipalPointV = (cy - H/2)/H
  * frames are UNDISTORTED, so DistortionModel=brown3 with all-zero coefficients (sidesteps RS's
    brown3t2 t1/t2 swap). cv2.undistort keeps K, so the XMP intrinsics are exact for the written image.
  * association is on header.stamp (NOT bag-record time -- the II-C degradation fault), with
    tau = lidar_clock - camera_clock (tau_solve_v2 sign): pose looked up at t_img + tau.
    Stop-and-shoot frames are immune to tau; moving frames inherit its error (~18 cm/s of walking).

Run (Anaconda Prompt, rigstation):
    python rs_bundle.py --bag <ORIG_BAG_DIR> --odom <RESOLVE_ODOM_BAG_DIR> --cloud <resolve_scans.pcd> --out <OUT_DIR>
        [--tau 0.18] [--prior exact|locked|initial] [--min-move 0.08] [--min-rot 4] [--max-frames 600]
"""
import os, sys, csv, argparse, shutil
import numpy as np, cv2
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

# ---- EMBEDDED CALIBRATION (verbatim from fuse_pano.py / per_shot_texture.py) ----
K = np.array([[848.759, 0, 921.002], [0, 849.231, 565.962], [0, 0, 1]], dtype=np.float64)
DIST = np.array([-0.014979, -0.013547, -0.001997, 0.000698, 0.003842])
R_L2C = np.array([
    [0.079231956747140869, 0.99456000522703925, -0.067621690549788172],
    [-0.98716139340257103, 0.087718305377614436, 0.13348364048516903],
    [0.13868915028045117, 0.056177352237994721, 0.9887413335600036]])
T_L2C = np.array([0.018336757321533628, -0.053568141733719279, -0.15964461058920226])
IMG_W, IMG_H = 1920, 1200

ODOM_TOPIC = "/aft_mapped_to_init"


def compose_world_to_cam(R_wl, t_wl):
    """T_lidar_in_map (body->map) -> world-to-camera. Extrinsic applied ONCE, here (fuse_pano verbatim)."""
    R = R_L2C @ R_wl.T
    t = T_L2C - R @ t_wl
    return R, t


# ---- pose math (verbatim: pointlio_pose_matcher v2 / make_full_pan_anchor) ----
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

def interpolate_pose(odom_t, odom_pos, odom_quat, tq, max_gap=0.5):
    M = len(odom_t)
    if M == 0 or tq < odom_t[0] or tq > odom_t[-1]: return None, None, False
    j = int(np.searchsorted(odom_t, tq))
    if j < M and odom_t[j] == tq: return odom_pos[j].copy(), quat_normalize(odom_quat[j]), True
    i = j - 1; t0, t1 = odom_t[i], odom_t[i+1]; gap = t1 - t0
    if gap > max_gap: return None, None, False
    u = (tq - t0) / gap
    return odom_pos[i] + u*(odom_pos[i+1]-odom_pos[i]), quat_slerp(odom_quat[i], odom_quat[i+1], u), True


# ---- bag readers (header.stamp everywhere) ----
def read_odom(bag, ts):
    t, p, q = [], [], []
    with Reader(bag) as r:
        conns = [c for c in r.connections if c.topic == ODOM_TOPIC]
        if not conns: raise SystemExit("no %s in %s" % (ODOM_TOPIC, bag))
        for conn, bt, raw in r.messages(connections=conns):
            m = ts.deserialize_cdr(raw, conn.msgtype)
            t.append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9)
            pp = m.pose.pose.position; qq = m.pose.pose.orientation
            p.append([pp.x, pp.y, pp.z]); q.append([qq.x, qq.y, qq.z, qq.w])
    t = np.array(t); p = np.array(p); q = np.array(q)
    o = np.argsort(t); t, p, q = t[o], p[o], q[o]
    keep = np.concatenate([[True], np.diff(t) > 0])
    return t[keep], p[keep], q[keep]

def image_topic(bag):
    with Reader(bag) as r:
        cand = {c.topic: c.msgcount for c in r.connections if 'Image' in c.msgtype}
    if not cand: raise SystemExit("no image topic in %s" % bag)
    comp = [t for t in cand if 'compress' in t.lower()]
    return comp[0] if comp else max(cand, key=cand.get)

def iter_images(bag, topic, ts):
    """yields (header_stamp_s, header_stamp_ns_int, jpeg_bytes_or_None, msg) in bag order"""
    with Reader(bag) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for conn, bt, raw in r.messages(connections=conns):
            m = ts.deserialize_cdr(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 1_000_000_000 + int(m.header.stamp.nanosec)
            yield ns * 1e-9, ns, conn.msgtype, m

def decode(msgtype, m):
    if 'CompressedImage' in msgtype:
        return cv2.imdecode(np.frombuffer(bytes(m.data), np.uint8), cv2.IMREAD_COLOR)
    buf = np.frombuffer(bytes(m.data), np.uint8); enc = m.encoding.lower()
    if enc in ('bgr8', 'rgb8'):
        img = buf.reshape(m.height, m.width, 3)
        return img[:, :, ::-1].copy() if enc == 'rgb8' else img.copy()
    raise RuntimeError("unhandled encoding %s" % enc)


# ---- PCD / PLY ----
def read_pcd_xyzi(path):
    with open(path, 'rb') as f:
        while True:
            line = f.readline()
            if not line or line.startswith(b'DATA'): break
        raw = np.fromfile(f, dtype=np.float32)
    n = raw.size // 8
    raw = raw[:n * 8].reshape(n, 8)
    return raw[:, :3].astype(np.float64), raw[:, 3].copy()

def write_ply_rgb(path, P, rgb):
    """binary little-endian PLY, float xyz + uint8 rgb (the format RealityScan/CloudCompare read as colour)"""
    n = len(P)
    hdr = ("ply\nformat binary_little_endian 1.0\nelement vertex %d\n"
           "property float x\nproperty float y\nproperty float z\n"
           "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % n).encode()
    dt = np.dtype([('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('r', 'u1'), ('g', 'u1'), ('b', 'u1')])
    arr = np.empty(n, dt)
    arr['x'], arr['y'], arr['z'] = P[:, 0], P[:, 1], P[:, 2]
    arr['r'], arr['g'], arr['b'] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    with open(path, 'wb') as f:
        f.write(hdr); arr.tofile(f)


# ---- XMP ----
XMP_TMPL = """<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xcr:Version="3" xcr:PosePrior="{prior}" xcr:Coordinates="absolute"
       xcr:DistortionModel="brown3" xcr:FocalLength35mm="{f35:.6f}" xcr:Skew="0"
       xcr:AspectRatio="{aspect:.6f}" xcr:PrincipalPointU="{ppu:.6f}" xcr:PrincipalPointV="{ppv:.6f}"
       xcr:CalibrationPrior="exact" xcr:CalibrationGroup="-1" xcr:DistortionGroup="-1"
       xmlns:xcr="http://www.capturingreality.com/ns/xcr/1.1#">
      <xcr:Rotation>{rot}</xcr:Rotation>
      <xcr:Position>{pos}</xcr:Position>
      <xcr:DistortionCoeficients>0 0 0 0 0 0</xcr:DistortionCoeficients>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
"""

def write_xmp(path, R_cw, C, prior):
    f35 = 36.0 * K[0, 0] / IMG_W
    aspect = K[1, 1] / K[0, 0]
    ppu = (K[0, 2] - IMG_W / 2.0) / IMG_W
    ppv = (K[1, 2] - IMG_H / 2.0) / IMG_H
    rot = " ".join("%.9f" % v for v in R_cw.reshape(-1))
    pos = " ".join("%.6f" % v for v in C)
    with open(path, "w") as f:
        f.write(XMP_TMPL.format(prior=prior, f35=f35, aspect=aspect, ppu=ppu, ppv=ppv, rot=rot, pos=pos))


def rot_angle(Ra, Rb):
    return float(np.degrees(np.arccos(np.clip((np.trace(Ra.T @ Rb) - 1) / 2, -1, 1))))


# ---- main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True, help="ORIGINAL capture bag dir (camera frames)")
    ap.add_argument("--odom", required=True, help="re-solved odom bag dir (resolve_<bag>_<mode>/)")
    ap.add_argument("--cloud", required=True, help="re-solved scans.pcd")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tau", type=float, default=0.18, help="lidar_clock - camera_clock [s] (tau_solve_v2 sign)")
    ap.add_argument("--prior", default="exact", choices=["exact", "locked", "initial"])
    ap.add_argument("--min-move", type=float, default=0.08, help="m between kept frames")
    ap.add_argument("--min-rot", type=float, default=4.0, help="deg between kept frames")
    ap.add_argument("--max-frames", type=int, default=600)
    ap.add_argument("--jpeg-q", type=int, default=95)
    a = ap.parse_args()

    ts = get_typestore(Stores.ROS2_HUMBLE)
    if os.path.exists(a.out): shutil.rmtree(a.out)
    os.makedirs(os.path.join(a.out, "images"))

    print("[1/5] odom (re-solved):", a.odom)
    ot, op, oq = read_odom(a.odom, ts)
    print("      %d poses, %.1f s, extent x %.2f y %.2f z %.2f m" % (len(ot), ot[-1]-ot[0], *(op.max(0)-op.min(0))))

    topic = image_topic(a.bag)
    print("[2/5] frames from %s on %s  (tau %+.3f s, prior %s)" % (topic, a.bag, a.tau, a.prior))
    kept = []            # dicts
    lastR, lastC = None, None
    n_all = n_pose = 0
    pending = []         # candidate group (consecutive frames past the motion threshold)
    def flush():
        nonlocal lastR, lastC
        if not pending: return
        best = max(pending, key=lambda d: d["sharp"])
        kept.append(best); lastR, lastC = best["R_cw"], best["C"]
        pending.clear()
    for t_img, ns, mt, m in iter_images(a.bag, topic, ts):
        n_all += 1
        p, q, ok = interpolate_pose(ot, op, oq, t_img + a.tau)
        if not ok: continue
        n_pose += 1
        R_wl = quat_to_R(q)
        R_cw, t_cw = compose_world_to_cam(R_wl, p)
        C = -R_cw.T @ t_cw
        moved = lastC is None or np.linalg.norm(C - lastC) >= a.min_move or rot_angle(lastR, R_cw) >= a.min_rot
        if moved:
            img = decode(mt, m)
            if img is None: continue
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
            pending.append(dict(ns=ns, t=t_img, R_cw=R_cw, t_cw=t_cw, C=C, img=img, sharp=sharp))
            if len(pending) >= 3: flush()
        elif pending:
            flush()
        if len(kept) >= a.max_frames: break
    flush()
    print("      frames %d | poseable %d | kept %d (spacing %.2f m / %.0f deg, sharpest of 3)"
          % (n_all, n_pose, len(kept), a.min_move, a.min_rot))
    if not kept: raise SystemExit("no frames kept -- check tau / odom overlap")

    print("[3/5] writing undistorted frames + XMP sidecars")
    rows = []
    for d in kept:
        und = cv2.undistort(d["img"], K, DIST)          # K unchanged -> XMP intrinsics exact, zero distortion
        name = "img_%d" % d["ns"]
        cv2.imwrite(os.path.join(a.out, "images", name + ".jpg"), und, [cv2.IMWRITE_JPEG_QUALITY, a.jpeg_q])
        write_xmp(os.path.join(a.out, "images", name + ".xmp"), d["R_cw"], d["C"], a.prior)
        fwd = d["R_cw"].T @ np.array([0, 0, 1.0])
        rows.append([name, "%.6f" % d["t"], *["%.4f" % v for v in d["C"]], "%.1f" % np.degrees(np.arctan2(fwd[1], fwd[0])), "%.0f" % d["sharp"]])
        d["img"] = None
    with open(os.path.join(a.out, "manifest.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["image", "stamp_s", "cx", "cy", "cz", "heading_deg", "sharpness"]); w.writerows(rows)

    print("[4/5] colouring the cloud from the kept frames (z-buffer, best-centred camera)")
    P, inten = read_pcd_xyzi(a.cloud)
    col = np.zeros((len(P), 3), np.float32); best = np.full(len(P), -1.0)
    cx, cy, diag = IMG_W / 2, IMG_H / 2, np.hypot(IMG_W / 2, IMG_H / 2)
    OS = 0.5; w2, h2 = int(IMG_W * OS), int(IMG_H * OS)
    for i, d in enumerate(kept):
        img = cv2.imread(os.path.join(a.out, "images", "img_%d.jpg" % d["ns"]))
        pc = (d["R_cw"] @ P.T + d["t_cw"].reshape(3, 1)).T
        z = pc[:, 2]; infront = z > 0.15
        px = cv2.projectPoints(pc, np.zeros(3), np.zeros(3), K, np.zeros(5))[0].reshape(-1, 2)   # undistorted image
        u, v = px[:, 0], px[:, 1]
        fin = np.isfinite(u) & np.isfinite(v)
        inframe = infront & fin & (u >= 0) & (u < IMG_W) & (v >= 0) & (v < IMG_H)
        idx = np.where(inframe)[0]
        if not len(idx): continue
        ui = np.zeros(len(P), int); vi = np.zeros(len(P), int)
        ui[idx] = np.clip((u[idx] * OS).astype(int), 0, w2 - 1); vi[idx] = np.clip((v[idx] * OS).astype(int), 0, h2 - 1)
        zb = np.full((h2, w2), 1e9, np.float32)
        np.minimum.at(zb, (vi[idx], ui[idx]), z[idx].astype(np.float32))
        visible = inframe.copy()
        visible[idx] = z[idx] <= zb[vi[idx], ui[idx]] * 1.03 + 0.05
        centered = np.zeros(len(P)); centered[idx] = 1.0 - np.hypot(u[idx] - cx, v[idx] - cy) / diag
        score = np.where(visible, centered, -1.0)
        take = visible & (score > best); ti = np.where(take)[0]
        col[ti] = img[np.clip(v[ti].astype(int), 0, IMG_H - 1), np.clip(u[ti].astype(int), 0, IMG_W - 1)]
        best[ti] = score[ti]
        if (i + 1) % 50 == 0: print("      %d/%d frames" % (i + 1, len(kept)))
    pct = 100.0 * (best > 0).mean()
    lo, hi = np.percentile(inten, [2, 98]); g = np.clip((inten - lo) / (hi - lo + 1e-9), 0, 1)
    gray = (255 * np.power(g, 0.6)).astype(np.uint8)
    rgb = np.empty((len(P), 3), np.uint8)
    coloured = best > 0
    rgb[~coloured] = np.stack([gray[~coloured]] * 3, 1)
    rgb[coloured] = np.clip(col[coloured], 0, 255).astype(np.uint8)[:, ::-1]   # BGR -> RGB
    write_ply_rgb(os.path.join(a.out, "cloud_color.ply"), P, rgb)
    print("      photo-coloured %.1f%% of %d points -> cloud_color.ply" % (pct, len(P)))

    print("[5/5] README_RS.txt")
    with open(os.path.join(a.out, "README_RS.txt"), "w") as f:
        f.write("""RealityScan 2.2 -- click sequence for this bundle (FORWARD_PLAN stage B3)
1. New project. Alignment settings (Advanced): 'Merge georeferenced components' = Yes; Max feature reprojection error 3 px.
2. Import LASER SCAN: cloud_color.ply  -> type Mobile LiDAR, Registration = EXACT, Features source = COLOR,
   virtual cameras 'from prior camera poses' (the XMP priors).   The cloud defines the coordinate system (metres).
3. Import images: the whole images/ folder (each .jpg carries its .xmp; PosePrior = %s).
4. Align Images (F6).  GATE: ONE component, >= 90%% cameras aligned, cones point INWARD (no XMP flip).
   If photos and LiDAR split: Lock pose for continue on the LiDAR component, then 3+ control points on 3+ images/LSPs.
5. Reconstruction settings: raise 'Default grouping factor' (LiDAR-priority meshing). Set region. Calculate Model (Normal).
6. Texture: Correct colors = Yes, Adaptive texel size, Max texture resolution 16384. GATE: reads as the room (eye).
7. Export: Model (GLB or FBX), scale x100 (m -> cm), no spaces in filenames, UDIM if the atlas clips. -> UE 5.8 Nanite.
Frames: undistorted; intrinsics exact; zero distortion. Poses = re-solved Point-LIO, extrinsic applied once, tau %+.3f s.
""" % (a.prior, a.tau))
    print("DONE ->", a.out)


if __name__ == "__main__":
    main()
