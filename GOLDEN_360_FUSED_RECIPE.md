# GOLDEN 360 FUSED PANORAMA — REPEATABLE PROCESS
### Ratified 2026-09-24 on capture `114136`. The visual passed — this is the "do it again" list so the next pan is a REPEAT, not a re-derivation.

> **THE GATE (read first).** The deliverable is the IMAGE, never the numbers. A step's
> job is to feed the render; the render's job is to pass the eye. Acceptance is at the
> bottom (§7). If the final 360 doesn't read as the real room in real colour, the run
> FAILED no matter how green the intermediate numbers were.

---

## 0. WHAT THIS PRODUCES

One **equirectangular 360 panorama** of the room: real photo colour projected onto the
LiDAR geometry, everywhere a camera looked; LiDAR-intensity grayscale where none did.
This is the *see-what-we-captured* artifact — it proves the whole chain
**capture → geometry → anchor → colour** in a single picture. It is NOT yet the walkable
Unreal mesh (that is the next arc); it is the honest visual proof that the capture is good
enough to build one.

**Reference result (114136, 2026-09-24):** 77.7% of the cloud coloured, 306° of heading,
35 frames, one clean bag. Delivered as `pano_360_fullring_114136.png`.

---

## 1. MACHINE DIVISION (never violate)

- **JETSON (8 GB):** bringup, capture, pan-confirm, anchor export. These fit in memory.
- **STATION / sandbox:** the fusion render (`fuse_pano.py`).
- **NEVER bake or fuse on the Jetson** — a full projection over the cloud hard-locks the
  8 GB machine. The Jetson only ever *reads* its bag to export a ~10 MB bundle.

---

## 2. FIXED CALIBRATION — must be byte-identical every run

The whole thing only registers because these values are exact. They live embedded in
`fuse_pano.py` and in `per_shot_texture.py`. **Do not edit. If the rig is ever
re-calibrated, that is a new recipe.**

```
K    = [[848.759, 0, 921.002], [0, 849.231, 565.962], [0, 0, 1]]
DIST = [-0.014979, -0.013547, -0.001997, 0.000698, 0.003842]
R_L2C= [[ 0.0792320,  0.9945600, -0.0676217],
        [-0.9871614,  0.0877183,  0.1334836],
        [ 0.1386892,  0.0561774,  0.9887413]]
T_L2C= [0.0183368, -0.0535681, -0.1596446]      # metres
IMG  = 1920 x 1200
```

**Convention (the one handoff line):** poses are `T_lidar_in_map` (body→map). The
camera↔LiDAR extrinsic is applied **exactly once, downstream**, in
`compose_world_to_cam` (inside `fuse_pano.py`) — never in the matcher/exporter. Applying
it twice throws every photo ~28 m off; applying it zero times, ~85°.

---

## 3. CANONICAL TOOLS (md5-locked — verify before trusting)

| Stage | Script | md5 | Machine |
|---|---|---|---|
| Bringup (compressed cam) | `rig_start_compressed.sh` | `10b2bb6685fd5f446150dc3d88069000` | Jetson |
| ↳ camera node it starts | `rig_camera_compressed.py` | `446e6b5a7b8e61646bf947a6d2f96d89` | Jetson |
| Capture (hands-off pan) | `capture_walk.sh` | `46a4bd7e8fe1f44e97495a8424b10a20` | Jetson |
| ↳ capture engine it wraps | `capture_pointlio_texture.sh` | *(edited in place — see note)* | Jetson |
| Pan-confirm (read-only) | `check_pan_heading.py` | `20af111e90eff4abf1696aee62143a63` | Jetson |
| Anchor export (heading-spread) | `make_full_pan_anchor.py` | `f015c4a746cd2347b7d7ca11192ef1fe` | Jetson |
| Fusion render | `fuse_pano.py` | `d6246c2caecc39aab043ec43514846a6` | Station |
| Pose-math provenance | `pointlio_pose_matcher.py` v2 | `6827341d58e6d25384d07b47713c15bb` | (math source) |

**Note on `capture_pointlio_texture.sh`:** two in-place edits are load-bearing —
(1) the driver-count `sed` (`unitree_lidar_ros2|unilidar` → `unitree_lidar_ros2_node`),
(2) the `sudo nvpmodel -m 0` line removed (kept `jetson_clocks`) so no reboot prompt
mid-capture. It records `/aft_mapped_to_init` + `/camera/image_raw/compressed` +
`/unilidar/imu` and saves `scans.pcd` on clean SIGINT.

**`make_full_pan_anchor.py` and `fuse_pano.py` are the two tools born on 114136** — the
first fixes the old single-heading selection (it spreads by HEADING, not time); the second
is the self-contained, calibration-embedded render that passed the gate. Everything else is
proven from the prior compressed-capture work.

---

## 4. THE PROCESS — one command per step, paste back between each

Rig has NOT moved since 114136, so this reproduces the exact same pan. Assume the **L2 is
OFF** until the capture starts, and it turns OFF again when the run ends.

**STEP 1 — [Jetson] Bringup (rig ON, compressed camera).**
Run `rig_start_compressed.sh`.
*Expect:* LiDAR flowing; the compressed topic `/camera/image_raw/compressed` present;
"anchored capture clock" line. Nothing subscribing to raw `/image_raw`.

**STEP 2 — [Jetson] The pan (hands-off).**
Run `capture_walk.sh`. Do the **same wide slow pan on the stand** — ~85 s, sweep the full
room, keep translating a little (don't freeze on one spot). It records and, at the end,
saves geometry and stops itself.
*Expect:* a clean `geometry saved:` line and a bag dir `plio_texcap_<date>_<time>`.
*(The L2 turns off with the run.)*

**STEP 3 — [Jetson] Confirm the pan is in the odometry (read-only).**
Run `check_pan_heading.py <BAG_DIR>`.
*Expect / GATE:* `VERDICT: PAN PRESENT` with heading COVERAGE **> ~250°** and translation
of tens of cm. (114136: 309°, 60×87×4 cm.) If it says NO PAN, the rig didn't rotate —
redo Step 2. Don't proceed on a fixed heading.

**STEP 4 — [Jetson] Export the heading-spread anchor.**
Run `make_full_pan_anchor.py <BAG_DIR>`.
*Expect:* auto-detects `/camera/image_raw/compressed`; poseable **~95%**; ~35 frames;
heading COVERAGE **~300°**; writes `/tmp/panbundle.tar.gz` (~10 MB).

**STEP 5 — [Jetson→chat] Move + hand off.**
`cp /tmp/panbundle.tar.gz ~/Desktop/` and upload `panbundle.tar.gz`.

**STEP 6 — [Station] Fuse + render.**
`python3 fuse_pano.py --cloud scans_<date>_<time>.pcd --bundle panbundle --out pano_full.png`
*Expect:* `photo-coloured: ~78% of cloud`; a full-ring equirectangular PNG.

**STEP 7 — the visual gate (§7).**

---

## 5. REPRODUCTION TARGETS (match these; large misses = a knob moved)

| Signal | 114136 (reference) | Pass band |
|---|---|---|
| Capture length | 87.4 s | 60–120 s |
| Camera topic | `/camera/image_raw/compressed`, 2047 frames | compressed, >1500 frames |
| Odom density | 1.70 M msgs @ ~20 kHz, no hole | dense, no in-run hole |
| Heading sweep (Step 3) | 309° | > ~250° |
| Translation (Step 3) | 60 × 87 × 4 cm | tens of cm (real parallax) |
| Poseable (Step 4) | 95% (1941/2047) | ≥ 90% |
| Frames selected | 35 | 30–40 |
| Heading coverage (Step 4) | 306° | > ~280° |
| Cloud coloured (Step 6) | 77.7% | ≥ ~70% |

---

## 6. KNOWN-GOOD BLEMISHES (expected — NOT failures, do not chase during a repro run)

- **Teal / cyan seams** where two frames meet = per-shot auto-exposure differences (the
  render takes one best camera per point). Cosmetic. Fix is a later exposure/white-balance
  equalization or feathered multi-frame blend — a render pass, not a capture problem.
- **Grayscale caps, top and bottom** = the horizontal pan never tilted to the ceiling /
  floor-underfoot, plus the L2's blind cones straight up/down. To fill them, add a few
  tilted-up / tilted-down frames to the sweep. Expected on a level pan.

---

## 7. THE VISUAL ACCEPTANCE TEST (the only gate that counts)

The run PASSES when the final 360:
1. reads as the **actual room, all the way around**, in real colour across the horizontal
   band (windows, arch, doorways, framed art, mantel all recognizable);
2. has photo colour **landing on the geometry** — edges of pictures/doors sit on the
   LiDAR structure, no smear, no doubled walls, no colour floating off surfaces;
3. hits the §5 colour/heading numbers (≥ ~70% coloured, ≥ ~280° heading).

Grayscale caps and teal seams (§6) do NOT fail the gate. Colour landing on the WRONG
surface, smeared walls, or a collapsed heading DO.

---

## 8. WHY EARLIER ATTEMPTS FAILED (so they are never repeated)

- **Raw `/image_raw` recording** choked the recorder → 127 s odom hole → most frames
  un-poseable. FIX: record compressed (Step 1). *[proven dead on 114136: dense odom, no hole]*
- **Time-spread frame selection** (`make_extrinsic_bundle.py`) picked 30 frames that, on a
  single-heading recording, all faced one way → coloured only a wedge. FIX:
  `make_full_pan_anchor.py` spreads by HEADING → full ring.
- **Cross-capture mismatch** — colouring a cloud from one bag with frames/poses from a
  different bag. FIX: cloud, frames, and poses ALL come from the same bag (Steps 2/4/6).
- **Baking on the Jetson** hard-locked it. FIX: fusion runs on the station only (§1).

---

## 9. WHAT THIS RUN CERTIFIED (new, banked)

- **The extrinsic is real-world CORRECT.** Photo colour landed on geometry across 306° of
  the room, not just a checkerboard wedge — the strongest real-world test to date. A wrong
  extrinsic would have smeared colour off the surfaces everywhere. This closes the long-open
  "extrinsic code-verified, real-world UNCERTIFIED" item, at panorama scale.
- **The compressed-capture + moving-odom fix works end to end on hardware.** Dense odom,
  95% poseable, a real 309° pan with parallax — the exact capture the Master was blocked on.

**NEXT after reproduction:** with the same clean bag, take the geometry branch forward —
`planar_shell` shell + occlusion-gated texture bake on the STATION → Unreal walkable /
relightable — and, if wanted, the exposure-equalization pass to clean the 360's seams.
