#!/usr/bin/env python3
"""
frame_qc.py — the RealityScan-facing capture gate the current gates lack.
============================================================================
WHY (ADR-003 conflicts #2 image-quality, #4 sharpness/overlap):
  capture_autopsy / matcher% / planar_shell all check OUR pipeline's health
  (odom moved? poses dense? planes flat?). NONE of them checks what
  RealityScan actually consumes: SHARP, well-compressed frames. A capture can
  pass every existing gate and still be un-alignable in RealityScan because the
  frames are motion-blurred, or texture badly because the camera's native JPEG
  is over-compressed. This tool measures both, per frame, BEFORE the shoot.

WHAT IT REPORTS PER FRAME:
  - sharpness = variance of the Laplacian (cv2). Higher = sharper. Motion blur
    tanks it. This is the standard blur metric.
  - jpeg_quality = libjpeg quality factor estimated from the quantization
    tables (via ImageMagick `identify -format %Q`). This is the TEXTURE ceiling.
  - subsampling = chroma sampling factor (4:4:4 best .. 4:2:0 lossiest chroma).
  - WxH + format + EXIF make/model/time when present.

VERDICT LOGIC (thresholds are CLI-tunable — calibrate on YOUR frames first):
  - BLUR    if sharpness < --sharp-min           (default 100.0; scene-relative)
  - LOWQ    if jpeg_quality < --q-min            (default 90)
  - CHROMA  if subsampling is 4:2:0              (warn: chroma loss for texture)
  A frame is PASS only if none fire. The tool prints a per-frame table, the
  distribution, and a GO/NO-GO summary, and exits non-zero if the fail rate
  exceeds --max-fail-frac (default 0.15) — so it can sit in the gate chain.

UP/DOWN-PIPELINE EFFECTS (the whole point of this project's discipline):
  - UP (capture): a NO-GO here means fix the SHOOT (slower motion / more light /
    faster shutter / stop-and-shoot; raise the camera's MJPEG quality) — NOT the
    processing. These are the only knobs that exist before the bag is written.
  - DOWN (RealityScan): sharp+high-Q frames -> more tie-points, one component,
    lower reprojection error, cleaner texture. Blurry/low-Q frames -> split
    components + baked-in texture artifacts that no delight step can remove.

USAGE:
  python3 frame_qc.py IMG [IMG ...]
  python3 frame_qc.py --dir frames_folder --glob '*.jpg'
  python3 frame_qc.py --dir f --sharp-min 120 --q-min 92 --max-fail-frac 0.1
============================================================================
"""
import sys, os, argparse, subprocess, glob as globmod, json
import numpy as np
import cv2


def imagemagick_probe(path):
    """quality (%Q), sampling-factor, WxH, format via ImageMagick identify.
    Returns dict; fields None if identify missing or field absent."""
    out = {"q": None, "subsampling": None, "wh": None, "fmt": None}
    try:
        fmt = "%Q|%[jpeg:sampling-factor]|%wx%h|%m"
        r = subprocess.run(["identify", "-format", fmt, path],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            parts = r.stdout.strip().split("|")
            if len(parts) >= 4:
                out["q"] = _to_int(parts[0])
                out["subsampling"] = parts[1].strip() or None
                out["wh"] = parts[2].strip() or None
                out["fmt"] = parts[3].strip() or None
    except Exception:
        pass
    return out


def _to_int(s):
    try:
        return int(s)
    except Exception:
        return None


def subsampling_label(sf):
    """Map ImageMagick sampling-factor to a human 4:x:x label + chroma-loss flag."""
    if not sf:
        return ("?", False)
    sf = sf.replace(";", ",")
    # common encodings: '2x2,1x1,1x1'=4:2:0 ; '2x1,1x1,1x1'=4:2:2 ; '1x1,1x1,1x1'=4:4:4
    first = sf.split(",")[0].strip()
    table = {"2x2": ("4:2:0", True), "2x1": ("4:2:2", False),
             "1x2": ("4:4:0", False), "1x1": ("4:4:4", False)}
    return table.get(first, (sf, first == "2x2"))


def sharpness_varlap(path):
    """Variance of the Laplacian on the luma channel. None if unreadable.
    Downscale-invariant-ish: we DO NOT resize (blur is what we want to see),
    but we report the image's long edge so you can compare like-for-like."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None, None
    lap = cv2.Laplacian(img, cv2.CV_64F)
    return float(lap.var()), int(max(img.shape))


def exif_bits(path):
    try:
        from PIL import Image
        im = Image.open(path)
        info = {}
        ex = getattr(im, "_getexif", lambda: None)()
        if ex:
            # 271 Make, 272 Model, 306 DateTime, 33434 ExposureTime
            tags = {271: "make", 272: "model", 306: "datetime", 33434: "exposure"}
            for k, name in tags.items():
                if k in ex:
                    info[name] = ex[k]
        return info
    except Exception:
        return {}


def analyze(path):
    mm = imagemagick_probe(path)
    sharp, longedge = sharpness_varlap(path)
    sublabel, chroma_loss = subsampling_label(mm["subsampling"])
    return {
        "file": os.path.basename(path),
        "sharp": sharp,
        "longedge": longedge,
        "q": mm["q"],
        "sub": sublabel,
        "chroma_loss": chroma_loss,
        "wh": mm["wh"],
        "fmt": mm["fmt"],
        "exif": exif_bits(path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--glob", default="*.jpg")
    ap.add_argument("--sharp-min", type=float, default=100.0)
    ap.add_argument("--q-min", type=int, default=90)
    ap.add_argument("--max-fail-frac", type=float, default=0.15)
    ap.add_argument("--json", action="store_true", help="emit JSON too")
    args = ap.parse_args()

    paths = list(args.images)
    if args.dir:
        paths += sorted(globmod.glob(os.path.join(args.dir, args.glob)))
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        print("no images given (positional paths, or --dir --glob)")
        return 2

    rows = [analyze(p) for p in paths]

    # per-frame table
    hdr = "%-26s %10s %6s %5s %7s %-9s %s" % (
        "file", "sharp", "long", "Q", "sub", "size", "verdict")
    print(hdr); print("-" * len(hdr))
    n_fail = 0
    sharps = []
    for r in rows:
        flags = []
        if r["sharp"] is None:
            flags.append("UNREADABLE")
        else:
            sharps.append(r["sharp"])
            if r["sharp"] < args.sharp_min:
                flags.append("BLUR")
        if r["q"] is not None and r["q"] < args.q_min:
            flags.append("LOWQ")
        if r["chroma_loss"]:
            flags.append("CHROMA420")
        verdict = "PASS" if not flags else " ".join(flags)
        if any(f in ("BLUR", "LOWQ", "UNREADABLE") for f in flags):
            n_fail += 1
        print("%-26s %10s %6s %5s %7s %-9s %s" % (
            r["file"][:26],
            ("%.1f" % r["sharp"]) if r["sharp"] is not None else "-",
            r["longedge"] if r["longedge"] else "-",
            r["q"] if r["q"] is not None else "-",
            r["sub"], r["wh"] or "-", verdict))

    # distribution + summary
    print()
    if sharps:
        a = np.array(sharps)
        print("sharpness  min=%.1f  p10=%.1f  median=%.1f  p90=%.1f  max=%.1f"
              % (a.min(), np.percentile(a, 10), np.median(a),
                 np.percentile(a, 90), a.max()))
    qs = [r["q"] for r in rows if r["q"] is not None]
    if qs:
        print("jpeg Q     min=%d  median=%d  max=%d   (texture ceiling)"
              % (min(qs), int(np.median(qs)), max(qs)))
    subs = sorted(set(r["sub"] for r in rows))
    print("subsampling seen: %s" % ", ".join(subs))
    frac = n_fail / len(rows)
    print("\nFAIL frac = %d/%d = %.0f%%   (threshold %.0f%%)"
          % (n_fail, len(rows), 100 * frac, 100 * args.max_fail_frac))
    go = frac <= args.max_fail_frac
    print("VERDICT: %s" % ("GO" if go else "NO-GO — fix the SHOOT, not the processing"))

    if args.json:
        print("\n" + json.dumps(rows, indent=2, default=str))
    return 0 if go else 2


if __name__ == "__main__":
    sys.exit(main())
