#!/usr/bin/env python3
"""extract_frames.py v3 — pull the MATCHED camera frames out of a capture bag.
Usage:
    python3 extract_frames.py <bag_dir> <posed_images.npz> [out_dir]
v3 (debugged + conflict-checked against the proven matched_inputs bundle):
  - ROS2-Humble typestore passed to AnyReader (bag has no embedded type defs).
  - Extracts BY INDEX via the npz 'ok' mask (no timestamp matching).
  - Names frames img_{i:05d}.png — EXACTLY the old bundle's convention, so all
    downstream tooling (texture engine) consumes it unchanged.
  - ROS encoding semantics corrected: "yuv422" = UYVY, "yuv422_yuy2"/"yuyv" = YUY2.
"""
import sys, os
from pathlib import Path
import numpy as np

def decode_image(msg):
    import cv2
    h, w, enc = msg.height, msg.width, msg.encoding.lower()
    buf = np.frombuffer(msg.data, dtype=np.uint8)
    if enc in ("rgb8", "bgr8"):
        img = buf.reshape(h, w, 3)
        return img[:, :, ::-1].copy() if enc == "rgb8" else img
    if enc == "mono8":
        return buf.reshape(h, w)
    if enc in ("yuv422_yuy2", "yuyv"):                 # YUYV byte order
        return cv2.cvtColor(buf.reshape(h, w, 2), cv2.COLOR_YUV2BGR_YUY2)
    if enc in ("yuv422", "uyvy"):                      # ROS "yuv422" = UYVY
        return cv2.cvtColor(buf.reshape(h, w, 2), cv2.COLOR_YUV2BGR_UYVY)
    raise ValueError(f"unhandled encoding: {msg.encoding}")

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    bag_dir, npz_path = sys.argv[1], sys.argv[2]
    out_dir = Path(sys.argv[3] if len(sys.argv) > 3 else "frames"); out_dir.mkdir(exist_ok=True)

    z = np.load(npz_path, allow_pickle=True)
    ok = np.asarray(z["ok"], dtype=bool)
    print(f"npz: {len(ok)} images total, {ok.sum()} matched (ok mask)")

    import cv2
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore
    ts = get_typestore(Stores.ROS2_HUMBLE)

    written, enc_seen = 0, None
    with AnyReader([Path(bag_dir)], default_typestore=ts) as reader:
        conns = [c for c in reader.connections if c.topic == "/image_raw"]
        i = 0
        for conn, bag_ts, raw in reader.messages(connections=conns):
            if i >= len(ok):
                break
            if ok[i]:
                msg = reader.deserialize(raw, conn.msgtype)
                if enc_seen is None:
                    enc_seen = msg.encoding
                    print(f"image encoding: {enc_seen}")
                img = decode_image(msg)
                cv2.imwrite(str(out_dir / f"img_{i:05d}.png"), img)
                written += 1
            i += 1
    print(f"bag /image_raw messages seen: {i}")
    print(f"wrote {written}/{ok.sum()} matched frames -> {out_dir}/")
    os.system(f'ls "{out_dir}" | head -3; ls "{out_dir}" | wc -l')

if __name__ == "__main__":
    main()
