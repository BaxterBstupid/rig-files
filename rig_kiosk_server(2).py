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
    "capture":    os.path.expanduser("~/point_lio_capture.sh"),
    "start_lean": os.path.expanduser("~/rig_start_lean.sh"),
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

# per-device thermal gauge specs (real trip points; Jetson color = conservative 68/80 bands,
# real kernel trips 68/70/99 shown as ticks. L2 = manual 85 ceiling, prevention line 78.)
THERMAL = {
    "jetson": {"floor": 35.0, "ceiling": 104.5, "green": 68.0, "yellow": 80.0,
               "ticks": [{"at": 68, "kind": "watch"}, {"at": 70, "kind": "throttle"}, {"at": 99, "kind": "hard"}]},
    "l2":     {"floor": 30.0, "ceiling": 85.0,  "green": 70.0, "yellow": 78.0,
               "ticks": [{"at": 70, "kind": "watch"}, {"at": 78, "kind": "cool"}]},
}

# ============================================================
# DATA SOURCE — real ROS2 on the Jetson, or mock in sandbox/PC
# ============================================================
STATE = {"data": {}, "lock": threading.Lock()}
# latest camera frame (downscaled JPEG bytes) for the /camera.jpg endpoint
CAM = {"jpeg": None, "lock": threading.Lock()}

# latest LiDAR scan as compact float32 [x,y,z,intensity]*N (downsampled) for the /cloud viewer
CLOUD = {"bin": None, "n": 0, "ts": 0.0, "lock": threading.Lock()}
CLOUD_MAX_POINTS = 4000      # keep the WiFi payload small (~64 KB/frame at 4000 pts)
CLOUD_FPS = 6.0

def cloud_to_bin(data, point_step, n_points, fields):
    """PointCloud2 bytes -> float32 [x,y,z,intensity]*M bytes, using the message's OWN field
    offsets (so padding/extra fields like ring/time never matter). fields: [(name, offset, datatype)]."""
    import numpy as np
    dt_map = {1:"i1",2:"u1",3:"<i2",4:"<u2",5:"<i4",6:"<u4",7:"<f4",8:"<f8"}
    names, fmts, offs = [], [], []
    for name, off, dtype in fields:
        if name in ("x","y","z","intensity"):
            names.append(name); fmts.append(dt_map[dtype]); offs.append(off)
    if not all(k in names for k in ("x","y","z")):
        return None, 0
    dt = np.dtype({"names": names, "formats": fmts, "offsets": offs, "itemsize": point_step})
    arr = np.frombuffer(data, dtype=dt, count=n_points)
    if n_points > CLOUD_MAX_POINTS:
        arr = arr[::-(-n_points // CLOUD_MAX_POINTS)]   # ceil stride -> never exceeds the cap
    out = np.empty((len(arr), 4), dtype="<f4")
    out[:,0] = arr["x"]; out[:,1] = arr["y"]; out[:,2] = arr["z"]
    out[:,3] = arr["intensity"] if "intensity" in names else 0.0
    out = out[np.isfinite(out).all(axis=1)]      # drop NaN/inf points
    return out.tobytes(), len(out)

# ---------- LIVE COVERAGE MAP (world-frame accumulation of /cloud_registered) ----------
REG_TOPIC = "/cloud_registered"        # Point-LIO's per-scan world-frame cloud (verified in source)
MAP_VOXEL = 0.05
MAP_MAX_VOXELS = 2_000_000             # hard memory cap (~56 MB); capped flag exposed, hits still count
_MAP = {"vm": None, "lock": threading.Lock(), "was_capturing": False}

def note_capture_transition(capturing):
    """rising edge: fresh map per capture. falling edge: the STOP IS THE BUTTON -
    MESH CHECK fires automatically so the coverage verdict is waiting by the time
    the operator looks at a screen. (A tracking collapse mid-capture also reads as
    a falling edge; the extra meshcheck it fires is harmless and even informative.)"""
    if capturing and not _MAP["was_capturing"]:
        get_map().clear()
    elif _MAP["was_capturing"] and not capturing:
        try: start_meshcheck()
        except Exception: pass
    _MAP["was_capturing"] = capturing

def get_map():
    if _MAP["vm"] is None:
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        from map_accumulator import VoxelMap
        _MAP["vm"] = VoxelMap(MAP_VOXEL, MAP_MAX_VOXELS)
    return _MAP["vm"]

# ---------- MESH CHECK (instrument mesh of the accumulated map) ----------
MESH_DIR = "/tmp/rig_meshcheck"
MESH = {"state": "idle", "meta": None, "err": "", "started": 0.0, "lock": threading.Lock()}

def start_meshcheck(depth=8):
    import subprocess, sys as _sys, os as _os
    with MESH["lock"]:
        if MESH["state"] == "running":
            return {"ok": False, "err": "already running"}
        vm = get_map()
        vm.merge()
        pts, cnts = vm.full_points_counts()
        if len(pts) < 5000:
            return {"ok": False, "err": f"map too small ({len(pts)} voxels) - run lean/capture first"}
        _os.makedirs(MESH_DIR, exist_ok=True)
        import numpy as _np
        snap = _np.empty((len(pts), 4), _np.float32)
        snap[:, :3] = pts; snap[:, 3] = cnts
        snap_path = _os.path.join(MESH_DIR, "map_snapshot.npy")
        _np.save(snap_path, snap)
        script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "mesh_check.py")
        prefix = _os.path.join(MESH_DIR, "mesh")
        proc = subprocess.Popen([_sys.executable, script, snap_path, prefix, "--depth", str(depth)],
                                stdout=open(_os.path.join(MESH_DIR, "mesh.log"), "w"),
                                stderr=subprocess.STDOUT)
        MESH["state"] = "running"; MESH["err"] = ""; MESH["meta"] = None; MESH["started"] = time.time()
    def waiter():
        rc = proc.wait()
        with MESH["lock"]:
            if rc == 0:
                try:
                    MESH["meta"] = json.load(open(os.path.join(MESH_DIR, "mesh.json")))
                    MESH["state"] = "done"
                except Exception as e:
                    MESH["state"] = "error"; MESH["err"] = f"no meta: {e}"
            else:
                tail = ""
                try: tail = open(os.path.join(MESH_DIR, "mesh.log")).read()[-400:]
                except Exception: pass
                MESH["state"] = "error"; MESH["err"] = f"exit {rc}: {tail}"
    threading.Thread(target=waiter, daemon=True).start()
    return {"ok": True, "state": "running"}
CAM_W, CAM_H, CAM_QUALITY = 480, 300, 50   # low-res reference, small payload

def _mock_cloud(t):
    """synthetic scan: a room box + floor, slowly rotating, with intensity by height"""
    import numpy as np, math
    rng = np.random.default_rng(int(t*10) % 1000)
    n = 1800
    a = rng.uniform(-math.pi, math.pi, n); r = rng.uniform(2.0, 6.0, n)
    x = r*np.cos(a); y = r*np.sin(a); z = rng.uniform(-1.2, 1.8, n)
    wall = rng.random(n) < 0.7
    x[wall] = np.sign(x[wall])*6.0*rng.random(wall.sum()) ; y[wall] = np.clip(y[wall], -6, 6)
    c, s_ = math.cos(t*0.3), math.sin(t*0.3)
    xr, yr = x*c - y*s_, x*s_ + y*c
    inten = (z - z.min()) / (np.ptp(z) + 1e-6) * 200.0
    out = np.column_stack([xr, yr, z, inten]).astype("<f4")
    return out.tobytes(), n

_ROOM = {"surf": None}
def _mock_room_scan(t):
    """One 'registered scan' from a sensor walking a 6x4x2.6 room with a missing
    wall patch (the deliberate hole). World frame. Feeds the coverage map in mock."""
    import numpy as np, math
    if _ROOM["surf"] is None:
        rng = np.random.default_rng(3)
        def plane(n, o, u, v, ul, vl):
            a = rng.uniform(0, ul, (n,1)); b = rng.uniform(0, vl, (n,1))
            return np.array(o) + a*np.array(u) + b*np.array(v)
        surf = np.concatenate([
            plane(30000, (0,0,0), (1,0,0), (0,1,0), 6, 4),
            plane(15000, (0,0,2.6), (1,0,0), (0,1,0), 6, 4),
            plane(15000, (0,0,0), (0,1,0), (0,0,1), 4, 2.6),
            plane(15000, (6,0,0), (0,1,0), (0,0,1), 4, 2.6),
            plane(15000, (0,0,0), (1,0,0), (0,0,1), 6, 2.6),
            plane(15000, (0,4,0), (1,0,0), (0,0,1), 6, 2.6),
            plane(6000,  (1.5,1.5,0.8), (1,0,0), (0,1,0), 1.0, 0.6),
        ])
        hole = (surf[:,1] > 3.99) & (surf[:,0] > 2.4) & (surf[:,0] < 3.6) & (surf[:,2] > 0.9) & (surf[:,2] < 1.7)
        _ROOM["surf"] = surf[~hole]
    surf = _ROOM["surf"]
    import numpy as np
    cx, cy = 3 + 1.8*math.cos(t*0.15), 2 + 1.1*math.sin(t*0.15)   # sensor path, ~42 s lap
    d2 = (surf[:,0]-cx)**2 + (surf[:,1]-cy)**2
    near = np.flatnonzero(d2 < 16.0)
    if len(near) == 0: return None
    rng = np.random.default_rng(int(t*10) % 99991)
    pick = rng.choice(near, size=min(900, len(near)), replace=False)
    return surf[pick] + rng.normal(0, 0.008, (len(pick), 3))

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
        try:
            b, n = _mock_cloud(time.time())
            with CLOUD["lock"]:
                CLOUD["bin"] = b; CLOUD["n"] = n; CLOUD["ts"] = time.time()
        except Exception:
            pass
        note_capture_transition(cap)
        try:
            scan = _mock_room_scan(time.time())
            if scan is not None and cap:
                get_map().add_points(scan)
            if int(time.time()) % 2 == 0:
                get_map().merge()
            vm = _MAP["vm"]
            with STATE["lock"]:
                if STATE["data"]:
                    STATE["data"]["map"] = {"voxels": (len(vm.keys) if vm is not None else 0),
                                            "capped": (vm.capped if vm is not None else False)}
        except Exception:
            pass
        time.sleep(0.5)

def ros_reader():
    """Real reader — rig_monitor's engine, returning a dict. Jetson only."""
    import rclpy
    from collections import deque
    from sensor_msgs.msg import PointCloud2, Image, Imu
    from nav_msgs.msg import Odometry
    from std_msgs.msg import Float32
    try:
        import cv2
        from cv_bridge import CvBridge
        _bridge = CvBridge(); _cam_ok = True
    except Exception as _e:
        _cam_ok = False; print("[kiosk] camera feed disabled:", _e)
    _last_encode = [0.0]   # throttle: only encode ~8fps regardless of camera rate
    tmap = {"PointCloud2": PointCloud2, "Image": Image, "Imu": Imu, "Odometry": Odometry}
    WINDOW = 2.0
    stamps = {k: deque() for k in STREAMS}
    ever   = {k: False for k in STREAMS}
    l2_temp = {"v": None}
    _last_cloud = [0.0]

    rclpy.init()
    node = rclpy.create_node("rig_kiosk")
    def make_cb(kk):
        def cb(msg):
            stamps[kk].append(time.time()); ever[kk] = True
            # lidar: stash a downsampled float32 cloud for the /cloud viewer, throttled
            if kk == "lidar":
                nowl = time.time()
                if nowl - _last_cloud[0] >= 1.0 / CLOUD_FPS:
                    _last_cloud[0] = nowl
                    try:
                        flds = [(fl.name, fl.offset, fl.datatype) for fl in msg.fields]
                        b, n = cloud_to_bin(bytes(msg.data), msg.point_step, msg.width * msg.height, flds)
                        if b is not None:
                            with CLOUD["lock"]:
                                CLOUD["bin"] = b; CLOUD["n"] = n; CLOUD["ts"] = nowl
                    except Exception:
                        pass
            # camera: also stash a downscaled JPEG, throttled to ~8fps
            if kk == "camera" and _cam_ok:
                nowc = time.time()
                if nowc - _last_encode[0] >= 0.125:   # ~8 fps
                    _last_encode[0] = nowc
                    try:
                        img = _bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
                        small = cv2.resize(img, (CAM_W, CAM_H), interpolation=cv2.INTER_AREA)
                        ok, buf = cv2.imencode(".jpg", small,
                                               [cv2.IMWRITE_JPEG_QUALITY, CAM_QUALITY])
                        if ok:
                            with CAM["lock"]:
                                CAM["jpeg"] = buf.tobytes()
                    except Exception:
                        pass
        return cb
    for k, cfg in STREAMS.items():
        node.create_subscription(tmap[cfg["type"]], cfg["topic"], make_cb(k), 50)
    node.create_subscription(Float32, L2_TEMP_TOPIC, lambda m: l2_temp.__setitem__("v", m.data), 10)
    def reg_cb(msg):
        try:
            flds = [(fl.name, fl.offset, fl.datatype) for fl in msg.fields]
            b, n = cloud_to_bin(bytes(msg.data), msg.point_step, msg.width * msg.height, flds)
            if b is not None and n:
                import numpy as _np
                arr = _np.frombuffer(b, _np.float32).reshape(-1, 4)
                get_map().add_points(arr[:, :3])
        except Exception:
            pass
    node.create_subscription(PointCloud2, REG_TOPIC, reg_cb, 50)

    # FIX (2026-08-28): spin CONTINUOUSLY in a dedicated thread so we catch EVERY message
    # on high-rate topics (was under-counting to ~3Hz because the old loop threw in a
    # spin_once + sleep, missing most messages). The snapshot loop below is display-only.
    def _spin():
        try: rclpy.spin(node)
        except Exception: pass
    threading.Thread(target=_spin, daemon=True).start()

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

    def gauge(t, spec):
        if t is None:
            return {"temp": None, "frac": 0, "state": "na", "ticks": spec["ticks"],
                    "floor": spec["floor"], "ceiling": spec["ceiling"]}
        frac = (t - spec["floor"]) / (spec["ceiling"] - spec["floor"])
        frac = max(0.0, min(1.0, frac))
        state = "ok" if t < spec["green"] else ("watch" if t < spec["yellow"] else "hot")
        return {"temp": round(t, 1), "frac": round(frac, 3), "state": state,
                "ticks": spec["ticks"], "floor": spec["floor"], "ceiling": spec["ceiling"]}

    while rclpy.ok():
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
        d["jetson"] = gauge(jt, THERMAL["jetson"])
        d["l2"]     = gauge(l2_temp["v"], THERMAL["l2"])
        note_capture_transition(capturing)
        if int(now * 10) % 20 == 0:          # ~every 2 s of loop passes
            try: get_map().merge()
            except Exception: pass
        d["capturing"] = capturing
        d["rig_on"] = any(ever[k] for k in ("lidar","camera","imu"))
        vm = _MAP["vm"]
        d["map"] = {"voxels": (len(vm.keys) if vm is not None else 0),
                    "capped": (vm.capped if vm is not None else False)}
        with STATE["lock"]:
            STATE["data"] = d
        time.sleep(0.1)

# ============================================================
# BUTTON ACTIONS — fire the REAL scripts
# ============================================================
def run_script(which):
    # exit_kiosk: close the fullscreen kiosk by ending the kiosk Firefox process directly.
    # (Firefox blocks window.close() on pages reached by navigation, so the page can't close itself.)
    if which == "exit_kiosk":
        if USE_MOCK:
            return {"ok": True, "msg": "[MOCK] would close kiosk firefox"}
        # kill ONLY the kiosk's own Firefox (its PID was recorded by the launcher);
        # your normal Firefox is a different process and is never touched.
        pidfile = os.path.expanduser("~/.kiosk_firefox.pid")
        try:
            pid = int(open(pidfile).read().strip())
            os.kill(pid, 15)   # SIGTERM = graceful quit
            return {"ok": True, "msg": f"closing kiosk (pid {pid})"}
        except FileNotFoundError:
            return {"ok": False, "msg": "no kiosk pid file - was it launched via rig_kiosk_launch.sh?"}
        except ProcessLookupError:
            return {"ok": True, "msg": "kiosk already closed"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}
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
        if u.path in ("/", "/index.html", "/launch"):
            try:
                with open(os.path.join(HERE, "launch.html"), "rb") as f:
                    self._send(200, f.read(), "text/html")
            except FileNotFoundError:
                self._send(404, b"launch.html not found next to the server", "text/plain")
        elif u.path in ("/kiosk", "/kiosk.html"):
            try:
                with open(os.path.join(HERE, "rig_kiosk.html"), "rb") as f:
                    self._send(200, f.read(), "text/html")
            except FileNotFoundError:
                self._send(404, b"rig_kiosk.html not found next to the server", "text/plain")
        elif u.path == "/data":
            with STATE["lock"]:
                self._send(200, json.dumps(STATE["data"]))
        elif u.path == "/cloud.bin":
            with CLOUD["lock"]:
                b, n, ts = CLOUD["bin"], CLOUD["n"], CLOUD["ts"]
            if b is None:
                self._send(503, b"no cloud yet", "text/plain"); return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("X-Points", str(n)); self.send_header("X-Stamp", str(ts))
            self.send_header("Cache-Control", "no-store"); self.end_headers()
            self.wfile.write(b)
        elif u.path in ("/cloud", "/cloud.html"):
            try:
                with open(os.path.join(HERE, "cloud.html"), "rb") as f:
                    self._send(200, f.read(), "text/html")
            except FileNotFoundError:
                self._send(404, b"cloud.html not found next to the server", "text/plain")
        elif u.path == "/camera.jpg":
            with CAM["lock"]:
                jpg = CAM["jpeg"]
            if jpg:
                self._send(200, jpg, "image/jpeg")
            else:
                self._send(503, b"no frame yet", "text/plain")
        elif u.path == "/map.bin":
            vm = get_map(); vm.merge()
            snap = vm.snapshot(150_000)
            b = snap.tobytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("X-Voxels", str(len(vm.keys)))
            self.send_header("X-Capped", "1" if vm.capped else "0")
            self.send_header("Cache-Control", "no-store"); self.end_headers()
            self.wfile.write(b)
        elif u.path == "/map.json":
            vm = get_map()
            self._send(200, json.dumps({"voxels": len(vm.keys), "capped": vm.capped,
                                        "voxel_size": MAP_VOXEL, "total_in": vm.total_in}))
        elif u.path == "/mesh.bin":
            try:
                with open(os.path.join(MESH_DIR, "mesh.meshbin"), "rb") as fmesh:
                    b = fmesh.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store"); self.end_headers()
                self.wfile.write(b)
            except FileNotFoundError:
                self._send(404, b"no mesh yet - run MESH CHECK", "text/plain")
        elif u.path == "/meshstatus":
            with MESH["lock"]:
                self._send(200, json.dumps({"state": MESH["state"], "meta": MESH["meta"],
                                            "err": MESH["err"],
                                            "elapsed": round(time.time()-MESH["started"],1) if MESH["state"]=="running" else 0}))
        elif u.path == "/action":
            q = parse_qs(u.query); do = (q.get("do") or [""])[0]
            if do == "meshcheck":
                self._send(200, json.dumps(start_meshcheck())); return
            if do == "mapreset":
                get_map().clear(); self._send(200, json.dumps({"ok": True})); return
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
