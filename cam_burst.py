#!/usr/bin/env python3
# cam_burst.py v2 — LEAD-IN delay + save a SEQUENCE of frames over a pan.
# Reads the TOPIC /camera/image_raw/compressed (coexists with node/pad/rqt).
#
# Usage:  python3 cam_burst.py OUTDIR [DURATION_S] [LEAD_S] [INTERVAL_S]
#   OUTDIR     : folder for the frames (created if needed)
#   DURATION_S : capture length once it starts (default 10)
#   LEAD_S     : countdown before capture starts, so you can walk to the rig (default 20)
#   INTERVAL_S : min seconds between saved frames (default 0.4 -> ~25 frames over 10 s)
#
# Beeps (terminal bell) on the last 5 s of the lead-in and a double-beep at GO.
# Each saved frame is one full sensor integration, so at long exposure the frame IS the smear.
import sys, os, time
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage

def beep():
    try:
        sys.stdout.write('\a'); sys.stdout.flush()
    except Exception:
        pass

def main():
    outdir   = sys.argv[1] if len(sys.argv) > 1 else 'pan_frames'
    dur      = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    lead     = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0
    interval = float(sys.argv[4]) if len(sys.argv) > 4 else 0.4
    os.makedirs(outdir, exist_ok=True)

    rclpy.init()
    node = rclpy.create_node('cam_burst')
    qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST)
    holder = {}
    node.create_subscription(CompressedImage, '/camera/image_raw/compressed',
                             lambda m: holder.__setitem__('data', bytes(m.data)), qos)

    # --- LEAD-IN: walk to the rig; discovery warms up while we wait ---
    print("Lead-in %.0f s — walk to the rig. Then capturing %.0f s into %s."
          % (lead, dur, outdir), flush=True)
    print("(beeps on the last 5 s; DOUBLE-beep = start panning)", flush=True)
    t_go = time.time() + lead
    last_tick = None
    while time.time() < t_go:
        rclpy.spin_once(node, timeout_sec=0.05)
        r = int(t_go - time.time()) + 1
        if 1 <= r <= 5 and r != last_tick:
            print("  %d ..." % r, flush=True); beep(); last_tick = r

    print("*** PAN NOW ***", flush=True); beep(); beep()

    # --- CAPTURE window ---
    t_end = time.time() + dur
    next_save = time.time()
    n = 0; last = None; last_saved = None
    while rclpy.ok() and time.time() < t_end:
        rclpy.spin_once(node, timeout_sec=0.05)
        if 'data' in holder:
            last = holder['data']
        now = time.time()
        if last is not None and last is not last_saved and now >= next_save:
            with open(os.path.join(outdir, "frame_%03d.jpg" % n), 'wb') as f:
                f.write(last)
            last_saved = last; n += 1; next_save += interval

    print("done — saved %d frames to %s" % (n, outdir), flush=True); beep()
    if n == 0:
        print("!! NO FRAMES — is the camera node up?", file=sys.stderr)
    node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__':
    main()
