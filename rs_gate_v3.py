#!/usr/bin/env python3
"""
rs_gate.py  v3 -- turn a RealityScan rs_gate.html report into PASS / FAIL lines.  Runs on Shadow (rigstation) or anywhere.

    python rs_gate.py <report.html> --stage report|align|lidar|merge|mesh [--images <images_dir>] [--label text]
    python rs_gate.py --selftest

Reads the COMP| and CAM| lines the rs_gate.html template writes. Tolerates: an HTML wrapper, a COMP line with only
name|cams (if the nested stats functions did not evaluate), and unevaluated $(...) leftovers (reported, not fatal).
Exit 0 = PASS, 1 = FAIL, 2 = report unreadable / template not evaluated.
v3: unevaluated template = exit 2; unevaluated nested stats = FAIL on align/merge; .jpg count case-insensitive.
Gates (reference section 3 + audit 2026-10-07 section 5):
  align : ONE component; cameras >= 90 % of photos; mean reproj <= 1.5 px, max <= 3 px (when stats present);
          median priorError3D <= 0.10 m (frame check, when priors present)
  lidar : exactly one photo component + one Laserscan component; LSP count == photo count
  merge : ONE component holding photos + LSPs (>= 90 % of 2N); control points used >= 6; mean reproj <= 3 px
  mesh  : one component present (the mesh itself is judged by the eye)
"""
import sys, os, re, glob, argparse, statistics, tempfile

NAN = float("nan")

def num(s, default=NAN):
    try: return float(str(s).strip())
    except Exception: return default

def parse(text):
    comps, cams, leftovers = [], [], 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("COMP|"):
            f = [x.strip() for x in line.split("|")]
            if "$" in line: leftovers += 1
            c = dict(name=f[1] if len(f) > 1 else "?", cams=int(num(f[2], 0)) if len(f) > 2 else 0,
                     points=int(num(f[3], 0)) if len(f) > 3 else 0, cps=int(num(f[4], 0)) if len(f) > 4 else 0,
                     mean=num(f[5]) if len(f) > 5 else NAN, median=num(f[6]) if len(f) > 6 else NAN,
                     max=num(f[7]) if len(f) > 7 else NAN, georef=f[8] if len(f) > 8 else "?", metric=f[9] if len(f) > 9 else "?")
            comps.append(c)
        elif line.startswith("CAM|"):
            f = [x.strip() for x in line.split("|")]
            if "$" in line: leftovers += 1; continue
            if len(f) < 6: continue
            cams.append(dict(name=f[1], x=num(f[2]), y=num(f[3]), z=num(f[4]), prior3d=num(f[5]), f=num(f[6]) if len(f) > 6 else NAN))
    return comps, cams, leftovers

def fmt(v): return "%.2f" % v if v == v else "n/a"

def gate(comps, cams, stage, n_photos):
    fails = []
    def need(cond, msg):
        if not cond: fails.append(msg)
    photo_comp = [c for c in comps if not c["name"].lower().startswith("laserscan")]
    laser_comp = [c for c in comps if c["name"].lower().startswith("laserscan")]
    big = max(comps, key=lambda c: c["cams"]) if comps else None
    pe = [c["prior3d"] for c in cams if c["prior3d"] == c["prior3d"] and c["name"].lower().endswith(".jpg")]
    if stage == "report":
        pass
    elif stage == "align":
        need(len(comps) == 1, "expected ONE component, got %d" % len(comps))
        if big and n_photos: need(big["cams"] >= 0.9 * n_photos, "cameras %d < 90%% of %d photos" % (big["cams"], n_photos))
        if big and big["mean"] == big["mean"]:
            need(big["mean"] <= 1.5, "mean reprojection %.2f px > 1.5" % big["mean"])
            need(big["max"] <= 3.0, "max reprojection %.2f px > 3.0" % big["max"])
        if pe: need(statistics.median(pe) <= 0.10, "photo block floated: median priorError3D %.3f m > 0.10" % statistics.median(pe))
    elif stage == "lidar":
        need(len(laser_comp) == 1, "expected one Laserscan component, got %d" % len(laser_comp))
        need(len(photo_comp) == 1, "expected one photo component, got %d (duplicates = aligned more than once)" % len(photo_comp))
        if laser_comp and photo_comp:
            need(laser_comp[0]["cams"] == photo_comp[0]["cams"], "LSP count %d != photo count %d" % (laser_comp[0]["cams"], photo_comp[0]["cams"]))
    elif stage == "merge":
        need(len(comps) == 1, "still %d components -- not merged" % len(comps))
        if big and n_photos: need(big["cams"] >= 0.9 * 2 * n_photos, "merged component has %d cams, expected ~%d" % (big["cams"], 2 * n_photos))
        if big:
            need(big["cps"] >= 6, "control points used %d < 6" % big["cps"])
            if big["mean"] == big["mean"]: need(big["mean"] <= 3.0, "mean reprojection %.2f px > 3.0" % big["mean"])
    elif stage == "mesh":
        need(len(comps) >= 1, "no component")
    else:
        raise SystemExit("unknown stage %s" % stage)
    return fails, pe

def run(report, stage, images, label):
    try:
        raw = open(report, "r", encoding="utf-8", errors="replace").read()
    except OSError as e:
        print("GATE FAIL: cannot read report:", e); return 2
    text = re.sub(r"<[^>]+>", "\n", raw)
    if "RSGATE|" not in text:
        print("GATE FAIL: report has no RSGATE header -- template not evaluated? First 300 chars:\n", text[:300]); return 2
    if re.search(r"^\$IterateComponents\(|^\$ExportCameras\(", text, re.M):
        print("GATE FAIL: template functions were written out literally -- RealityScan did not evaluate the template (check rs_gate.html path / report engine)"); return 2
    comps, cams, leftovers = parse(text)
    n_photos = len([f for f in os.listdir(images) if f.lower().endswith(".jpg")]) if images and os.path.isdir(images) else None
    print("=== rs_gate %s %s  report=%s" % (stage, label, os.path.basename(report)))
    print("components: %d   cameras listed: %d   photos on disk: %s" % (len(comps), len(cams), n_photos))
    if leftovers: print("  WARNING: %d line(s) still contain $(...) -- a template function did not evaluate; stats may be n/a" % leftovers)
    for c in comps:
        print("  %-24s cams %5d  points %8d  CPs %2d  reproj mean %s med %s max %s px  georef %s metric %s"
              % (c["name"], c["cams"], c["points"], c["cps"], fmt(c["mean"]), fmt(c["median"]), fmt(c["max"]), c["georef"], c["metric"]))
    fails, pe = gate(comps, cams, stage, n_photos)
    if pe:
        s = sorted(pe)
        print("  frame check: photo priorError3D median %.3f m  p90 %.3f m  max %.3f m  (n=%d)"
              % (statistics.median(pe), s[int(0.9 * (len(s) - 1))], s[-1], len(pe)))
    if not comps and stage != "report":
        fails.append("no COMP lines parsed")
    if leftovers and stage in ("align", "merge"):
        fails.append("component stats did not evaluate ($(...) left in a COMP line) -- fix rs_gate.html, then re-run the 'report' stage on this stage's .rsproj")
    if fails:
        print("GATE FAIL (%s):" % stage)
        for m in fails: print("  - " + m)
        return 1
    print("GATE PASS (%s)" % stage)
    return 0

def selftest():
    full = """<html><body><pre>
RSGATE|v1|2026-10-07
COMP|Component 0|900|123456|0|0.84|0.61|2.9|false|true
COMP|Laserscan component|900|40000|0|0.40|0.30|1.1|false|true
CAM|img_1.jpg|-0.94|0.07|-0.02|0.031|15.9
CAM|img_2.jpg|-0.90|0.11|-0.02|0.044|15.9
CAM|img_1_1_color.lsp|-0.94|0.07|-0.02|0.000|15.9
END</pre></body></html>"""
    simple = "RSGATE|v1|x\nCOMP|Component 0|900\nCOMP|Component 0 (1)|900\nCAM|img_1.jpg|0|0|0|0.5|15.9\nEND\n"
    merged = "RSGATE|v1|x\nCOMP|Component 0|1800|500000|6|1.9|1.2|2.8|false|true\nEND\n"
    cases = [(full, "lidar", 0), (full, "merge", 1), (full, "align", 1), (simple, "lidar", 1), (simple, "align", 1),
             (merged, "merge", 0), ("garbage", "align", 2)]
    ok = True
    for txt, stage, want in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
            fh.write(txt); p = fh.name
        try:
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): rc = run(p, stage, None, "selftest")
        finally:
            os.unlink(p)
        ok &= (rc == want)
        print("  selftest %-6s expect %d got %d %s" % (stage, want, rc, "ok" if rc == want else "MISMATCH"))
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?"); ap.add_argument("--stage", default=None)
    ap.add_argument("--images", default=None); ap.add_argument("--label", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: sys.exit(selftest())
    if not a.report or not a.stage: ap.error("report and --stage required (or --selftest)")
    sys.exit(run(a.report, a.stage, a.images, a.label))
