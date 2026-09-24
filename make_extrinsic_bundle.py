#!/usr/bin/env python3
"""
make_extrinsic_bundle.py — build a SMALL bundle for the off-rig extrinsic-alignment check.
Picks ~30 well-spread poseable keyframes from a bag, decodes just those, and tars them
with the shell geometry + poses so the whole thing is a ~20 MB upload (not a 40 GB bag).

Run on the machine that has the bag (Jetson/Shadow):
    python3 make_extrinsic_bundle.py [BAG] [SHELLDIR] [IMAGE_TOPIC] [NKEY]
Defaults target fusioncap_130955:
    BAG=/mnt/rigdata/fusioncap_130955  SHELLDIR=/mnt/rigdata/shell_130955
    IMAGE_TOPIC=/image_raw             NKEY=30
Needs pointlio_pose_matcher.py in ~/anchor_test (for read_bag/match) + rosbags + cv2.
Output: /tmp/ebundle.tar.gz  -> upload that to the chat.
"""
import sys, os, shutil, tarfile
import numpy as np, cv2
sys.path.insert(0, os.path.expanduser("~/anchor_test"))
sys.path.insert(0, os.getcwd())
import pointlio_pose_matcher as M
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from pathlib import Path

BAG      = sys.argv[1] if len(sys.argv) > 1 else "/mnt/rigdata/fusioncap_130955"
SHELLDIR = sys.argv[2] if len(sys.argv) > 2 else "/mnt/rigdata/shell_130955"
IMGTOPIC = sys.argv[3] if len(sys.argv) > 3 else "/image_raw"
NKEY     = int(sys.argv[4]) if len(sys.argv) > 4 else 30
OUT      = "/tmp/ebundle"

print("[1/4] matching poses from", BAG, "(topic", IMGTOPIC + ")")
odom_t, opos, oquat, image_t = M.read_bag(BAG, "/aft_mapped_to_init", IMGTOPIC)
res = M.match_images_to_poses(odom_t, opos, oquat, image_t, max_gap=0.5)
ok = res['ok']; ok_idx = np.where(ok)[0]
print("    matched %d / %d images" % (ok.sum(), len(ok)))
if len(ok_idx) == 0:
    raise SystemExit("no poseable frames — nothing to bundle")
if len(ok_idx) < NKEY:
    NKEY = len(ok_idx)
sel = ok_idx[np.linspace(0, len(ok_idx) - 1, NKEY).astype(int)]
selorder = {int(s): i for i, s in enumerate(sel)}   # bag image index -> selection order
print("    picking %d spread keyframes" % NKEY)

if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT + "/frames")

print("[2/4] decoding the %d selected frames" % NKEY)
TS = get_typestore(Stores.ROS2_HUMBLE)
n = 0
with AnyReader([Path(BAG)], default_typestore=TS) as r:
    conns = [c for c in r.connections if c.topic == IMGTOPIC]
    for con, _, raw in r.messages(connections=conns):
        if n in selorder:
            m = r.deserialize(raw, con.msgtype)
            if 'CompressedImage' in con.msgtype:
                img = cv2.imdecode(np.frombuffer(bytes(m.data), np.uint8), cv2.IMREAD_COLOR)
            else:
                buf = np.frombuffer(bytes(m.data), np.uint8); enc = m.encoding.lower()
                if enc in ('bgr8', 'rgb8'):
                    img = buf.reshape(m.height, m.width, 3)
                    if enc == 'rgb8':
                        img = img[:, :, ::-1]
                elif enc in ('yuv422', 'uyvy'):
                    img = cv2.cvtColor(buf.reshape(m.height, m.width, 2), cv2.COLOR_YUV2BGR_UYVY)
                elif enc in ('mono8',):
                    img = cv2.cvtColor(buf.reshape(m.height, m.width), cv2.COLOR_GRAY2BGR)
                else:
                    raise SystemExit("unhandled image encoding '%s' — tell Claude" % enc)
            if img is None:
                raise SystemExit("frame %d failed to decode" % n)
            cv2.imwrite(OUT + "/frames/img_%03d.jpg" % selorder[n], img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        n += 1

print("[3/4] writing poses.npz (selection order) + copying shell.obj/objects.ply")
np.savez(OUT + "/poses.npz",
         pos=res['pos'][sel], R=res['R'][sel], quat=res['quat'][sel],
         ok=np.ones(NKEY, bool), image_t=res['image_t'][sel], sel_bag_idx=sel,
         convention="T_lidar_in_map (body->map); subset for extrinsic alignment check")
for fn in ("shell.obj", "objects.ply"):
    src = os.path.join(SHELLDIR, fn)
    if os.path.exists(src):
        shutil.copy(src, OUT)
    else:
        print("    WARN: %s not found — bundling without it" % src)

print("[4/4] taring")
with tarfile.open("/tmp/ebundle.tar.gz", "w:gz") as t:
    t.add(OUT, arcname="ebundle")
mb = os.path.getsize("/tmp/ebundle.tar.gz") / 1e6
print("DONE -> /tmp/ebundle.tar.gz  (%.1f MB)  frames=%d  poseable=%d/%d"
      % (mb, NKEY, ok.sum(), len(ok)))
print("Upload /tmp/ebundle.tar.gz to the chat.")
