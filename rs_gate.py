#!/usr/bin/env python3
"""
rs_gate.py  v1 -- turn a RealityScan rs_gate.html report into PASS / FAIL lines.  Runs on Shadow (rigstation) or anywhere.

    python rs_gate.py <report.html> --stage report|align|lidar|merge|mesh [--images <images_dir>] [--label text]

Reads the COMP| and CAM| lines the rs_gate.html template writes. Prints every component with its numbers, the
camera-prior frame check (median priorError3D), and the stage gate verdict. Exit 0 = PASS, 1 = FAIL, 2 = report unreadable.
Gates (reference section 3 + audit 2026-10-07 section 5):
  align : ONE component; cameras >= 90 % of photos; mean reproj <= 1.5 px, max <= 3 px; median priorError3D <= 0.10 m (frame check)
  lidar : photo component + Laserscan component; LSP count == photo count; no third component
  merge : ONE component holding photos + LSPs (>= 90 % of both); control points used >= 6; mean reproj <= 3 px
  mesh  : one component, model present (report only lists components; mesh is judged by the eye)
"""
import sys, os, re, glob, argparse, statistics

ap = argparse.ArgumentParser()
ap.add_argument("report"); ap.add_argument("--stage", required=True)
ap.add_argument("--images", default=None); ap.add_argument("--label", default="")
a = ap.parse_args()

try:
    raw = open(a.report, "r", encoding="utf-8", errors="replace").read()
except OSError as e:
    print("GATE FAIL: cannot read report:", e); sys.exit(2)
text = re.sub(r"<[^>]+>", "\n", raw)          # tolerate an HTML wrapper
if "RSGATE|" not in text:
    print("GATE FAIL: report has no RSGATE header -- template not evaluated? First 300 chars:\n", text[:300]); sys.exit(2)

def num(s, default=float("nan")):
    try: return float(s)
    except Exception: return default

comps, cams = [], []
for line in text.splitlines():
    line = line.strip()
    if line.startswith("COMP|"):
        f = line.split("|")
        if len(f) < 10 or "$" in line:
            print("  (unparsed component line:", line[:120], ")"); continue
        comps.append(dict(name=f[1], cams=int(num(f[2], 0)), points=int(num(f[3], 0)), cps=int(num(f[4], 0)),
                          mean=num(f[5]), median=num(f[6]), max=num(f[7]), georef=f[8], metric=f[9]))
    elif line.startswith("CAM|"):
        f = line.split("|")
        if len(f) < 7 or "$" in line: continue
        cams.append(dict(name=f[1], x=num(f[2]), y=num(f[3]), z=num(f[4]), prior3d=num(f[5]), f=num(f[6])))

n_photos = len(glob.glob(os.path.join(a.images, "*.jpg"))) if a.images else None
print("=== rs_gate %s %s  report=%s" % (a.stage, a.label, os.path.basename(a.report)))
print("components: %d   cameras listed: %d   photos on disk: %s" % (len(comps), len(cams), n_photos))
for c in comps:
    print("  %-24s cams %5d  points %8d  CPs %2d  reproj mean %.2f med %.2f max %.2f px  georef %s metric %s"
          % (c["name"], c["cams"], c["points"], c["cps"], c["mean"], c["median"], c["max"], c["georef"], c["metric"]))
pe = [c["prior3d"] for c in cams if c["prior3d"] == c["prior3d"] and c["name"].lower().endswith(".jpg")]
if pe:
    print("  frame check: photo priorError3D median %.3f m  p90 %.3f m  max %.3f m  (n=%d)"
          % (statistics.median(pe), sorted(pe)[int(0.9 * (len(pe) - 1))], max(pe), len(pe)))
fails = []
def need(cond, msg):
    if not cond: fails.append(msg)

photo_comp = [c for c in comps if not c["name"].lower().startswith("laserscan")]
laser_comp = [c for c in comps if c["name"].lower().startswith("laserscan")]
big = max(comps, key=lambda c: c["cams"]) if comps else None

if a.stage == "report":
    pass
elif a.stage == "align":
    need(len(comps) == 1, "expected ONE component, got %d" % len(comps))
    if big and n_photos: need(big["cams"] >= 0.9 * n_photos, "cameras %d < 90%% of %d photos" % (big["cams"], n_photos))
    if big:
        need(big["mean"] <= 1.5, "mean reprojection %.2f px > 1.5" % big["mean"])
        need(big["max"] <= 3.0, "max reprojection %.2f px > 3.0" % big["max"])
    if pe: need(statistics.median(pe) <= 0.10, "photo block floated: median priorError3D %.3f m > 0.10" % statistics.median(pe))
elif a.stage == "lidar":
    need(len(laser_comp) == 1, "expected one Laserscan component, got %d" % len(laser_comp))
    need(len(photo_comp) == 1, "expected one photo component, got %d (duplicates = F6 ran more than once)" % len(photo_comp))
    if laser_comp and photo_comp:
        need(laser_comp[0]["cams"] == photo_comp[0]["cams"], "LSP count %d != photo count %d" % (laser_comp[0]["cams"], photo_comp[0]["cams"]))
elif a.stage == "merge":
    need(len(comps) == 1, "still %d components -- not merged" % len(comps))
    if big and n_photos: need(big["cams"] >= 0.9 * 2 * n_photos, "merged component has %d cams, expected ~%d" % (big["cams"], 2 * n_photos))
    if big:
        need(big["cps"] >= 6, "control points used %d < 6" % big["cps"])
        need(big["mean"] <= 3.0, "mean reprojection %.2f px > 3.0" % big["mean"])
elif a.stage == "mesh":
    need(len(comps) >= 1, "no component")
else:
    print("unknown stage", a.stage); sys.exit(2)

if fails:
    print("GATE FAIL (%s):" % a.stage)
    for m in fails: print("  - " + m)
    sys.exit(1)
print("GATE PASS (%s)" % a.stage)
