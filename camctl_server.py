#!/usr/bin/env python3
# =============================================================================
# ARDUCAM CONTROL PAD  —  camctl_server.py   (single self-contained file)
# -----------------------------------------------------------------------------
# A Rig-Kiosk-style web control pad for the Arducam B0578 GS on the Jetson:
#   * a slider/toggle/menu for every v4l2 control, applied LIVE to the hardware,
#   * a live preview relayed from the ROS topic (device never opened twice),
#   * a saveable profile the capture pipeline can load on startup, and
#   * a camera-only QUICK CHECK: RECORD a short clip of the live feed, then
#     REPLAY it with a scrubber to scroll through it frame by frame.
#     (This is NOT the LiDAR/IMU take — it's just the camera, for eyeballing.)
#
# WHY ONE FILE: the daily Desktop sweep orphans kiosk files. Keep this in ~/
# (or bless into the vault) and it always launches whole. HTML is embedded.
#
# THE ONE HARD RULE: only ONE process may STREAM /dev/arducam. rig_camera_
# compressed.py owns the stream. So this pad NEVER opens the device for video —
# it sets controls with `v4l2-ctl` (fine concurrently) and gets preview + the
# recorder frames from the ROS topic /camera/image_raw/compressed (relay).
#
# RUN (controls work with/without ROS; preview + record need ROS + camera node):
#     source /opt/ros/humble/setup.bash
#     python3 ~/camctl_server.py
#   open  http://<jetson>:8081/   (localhost on the Jetson, or tailnet/LAN)
#
# ENV: CAMCTL_PORT (8081) · ARDUCAM_DEV (/dev/arducam) · CAMCTL_RECCAP (600)
# =============================================================================
import os, sys, json, time, threading, subprocess, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT    = int(os.environ.get("CAMCTL_PORT", "8081"))
DEV     = os.environ.get("ARDUCAM_DEV", "/dev/arducam")
TOPIC   = os.environ.get("CAMCTL_TOPIC", "/camera/image_raw/compressed")
PROFILE = os.path.expanduser("~/arducam_profile.json")
RECCAP  = int(os.environ.get("CAMCTL_RECCAP", "600"))   # frame cap (~30s @20Hz) — RAM guard

GATED = {
    "exposure_time_absolute":    ("auto_exposure",           1),  # active only when auto_exposure = 1 (Manual)
    "white_balance_temperature": ("white_balance_automatic", 0),  # active only when wb_auto = 0
}
MENU_ONLY_VALID = {"auto_exposure": [1, 3]}

# -----------------------------------------------------------------------------
# v4l2 layer
# -----------------------------------------------------------------------------
_LINE = re.compile(r'^\s*(\w+)\s+0x[0-9a-fA-F]+\s+\((\w+)\)\s*:\s*(.*)$')
_OPT  = re.compile(r'^\s+(\d+):\s*(.+?)\s*$')

def v4l2_list():
    try:
        out = subprocess.run(["v4l2-ctl", "-d", DEV, "--list-ctrls-menus"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception as e:
        return {"_error": f"{DEV}: {e}"}
    ctrls, last_menu = {}, None
    for line in out.splitlines():
        m = _LINE.match(line)
        if m:
            name, typ, rest = m.group(1), m.group(2), m.group(3)
            d = {"type": typ, "menu": {}}
            for k in ("min", "max", "step", "default", "value"):
                mm = re.search(rf'\b{k}=(-?\d+)', rest)
                if mm:
                    d[k] = int(mm.group(1))
            d["inactive"] = ("flags=inactive" in rest)
            ctrls[name] = d
            last_menu = name if typ == "menu" else None
            continue
        mo = _OPT.match(line)
        if mo and last_menu:
            ctrls[last_menu]["menu"][int(mo.group(1))] = mo.group(2)
    if not ctrls:
        return {"_error": f"no controls parsed from {DEV} (is the camera present?)"}
    return ctrls

def _raw_set(name, val):
    subprocess.run(["v4l2-ctl", "-d", DEV, f"--set-ctrl={name}={val}"],
                   capture_output=True, text=True, timeout=5)

def _clamp(d, val):
    lo, hi, st = d.get("min", val), d.get("max", val), (d.get("step", 1) or 1)
    val = max(lo, min(hi, int(val)))
    val = lo + round((val - lo) / st) * st
    return int(max(lo, min(hi, val)))

def apply_set(name, val):
    ctrls = v4l2_list()
    if "_error" in ctrls or name not in ctrls:
        return {"ok": False, "err": f"unknown control {name}"}
    d = ctrls[name]
    val = int(val)
    if name in MENU_ONLY_VALID:
        if val not in MENU_ONLY_VALID[name]:
            return {"ok": False, "err": f"{name} accepts {MENU_ONLY_VALID[name]}"}
    else:
        val = _clamp(d, val)
    if name in GATED:
        owner, unlock = GATED[name]
        if ctrls.get(owner, {}).get("value") != unlock:
            _raw_set(owner, unlock)
    _raw_set(name, val)
    return {"ok": True, "ctrls": v4l2_list()}

def save_profile():
    ctrls = v4l2_list()
    if "_error" in ctrls:
        return {"ok": False, "err": ctrls["_error"]}
    prof = {n: c["value"] for n, c in ctrls.items() if "value" in c}
    try:
        with open(PROFILE, "w") as f:
            json.dump(prof, f, indent=2)
    except Exception as e:
        return {"ok": False, "err": str(e)}
    return {"ok": True, "path": PROFILE, "saved": prof}

def load_profile():
    if not os.path.exists(PROFILE):
        return {"ok": False, "err": "no profile saved yet"}
    try:
        prof = json.load(open(PROFILE))
    except Exception as e:
        return {"ok": False, "err": str(e)}
    owners = ["auto_exposure", "white_balance_automatic"]
    for k in owners:
        if k in prof:
            _raw_set(k, prof[k])
    for k, v in prof.items():
        if k not in owners:
            _raw_set(k, v)
    return {"ok": True, "loaded": prof, "ctrls": v4l2_list()}

# -----------------------------------------------------------------------------
# Preview relay + camera-only recorder (both fed by the ROS topic callback)
# -----------------------------------------------------------------------------
_latest = {"jpg": None, "t": 0.0}
_rec    = {"on": False, "frames": [], "t0": 0.0, "cap": RECCAP}  # frames = [(t, jpgbytes), ...]

def rec_state():
    fr = _rec["frames"]; n = len(fr)
    if n >= 2:      secs = fr[-1][0] - fr[0][0]
    elif _rec["on"]: secs = time.time() - _rec["t0"]
    else:           secs = 0.0
    return {"on": _rec["on"], "count": n, "secs": round(secs, 1), "cap": _rec["cap"]}

def ros_reader():
    try:
        import rclpy
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
        from sensor_msgs.msg import CompressedImage
    except Exception as e:
        print(f"[camctl] preview/record OFF (no rclpy/ROS in this shell): {e}", flush=True)
        return
    try:
        rclpy.init()
        node = rclpy.create_node("arducam_camctl")
        qos = QoSProfile(depth=1)
        qos.reliability = ReliabilityPolicy.BEST_EFFORT
        qos.history = HistoryPolicy.KEEP_LAST
        def cb(msg):
            b = bytes(msg.data)
            _latest["jpg"] = b; _latest["t"] = time.time()
            if _rec["on"]:
                if len(_rec["frames"]) < _rec["cap"]:
                    _rec["frames"].append((time.time(), b))
                if len(_rec["frames"]) >= _rec["cap"]:
                    _rec["on"] = False   # auto-stop at the cap (RAM guard)
        node.create_subscription(CompressedImage, TOPIC, cb, qos)
        threading.Thread(target=lambda: rclpy.spin(node), daemon=True).start()
        print(f"[camctl] preview + recorder subscribed to {TOPIC}", flush=True)
    except Exception as e:
        print(f"[camctl] preview/record OFF (ROS reader failed): {e}", flush=True)

# -----------------------------------------------------------------------------
# HTTP
# -----------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def do_GET(self):
        u = urlparse(self.path); path = u.path
        if path in ("/", "/index.html"):
            self._send(200, HTML, "text/html; charset=utf-8")
        elif path == "/ctrls":
            self._send(200, json.dumps(v4l2_list()))
        elif path == "/load":
            self._send(200, json.dumps(load_profile()))
        elif path == "/rec/state":
            self._send(200, json.dumps(rec_state()))
        elif path == "/preview.jpg":
            jpg = _latest["jpg"]
            if jpg and (time.time() - _latest["t"] < 3.0):
                self._send(200, jpg, "image/jpeg")
            else:
                self._send(503, b"", "image/jpeg")
        elif path == "/rec/frame":
            try:
                i = int(parse_qs(u.query).get("i", ["-1"])[0])
            except Exception:
                i = -1
            fr = _rec["frames"]
            if 0 <= i < len(fr):
                self._send(200, fr[i][1], "image/jpeg")
            else:
                self._send(503, b"", "image/jpeg")
        else:
            self._send(404, json.dumps({"err": "not found"}))

    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/set":
            name = q.get("ctrl", [""])[0]; val = q.get("val", [""])[0]
            try:
                res = apply_set(name, int(val))
            except Exception as e:
                res = {"ok": False, "err": str(e)}
            self._send(200, json.dumps(res))
        elif u.path == "/save":
            self._send(200, json.dumps(save_profile()))
        elif u.path == "/rec/start":
            _rec["frames"] = []; _rec["t0"] = time.time(); _rec["on"] = True
            self._send(200, json.dumps(rec_state()))
        elif u.path == "/rec/stop":
            _rec["on"] = False
            self._send(200, json.dumps(rec_state()))
        else:
            self._send(404, json.dumps({"err": "not found"}))

# -----------------------------------------------------------------------------
# Embedded control-pad HTML (kiosk palette + panel language)
# -----------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Arducam Control</title>
<style>
  :root{
    --bg:#0d1013; --panel:#161b21; --edge:#232b34; --ink:#eef2f4; --dim:#8a97a3;
    --green:#3ad17a; --amber:#f5c542; --red:#ff5a52; --blue:#4aa8ff;
    --font:"DejaVu Sans","Liberation Sans",system-ui,sans-serif;
    --mono:"DejaVu Sans Mono","Liberation Mono",monospace;
  }
  *{margin:0;padding:0;box-sizing:border-box;}
  html,body{background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-tap-highlight-color:transparent;}
  body{padding:12px;}
  .screen{display:flex;flex-direction:column;gap:12px;max-width:1200px;margin:0 auto;}
  .status{border-radius:14px;border:2px solid var(--edge);background:var(--panel);
    display:flex;align-items:center;gap:16px;padding:14px 22px;}
  .status .dot{width:22px;height:22px;border-radius:50%;background:var(--green);box-shadow:0 0 16px var(--green);flex:none;}
  .status .dot.off{background:var(--dim);box-shadow:none;}
  .status .label{font-size:30px;font-weight:800;letter-spacing:.5px;}
  .status .sub{margin-left:auto;font-family:var(--mono);font-size:14px;color:var(--dim);text-align:right;line-height:1.5;}
  .main{display:flex;gap:12px;align-items:stretch;flex-wrap:wrap;}
  .col-left{flex:1 1 360px;display:flex;flex-direction:column;gap:12px;min-width:320px;}
  .col-right{flex:1 1 460px;min-width:340px;}
  .panel{background:var(--panel);border:2px solid var(--edge);border-radius:14px;padding:14px 16px;}
  .preview{position:relative;background:#05070a;border:2px solid var(--edge);border-radius:14px;
    overflow:hidden;aspect-ratio:16/10;display:flex;align-items:center;justify-content:center;}
  .preview img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#05070a;}
  .preview .tag{position:absolute;top:9px;left:11px;z-index:3;font-size:12px;color:var(--dim);
    font-family:var(--mono);background:rgba(0,0,0,.55);padding:4px 9px;border-radius:6px;}
  .preview .tag.rep{color:var(--blue);}
  .preview .off{position:absolute;inset:0;z-index:2;display:none;align-items:center;justify-content:center;
    text-align:center;color:var(--dim);font-size:14px;padding:20px;line-height:1.5;}
  .preview.offline .off{display:flex;}
  /* recorder */
  .recrow{display:flex;align-items:center;gap:12px;margin-bottom:11px;}
  .recbtn{border:2px solid #5c2a2a;background:var(--panel);color:var(--red);font-weight:800;font-size:17px;
    border-radius:11px;padding:12px 22px;cursor:pointer;letter-spacing:.5px;flex:none;}
  .recbtn.on{background:#301414;animation:pulse 1s infinite;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
  .recinfo{font-size:12px;color:var(--dim);font-family:var(--mono);line-height:1.4;}
  .replayrow{display:flex;align-items:center;gap:10px;}
  .rbtn{border:2px solid var(--edge);background:var(--panel);color:var(--ink);font-weight:700;font-size:15px;
    border-radius:9px;padding:9px 15px;cursor:pointer;flex:none;}
  .rbtn.live.on{border-color:#1f5c3a;color:var(--green);}
  .replayrow input[type=range]{flex:1;height:26px;accent-color:var(--blue);cursor:pointer;}
  .replayrow input[type=range]:disabled{opacity:.35;}
  .framelbl{width:78px;text-align:right;font-family:var(--mono);font-size:13px;color:var(--dim);flex:none;}
  /* presets + controls */
  .presets{display:flex;flex-wrap:wrap;gap:8px;}
  .pbtn{flex:1 1 auto;min-width:120px;border-radius:11px;border:2px solid var(--edge);background:var(--panel);
    color:var(--ink);font-size:14px;font-weight:700;padding:12px 10px;cursor:pointer;text-align:center;}
  .pbtn:active{transform:scale(.98);}
  .pbtn.lock{border-color:#264a6b;} .pbtn.reset{border-color:#5c2a2a;} .pbtn.save{border-color:#1f5c3a;}
  .shutrow{display:flex;flex-wrap:wrap;gap:7px;}
  .chip{border:2px solid var(--edge);background:var(--panel);color:var(--ink);font-family:var(--mono);
    font-size:14px;font-weight:700;border-radius:9px;padding:10px 12px;cursor:pointer;min-width:64px;text-align:center;}
  .chip:active{transform:scale(.97);}
  .chip.on{border-color:#1f5c3a;background:#12301f;color:var(--green);}
  .shuthint{font-size:12px;color:var(--dim);font-family:var(--mono);margin-top:10px;}
  h2{font-size:13px;color:var(--dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:10px;font-weight:700;}
  .row{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--edge);}
  .row:last-child{border-bottom:none;}
  .row .nm{width:118px;flex:none;font-size:14px;font-weight:600;}
  .row .nm small{display:block;font-size:11px;color:var(--dim);font-weight:500;font-family:var(--mono);}
  .row input[type=range]{flex:1;height:26px;accent-color:var(--green);cursor:pointer;background:transparent;}
  .row .num{width:74px;flex:none;font-family:var(--mono);font-size:14px;text-align:right;background:#0b0e11;
    border:1px solid var(--edge);border-radius:6px;color:var(--ink);padding:6px 8px;}
  .row.disabled{opacity:.4;}
  .row.disabled input,.row.disabled .num{pointer-events:none;}
  .toggle{width:132px;flex:none;display:flex;border:2px solid var(--edge);border-radius:9px;overflow:hidden;}
  .toggle button{flex:1;background:var(--panel);color:var(--dim);border:none;font-size:13px;font-weight:700;
    padding:9px 4px;cursor:pointer;font-family:var(--font);}
  .toggle button.on{background:#12301f;color:var(--green);}
  select.menu{flex:1;background:#0b0e11;border:1px solid var(--edge);border-radius:6px;color:var(--ink);
    padding:8px;font-family:var(--mono);font-size:13px;}
  .banner{background:#241416;border:2px solid var(--red);color:var(--red);border-radius:11px;
    padding:12px 16px;font-size:14px;font-weight:600;display:none;}
  .banner.show{display:block;}
  .hint{font-size:11px;color:#3a4650;text-align:right;margin-top:4px;font-family:var(--mono);}
</style></head>
<body><div class="screen">

  <div class="status">
    <div class="dot" id="dot"></div>
    <div class="label">ARDUCAM CONTROL</div>
    <div class="sub" id="sub">connecting…</div>
  </div>

  <div class="banner" id="banner"></div>

  <div class="main">
    <div class="col-left">
      <div class="preview" id="preview">
        <img id="pv" alt="preview">
        <div class="tag" id="pvtag">LIVE · /camera/image_raw/compressed</div>
        <div class="off">no camera feed<br>start the camera node<br>(controls still work)</div>
      </div>

      <div class="panel">
        <div class="recrow">
          <button class="recbtn" id="recBtn" onclick="toggleRec()">&#9679; REC</button>
          <div class="recinfo" id="recInfo">quick camera check — not the LiDAR/IMU take</div>
        </div>
        <div class="replayrow">
          <button class="rbtn" id="playBtn" onclick="togglePlay()">&#9654;</button>
          <button class="rbtn live on" id="liveBtn" onclick="goLive()">LIVE</button>
          <input type="range" id="scrub" min="0" max="0" value="0" disabled oninput="scrubTo(this.value)">
          <div class="framelbl" id="frameLbl">&mdash;</div>
        </div>
      </div>

      <div class="presets">
        <button class="pbtn lock"  onclick="preset('lock')">Lock for capture</button>
        <button class="pbtn reset" onclick="preset('auto')">Reset to auto</button>
        <button class="pbtn save"  onclick="preset('save')">Save profile</button>
        <button class="pbtn"       onclick="preset('load')">Load profile</button>
      </div>
      <div class="hint" id="phint"></div>
    </div>

    <div class="col-right">
      <div class="panel" style="margin-bottom:12px;">
        <h2>Shutter</h2>
        <div class="shutrow" id="shutRow"></div>
        <div class="shuthint" id="shutHint">tap a speed — sets Manual exposure automatically</div>
      </div>
      <div class="panel">
        <h2>Camera controls</h2>
        <div id="rows"></div>
      </div>
    </div>
  </div>
</div>

<script>
const ORDER = ["auto_exposure","exposure_time_absolute","white_balance_automatic","white_balance_temperature",
  "gain","brightness","contrast","saturation","gamma","hue","sharpness","backlight_compensation","power_line_frequency"];
const META = {
  auto_exposure:{label:"Exposure"}, exposure_time_absolute:{label:"Exposure time",unit:"×0.1 ms"},
  white_balance_automatic:{label:"White balance"}, white_balance_temperature:{label:"WB temp",unit:"K"},
  gain:{label:"Gain"}, brightness:{label:"Brightness"}, contrast:{label:"Contrast"},
  saturation:{label:"Saturation"}, gamma:{label:"Gamma"}, hue:{label:"Hue"},
  sharpness:{label:"Sharpness"}, backlight_compensation:{label:"Backlight"}, power_line_frequency:{label:"Powerline"}
};
let STATE={}, built=false, dragging=null;
function shutter(v){ const ms=v/10; const s=ms>0?Math.round(1000/ms):0; return ms.toFixed(1)+" ms · ≈1/"+s+" s"; }
function post(url){ return fetch(url,{method:"POST"}).then(r=>r.json()); }

// ---- SHUTTER: cinematographer speeds -> exposure_time_absolute (units of 0.1 ms) ----
const SHUTTERS=[30,48,50,60,100,125,250,500,1000];
function den2exp(D){ return Math.max(1,Math.min(5000,Math.round(10000/D))); }  // 1/D s -> 0.1ms units
function exp2den(v){ return v>0?Math.round(10000/v):0; }
function buildShutter(){
  const host=document.getElementById("shutRow"); if(!host||host.childElementCount)return;
  for(const D of SHUTTERS){ const c=document.createElement("button"); c.className="chip"; c.id="chip_"+D;
    c.textContent="1/"+D; c.onclick=()=>setCtrl("exposure_time_absolute",den2exp(D)); host.appendChild(c); }
}
function syncShutter(){
  const ex=STATE.exposure_time_absolute, ae=STATE.auto_exposure; if(!ex)return;
  const manual = ae ? (ae.value===1) : !ex.inactive;
  const h=document.getElementById("shutHint");
  document.querySelectorAll(".chip").forEach(c=>c.classList.remove("on"));
  if(!manual){ h.textContent="AUTO exposure — tap a speed to lock a manual shutter"; return; }
  let best=null,bd=1e9; for(const S of SHUTTERS){ const d=Math.abs(den2exp(S)-ex.value); if(d<bd){bd=d;best=S;} }
  if(best!==null && bd<=Math.max(1,den2exp(best)*0.04)){ const el=document.getElementById("chip_"+best); if(el)el.classList.add("on"); }
  h.textContent="current ≈ 1/"+exp2den(ex.value)+" s   ("+(ex.value/10).toFixed(1)+" ms · raw "+ex.value+")";
}

function setCtrl(name,val){
  post("/set?ctrl="+encodeURIComponent(name)+"&val="+val).then(res=>{
    if(res && res.ctrls){ STATE=res.ctrls; syncValues(); }
    else if(res && res.err){ flash(res.err); }
  });
}
function buildRows(){
  const host=document.getElementById("rows"); host.innerHTML="";
  const names=ORDER.filter(n=>n in STATE).concat(Object.keys(STATE).filter(n=>n[0]!=="_"&&!ORDER.includes(n)));
  for(const name of names){
    const d=STATE[name], meta=META[name]||{label:name};
    const row=document.createElement("div"); row.className="row"; row.id="row_"+name;
    const nm=document.createElement("div"); nm.className="nm";
    nm.innerHTML=meta.label+(meta.unit?("<small>"+meta.unit+"</small>"):"");
    row.appendChild(nm);
    if(name==="auto_exposure"){ row.appendChild(toggle(name,3,1,"Auto","Manual")); }
    else if(name==="white_balance_automatic"){ row.appendChild(toggle(name,1,0,"Auto","Manual")); }
    else if(d.type==="menu"){
      const sel=document.createElement("select"); sel.className="menu";
      for(const k in d.menu){ const o=document.createElement("option"); o.value=k; o.textContent=d.menu[k]; sel.appendChild(o); }
      sel.value=d.value; sel.onchange=()=>setCtrl(name,sel.value); row.appendChild(sel);
    }else{
      const rg=document.createElement("input"); rg.type="range";
      rg.min=d.min; rg.max=d.max; rg.step=d.step||1; rg.value=d.value; rg.id="rg_"+name;
      const nb=document.createElement("input"); nb.type="number"; nb.className="num";
      nb.min=d.min; nb.max=d.max; nb.step=d.step||1; nb.value=d.value; nb.id="nb_"+name;
      let t=null;
      const live=v=>{ nb.value=v; if(name==="exposure_time_absolute") nm.querySelector("small").textContent=shutter(v); };
      rg.oninput=()=>{ dragging=name; live(rg.value); clearTimeout(t); t=setTimeout(()=>{setCtrl(name,rg.value);dragging=null;},140); };
      rg.onchange=()=>{ setCtrl(name,rg.value); dragging=null; };
      nb.onchange=()=>{ rg.value=nb.value; setCtrl(name,nb.value); };
      row.appendChild(rg); row.appendChild(nb);
    }
    host.appendChild(row);
  }
  built=true; buildShutter(); syncValues();
}
function toggle(name,onVal,offVal,onTxt,offTxt){
  const t=document.createElement("div"); t.className="toggle";
  const a=document.createElement("button"), b=document.createElement("button");
  a.textContent=onTxt; b.textContent=offTxt;
  a.onclick=()=>setCtrl(name,onVal); b.onclick=()=>setCtrl(name,offVal);
  a.id="tg_"+name+"_on"; b.id="tg_"+name+"_off";
  t.appendChild(a); t.appendChild(b); return t;
}
function syncValues(){
  for(const name in STATE){
    const d=STATE[name]; if(name[0]==="_")continue;
    const row=document.getElementById("row_"+name); if(!row)continue;
    row.classList.toggle("disabled", !!d.inactive);
    const on=document.getElementById("tg_"+name+"_on"), off=document.getElementById("tg_"+name+"_off");
    if(on&&off){ const av=(name==="auto_exposure")?3:1; on.classList.toggle("on",d.value===av); off.classList.toggle("on",d.value!==av); }
    if(name===dragging)continue;
    const rg=document.getElementById("rg_"+name), nb=document.getElementById("nb_"+name);
    if(rg)rg.value=d.value; if(nb)nb.value=d.value;
    const sm=row.querySelector(".nm small");
    if(name==="exposure_time_absolute"&&sm)sm.textContent=shutter(d.value);
  }
  syncShutter();
}
function preset(kind){
  const ph=document.getElementById("phint");
  if(kind==="lock"){
    setCtrl("auto_exposure",1); setTimeout(()=>setCtrl("exposure_time_absolute",200),120);
    setTimeout(()=>setCtrl("white_balance_automatic",0),240); setTimeout(()=>setCtrl("white_balance_temperature",5000),360);
    ph.textContent="locked: manual exposure ≈1/50 s, WB 5000K — now tune from the preview";
  }else if(kind==="auto"){
    setCtrl("auto_exposure",3); setTimeout(()=>setCtrl("white_balance_automatic",1),120);
    ph.textContent="reset to auto exposure + auto white balance";
  }else if(kind==="save"){ post("/save").then(r=>{ ph.textContent=r.ok?("saved → "+r.path):("save failed: "+r.err); }); }
  else if(kind==="load"){ fetch("/load").then(r=>r.json()).then(r=>{
    if(r.ok){ STATE=r.ctrls; syncValues(); ph.textContent="profile loaded + applied"; } else ph.textContent="load failed: "+r.err; }); }
}
function flash(msg){ const b=document.getElementById("banner"); b.textContent=msg; b.classList.add("show"); setTimeout(()=>b.classList.remove("show"),4000); }

// ---- preview + camera-only RECORD / REPLAY ----
const pv=document.getElementById("pv"), prev=document.getElementById("preview"), pvtag=document.getElementById("pvtag");
let mode="live";                 // "live" | "replay"
let rec={on:false,count:0};
let playing=false, playT=null, recPoll=null;

pv.onload=()=>prev.classList.remove("offline");
pv.onerror=()=>{ if(mode==="live") prev.classList.add("offline"); };
setInterval(()=>{ if(mode==="live") pv.src="/preview.jpg?t="+Date.now(); }, 130);

function goLive(){ stopPlay(); mode="live"; document.getElementById("liveBtn").classList.add("on");
  pvtag.textContent="LIVE · /camera/image_raw/compressed"; pvtag.classList.remove("rep"); }
function scrubTo(i){ if(rec.count===0)return; stopPlayKeep(); mode="replay";
  document.getElementById("liveBtn").classList.remove("on");
  pvtag.textContent="REPLAY · frame "+(+i+1)+"/"+rec.count; pvtag.classList.add("rep");
  pv.src="/rec/frame?i="+i; document.getElementById("frameLbl").textContent=(+i+1)+" / "+rec.count; }
function togglePlay(){ playing?stopPlay():startPlay(); }
function startPlay(){ if(rec.count<2)return; playing=true; document.getElementById("playBtn").innerHTML="&#9208;";
  const sc=document.getElementById("scrub"); let i=+sc.value;
  playT=setInterval(()=>{ i=(i+1)%rec.count; sc.value=i; scrubShow(i); }, 60); }
function scrubShow(i){ mode="replay"; document.getElementById("liveBtn").classList.remove("on");
  pvtag.textContent="REPLAY · frame "+(+i+1)+"/"+rec.count; pvtag.classList.add("rep");
  pv.src="/rec/frame?i="+i; document.getElementById("frameLbl").textContent=(+i+1)+" / "+rec.count; }
function stopPlay(){ playing=false; if(playT)clearInterval(playT); playT=null; document.getElementById("playBtn").innerHTML="&#9654;"; }
function stopPlayKeep(){ if(playing){ playing=false; if(playT)clearInterval(playT); playT=null; document.getElementById("playBtn").innerHTML="&#9654;"; } }

function updRec(s){
  rec.on=s.on; rec.count=s.count;
  const b=document.getElementById("recBtn"), info=document.getElementById("recInfo"), sc=document.getElementById("scrub");
  if(s.on){ b.classList.add("on"); b.innerHTML="&#9632; STOP"; info.textContent="recording… "+s.count+" frames · "+s.secs+" s (cap "+s.cap+")"; }
  else{ b.classList.remove("on"); b.innerHTML="&#9679; REC";
    if(s.count>0){ info.textContent=s.count+" frames · "+s.secs+" s — scrub or play to review"; sc.disabled=false; sc.max=Math.max(0,s.count-1); }
    else info.textContent="quick camera check — not the LiDAR/IMU take"; }
}
function toggleRec(){
  if(!rec.on){ goLive(); post("/rec/start").then(s=>{ updRec(s); startRecPoll(); }); }
  else { post("/rec/stop").then(s=>{ updRec(s); if(s.count>0){ document.getElementById("scrub").value=0; scrubTo(0); } }); }
}
function startRecPoll(){ clearInterval(recPoll); recPoll=setInterval(()=>{
  fetch("/rec/state").then(r=>r.json()).then(s=>{ updRec(s); if(!s.on) clearInterval(recPoll); }); }, 500); }

function refresh(){
  fetch("/ctrls").then(r=>r.json()).then(d=>{
    if(d._error){ document.getElementById("dot").classList.add("off");
      document.getElementById("sub").textContent="camera not found"; flash(d._error); return; }
    document.getElementById("dot").classList.remove("off");
    document.getElementById("sub").innerHTML="device """ + DEV + r"""<br>"+Object.keys(d).length+" controls";
    STATE=d; if(!built) buildRows(); else syncValues();
  }).catch(()=>{});
}
refresh(); setInterval(refresh, 2000);
</script>
</body></html>
"""

# -----------------------------------------------------------------------------
def main():
    threading.Thread(target=ros_reader, daemon=True).start()
    print(f"[camctl] Arducam control pad → http://0.0.0.0:{PORT}/   (device {DEV}, rec cap {RECCAP} frames)", flush=True)
    print(f"[camctl] open from PC/Shadow: http://100.85.175.10:{PORT}/  (tailnet)  or  http://192.168.0.204:{PORT}/  (LAN)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
