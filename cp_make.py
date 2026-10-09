#!/usr/bin/env python3
"""
cp_make.py -- turn corner clicks on PHOTOS into a RealityScan control-point measurement file that also covers the LSPs.

    python cp_make.py <clicks.csv> <S2_lidar.html> <S2b_lidar_lsp.html> <out>/cps.cpm [--min-views 3]

clicks.csv  (you write this; one line per click, pixels from the TOP-LEFT of the photo, # comments allowed):
    image, point, x, y
    img_1790187031421918774.jpg, CP1, 1812.0, 944.5
    ...
S2_lidar.html / S2b_lidar_lsp.html  = the lidar-stage reports (Component 0 selected / Laserscan selected); their CAM lines carry
    the exact image names + paths RealityScan knows, so the output references images exactly as the project does.

Why mirroring is valid: every img_X_1_color.lsp is a virtual camera rendered AT THE POSE of img_X.jpg with the same intrinsics
(LiDAR import "From component"), so a corner's pixel position in the LSP view equals its position in the photo (when the S1
frame check passed and the LSP block did not float).  One click per photo therefore yields two measurements.
Output format = RealityScan "Image, Point, X, Y" comma-separated, pixels from the top-left   [DOC cpmeasurementsimport.htm].
Rules enforced: every point must be measured in >= --min-views photos (RS help: CPs on >= 3 images to connect components;
the reference procedure wants each CP in both blocks); points failing that are dropped with a message.
"""
import sys, os, csv, argparse, re

def norm(name):
    """RealityScan's imageExt already carries the dot, so a template writing $(imageName).$(imageExt) yields 'img..jpg'.
    Collapse repeated dots and lower-case: one canonical key for clicks, reports and the output file."""
    return re.sub(r"\.{2,}", ".", os.path.basename(name).strip()).lower()

def read_cams(report):
    cams = {}
    for line in open(report, encoding="utf-8", errors="replace"):
        if line.startswith("CAM|"):
            f = [x.strip() for x in line.rstrip("\r\n").split("|")]
            if len(f) >= 2 and "$" not in line: cams[norm(f[1])] = (re.sub(r"\.{2,}", ".", f[1]), f[7] if len(f) > 7 else "")
    return cams

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clicks"); ap.add_argument("photo_report"); ap.add_argument("lsp_report"); ap.add_argument("out")
    ap.add_argument("--min-views", type=int, default=3); ap.add_argument("--full-path", action="store_true", help="write imagePath+name (export style) instead of bare names")
    a = ap.parse_args()
    photos, lsps = read_cams(a.photo_report), read_cams(a.lsp_report)
    if not photos or not lsps: sys.exit("no CAM lines in a report -- run the lidar stage first (needs template v6+)")
    print("report names look like: photo %r   LSP %r" % (next(iter(photos.values()))[0], next(iter(lsps.values()))[0]))
    rows, bad = [], []
    for r in csv.reader(l for l in open(a.clicks, encoding="utf-8") if l.strip() and not l.lstrip().startswith("#")):
        if len(r) < 4: continue
        img, pt, x, y = r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()
        if x.lower() == "x": continue   # header
        key = norm(img)
        if key not in photos: bad.append(img); continue
        stem = os.path.splitext(photos[key][0])[0]
        lkey = norm(stem + "_1_color.lsp")
        if lkey not in lsps: bad.append(img + " (no matching LSP)"); continue
        rows.append((photos[key], pt, float(x), float(y)))
        rows.append((lsps[lkey], pt, float(x), float(y)))
    views = {}
    for (name, path), pt, x, y in rows:
        if name.lower().endswith(".jpg"): views[pt] = views.get(pt, 0) + 1
    keep = {pt for pt, n in views.items() if n >= a.min_views}
    dropped = sorted(set(views) - keep)
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        fh.write("# cps.cpm made by cp_make.py from %s -- Image, Point, X, Y (pixels, top-left); LSP rows mirror photo rows\n" % os.path.basename(a.clicks))
        for (name, path), pt, x, y in rows:
            if pt in keep: fh.write("%s, %s, %.2f, %.2f\n" % ((path + name) if a.full_path else name, pt, x, y))
    print("points kept: %d (%s)   dropped (< %d photos): %s   unknown images: %d" % (len(keep), ", ".join(sorted(keep)), a.min_views, dropped or "none", len(bad)))
    for b in bad[:5]: print("  unknown:", b, "  (click names must match the report names above)")
    if not rows: print("NOTHING MATCHED -- first click image: %r ; first report photo: %r" % (next(csv.reader(open(a.clicks, encoding="utf-8")))[0] if os.path.getsize(a.clicks) else "", next(iter(photos.values()))[0]))
    print("wrote", a.out, "with", sum(1 for (n, p), pt, x, y in rows if pt in keep), "measurements")
    return 0 if len(keep) >= 6 and not bad else 1

if __name__ == "__main__":
    sys.exit(main())
