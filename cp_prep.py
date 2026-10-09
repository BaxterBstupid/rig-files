#!/usr/bin/env python3
"""
cp_prep.py  v1 -- control-point prep for the RealityScan merge (reference §3 step 6).
Ranks every frame in an rsbundle images/ folder by sharpness (variance of the Laplacian),
picks the sharpest frame in each of N equal time slices of the walk (filenames carry the ns
stamp, so sorted order = time), and tiles them into ONE labelled contact sheet so the six
control-point corners can be chosen before touching RealityScan.

    python3 cp_prep.py <images_dir> <out_dir> [--n 12] [--cols 3]

Writes:  <out_dir>/sharpness.csv          every frame: name, time-slice, sharpness
         <out_dir>/cp_contact_sheet.jpg   N sharpest-per-slice frames, labelled
         <out_dir>/cp_picks.txt           the N chosen filenames (for the RS 2D view)
Reads only. Light: ~900 JPEGs at 1/4 scale, well under a minute on the Jetson.
"""
import sys, os, glob, argparse, csv
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument("images"); ap.add_argument("out")
ap.add_argument("--n", type=int, default=12, help="time slices = frames on the sheet")
ap.add_argument("--cols", type=int, default=3)
ap.add_argument("--tile", type=int, default=640, help="tile width px")
a = ap.parse_args()

files = sorted(glob.glob(os.path.join(a.images, "*.jpg")) + glob.glob(os.path.join(a.images, "*.png")))
if not files:
    raise SystemExit("no .jpg/.png in %s" % a.images)
os.makedirs(a.out, exist_ok=True)

print("[1/3] sharpness of %d frames" % len(files))
sharp = np.zeros(len(files))
for i, f in enumerate(files):
    im = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
    if im is None:
        sharp[i] = -1; continue
    im = cv2.resize(im, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    sharp[i] = cv2.Laplacian(im, cv2.CV_64F).var()
    if (i + 1) % 100 == 0: print("      %d/%d" % (i + 1, len(files)))

slice_of = (np.arange(len(files)) * a.n) // len(files)
with open(os.path.join(a.out, "sharpness.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["frame", "slice", "sharpness"])
    for f, s, v in zip(files, slice_of, sharp):
        w.writerow([os.path.basename(f), int(s), "%.1f" % v])
ok = sharp[sharp >= 0]
print("      sharpness: min %.0f  p25 %.0f  median %.0f  p75 %.0f  max %.0f"
      % (ok.min(), np.percentile(ok, 25), np.median(ok), np.percentile(ok, 75), ok.max()))

print("[2/3] sharpest frame per slice")
picks = []
for s in range(a.n):
    idx = np.where(slice_of == s)[0]
    if len(idx) == 0: continue
    best = idx[np.argmax(sharp[idx])]
    picks.append(best)
    print("      slice %2d: %-40s %7.0f  (slice median %.0f)"
          % (s, os.path.basename(files[best]), sharp[best], np.median(sharp[idx])))
with open(os.path.join(a.out, "cp_picks.txt"), "w") as fh:
    for i in picks: fh.write(os.path.basename(files[i]) + "\n")

print("[3/3] contact sheet")
tiles = []
for k, i in enumerate(picks):
    im = cv2.imread(files[i])
    h = int(im.shape[0] * a.tile / im.shape[1])
    im = cv2.resize(im, (a.tile, h), interpolation=cv2.INTER_AREA)
    label = "%d  %s  sharp %.0f" % (k + 1, os.path.basename(files[i]), sharp[i])
    cv2.rectangle(im, (0, 0), (a.tile, 34), (0, 0, 0), -1)
    cv2.putText(im, label, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    tiles.append(im)
while len(tiles) % a.cols: tiles.append(np.zeros_like(tiles[0]))
rows = [np.hstack(tiles[r:r + a.cols]) for r in range(0, len(tiles), a.cols)]
sheet = np.vstack(rows)
out = os.path.join(a.out, "cp_contact_sheet.jpg")
cv2.imwrite(out, sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
print("      -> %s  (%dx%d)" % (out, sheet.shape[1], sheet.shape[0]))
print("DONE: %d picks in %s" % (len(picks), a.out))
