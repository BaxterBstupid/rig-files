#!/usr/bin/env python3
"""
bag_motion.py -- FAST motion classifier for a folder of fusioncap bags (IMU only, no odom decode).
Answers "which of these bags is a PAN, which is a WALK, which is STATIC, and is it re-solvable?"
without trusting the live odometry (the thing that lies on a pan). The gyro is the truth.

Per bag: duration | cloud count + rate (12 Hz = nothing dropped live) | odom count |
         gyro heading RANGE + NET about gravity (deg) | mean |gyro| | still start? |
         accel-variance (walking shakes the accelerometer; a stand pan barely does) | VERDICT

Deps: numpy, rosbags. Run (Jetson or Shadow):
    python3 bag_motion.py /mnt/rigdata            # every fusioncap_* / plio_texcap_* under it
    python3 bag_motion.py <one_bag_dir>
"""
import sys, os, glob
import numpy as np
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

IMU = "/unilidar/imu"; CLOUD = "/unilidar/cloud"; ODOM = "/aft_mapped_to_init"


def exp_so3(v):
    th = np.linalg.norm(v)
    if th < 1e-12:
        return np.eye(3)
    k = v / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def analyse(bag, ts):
    try:
        with Reader(bag) as r:
            counts = {c.topic: c.msgcount for c in r.connections}
            dur = (r.duration or 0) / 1e9
            conns = [c for c in r.connections if c.topic == IMU]
            t, g, a = [], [], []
            for conn, bt, raw in r.messages(connections=conns):
                m = ts.deserialize_cdr(raw, conn.msgtype)
                t.append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9)
                g.append([m.angular_velocity.x, m.angular_velocity.y, m.angular_velocity.z])
                a.append([m.linear_acceleration.x, m.linear_acceleration.y, m.linear_acceleration.z])
    except Exception as e:
        return {"bag": os.path.basename(bag.rstrip("/")), "err": str(e)[:60]}
    out = {"bag": os.path.basename(bag.rstrip("/")), "dur": dur,
           "cloud": counts.get(CLOUD, 0), "odom": counts.get(ODOM, 0), "imu": counts.get(IMU, 0)}
    out["cloud_hz"] = out["cloud"] / dur if dur > 0 else 0
    if len(t) < 100:
        out["verdict"] = "no IMU"; return out
    t = np.array(t); g = np.array(g); a = np.array(a)
    o = np.argsort(t); t, g, a = t[o], g[o], a[o]
    gb = a[:250].mean(0); gb /= np.linalg.norm(gb)              # gravity in body0
    ax = int(np.argmin(np.abs(gb))); fwd = np.eye(3)[ax]          # body axis most perpendicular to g
    f0 = fwd - np.dot(fwd, gb) * gb; f0 /= np.linalg.norm(f0); s = np.cross(gb, f0)
    R = np.eye(3); hd = [0.0]
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        if 0 < dt < 0.5:
            R = R @ exp_so3(0.5 * (g[i] + g[i - 1]) * dt)
        f = R @ fwd; f = f - np.dot(f, gb) * gb
        hd.append(np.arctan2(np.dot(s, f), np.dot(f0, f)))
    hd = np.degrees(np.unwrap(np.array(hd)))
    gn = np.degrees(np.linalg.norm(g, axis=1))
    an = np.linalg.norm(a, axis=1)
    # translation proxy: std of |acc| over 1 s windows, median (walking ~0.5-1.5; stand pan ~0.05-0.2)
    n = len(an); w = 250
    win_std = [an[i:i + w].std() for i in range(0, n - w, w)] or [an.std()]
    out.update({"hdg_range": float(hd.max() - hd.min()), "hdg_net": float(hd[-1] - hd[0]),
                "gyro_mean": float(gn.mean()), "gyro_p99": float(np.percentile(gn, 99)),
                "still_start": float(gn[:750].mean()), "acc_std": float(np.median(win_std))})
    rng, mv, acs = out["hdg_range"], out["gyro_mean"], out["acc_std"]
    if rng < 15 and mv < 2:
        v = "STATIC"
    elif rng >= 90 and acs < 0.35:
        v = "PAN (rotation, little translation)"
    elif rng >= 90:
        v = "WALK+TURN"
    elif acs >= 0.35:
        v = "WALK (little heading)"
    else:
        v = "small motion"
    out["verdict"] = v
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    if os.path.exists(os.path.join(root, "metadata.yaml")):
        bags = [root]
    else:
        bags = sorted(glob.glob(os.path.join(root, "fusioncap_*")) + glob.glob(os.path.join(root, "plio_texcap_*")))
        bags = [b for b in bags if os.path.isdir(b)]
    ts = get_typestore(Stores.ROS2_HUMBLE)
    print(f"{'bag':22s} {'dur_s':>6s} {'cloud':>5s} {'c_Hz':>5s} {'odom':>8s} {'hdgRng':>6s} {'hdgNet':>6s} "
          f"{'gyro':>5s} {'start':>5s} {'accSD':>5s}  verdict")
    for b in bags:
        o = analyse(b, ts)
        if "err" in o:
            print(f"{o['bag']:22s} ERROR {o['err']}"); continue
        if "hdg_range" not in o:
            print(f"{o['bag']:22s} {o['dur']:6.1f} {o['cloud']:5d} {o['cloud_hz']:5.1f} {o['odom']:8d}   {o['verdict']}"); continue
        resolv = "resolvable" if o["cloud"] > 0 else "NOT re-solvable"
        drop = "" if o["cloud_hz"] >= 11.0 or o["cloud"] == 0 else f"  !! cloud {o['cloud_hz']:.1f} Hz (dropped live)"
        start = "still" if o["still_start"] < 1.0 else "MOVING"
        print(f"{o['bag']:22s} {o['dur']:6.1f} {o['cloud']:5d} {o['cloud_hz']:5.1f} {o['odom']:8d} "
              f"{o['hdg_range']:6.0f} {o['hdg_net']:+6.0f} {o['gyro_mean']:5.1f} {start:>5s} {o['acc_std']:5.2f}  "
              f"{o['verdict']}  [{resolv}]{drop}")
    print("\ncolumns: hdgRng/hdgNet = gyro-integrated heading range / net (deg) | gyro = mean |rate| deg/s | "
          "start = first 3 s still? | accSD = |acc| std per 1 s (translation proxy; stand pan ~0.1, walking ~0.5+)")


if __name__ == "__main__":
    main()
