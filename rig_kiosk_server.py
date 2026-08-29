#!/usr/bin/env python3
"""
rig_kiosk_server.py  —  FUNCTIONAL FIELD KIOSK backend (Plan A)

One small dependency-free server that:
  1. serves the kiosk page (rig_kiosk.html) to a fullscreen browser on the Waveshare
  2. reads LIVE rig health (the rig_monitor engine: ROS2 rates + Jetson temp + card space
     + L2 apd_temperature) and serves it as JSON at /data
  3. fires the REAL existing scripts when buttons are tapped (/action?do=start|stop|capture)

Design: rugged = few parts. Uses Python's built-in http.server (no Flask/pip).
The reading logic is rig_monitor.py's engine, refactored to RETURN a dict instead of
drawing terminal bars — so the kiosk absorbs rig_monitor (Plan A) and the terminal
version can retire once this is proven hot.

RUN (on the Jetson, in the ROS2 env):
    source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash
    python3 rig_kiosk_server.py
then open a fullscreen browser at http://localhost:8080  (chromium --kiosk http://localhost:8080)

SET USE_MOCK=1 to run WITHOUT ROS (sandbox/PC demo — fake data, buttons no-op-logged).
"""
import os, sys, json, time, threading, subprocess, glob, shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

USE_MOCK = os.environ.get("USE_MOCK", "0") == "1"
PORT = int(os.environ.get("KIOSK_PORT", "8080"))
HERE = os.path.dirname(os.path.abspath(__file__))

# --- the REAL scripts the buttons fire (confirmed from the desktop icons) ---
SCRIPTS = {
    "start":   os.path.expanduser("~/rig_start.sh"),
    "stop":    os.path.expanduser("~/rig_stop.sh"),
    "capture": os.path.expanduser("~/point_lio_capture.sh"),
}
RECORD_PATH = os.environ.get("RECORD_PATH", os.path.expanduser("~/Desktop"))

# nominal rates (measured 2026-08-27) — same as rig_monitor v3
STREAMS = {
    "lidar":  {"topic": "/unilidar/cloud",       "hz": 12.0,  "type": "PointCloud2"},
    "camera": {"topic": "/image_raw",            "hz": 30.0,  "type": "Image"},
    "imu":    {"topic": "/unilidar/imu",         "hz": 251.0, "type": "Imu"},
    "odom":   {"topic": "/aft_mapped_to_init",   "hz": 100.0, "type": "Odometry", "capture_only": True},
}
L2_TEMP_TOPIC = "/unilidar/apd_temperature"   # now published by our driver mod
TEMP_GREEN, TEMP_YELLOW = 68.0, 80.0          # recalibrated to the 59-63C baseline

# ============================================================
# DATA SOURCE — real ROS2 on the Jetson, or mock in sandbox/PC
# ============================================================
STATE = {"data": {}, "lock": threading.Lock()}

def mock_reader():
    """Fake but plausible live data for sandbox/PC testing."""
    import random
    t0 = time.time()
    while True:
        cap = (int(time.time()) // 15) % 2 == 0   # pretend we toggle capture every 15s
        d = {
            "lidar":  {"hz": 12.0, "frac": 1.0, "state": "ok"},
            "camera": {"hz": 29 + random.uniform(-1,1), "frac": 0.97, "state": "ok"},
            "imu":    {"hz": 251, "frac": 1.0, "state": "ok"},
            "odom":   ({"hz": 99, "frac": 0.99, "state": "ok"} if cap
                       else {"hz": 0, "frac": 0, "state": "waiting"}),
            "card":   {"secs_left": 1080, "gb_free": 210, "state": "ok"},
            "jetson": {"temp": 61 + random.uniform(-1,1), "state": "watch"},
            "l2":     {"temp": 38 + random.uniform(-1,1), "state": "ok"},
            "capturing": cap,
            "rig_on": True,
        }
        with STATE["lock"]:
            STATE["data"] = d
        time.sleep(0.5)

def ros_reader():
    """Real reader — rig_monitor's engine, returning a dict. Jetson only."""
    import rclpy
    from collections import deque
    from sensor_msgs.msg import PointCloud2, Image, Imu
    from nav_msgs.msg import Odometry
    from std_msgs.msg import Float32
    tmap = {"PointCloud2": PointCloud2, "Image": Image, "Imu": Imu, "Odometry": Odometry}
    WINDOW = 2.0
    stamps = {k: deque() for k in STREAMS}
    ever   = {k: False for k in STREAMS}
    l2_temp = {"v": None}

    rclpy.init()
    node = rclpy.create_node("rig_kiosk")
    for k, cfg in STREAMS.items():
        def cb(msg, kk=k): stamps[kk].append(time.time()); ever[kk] = True
        node.create_subscription(tmap[cfg["type"]], cfg["topic"], cb, 10)
    node.create_subscription(Float32, L2_TEMP_TOPIC, lambda m: l2_temp.__setitem__("v", m.data), 10)

    def rate(k, now):
        dq = stamps[k]
        while dq and now - dq[0] > WINDOW: dq.popleft()
        return len(dq) / WINDOW if dq else 0.0

    def jetson_temp():
        best = None
        for z in glob.glob('/sys/class/thermal/thermal_zone*'):
            try:
                c = int(open(os.path.join(z, 'temp')).read().strip()) / 1000.0
                best = c if best is None else max(best, c)
            except Exception: pass
        return best

    def band(t):
        if t is None: return "na"
        if t < TEMP_GREEN: return "ok"
        if t < TEMP_YELLOW: return "watch"
        return "hot"

    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.05)
        now = time.time()
        capturing = rate("odom", now) > STREAMS["odom"]["hz"] * 0.35
        d = {}
        for k, cfg in STREAMS.items():
            r = rate(k, now); frac = r / cfg["hz"] if cfg["hz"] else 0
            if cfg.get("capture_only") and not capturing:
                d[k] = {"hz": 0, "frac": 0, "state": "waiting"}
            else:
                st = "ok" if frac >= 0.7 else ("low" if frac >= 0.35 else "dropped")
                d[k] = {"hz": round(r, 1), "frac": min(1, frac), "state": st}
        # card
        try:
            free = shutil.disk_usage(RECORD_PATH).free
            d["card"] = {"gb_free": round(free/1e9, 1), "secs_left": None, "state": "ok"}
        except Exception:
            d["card"] = {"gb_free": None, "secs_left": None, "state": "na"}
        jt = jetson_temp()
        d["jetson"] = {"temp": round(jt,1) if jt else None, "state": band(jt)}
        d["l2"]     = {"temp": round(l2_temp["v"],1) if l2_temp["v"] is not None else None,
                       "state": band(l2_temp["v"])}
        d["capturing"] = capturing
        d["rig_on"] = any(ever[k] for k in ("lidar","camera","imu"))
        with STATE["lock"]:
            STATE["data"] = d
        time.sleep(0.1)

# ============================================================
# BUTTON ACTIONS — fire the REAL scripts
# ============================================================
def run_script(which):
    path = SCRIPTS.get(which)
    if not path or not os.path.exists(path):
        return {"ok": False, "msg": f"script not found: {path}"}
    if USE_MOCK:
        return {"ok": True, "msg": f"[MOCK] would run {path}"}
    try:
        # launch in its own terminal so the operator can see output / Ctrl-C (matches the icons)
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", path])
        return {"ok": True, "msg": f"launched {which}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

# ============================================================
# HTTP SERVER
# ============================================================
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # quiet
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control","no-store"); self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())
    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "rig_kiosk.html"), "rb") as f:
                    self._send(200, f.read(), "text/html")
            except FileNotFoundError:
                self._send(404, b"rig_kiosk.html not found next to the server", "text/plain")
        elif u.path == "/data":
            with STATE["lock"]:
                self._send(200, json.dumps(STATE["data"]))
        elif u.path == "/action":
            q = parse_qs(u.query); do = (q.get("do") or [""])[0]
            self._send(200, json.dumps(run_script(do)))
        else:
            self._send(404, b"{}")

def main():
    reader = mock_reader if USE_MOCK else ros_reader
    threading.Thread(target=reader, daemon=True).start()
    print(f"[kiosk] {'MOCK' if USE_MOCK else 'ROS2'} mode — serving http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
