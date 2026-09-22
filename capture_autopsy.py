#!/usr/bin/env python3
"""
capture_autopsy.py  —  capture-METHOD post-mortem across many Point-LIO bags.

Fixes what check_capture couldn't do (its AnyReader lacked the typestore, so odom
never decoded) and answers the real question: across every capture we own, WHERE
did tracking hold and where did it collapse? The pattern in this one table is the
diagnosis of the capture method.

Reads odom by BAG-RECORD time (robust to Point-LIO's frozen header stamps), and
flags mid-run gaps (odom died and came back) — the failure check_capture's span-only
measure would miss.

Run on the JETSON:
  python3 capture_autopsy.py /mnt/rigdata/fusioncap_* /mnt/rigdata/"Fusioncap scans"/fusioncap_*
Loose-glob non-bag paths (.pcd/.ply/.npy) are skipped automatically.
"""
import os, sys
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

ODOM  = "/aft_mapped_to_init"
IMG   = "/image_raw"
CLOUD = "/unilidar/cloud"
GAP_S = 0.5   # odom silence longer than this counts as a dropout

TS = get_typestore(Stores.ROS2_HUMBLE)


def is_bag(p):
    if not os.path.isdir(p):
        return False
    try:
        if os.path.exists(os.path.join(p, "metadata.yaml")):
            return True
        return any(f.endswith((".db3", ".mcap")) for f in os.listdir(p))
    except OSError:
        return False


def analyze(bag):
    with AnyReader([Path(bag)], default_typestore=TS) as r:
        dur = (r.duration / 1e9) if getattr(r, "duration", None) else 0.0
        counts = {c.topic: c.msgcount for c in r.connections}
        nimg, ncloud = counts.get(IMG, 0), counts.get(CLOUD, 0)
        oconns = [c for c in r.connections if c.topic == ODOM]
        if not oconns:
            return dict(dur=dur, span=0.0, pct=0.0, n=0, gaps=0, big=0.0,
                        img=nimg, cloud=ncloud, note="NO ODOM TOPIC")
        stamps = sorted(t for _, t, _ in r.messages(connections=oconns))
        n = len(stamps)
        span = (stamps[-1] - stamps[0]) / 1e9 if n > 1 else 0.0
        gaps = 0; big = 0.0
        for i in range(1, n):
            d = (stamps[i] - stamps[i - 1]) / 1e9
            if d > GAP_S:
                gaps += 1; big = max(big, d)
        pct = 100 * span / dur if dur > 0 else 0.0
        return dict(dur=dur, span=span, pct=pct, n=n, gaps=gaps, big=big,
                    img=nimg, cloud=ncloud, note="")


def verdict(a):
    if a["n"] == 0 or a["pct"] < 40:
        return "RESHOOT"
    if a["pct"] < 75 or a["gaps"] > 0:
        return "CAUTION"
    return "GOOD"


def main(paths):
    rows = []
    for p in paths:
        p = p.rstrip("/")
        if not is_bag(p):
            continue
        name = os.path.basename(p)
        try:
            a = analyze(p); a["name"] = name; a["verdict"] = verdict(a)
        except Exception as e:
            a = dict(name=name, dur=0, span=0, pct=0, n=0, gaps=0, big=0,
                     img=0, cloud=0, verdict="ERR", note=repr(e)[:46])
        rows.append(a)
    rows.sort(key=lambda x: x["pct"])   # worst tracking first — the pattern reads top-down

    print(f"\n{'capture':22} {'dur_s':>6} {'odom_s':>6} {'track':>6} {'poses':>6} "
          f"{'gaps':>4} {'biggap':>6} {'imgs':>5} {'clouds':>6} {'verdict':>8}  note")
    print("-" * 110)
    g = c = b = 0
    for a in rows:
        print(f"{a['name']:22} {a['dur']:6.1f} {a['span']:6.1f} {a['pct']:5.0f}% "
              f"{a['n']:6d} {a['gaps']:4d} {a['big']:6.1f} {a['img']:5d} {a['cloud']:6d} "
              f"{a['verdict']:>8}  {a.get('note','')}")
        v = a["verdict"]; g += v == "GOOD"; c += v == "CAUTION"; b += v in ("RESHOOT", "ERR")
    print("-" * 110)
    print(f"{len(rows)} captures   GOOD {g}   CAUTION {c}   RESHOOT/ERR {b}   "
          f"(GOOD = odom ≥ 75% of duration AND no >{GAP_S}s gaps)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 capture_autopsy.py <bag_dir> [more ...]")
    main(sys.argv[1:])
