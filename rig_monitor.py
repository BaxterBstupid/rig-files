#!/usr/bin/env python3
"""
rig_monitor.py  —  LIVE RIG HEARTBEAT + CARD FUEL GAUGE   (constant, glanceable)

A CONSTANT live monitor (not an end-of-capture autopsy). Run it DURING capture; it
draws two things you take in at a glance:

  1. FLOW HEARTBEAT — per-sensor bars showing data is actually arriving at normal rates.
     A stream that drops -> its bar collapses to red the INSTANT it happens.
  2. CARD FUEL GAUGE — recording time left on the drive (free space / measured data rate),
     draining live, green->yellow->red as it fills.

Founding principle: TIME is the universal marker. Expected data rate is a hardware constant,
independent of scene, motion, or the downstream pipeline. If runtime elapses and the expected
data isn't arriving -> fault. Geometry/coverage are NOT used here (content-dependent).

Terminal text-bars: dependency-free, renders identically on the bench monitor and the
Waveshare. Glanceable — green+full = keep rolling; collapsed/red = look now.

USAGE (on the Jetson, rig running):
    python3 rig_monitor.py                       # watches default topics, records-path guess
    python3 rig_monitor.py --record-path /media/usb0   # point at the actual capture drive

The VISUAL check (watching the live cloud) remains the standing backstop; this is the
numeric heartbeat beside it.
"""
import sys, os, time, shutil, argparse, threading
from collections import deque

# ---- expected nominal rates (Hz) — the hardware constants ----
# ── NOMINAL RATES: MEASURED on the real rig 2026-08-27 via `ros2 topic hz` ──
#   LiDAR  12.0Hz  (rock steady, ~0 jitter)
#   Camera ~14Hz   (VARIABLE 10-15Hz, heavy jitter — frames up to ~400ms apart is NORMAL)
#   IMU    251Hz   (rock steady)
#   Odom   ~100Hz  (ONLY publishes while Point-LIO is running — expect red bar otherwise)
STREAMS = {
    "LiDAR ":  {"topic":"/unilidar/cloud",    "hz":12.0,  "type":"PointCloud2"},
    "Camera":  {"topic":"/image_raw",         "hz":14.0,  "type":"Image"},
    "IMU   ":  {"topic":"/unilidar/imu",      "hz":251.0, "type":"Imu"},
    "Odom  ":  {"topic":"/aft_mapped_to_init","hz":100.0, "type":"Odometry"},
}
WINDOW = 2.0          # seconds of rate-averaging
DROP_FRAC = 0.35      # below this fraction of nominal rate for a stream = DROPPED alarm
BAR_W = 20

def bar(frac, w=BAR_W):
    frac=max(0.0,min(1.0,frac))
    fill=int(round(frac*w))
    return "█"*fill + "░"*(w-fill)

def color(s, c):
    codes={"green":"\033[92m","yellow":"\033[93m","red":"\033[91m","dim":"\033[2m","reset":"\033[0m"}
    return f"{codes.get(c,'')}{s}{codes['reset']}"

class RateTracker:
    def __init__(self): self.stamps=deque()
    def tick(self, t): self.stamps.append(t)
    def rate(self, now):
        while self.stamps and now-self.stamps[0]>WINDOW: self.stamps.popleft()
        return len(self.stamps)/WINDOW if self.stamps else 0.0

def human_time(sec):
    if sec is None: return "??"
    if sec<0: sec=0
    m=int(sec//60); s=int(sec%60)
    return f"{m}m{s:02d}s"

def draw(trackers, rates, record_path, data_rate_bps, free_bytes, running_s):
    os.system('clear')
    print(color("  ═══ RIG MONITOR — live heartbeat ═══", "green"))
    print(f"  recording {human_time(running_s)}   (Ctrl-C to stop monitor)\n")
    # flow bars
    any_drop=False
    for name,cfg in STREAMS.items():
        r=rates.get(name,0.0); nom=cfg["hz"]
        frac=r/nom if nom else 0
        if frac>=0.7:      c="green"; tag="✓"
        elif frac>=DROP_FRAC: c="yellow"; tag="low"
        else:              c="red"; tag="✗ DROPPED"; any_drop=True
        print(f"   {name}  {color(bar(frac),c)}  {r:5.1f}/{nom:.0f}Hz {color(tag,c)}")
    print()
    # card fuel gauge
    if free_bytes is not None and data_rate_bps and data_rate_bps>0:
        secs_left=free_bytes/data_rate_bps
        # frac of a nominal "full session" — show relative to e.g. 30 min headroom scale
        scale=30*60
        frac=min(1.0, secs_left/scale)
        c = "green" if secs_left>300 else ("yellow" if secs_left>120 else "red")
        gb_free=free_bytes/1e9; rate_mbs=data_rate_bps/1e6
        print(f"   Card   {color(bar(frac),c)}  {color(human_time(secs_left)+' left',c)}   "
              f"({gb_free:.1f}GB free, {rate_mbs:.0f}MB/s)")
    else:
        print(f"   Card   {color(bar(0),'dim')}  (measuring rate…)")
    print()
    if any_drop:
        print(color("   *** ALARM: a sensor stream has DROPPED — something fell out ***","red"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--record-path", default=None, help="path on the capture drive (for free-space)")
    args=ap.parse_args()

    try:
        import rclpy
        from rclpy.node import Node
        from sensor_msgs.msg import PointCloud2, Image, Imu
        from nav_msgs.msg import Odometry
    except Exception as e:
        print("ERROR: ROS2 python (rclpy) not available in this environment.")
        print(f"  ({e})")
        print("Run this on the Jetson inside the ROS2 env. (Logic self-test: --selftest)")
        sys.exit(2)

    typemap={"PointCloud2":PointCloud2,"Image":Image,"Imu":Imu,"Odometry":Odometry}
    trackers={n:RateTracker() for n in STREAMS}

    rclpy.init()
    node=rclpy.create_node("rig_monitor")
    for name,cfg in STREAMS.items():
        t=trackers[name]
        node.create_subscription(typemap[cfg["type"]], cfg["topic"],
                                 (lambda msg, tr=t: tr.tick(time.time())), 10)

    # data-rate for fuel gauge: sample the record dir's growth, OR estimate from nominal
    record_path=args.record_path
    start=time.time()
    last_draw=0
    # rough data-rate estimate: measure free-space delta over time if path given
    prev_free=None; prev_t=None; est_bps=None
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
            now=time.time()
            if now-last_draw>0.5:
                rates={n:trackers[n].rate(now) for n in STREAMS}
                free=None
                if record_path and os.path.exists(record_path):
                    try:
                        free=shutil.disk_usage(record_path).free
                        if prev_free is not None and now>prev_t:
                            d=(prev_free-free)/(now-prev_t)   # bytes/s being written
                            if d>1e5: est_bps=0.7*(est_bps or d)+0.3*d if est_bps else d
                        prev_free, prev_t = free, now
                    except Exception: pass
                draw(trackers, rates, record_path, est_bps, free, now-start)
                last_draw=now
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()

if __name__=="__main__":
    if "--selftest" in sys.argv:
        print("selftest handled by separate harness"); sys.exit(0)
    main()
