#!/usr/bin/env python3
"""ARCHIVE MINER: fusioncap bag -> coverage map -> MESH CHECK report. No ROS needed.
Reads /unilidar/cloud (sensor frame) + /aft_mapped_to_init (Point-LIO odometry) straight
from the .db3 (pure-python rosbags), interpolates a pose per scan (SLERP), registers
scans into the world frame, accumulates the hit-counted voxel map, meshes it, and writes
<prefix>.report.json + <prefix>.map.npy + mesh files (via mesh_check.py, same dir).

Approximations (stated, acceptable for a coverage instrument):
  - one pose per scan (no intra-scan deskew): ~cm smear at handheld speed, ~ voxel size
  - lidar==body frame (Point-LIO's internal lidar-imu offset is cm-scale, ignored)
Honesty: scans without bracketing odometry are DROPPED and COUNTED, never guessed."""
import sys, os, json, time, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quatmath import matrix_from_quat, slerp
from map_accumulator import VoxelMap
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

def parse_cloud(msg):
    """PointCloud2 -> (N,3) float32 xyz using the declared field offsets."""
    off = {f.name: f.offset for f in msg.fields}
    if not all(k in off for k in ("x","y","z")): return None
    raw = np.frombuffer(bytes(msg.data), np.uint8)
    n = msg.width * msg.height
    if n == 0 or len(raw) < n * msg.point_step: return None
    rec = raw[:n*msg.point_step].reshape(n, msg.point_step)
    out = np.empty((n,3), np.float32)
    for i,k in enumerate(("x","y","z")):
        out[:,i] = rec[:, off[k]:off[k]+4].copy().view("<f4").ravel()
    return out[np.isfinite(out).all(axis=1)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag"); ap.add_argument("prefix")
    ap.add_argument("--cloud-topic", default="/unilidar/cloud")
    ap.add_argument("--odom-topic", default="/aft_mapped_to_init")
    ap.add_argument("--voxel", type=float, default=0.05)
    ap.add_argument("--time-source", choices=("header","bag"), default="header")
    ap.add_argument("--max-voxels", type=int, default=2_000_000)
    ap.add_argument("--max-pose-gap", type=float, default=0.5,
                    help="drop scans whose bracketing poses are further apart than this (odometry cutout)")
    a = ap.parse_args()
    T0 = time.time()
    ts = get_typestore(Stores.ROS2_HUMBLE)

    ot, opos, oquat = [], [], []
    scans = []          # (t_used, header_t, bag_t, xyz)
    with Reader(a.bag) as r:
        conns = [c for c in r.connections if c.topic in (a.cloud_topic, a.odom_topic)]
        for conn, t_bag, raw in r.messages(connections=conns):
            m = ts.deserialize_cdr(raw, conn.msgtype)
            th = m.header.stamp.sec + m.header.stamp.nanosec*1e-9
            if conn.topic == a.odom_topic:
                p = m.pose.pose.position; q = m.pose.pose.orientation
                ot.append(th if a.time_source=="header" else t_bag*1e-9)
                opos.append([p.x,p.y,p.z]); oquat.append([q.x,q.y,q.z,q.w])
            else:
                xyz = parse_cloud(m)
                if xyz is not None and len(xyz):
                    tu = th if a.time_source=="header" else t_bag*1e-9
                    scans.append((tu, th, t_bag*1e-9, xyz))
    ot = np.array(ot); opos = np.array(opos); oquat = np.array(oquat)
    order = np.argsort(ot); ot, opos, oquat = ot[order], opos[order], oquat[order]
    print(f"[mine] odom {len(ot)} msgs spanning {ot[-1]-ot[0]:.1f}s | scans {len(scans)}", flush=True)
    if len(ot) < 2 or not scans:
        print("[mine] not enough data"); sys.exit(2)

    off_hb = np.median([s[2]-s[1] for s in scans])
    vm = VoxelMap(a.voxel, a.max_voxels)
    used = dropped = 0; pts_total = 0
    for i,(tu, th, tb, xyz) in enumerate(scans):
        j = np.searchsorted(ot, tu, side="right")
        if j == 0 or j >= len(ot) or (ot[j]-ot[j-1]) > a.max_pose_gap:
            dropped += 1; continue          # outside span OR inside an odometry gap: never guess
        f = (tu - ot[j-1]) / max(ot[j]-ot[j-1], 1e-9)
        R = matrix_from_quat(slerp(oquat[j-1], oquat[j], f))
        p = opos[j-1]*(1-f) + opos[j]*f
        vm.add_points(xyz @ R.T + p)
        used += 1; pts_total += len(xyz)
        if i % 50 == 0: vm.merge()
    vm.merge()
    print(f"[mine] registered {used}/{len(scans)} scans ({dropped} dropped, no bracketing pose) | "
          f"{pts_total:,} pts -> {len(vm.keys):,} voxels{' CAPPED' if vm.capped else ''}", flush=True)

    pts, cnts = vm.full_points_counts()
    snap = np.empty((len(pts),4), np.float32); snap[:,:3]=pts; snap[:,3]=cnts
    np.save(a.prefix + ".map.npy", snap)
    import subprocess
    mesher = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mesh_check.py")
    rc = subprocess.run([sys.executable, mesher, a.prefix + ".map.npy", a.prefix,
                        "--voxel", str(a.voxel)], capture_output=True, text=True)
    print(rc.stdout, flush=True)
    mesh_meta = json.load(open(a.prefix + ".json")) if rc.returncode == 0 else {"error": rc.stderr[-300:]}
    report = {"bag": a.bag, "scans_total": len(scans), "scans_used": used, "scans_dropped": dropped,
              "points_in": int(pts_total), "voxels": int(len(vm.keys)), "capped": bool(vm.capped),
              "voxel_size": a.voxel, "odom_msgs": int(len(ot)),
              "odom_span_s": round(float(ot[-1]-ot[0]),2),
              "bag_minus_header_median_s": round(float(off_hb),4),
              "time_source": a.time_source, "mesh": mesh_meta,
              "approximations": ["no intra-scan deskew (~cm smear)", "lidar==body frame"],
              "seconds": round(time.time()-T0,1)}
    open(a.prefix + ".report.json","w").write(json.dumps(report, indent=1))
    print(f"[mine] report -> {a.prefix}.report.json ({report['seconds']}s total)", flush=True)

if __name__ == "__main__":
    main()
