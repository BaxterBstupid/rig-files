#!/usr/bin/env python3
"""
join_check.py  v2 -- show how one bundle frame joins its neighbours in the walk, on ONE board.
Takes frame F with --before N frames and --after M frames (filename order = time). For each
adjacent pair: SIFT matches, RANSAC-consistent inliers, the share of each frame they cover, the
median pixel shift, and a 50/50 overlay of the pair at that shift (far scene lines up, near
things double = parallax). Writes one image: top row the frames in order (F marked), second row
the pair overlays with their numbers.

    python3 join_check.py <images_dir> <frame_name.jpg> <out_dir> [--before 4] [--after 5]

Writes:  <out_dir>/join_board_<frame>.jpg   and prints the per-pair table.  Reads only.
"""
import os, glob, argparse
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument("images"); ap.add_argument("frame"); ap.add_argument("out")
ap.add_argument("--before", type=int, default=4); ap.add_argument("--after", type=int, default=5)
ap.add_argument("--tile", type=int, default=400)
a = ap.parse_args()

files = sorted(glob.glob(os.path.join(a.images, "*.jpg")))
names = [os.path.basename(f) for f in files]
if a.frame not in names: raise SystemExit("frame not found: %s" % a.frame)
i0 = names.index(a.frame)
idx = [i for i in range(i0 - a.before, i0 + a.after + 1) if 0 <= i < len(files)]
os.makedirs(a.out, exist_ok=True)
def stamp(n):
    try: return int(n.split("_")[1].split(".")[0]) / 1e9
    except Exception: return float("nan")
def short(n): return n[-14:-4]

sift = cv2.SIFT_create(nfeatures=4000)
imgs, kps, des = {}, {}, {}
for i in idx:
    im = cv2.imread(files[i]); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    k, d = sift.detectAndCompute(g, None); imgs[i], kps[i], des[i] = im, k, d
print("frames in order (* = the one asked for):")
for i in idx: print("  %s %s  features %d" % ("*" if i == i0 else " ", names[i], len(kps[i])))

W = a.tile; H = int(imgs[idx[0]].shape[0] * W / imgs[idx[0]].shape[1])
top = []
for i in idx:
    t = cv2.resize(imgs[i], (W, H), interpolation=cv2.INTER_AREA)
    cv2.rectangle(t, (0, 0), (W, 26), (0, 0, 0), -1)
    cv2.putText(t, short(names[i]) + ("  *" if i == i0 else ""), (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (0, 255, 0) if i == i0 else (255, 255, 255), 1)
    if i == i0: cv2.rectangle(t, (0, 0), (W - 1, H - 1), (0, 255, 0), 3)
    top.append(t)

bf = cv2.BFMatcher(cv2.NORM_L2)
def hull(p, s): return 0.0 if len(p) < 3 else cv2.contourArea(cv2.convexHull(p.astype(np.float32))) / (s[0] * s[1])
print("\npair                     dt[s]  matches  inliers  cover  shift(px, full-res)")
bottom = []
for j in range(len(idx) - 1):
    p, q = idx[j], idx[j + 1]
    A, B = imgs[p], imgs[q]
    label = "%s>%s" % (short(names[p])[-6:], short(names[q])[-6:])
    good = []
    if des[p] is not None and des[q] is not None:
        good = [x for x, y in bf.knnMatch(des[p], des[q], k=2) if x.distance < 0.75 * y.distance]
    if len(good) < 8:
        print("%-24s  too few matches (%d)" % (label, len(good)))
        ov = cv2.resize(A, (W, H)); cv2.putText(ov, "no join", (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 1)
        bottom.append(ov); continue
    pa = np.float32([kps[p][x.queryIdx].pt for x in good]); pb = np.float32([kps[q][x.trainIdx].pt for x in good])
    F, mask = cv2.findFundamentalMat(pa, pb, cv2.FM_RANSAC, 2.0, 0.999)
    inl = mask.ravel().astype(bool) if mask is not None else np.zeros(len(good), bool)
    d = pb[inl] - pa[inl]; dx, dy = (np.median(d[:, 0]), np.median(d[:, 1])) if inl.sum() else (0, 0)
    dt = stamp(names[q]) - stamp(names[p])
    cov = 100 * min(hull(pa[inl], A.shape), hull(pb[inl], B.shape))
    print("%-24s  %5.2f   %6d   %6d   %3.0f%%   dx %+6.0f dy %+6.0f" % (label, dt, len(good), inl.sum(), cov, dx, dy))
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    ov = cv2.addWeighted(A, 0.5, cv2.warpAffine(B, M, (A.shape[1], A.shape[0])), 0.5, 0)
    ov = cv2.resize(ov, (W, H), interpolation=cv2.INTER_AREA)
    cv2.rectangle(ov, (0, 0), (W, 26), (0, 0, 0), -1)
    cv2.putText(ov, "%s  %.2fs  inl %d  %.0f%%" % (label, dt, inl.sum(), cov), (6, 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    bottom.append(ov)
bottom.append(np.zeros((H, W, 3), np.uint8))   # pad to the frame row's width
board = np.vstack([np.hstack(top), np.hstack(bottom)])
out = os.path.join(a.out, "join_board_%s.jpg" % short(a.frame))
cv2.imwrite(out, board, [cv2.IMWRITE_JPEG_QUALITY, 85])
print("\nDONE -> %s  (%dx%d)" % (out, board.shape[1], board.shape[0]))
