#!/usr/bin/env python3
"""
bag_health.py -- read-only autopsy of a fusioncap / plio_texcap bag for the GEOMETRY question.
Answers, from the bag alone (no rig, no ROS):

  1. TOPICS      what is in the bag (counts, rates) -- is it re-solvable (/unilidar/cloud)?
  2. IMU STAMPS  host-stamp jitter: the Unitree ROS2 driver stamps every IMU packet with the
                 Jetson's wall clock AT PARSE TIME (not the sensor's sample time). Gaps/bursts
                 here = the driver starving under load. (point_lio_unilidar #21: "2us-100ms")
  3. IMU VALUES  |acc| sanity (unilidar_sdk2 #9: bogus ~21 m/s^2 readings when Z is sideways),
                 gyro magnitude profile (was the rig really still during init? how fast the pan?)
  4. CLOUD       frame spacing + per-point time span per frame (deskew timeline health)
  5. ODOM        /aft_mapped_to_init continuity (gaps = Point-LIO stalled live)
  6. GYRO vs ODOM  integrate the gyro on SO(3) and compare to Point-LIO's orientation over the
                 whole capture: heading (about gravity) odom vs gyro, tilt wander, z wander.
                 If Point-LIO's heading LAGS the gyro -> the live estimate under-rotated (fan).
                 If they agree -> the heading track was fine and the fan is elsewhere.

Deps: numpy, cv2, rosbags (rigstation env). Writes <out>/bag_health.png + prints a report.
Run (Anaconda Prompt, rigstation):
    python bag_health.py <BAG_DIR> [OUT_DIR]
"""
import sys, os
import numpy as np
import cv2
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

IMU_TOPIC = "/unilidar/imu"
CLOUD_TOPIC = "/unilidar/cloud"
ODOM_TOPIC = "/aft_mapped_to_init"


# ---------------------------------------------------------------- rotation helpers
def quat_to_R(q):
    x, y, z, w = q / (np.linalg.norm(q) + 1e-12)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def exp_so3(v):
    th = np.linalg.norm(v)
    if th < 1e-12:
        return np.eye(3)
    k = v / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def rot_angle(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def heading_series(R_list, g, fwd):
    """Continuous heading (deg) of body axis `fwd` about gravity axis `g` (both in body0 frame),
    for a list of body0<-body(t) rotations."""
    g = g / np.linalg.norm(g)
    f0 = fwd - np.dot(fwd, g) * g
    f0 /= np.linalg.norm(f0)
    s = np.cross(g, f0)
    out = []
    for R in R_list:
        f = R @ fwd
        f = f - np.dot(f, g) * g
        out.append(np.arctan2(np.dot(s, f), np.dot(f0, f)))
    return np.degrees(np.unwrap(np.array(out)))


def tilt_series(R_list, g):
    """Angle (deg) between gravity-in-body0 and gravity carried by each rotation (tilt wander)."""
    g = g / np.linalg.norm(g)
    return np.array([np.degrees(np.arccos(np.clip(np.dot(g, R @ g), -1, 1))) for R in R_list])


# ---------------------------------------------------------------- stats helpers
def dstats(d, name, unit="ms", scale=1e3):
    d = np.asarray(d) * scale
    if len(d) == 0:
        print(f"  {name}: (none)")
        return
    p = np.percentile(d, [1, 50, 99])
    print(f"  {name}: n={len(d)}  mean {d.mean():.3f}  p1 {p[0]:.3f}  p50 {p[1]:.3f}  "
          f"p99 {p[2]:.3f}  min {d.min():.3f}  max {d.max():.3f} {unit}")


def plot_panel(img, x0, y0, w, h, series, title, colors):
    """Minimal cv2 line plot: series = list of (x, y) arrays sharing an x-range."""
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (60, 60, 60), 1)
    cv2.putText(img, title, (x0 + 6, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
    xs = np.concatenate([s[0] for s in series if len(s[0])])
    ys = np.concatenate([s[1] for s in series if len(s[1])])
    if len(xs) == 0:
        return
    xa, xb = xs.min(), xs.max()
    ya, yb = ys.min(), ys.max()
    if yb - ya < 1e-9:
        ya, yb = ya - 1, yb + 1
    pad = 0.05 * (yb - ya); ya -= pad; yb += pad
    for (x, y), c in zip(series, colors):
        if len(x) < 2:
            continue
        px = (x0 + 4 + (x - xa) / (xb - xa + 1e-12) * (w - 8)).astype(np.int32)
        py = (y0 + h - 4 - (y - ya) / (yb - ya) * (h - 24)).astype(np.int32)
        pts = np.stack([px, py], 1).reshape(-1, 1, 2)
        cv2.polylines(img, [pts], False, c, 1, cv2.LINE_AA)
    cv2.putText(img, f"{ya:.1f}", (x0 + 4, y0 + h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)
    cv2.putText(img, f"{yb:.1f}", (x0 + 4, y0 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1)


# ---------------------------------------------------------------- main
def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python bag_health.py <BAG_DIR> [OUT_DIR]")
    bag = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(outdir, exist_ok=True)
    ts = get_typestore(Stores.ROS2_HUMBLE)

    imu_t, imu_bt, acc, gyr = [], [], [], []
    od_t, od_bt, od_p, od_q = [], [], [], []
    cl_t, cl_bt, cl_n, cl_span = [], [], [], []
    counts = {}

    with Reader(bag) as r:
        print("=" * 78)
        print("1. TOPICS in", bag)
        print("=" * 78)
        for c in r.connections:
            counts[c.topic] = (c.msgtype, c.msgcount)
            print(f"  {c.topic:40s} {c.msgtype:45s} {c.msgcount}")
        dur = (r.duration or 0) / 1e9
        print(f"  bag duration {dur:.1f} s")
        topics = [t for t in (IMU_TOPIC, CLOUD_TOPIC, ODOM_TOPIC) if t in counts]
        conns = [c for c in r.connections if c.topic in topics]
        for conn, bt, raw in r.messages(connections=conns):
            m = ts.deserialize_cdr(raw, conn.msgtype)
            th = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
            if conn.topic == IMU_TOPIC:
                imu_t.append(th); imu_bt.append(bt * 1e-9)
                a = m.linear_acceleration; g = m.angular_velocity
                acc.append([a.x, a.y, a.z]); gyr.append([g.x, g.y, g.z])
            elif conn.topic == ODOM_TOPIC:
                p = m.pose.pose.position; q = m.pose.pose.orientation
                od_t.append(th); od_bt.append(bt * 1e-9)
                od_p.append([p.x, p.y, p.z]); od_q.append([q.x, q.y, q.z, q.w])
            elif conn.topic == CLOUD_TOPIC:
                cl_t.append(th); cl_bt.append(bt * 1e-9); cl_n.append(m.width * m.height)
                # per-point time span (field 'time', float32) if present
                toff = None
                for f in m.fields:
                    if f.name == "time":
                        toff = f.offset
                if toff is not None and m.width * m.height > 0:
                    buf = np.frombuffer(bytes(m.data), np.uint8)
                    n = m.width * m.height
                    tt = buf.reshape(n, m.point_step)[:, toff:toff + 4].copy().view(np.float32).ravel()
                    cl_span.append(float(tt.max() - tt.min()))

    imu_t = np.array(imu_t); imu_bt = np.array(imu_bt); acc = np.array(acc); gyr = np.array(gyr)
    od_t = np.array(od_t); od_bt = np.array(od_bt); od_p = np.array(od_p); od_q = np.array(od_q)
    cl_t = np.array(cl_t); cl_bt = np.array(cl_bt)

    print("  RE-SOLVABLE OFFLINE:", "YES (/unilidar/cloud present)" if CLOUD_TOPIC in counts
          else "NO  (/unilidar/cloud NOT recorded -> only the live Point-LIO result exists)")

    # ---------------------------------------------------------------- 2. IMU stamps
    print("=" * 78)
    print("2. IMU HOST-STAMP JITTER (/unilidar/imu header.stamp deltas)")
    print("=" * 78)
    if len(imu_t) > 2:
        o = np.argsort(imu_t); imu_t, imu_bt, acc, gyr = imu_t[o], imu_bt[o], acc[o], gyr[o]
        d = np.diff(imu_t)
        dstats(d, "header dt")
        dstats(np.diff(imu_bt), "bag-record dt")
        print(f"  header-vs-bag offset: mean {np.mean(imu_bt - imu_t)*1e3:.1f} ms  "
              f"(header earlier than record = positive)")
        nominal = np.median(d)
        gaps = np.where(d > 2.5 * nominal)[0]
        bursts = np.where(d < 0.25 * nominal)[0]
        print(f"  nominal {nominal*1e3:.2f} ms ({1/nominal:.1f} Hz) | GAPS >2.5x nominal: {len(gaps)} "
              f"(longest {d.max()*1e3:.1f} ms at t=+{(imu_t[d.argmax()]-imu_t[0]):.1f} s) | "
              f"BURSTS <0.25x nominal: {len(bursts)}")
        lost = int(np.sum(np.round(d[gaps] / nominal) - 1)) if len(gaps) else 0
        print(f"  samples implied missing inside gaps: ~{lost}  ({100.0*lost/max(len(d),1):.2f}%)")
        # per-10 s gap map
        T = imu_t - imu_t[0]
        print("  per-10s: [window]  gaps>2.5x  worst_dt_ms")
        for w0 in np.arange(0, T[-1], 10.0):
            m = (T[:-1] >= w0) & (T[:-1] < w0 + 10)
            if m.any():
                print(f"    [{w0:5.0f}-{w0+10:5.0f}s]  {int(np.sum(d[m] > 2.5*nominal)):4d}   {d[m].max()*1e3:7.1f}")
    else:
        print("  no IMU in bag")

    # ---------------------------------------------------------------- 3. IMU values
    print("=" * 78)
    print("3. IMU VALUES")
    print("=" * 78)
    if len(acc):
        an = np.linalg.norm(acc, axis=1); gn = np.linalg.norm(gyr, axis=1)
        T = imu_t - imu_t[0]
        print(f"  |acc| mean {an.mean():.2f}  p1 {np.percentile(an,1):.2f}  p99 {np.percentile(an,99):.2f}  "
              f"max {an.max():.2f} m/s^2   (expect ~9.6-9.8; unilidar_sdk2 #9 fault = ~21)")
        bad = an > 12.0
        print(f"  |acc| > 12 m/s^2 samples: {int(bad.sum())}" +
              (f"  first at t=+{T[bad.argmax()]:.1f} s" if bad.any() else ""))
        gmean = acc[:int(min(len(acc), 250))].mean(0)
        print(f"  gravity in body (first 1 s): [{gmean[0]:+.2f} {gmean[1]:+.2f} {gmean[2]:+.2f}]  "
              f"-> dominant axis {'XYZ'[int(np.argmax(np.abs(gmean)))]}")
        print(f"  |gyro| mean {np.degrees(gn.mean()):.2f} deg/s  p99 {np.degrees(np.percentile(gn,99)):.1f}  "
              f"max {np.degrees(gn.max()):.1f} deg/s")
        still = np.degrees(gn[:int(min(len(gn), 250 * 3))]).mean()
        print(f"  first 3 s mean |gyro| {still:.2f} deg/s  -> {'DEAD-STILL start' if still < 1.0 else 'MOVING start (no dead-still init)'}")
        print("  per-10s mean |gyro| deg/s:", " ".join(
            f"{np.degrees(gn[(T>=w)&(T<w+10)].mean()):.1f}" for w in np.arange(0, T[-1], 10.0) if ((T>=w)&(T<w+10)).any()))

    # ---------------------------------------------------------------- 4. cloud
    print("=" * 78)
    print("4. CLOUD FRAMES (/unilidar/cloud)")
    print("=" * 78)
    if len(cl_t) > 2:
        o = np.argsort(cl_t); cl_t = cl_t[o]; cl_bt = cl_bt[o]
        dstats(np.diff(cl_t), "frame dt")
        print(f"  points/frame median {int(np.median(cl_n))}  min {min(cl_n)}  max {max(cl_n)}")
        if cl_span:
            dstats(np.array(cl_span), "per-point time span", scale=1e3)
            print("  (healthy L2 frame: dt ~83.6 ms, span ~81 ms, ~5.3k pts)")
    else:
        print("  not recorded")

    # ---------------------------------------------------------------- 5. odom
    print("=" * 78)
    print("5. ODOM (/aft_mapped_to_init)")
    print("=" * 78)
    R_rel = heading_od = heading_gy = None
    if len(od_t) > 10:
        o = np.argsort(od_t); od_t, od_bt, od_p, od_q = od_t[o], od_bt[o], od_p[o], od_q[o]
        d = np.diff(od_t); d = d[d > 0]
        dstats(d, "header dt (nonzero)")
        gaps = np.diff(od_t)
        print(f"  longest silence {gaps.max():.2f} s at t=+{(od_t[gaps.argmax()]-od_t[0]):.1f} s  | "
              f"span {od_t[-1]-od_t[0]:.1f} s | msgs {len(od_t)}")
        ext = od_p.max(0) - od_p.min(0)
        print(f"  position extent x {ext[0]:.2f}  y {ext[1]:.2f}  z {ext[2]:.2f} m")
    else:
        print("  not recorded / too short")

    # ---------------------------------------------------------------- 6. gyro vs odom
    print("=" * 78)
    print("6. GYRO-INTEGRATED vs POINT-LIO ORIENTATION")
    print("=" * 78)
    if len(od_t) > 10 and len(imu_t) > 10:
        t0 = max(od_t[0], imu_t[0]); t1 = min(od_t[-1], imu_t[-1])
        if t1 - t0 < 2:
            print("  no shared timeline (>2 s) between IMU and odom header stamps")
        else:
            # gyro integration on SO(3), body0<-body(t), starting at t0
            mi = (imu_t >= t0) & (imu_t <= t1)
            gt, gw = imu_t[mi], gyr[mi]
            Rg = [np.eye(3)]
            for i in range(1, len(gt)):
                dt = gt[i] - gt[i - 1]
                if not 0 < dt < 0.5:
                    Rg.append(Rg[-1]); continue
                Rg.append(Rg[-1] @ exp_so3(0.5 * (gw[i] + gw[i - 1]) * dt))
            # odom at ~50 Hz on the same window
            mo = (od_t >= t0) & (od_t <= t1)
            ot, oq, op = od_t[mo], od_q[mo], od_p[mo]
            step = max(1, int(round(len(ot) / max(ot[-1] - ot[0], 1e-6) / 50)))
            ot, oq, op = ot[::step], oq[::step], op[::step]
            R0 = quat_to_R(oq[0])
            Ro = [R0.T @ quat_to_R(q) for q in oq]            # body0<-body(t)
            # gyro rotation sampled at odom times
            idx = np.clip(np.searchsorted(gt, ot), 0, len(Rg) - 1)
            Rg_at = [Rg[i] for i in idx]
            g_b0 = acc[mi][:250].mean(0)                       # gravity in body0 (first ~1 s of window)
            ax = int(np.argmin(np.abs(g_b0 / np.linalg.norm(g_b0))))   # body axis most perpendicular to g
            fwd = np.eye(3)[ax]
            heading_od = heading_series(Ro, g_b0, fwd)
            heading_gy = heading_series(Rg_at, g_b0, fwd)
            tilt_od = tilt_series(Ro, g_b0)
            tilt_gy = tilt_series(Rg_at, g_b0)
            diff = np.array([rot_angle(a.T @ b) for a, b in zip(Ro, Rg_at)])
            T = ot - ot[0]
            print(f"  window {T[-1]:.1f} s | heading axis = body {'XYZ'[ax]} about gravity (body {'XYZ'[int(np.argmax(np.abs(g_b0)))]})")
            print(f"  TOTAL heading: odom {heading_od[-1]-heading_od[0]:+.1f} deg | gyro {heading_gy[-1]-heading_gy[0]:+.1f} deg | "
                  f"ratio odom/gyro {((heading_od[-1]-heading_od[0])/(heading_gy[-1]-heading_gy[0]+1e-9)):.3f}")
            print(f"  heading divergence |odom-gyro|: max {np.abs((heading_od-heading_od[0])-(heading_gy-heading_gy[0])).max():.1f} deg | "
                  f"full-rotation divergence max {diff.max():.1f} deg")
            print(f"  tilt wander (deg from start): odom max {tilt_od.max():.1f} | gyro max {tilt_gy.max():.1f}")
            print(f"  z wander: {op[:,2].min():+.2f}..{op[:,2].max():+.2f} m")
            print("  per-10s: t   odom_hdg   gyro_hdg   diff   odom_tilt   z")
            for w0 in np.arange(0, T[-1] + 1e-6, 10.0):
                i = int(np.searchsorted(T, w0)); i = min(i, len(T) - 1)
                print(f"    {T[i]:5.0f}  {heading_od[i]-heading_od[0]:+8.1f}  {heading_gy[i]-heading_gy[0]:+8.1f}  "
                      f"{(heading_od[i]-heading_od[0])-(heading_gy[i]-heading_gy[0]):+6.1f}  {tilt_od[i]:6.1f}  {op[i,2]:+6.2f}")
            print("  READ: ratio ~1.00 & diff small  -> live heading tracked the gyro (fan is NOT heading lag)")
            print("        ratio <1 / diff growing   -> Point-LIO UNDER-ROTATED vs gyro (heading lag = fan)")
            print("        tilt wander >2 deg        -> world frame tilting during the pan (init/gravity)")

            # ---- figure
            W, H = 1400, 1000
            img = np.full((H, W, 3), 20, np.uint8)
            cv2.putText(img, f"bag_health  {os.path.basename(bag.rstrip('/'))}", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            plot_panel(img, 10, 40, 680, 300, [(T, heading_od - heading_od[0]), (T, heading_gy - heading_gy[0])],
                       "heading deg: odom (yellow) vs gyro (cyan)", [(0, 220, 255), (255, 220, 0)])
            plot_panel(img, 710, 40, 680, 300, [(T, (heading_od - heading_od[0]) - (heading_gy - heading_gy[0]))],
                       "heading diff odom-gyro (deg)", [(80, 80, 255)])
            plot_panel(img, 10, 360, 680, 300, [(T, tilt_od), (T, tilt_gy)],
                       "tilt from start (deg): odom (yellow) vs gyro (cyan)", [(0, 220, 255), (255, 220, 0)])
            plot_panel(img, 710, 360, 680, 300, [(T, op[:, 2] - op[0, 2])], "odom z (m)", [(120, 255, 120)])
            Ti = imu_t - imu_t[0]
            plot_panel(img, 10, 680, 680, 300, [(Ti[1:], np.diff(imu_t) * 1e3)], "IMU header dt (ms)", [(200, 200, 200)])
            plot_panel(img, 710, 680, 680, 300, [(Ti, np.linalg.norm(acc, axis=1))], "|acc| m/s^2", [(255, 160, 80)])
            out = os.path.join(outdir, "bag_health.png")
            cv2.imwrite(out, img)
            print("  wrote", out)
    else:
        print("  need both IMU and odom in the bag")


if __name__ == "__main__":
    main()
