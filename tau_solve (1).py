#!/usr/bin/env python3
"""TAU SOLVER: camera-vs-LiDAR clock offset from an ordinary fusioncap bag.
Method (Master §2, 'triple-vetted, result pending'): build a MOTION-SPEED signal from
each side - camera = mean |frame difference| rate, odometry = angular+linear speed -
then cross-correlate. The clocks' offset is the lag that aligns the two signals.
Gates (Master's own): peak width (>0.5 peak) < 100 ms AND half-split agreement < 30 ms.
Output speaks the correction rule directly: how much to SUBTRACT from LiDAR stamps."""
import sys, os, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quatmath import matrix_from_quat
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

def motion_signals(bag, image_topic, odom_topic, img_stride=1):
    ts = get_typestore(Stores.ROS2_HUMBLE)
    cam_t, cam_v = [], []
    od_t, od_q, od_p = [], [], []
    prev = None
    with Reader(bag) as r:
        conns = [c for c in r.connections if c.topic in (image_topic, odom_topic)]
        k = 0
        for conn, tb, raw in r.messages(connections=conns):
            m = ts.deserialize_cdr(raw, conn.msgtype)
            th = m.header.stamp.sec + m.header.stamp.nanosec*1e-9
            if conn.topic == odom_topic:
                p = m.pose.pose.position; q = m.pose.pose.orientation
                od_t.append(th); od_p.append([p.x,p.y,p.z]); od_q.append([q.x,q.y,q.z,q.w])
            else:
                k += 1
                if k % img_stride: continue
                raw8 = np.frombuffer(bytes(m.data), np.uint8)
                g = raw8.astype(np.float32).reshape(m.height, m.width, -1).mean(2)
                bh, bw = m.height//12, m.width//16
                img = g[:12*bh, :16*bw].reshape(12, bh, 16, bw).mean((1, 3)).ravel()  # 12x16 coarse blocks
                if prev is not None and len(img) == len(prev[1]):
                    dt = th - prev[0]
                    if 0 < dt < 1.0:
                        cam_t.append(0.5*(th+prev[0]))
                        cam_v.append(float(np.abs(img-prev[1]).mean())/dt)
                prev = (th, img)
    od_t = np.array(od_t); od_p = np.array(od_p); od_q = np.array(od_q)
    o = np.argsort(od_t); od_t, od_p, od_q = od_t[o], od_p[o], od_q[o]
    step = max(1, int(round((len(od_t)/(od_t[-1]-od_t[0]))/50)))   # ~50 Hz
    od_t, od_p, od_q = od_t[::step], od_p[::step], od_q[::step]
    sp_t, sp_v = [], []
    for i in range(1, len(od_t)):
        dt = od_t[i]-od_t[i-1]
        if not 0 < dt < 1.0: continue
        R0 = matrix_from_quat(od_q[i-1]); R1 = matrix_from_quat(od_q[i])
        dR = R0.T @ R1
        ang = np.arccos(np.clip((np.trace(dR)-1)/2, -1, 1))
        lin = np.linalg.norm(od_p[i]-od_p[i-1])
        sp_t.append(0.5*(od_t[i]+od_t[i-1])); sp_v.append(ang/dt)
    return np.array(cam_t), np.array(cam_v), np.array(sp_t), np.array(sp_v)

def zs(x):
    r = np.empty(len(x)); r[np.argsort(x)] = np.arange(len(x))   # rank transform:
    r /= max(len(x)-1, 1)                                        # immune to clipping/saturation
    return (r - r.mean()) / (r.std() + 1e-9)

def hp(x, dt=0.02, sigma_s=0.4):
    """high-pass: remove the slow speed envelope so the correlation peak is SHARP.
    slow envelopes correlate over ~seconds of lag (plateau); fast fluctuations localize."""
    n = int(4*sigma_s/dt) | 1
    k = np.exp(-0.5*((np.arange(n)-n//2)*dt/sigma_s)**2); k /= k.sum()
    return x - np.convolve(x, k, mode="same")

def solve(cam_t, cam_v, od_t, od_v, max_lag=0.6, grid=0.005):
    if len(cam_t) < 10 or len(od_t) < 10:
        return float("nan"), 0.0, float("inf"), None
    lo = max(cam_t.min(), od_t.min()) + max_lag
    hi = min(cam_t.max(), od_t.max()) - max_lag
    if hi - lo < 3.0:                       # under 3 s of usable overlap: refuse honestly
        return float("nan"), 0.0, float("inf"), None
    tt = np.arange(lo, hi, 0.02)
    cam = zs(hp(np.interp(tt, cam_t, cam_v)))
    lags = np.arange(-max_lag, max_lag+1e-9, grid)
    corr = np.array([float(np.dot(cam, zs(hp(np.interp(tt+L, od_t, od_v))))) for L in lags]) / len(tt)
    i = int(np.argmax(corr))
    # parabolic sub-grid refinement
    if 0 < i < len(lags)-1:
        y0,y1,y2 = corr[i-1],corr[i],corr[i+1]
        d = (y0-y2)/(2*(y0-2*y1+y2)+1e-12)
        tau = lags[i] + d*grid
    else:
        tau = lags[i]
    half = corr >= 0.5*corr[i]
    width = (half.sum()) * grid
    return tau, float(corr[i]), width, (lags, corr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag"); ap.add_argument("--image-topic", default="/image_raw")
    ap.add_argument("--odom-topic", default="/aft_mapped_to_init")
    a = ap.parse_args()
    ct, cv, ot, ov = motion_signals(a.bag, a.image_topic, a.odom_topic)
    print(f"[tau] camera samples {len(ct)} | odom speed samples {len(ot)}", flush=True)
    if len(ct) < 20 or len(ot) < 20:
        print("[tau] not enough motion data"); sys.exit(2)
    tau, peak, width, _ = solve(ct, cv, ot, ov)
    if not np.isfinite(tau):
        print("[tau] INSUFFICIENT OVERLAP between camera and odometry - no estimate"); sys.exit(2)
    # split the OVERLAP window (not the camera span - odometry may be much shorter)
    lo = max(ct.min(), ot.min()); hi = min(ct.max(), ot.max()); mid = 0.5*(lo+hi)
    tA = solve(ct[ct<mid], cv[ct<mid], ot, ov)[0]
    tB = solve(ct[ct>=mid], cv[ct>=mid], ot, ov)[0]
    halves = abs(tA-tB) if (np.isfinite(tA) and np.isfinite(tB)) else float("inf")
    ok = width < 0.100 and halves < 0.030
    if not np.isfinite(halves):
        print("[tau] halves check unavailable (overlap too short to split) - gate fails honestly")
    print(f"[tau] OFFSET (lidar-clock minus camera-clock): {tau*1000:+.1f} ms   peak corr {peak:.2f}")
    print(f"[tau] gates: peak width {width*1000:.0f} ms (<100) | halves differ {halves*1000:.1f} ms (<30)  -> {'PASS' if ok else 'WEAK - do not trust'}")
    if tau > 0:
        print(f"[tau] rule: LiDAR LAGS camera. SUBTRACT {abs(tau)*1000:.1f} ms from LiDAR timestamps.")
    else:
        print(f"[tau] rule: camera LAGS LiDAR. SUBTRACT {abs(tau)*1000:.1f} ms from camera timestamps.")
    json.dump({"tau_s": round(float(tau),4), "peak": round(peak,3),
               "width_s": round(float(width),3), "halves_s": round(float(halves),4),
               "gates_pass": bool(ok)}, open(os.path.basename(a.bag.rstrip('/'))+".tau.json","w"))

if __name__ == "__main__":
    main()
