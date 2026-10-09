#!/usr/bin/env python3
"""
cp_click.py -- guided corner clicking for the control-point merge (S3). Writes cp_clicks.csv for cp_make.py.

    python cp_click.py <images_dir> <cp_picks.txt> <out>/cp_clicks.csv [--plan plan.csv] [--views 3]

Opens each (corner, sharp frame) pair from the plan, full-resolution image scaled to fit the screen, with a 4x magnifier
following the mouse. LEFT CLICK = record the corner (pixel coords in the ORIGINAL image, top-left origin, as RealityScan
wants). Keys:  s = skip this frame (corner not visible)   z = undo last click   q = quit (everything so far is saved).
Every click is appended to the CSV immediately; re-running resumes where you stopped (already-clicked pairs are skipped).

Default plan = CANONICAL_ROOM_GEOGRAPHY.md (frames are 1-based rows of cp_picks.txt = contact-sheet numbers):
    CP1 arch casing, left springing            frames 5 6 8 11
    CP2 study French door, top-left corner      frames 1 5 6 8 11
    CP3 large gilt painting, bottom-left corner frames 1 5 6 11
    CP4 mantel shelf, top-right corner          frames 9 10 12
    CP5 firebox opening, top-left corner        frames 4 10 12
    CP6 gilt mirror FRAME, bottom-left corner   frames 9 10 12   (frame moulding only -- never the glass)
A plan file overrides it: one line per corner  "CP1, arch casing left springing, 5 6 8 11".
Rule from the reference: hard fixed corners only; each corner in >= 3 photos (cp_make.py enforces --min-views).
"""
import sys, os, csv, argparse

DEFAULT_PLAN = [
    ("CP1", "arch casing, LEFT springing (where the arch curve meets the vertical)", [5, 6, 8, 11]),
    ("CP2", "study French door, TOP-LEFT corner of the door frame", [1, 5, 6, 8, 11]),
    ("CP3", "large gilt painting, BOTTOM-LEFT corner of the frame", [1, 5, 6, 11]),
    ("CP4", "mantel shelf, TOP-RIGHT corner", [9, 10, 12]),
    ("CP5", "firebox opening, TOP-LEFT corner", [4, 10, 12]),
    ("CP6", "gilt mirror FRAME, BOTTOM-LEFT corner (moulding, not glass)", [9, 10, 12]),
]

def load_plan(path):
    plan = []
    for row in csv.reader(l for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")):
        if len(row) < 3: continue
        plan.append((row[0].strip(), row[1].strip(), [int(x) for x in row[2].split()]))
    return plan

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images"); ap.add_argument("picks"); ap.add_argument("out")
    ap.add_argument("--plan", default=""); ap.add_argument("--views", type=int, default=3, help="stop asking for a corner after this many clicks")
    ap.add_argument("--selftest", action="store_true", help="no GUI: write a synthetic CSV to prove the plumbing")
    a = ap.parse_args()
    picks = [l.strip() for l in open(a.picks, encoding="utf-8") if l.strip()]
    plan = load_plan(a.plan) if a.plan else DEFAULT_PLAN
    done = set()
    if os.path.exists(a.out):
        for row in csv.reader(l for l in open(a.out, encoding="utf-8") if l.strip() and not l.startswith("#")):
            if len(row) >= 4 and row[2].strip().lower() != "x": done.add((row[1].strip(), row[0].strip()))
    new = not os.path.exists(a.out) or os.path.getsize(a.out) == 0
    fh = open(a.out, "a", encoding="utf-8", newline="")
    if new: fh.write("image, point, x, y\n"); fh.flush()
    counts = {cp: sum(1 for (p, _) in done if p == cp) for cp, _, _ in plan}
    todo = [(cp, desc, picks[f - 1]) for cp, desc, frames in plan for f in frames if f - 1 < len(picks) and (cp, picks[f - 1]) not in done]
    print("picks: %d frames   plan: %d corners   already clicked: %d   to do: %d" % (len(picks), len(plan), len(done), len(todo)))
    if a.selftest:
        for cp, desc, img in todo:
            if counts[cp] >= a.views: continue
            fh.write("%s, %s, %.1f, %.1f\n" % (img, cp, 100.0, 200.0)); counts[cp] += 1
        fh.close(); print("selftest wrote", a.out); return 0
    import cv2
    try:
        import ctypes; sw, sh = ctypes.windll.user32.GetSystemMetrics(0) - 80, ctypes.windll.user32.GetSystemMetrics(1) - 160
    except Exception:
        sw, sh = 1600, 900
    state = {"pos": (0, 0), "click": None}
    def on_mouse(ev, x, y, flags, param):
        state["pos"] = (x, y)
        if ev == cv2.EVENT_LBUTTONDOWN: state["click"] = (x, y)
    cv2.namedWindow("cp_click"); cv2.setMouseCallback("cp_click", on_mouse); cv2.namedWindow("zoom")
    history = []
    i = 0
    while i < len(todo):
        cp, desc, img = todo[i]
        if counts[cp] >= a.views: i += 1; continue
        path = os.path.join(a.images, img)
        full = cv2.imread(path)
        if full is None: print("missing", path); i += 1; continue
        H, W = full.shape[:2]; scale = min(sw / W, sh / H, 1.0)
        disp0 = cv2.resize(full, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
        state["click"] = None
        while True:
            disp = disp0.copy()
            cv2.rectangle(disp, (0, 0), (disp.shape[1], 54), (0, 0, 0), -1)
            cv2.putText(disp, "%s  (%d/%d clicked)  %s" % (cp, counts[cp], a.views, desc), (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
            cv2.putText(disp, "%s   LEFT CLICK = record   s = not visible   z = undo   q = quit (saved)" % img, (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            mx, my = state["pos"]; cv2.drawMarker(disp, (mx, my), (0, 255, 0), cv2.MARKER_CROSS, 24, 1)
            cv2.imshow("cp_click", disp)
            fx, fy = int(mx / scale), int(my / scale); r = 40
            x0, y0 = max(0, min(W - 2 * r, fx - r)), max(0, min(H - 2 * r, fy - r))
            z = cv2.resize(full[y0:y0 + 2 * r, x0:x0 + 2 * r], (320, 320), interpolation=cv2.INTER_NEAREST)
            cv2.drawMarker(z, (int((fx - x0) * 4), int((fy - y0) * 4)), (0, 255, 0), cv2.MARKER_CROSS, 40, 1)
            cv2.imshow("zoom", z)
            k = cv2.waitKey(20) & 0xFF
            if state["click"]:
                cx, cy = state["click"]; px, py = cx / scale, cy / scale
                fh.write("%s, %s, %.1f, %.1f\n" % (img, cp, px, py)); fh.flush()
                counts[cp] += 1; history.append((img, cp)); print("  %s %s -> %.1f, %.1f" % (cp, img, px, py))
                i += 1; break
            if k == ord("s"): print("  %s %s skipped" % (cp, img)); i += 1; break
            if k == ord("z") and history:
                img_u, cp_u = history.pop(); counts[cp_u] -= 1
                rows = [l for l in open(a.out, encoding="utf-8")]
                for j in range(len(rows) - 1, -1, -1):
                    if rows[j].startswith(img_u + ", " + cp_u + ","): del rows[j]; break
                fh.close(); open(a.out, "w", encoding="utf-8", newline="").writelines(rows); fh = open(a.out, "a", encoding="utf-8", newline="")
                print("  undid %s %s" % (cp_u, img_u)); i = max(0, i - 1); break
            if k == ord("q"): fh.close(); cv2.destroyAllWindows(); print("saved", a.out); return 0
    fh.close(); cv2.destroyAllWindows()
    print("done:", ", ".join("%s=%d" % (cp, counts[cp]) for cp, _, _ in plan), "->", a.out)
    short = [cp for cp, _, _ in plan if counts[cp] < 3]
    if short: print("WARNING corners with < 3 clicks:", short, "-- add frames to the plan or re-run")
    return 0

if __name__ == "__main__":
    sys.exit(main())
