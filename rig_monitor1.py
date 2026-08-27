#!/usr/bin/env python3
"""
rig_monitor.py  —  LIVE RIG HEARTBEAT   (flow + card + heat, one glance)   v3

A CONSTANT live monitor (not an end-of-capture autopsy). Run DURING capture; one screen
shows everything that can kill or damage a capture, as glanceable bars:

  FLOW    — per-sensor bars: is data arriving at the normal rate? (drop -> red + ALARM)
  CARD    — recording time left (free space / measured write rate) -> warns before full
  HEAT    — Jetson + L2 temperature -> warns before throttle/damage

Founding principle: TIME is the universal marker (data rate is a hardware constant, independent
of scene/motion/pipeline). Rigor is CONSTANT & LIVE, not a surprise at the end. Visual check
(watching the live cloud) remains the standing backstop.

USAGE (on the Jetson, rig running):
    python3 rig_monitor.py
    python3 rig_monitor.py --record-path /media/usb0     # enables the card fuel gauge

Calibrated to the real rig 2026-08-27 (ros2 topic hz). Temp bands: your 50/55 ceiling.
"""
import sys, os, time, glob, shutil, argparse
from collections import deque

# ── NOMINAL RATES: MEASURED on the real rig 2026-08-27 ──
#   LiDAR 12.0Hz steady | Camera ~30Hz warmed-up (topic-hz avg lags; runs near requested 30) |
#   IMU 251Hz steady | Odom ~100Hz but ONLY while Point-LIO runs (neutral when absent, see below)
STREAMS = {
    "LiDAR ":  {"topic":"/unilidar/cloud",    "hz":12.0,  "type":"PointCloud2", "capture_only":False},
    "Camera":  {"topic":"/image_raw",         "hz":30.0,  "type":"Image",       "capture_only":False},
    "IMU   ":  {"topic":"/unilidar/imu",      "hz":251.0, "type":"Imu",         "capture_only":False},
    "Odom  ":  {"topic":"/aft_mapped_to_init","hz":100.0, "type":"Odometry",    "capture_only":True},
}
WINDOW    = 2.0     # sec rate-averaging (smooths the camera's real ~400ms jitter)
DROP_FRAC = 0.35    # below this fraction of nominal = DROPPED (0.35 tolerates camera jitter)
GREEN_FRAC= 0.70
BAR_W     = 20

# ── TEMP thresholds (operator spec 2026-08-27): green <50 / yellow 50-55 / red >55 ──
TEMP_GREEN = 50.0
TEMP_YELLOW= 55.0
# L2 temperature topic — UNCONFIRMED. Set this once `ros2 topic list` reveals the real one.
L2_TEMP_TOPIC = None   # e.g. "/unilidar/status"  (field: apd_temperature)

C_CODES={"green":"\033[92m","yellow":"\033[93m","red":"\033[91m","dim":"\033[2m","reset":"\033[0m"}
def col(s,c): return f"{C_CODES.get(c,'')}{s}{C_CODES['reset']}"
def bar(frac,w=BAR_W):
    frac=max(0.0,min(1.0,frac)); f=int(round(frac*w)); return "█"*f+"░"*(w-f)

class RateTracker:
    def __init__(self): self.stamps=deque(); self.ever=False
    def tick(self,t): self.stamps.append(t); self.ever=True
    def rate(self,now):
        while self.stamps and now-self.stamps[0]>WINDOW: self.stamps.popleft()
        return len(self.stamps)/WINDOW if self.stamps else 0.0

def read_jetson_temp():
    """Hottest Linux thermal zone in °C, or None."""
    best=None
    for z in glob.glob('/sys/class/thermal/thermal_zone*'):
        try:
            c=int(open(os.path.join(z,'temp')).read().strip())/1000.0
            best=c if best is None else max(best,c)
        except Exception: pass
    return best

def temp_band(c):
    if c is None: return "dim","--"
    if c < TEMP_GREEN:  return "green","ok"
    if c < TEMP_YELLOW: return "yellow","watch"
    return "red","HOT — cool it"

def human_time(sec):
    if sec is None or sec<0: return "??"
    return f"{int(sec//60)}m{int(sec%60):02d}s"

def draw(rates, trackers, capturing, jtemp, l2temp, est_bps, free, running_s):
    os.system('clear')
    print(col("  ═══ RIG MONITOR — live heartbeat ═══","green"))
    print(f"  up {human_time(running_s)}   {'[CAPTURING]' if capturing else '[rig on, not capturing]'}   (Ctrl-C to stop)\n")
    alarm=False
    # FLOW
    for name,cfg in STREAMS.items():
        r=rates[name]; nom=cfg["hz"]; frac=r/nom if nom else 0
        if cfg["capture_only"] and not capturing:
            # Odom when Point-LIO isn't running: neutral, NOT an alarm
            print(f"   {name}  {col(bar(0),'dim')}  {col('waiting for Point-LIO (not capturing)','dim')}")
            continue
        if frac>=GREEN_FRAC: c="green"; tag="✓"
        elif frac>=DROP_FRAC: c="yellow"; tag="low"
        else:
            c="red"; tag="✗ DROPPED"
            # only a real drop alarms: a stream that was flowing (ever) and now isn't,
            # or a non-capture-only sensor that's dead
            if trackers[name].ever or not cfg["capture_only"]: alarm=True
        print(f"   {name}  {col(bar(frac),c)}  {r:5.1f}/{nom:.0f}Hz {col(tag,c)}")
    print()
    # CARD
    if free is not None and est_bps and est_bps>0:
        secs=free/est_bps
        c="green" if secs>300 else ("yellow" if secs>120 else "red")
        print(f"   Card    {col(bar(min(1,secs/(30*60))),c)}  {col(human_time(secs)+' left',c)}  ({free/1e9:.1f}GB free, {est_bps/1e6:.0f}MB/s)")
    else:
        print(f"   Card    {col(bar(0),'dim')}  {col('(measuring… give --record-path)','dim')}")
    print()
    # HEAT
    for label,t in [("Jetson",jtemp),("L2    ",l2temp)]:
        c,tag=temp_band(t)
        frac=(t/85.0) if t is not None else 0   # scale to ~throttle point
        val=f"{t:.1f}°C" if t is not None else "??"
        note = "" if t is not None else ("(topic not set)" if label.strip()=="L2" else "(no zones?)")
        print(f"   {label}  {col(bar(frac),c)}  {col(val,c):>8s}  {col(tag,c)} {col(note,'dim')}")
        if c=="red" and t is not None: alarm=True
    print()
    if alarm:
        print(col("   *** ALARM: something needs attention (dropped stream or overheat) ***","red"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--record-path", default=None)
    args=ap.parse_args()
    try:
        import rclpy
        from sensor_msgs.msg import PointCloud2, Image, Imu
        from nav_msgs.msg import Odometry
    except Exception as e:
        print(f"ERROR: rclpy not available — run on the Jetson in the ROS2 env. ({e})"); sys.exit(2)
    tmap={"PointCloud2":PointCloud2,"Image":Image,"Imu":Imu,"Odometry":Odometry}
    trackers={n:RateTracker() for n in STREAMS}
    rclpy.init(); node=rclpy.create_node("rig_monitor")
    for name,cfg in STREAMS.items():
        node.create_subscription(tmap[cfg["type"]], cfg["topic"],
                                 (lambda m, tr=trackers[name]: tr.tick(time.time())), 10)
    # optional L2 temp subscription (only if a topic is configured)
    l2=[None]
    if L2_TEMP_TOPIC:
        try:
            # generic: expect a message with apd_temperature; wire concretely once topic known
            from rclpy.qos import qos_profile_sensor_data
            # placeholder: user sets the real msg type + field after `ros2 topic info`
            pass
        except Exception: pass

    start=time.time(); last=0; prev_free=prev_t=None; est=None
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            now=time.time()
            if now-last>0.5:
                rates={n:trackers[n].rate(now) for n in STREAMS}
                capturing = trackers["Odom  "].rate(now) > STREAMS["Odom  "]["hz"]*DROP_FRAC
                free=None
                if args.record_path and os.path.exists(args.record_path):
                    try:
                        free=shutil.disk_usage(args.record_path).free
                        if prev_free is not None and now>prev_t:
                            d=(prev_free-free)/(now-prev_t)
                            if d>1e5: est=0.7*(est or d)+0.3*d if est else d
                        prev_free,prev_t=free,now
                    except Exception: pass
                draw(rates, trackers, capturing, read_jetson_temp(), l2[0], est, free, now-start)
                last=now
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.shutdown()

if __name__=="__main__":
    main()
