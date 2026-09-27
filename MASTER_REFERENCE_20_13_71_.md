<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.71, 2026-09-27) *****        -->
<!-- Additive layer on the COMPLETE 20.13.70 (Stone Clause: nothing lost).           -->
<!--   20.13.70 holds: the OPERATIONAL TRIAD, the RE-SOLVE-FIRST workflow, the        -->
<!--   two-tau distinction, the 15 s dead-still init, the CORRECTED L2 physics        -->
<!--   (360 azimuth x 90 elevation), the Jetson-FREEZE -> kiosk-on-Shadow fix (II-I), -->
<!--   and PART I (folded 69 content: 114136 visual gate, golden recipe+tools).       -->
<!--   20.13.68 holds both ADRs + the STAGE 1-7 RealityScan->UE recipe verbatim.      -->
<!-- THIS 20.13.71 LAYER banks the 2026-09-27 pipeline-hygiene + tau-unblock session. -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ CAPTURE TO PROVE TAU UNBLOCKED  ⭐   (the single next action)
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**THE ONE NEXT CAPTURE:** a clean Golden-method capture on the CURRENT compressed
pipeline that MOVES — dead-still **15 s init → tip DOWN → tip UP → slow WALK**. That
single bag proves tau end to end AND serves the image, because:
- angular motion (the tips) + linear motion (the walk) both drive `tau_solve_v2` → tau solvable;
- it records the full re-solvable set (`point_lio_capture.sh`: cloud + odom + imu + compressed) → geometry + the kiss-icp cross-check survive;
- the tips paint ceiling/floor and the walk gives parallax → the picture fills.

**WHY A NEW CAPTURE IS REQUIRED (measured 2026-09-27, not assumed).** tau is a
per-PIPELINE constant (III-E), and we changed the pipeline (raw gscam → compressed
anchored-clock), so the old raw-era tau (~180 ms in the II-C lineage) does NOT carry
over — it must be re-solved on a CURRENT compressed + MOVING bag. The entire
`/mnt/rigdata` archive was inventoried: **only two compressed bags exist, both unusable** —
- `fusioncap_180728` — valid but **STATIC** (0.02 m / 1°; the 15 s-init test hold).
- `fusioncap_080826` — **CORRUPT**: Point-LIO died live in the freeze; only **10 odom
  poses over 0.0 s** (a real capture has tens of thousands) + empty `storage_identifier`.
Every MOVING bag is old-raw-era (`/image_raw`) → wrong-pipeline tau. There is no
compressed+moving bag to solve from. The capture is a bounded, well-prepared ask.

**PREREQS (all met, or a one-line check) so that capture actually yields tau:**
- **Freeze removed** — compressed camera (no SD choke) + kiosk render OFF the Jetson
  (II-I) → a clean MOVING capture is finally possible where the last dozen froze.
- **`tau_solve_v2.py` delivered** (III-D) — reads compressed + raw, auto-detects the
  topic, combines angular+linear. Keep it beside `quatmath.py` or it ImportErrors (audit M3).
- **POST-CAPTURE GUARD (III-C):** right after Ctrl-C, confirm the bag's `metadata.yaml`
  has a NON-EMPTY `storage_identifier` — catches a killed/malformed bag at capture time,
  not weeks later.

**CARRIED CURRENT-STATE (still true — see 20.13.70):** THE RIG IS OFF until a clear
command powers the L2. Vault discipline (Rig Check GREEN = deployed == `~/rig_originals`
by md5). Rig Check RED on `point_lio_capture.sh` (compressed edit unblessed — bless it
into the vault AFTER this capture proves out).


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART III — 2026-09-27 SESSION (pipeline hygiene + tau unblock)             ║
║  (benched all day; rig stayed OFF. Additive on 20.13.70.)                   ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## III-A. ON-BOARD MONITOR / KIOSK FAILURE — ROOT-CAUSED + FIXED  (was UNRESOLVED)
═══════════════════════════════════════════════════════════════════════════
The recurring "RIG KIOSK button does nothing" wall was root-caused to a stale-path
collision, NOT a code bug:
- `rig_button.py` is a Tkinter desktop button (the yellow "RIG KIOSK" tile). It
  `subprocess.Popen`s `~/rig_kiosk_launch.sh` and never reaps it → the 5 `<defunct>`
  zombies under it in `ps` were 5 dead button-presses.
- `rig_kiosk_launch.sh` hard-codes `~/Desktop/rig_kiosk_server.py`, but the **daily
  Desktop sweep** files the 6 kiosk files into dated folders (`ALL FILES …/`,
  `Sept 26th/`, …). Server missing → `~/Desktop/kiosk.log`:
  `can't open …/Desktop/rig_kiosk_server.py`. Server never starts → the launcher's
  Firefox opens a dead `:8080` → nothing survives. Every press hit the same missing file.
- The 6 files needed beside the server — `rig_kiosk_server.py`, `rig_kiosk.html`,
  `cloud.html`, `launch.html`, `three.min.js`, `map_accumulator.py` — all confirmed
  byte-identical to the vault (server md5 `6a901f2c58fc3267d72eb90bb9419096`). Restored
  with `restore_kiosk.sh ~/rig_originals`; **smoke-tested headless** → server serves
  `/data`, `/kiosk`, `/cloud` all `200` (no Firefox, no Jetson render).
- **PERMANENT GUARD (deployed + re-blessed):** `rig_kiosk_launch.sh` now **SELF-HEALS** —
  it runs `restore_kiosk.sh ~/rig_originals` before starting the server, so a Desktop
  sweep can never break the kiosk again (the launcher lives in `~`, not the Desktop, so
  it is itself sweep-safe). `restore_kiosk.sh`'s stale default source was fixed from
  "ALL FILES Sept 7" → `~/rig_originals`. Both edits re-blessed into the vault + manifest
  (launcher md5 `448876ba6e60e57d368ba60aab34e5b4`, restore md5
  `2980382ae8854046cf63f910c697fe8f`).
- **VAULT nick (open, minor):** the manifest lists `RigPreflight.desktop` but the file
  is missing from `~/rig_originals` (`md5sum -c` FAILED). Restore it or drop the line.

This RESOLVES the on-board-monitor thread. It is DISTINCT from II-I's freeze fix and both
stand: **II-I** moves the 3D RENDER to Shadow to stop GPU/EMC saturation; **III-A** makes
the LAUNCHER actually start the server. Server-on-Jetson + render-on-Shadow is the target.

═══════════════════════════════════════════════════════════════════════════
## III-B. PIPELINE INTEGRATION AUDIT — banked
═══════════════════════════════════════════════════════════════════════════
Full-run static audit (system-design + code-review + debug lenses) banked as
**`claude/PIPELINE_INTEGRATION_AUDIT_2026-09-27.md`**. Verdict: the run fits together on
the MATH (coordinate convention + projection + occlusion gating are consistent across
`make_full_pan_anchor` / `fuse_pano` / `fuse_to_fbx`) but NOT on the CONTRACTS. Top findings:
- **C1 (CRITICAL):** `tau_solve.py` read raw `Image` only (reshape on `m.height/m.width`)
  → CRASHES on the compressed topic every capture now records. The dropout blocker became
  a DECODE blocker. → fixed as `tau_solve_v2` (III-D).
- **H1:** three divergent frame-bundle formats (pano `img_%03d.jpg` vs FBX `img_%05d.png`)
  → one path's bundle will not feed another.
- **H2:** `capture_pointlio_texture.sh` (wrapped by `capture_walk.sh`) DROPS
  `/unilidar/cloud` → its bags are NOT re-solvable. Use `point_lio_capture.sh` (full set).
- **H3:** tau_solve's odom signal used ANGULAR speed only (ignored the linear it computed)
  → weak tau on a translation walk. → fixed in v2.
- **M1:** dual calibration source (`fuse_pano` EMBEDS K/extrinsic; `fuse_to_fbx` LOADS the
  yaml) → a re-cal silently staleness `fuse_pano`.
- **Drift vs `SYSTEM_DESIGN_pipeline_v2`:** the single shared B1 bundle contract and the
  BA pose-refinement hinge (v2's stated "linchpin") are NOT built; the fusers run on raw
  odom-interpolated poses. The seams are the implementation lagging a good design.

═══════════════════════════════════════════════════════════════════════════
## III-C. STORAGE-ID / rosbags SEAM — the killed-capture wound
═══════════════════════════════════════════════════════════════════════════
`rosbags` (the Python lib EVERY offline tool uses — `tau_solve`, `make_full_pan_anchor`,
`check_pan_heading`) failed to open `fusioncap_080826`: `Storage plugin '' not supported`.
Cause: the bag's `metadata.yaml` has `storage_identifier: ""` (EMPTY) even though the data
is plain sqlite3 (`fusioncap_080826_0.db3`). `ros2 bag info` (tolerant C++) reads it
anyway; `rosbags` (strict Python) bounces. The empty id AND the 10-pose truncation are the
SAME wound — a capture killed mid-record by the freeze that never finalized (`ros2 bag
reindex` rebuilt enough for `ros2 bag info` but left the storage id blank).
- **FIX (per bag):** set `storage_identifier: "sqlite3"` in `metadata.yaml` (data is .db3),
  backing it up first. Then `rosbags` opens it. (Done on 080826 → it opened, and confirmed
  the 10-pose corruption.)
- **GUARD (adopt):** a post-capture check that `storage_identifier` is non-empty. This is
  why the III-A/II-I freeze fix matters for DATA integrity, not just uptime — clean
  finalization = well-formed bags.

═══════════════════════════════════════════════════════════════════════════
## III-D. tau_solve_v2.py — the compressed-capable solver (delivered)
═══════════════════════════════════════════════════════════════════════════
Patched solver delivered under a DISTINCT name (so it cannot overwrite the blessed
`tau_solve.py`):
- **(C1)** reads BOTH `sensor_msgs/Image` and `sensor_msgs/CompressedImage` (`cv2.imdecode`);
  AUTO-DETECTS the image topic (prefers `/camera/image_raw/compressed`).
- **(H3)** the odom motion signal now COMBINES angular + linear speed (each standardized)
  → a translation walk drives the correlation, not only a pan.
- Gates unchanged (peak width < 100 ms AND half-split < 30 ms). **Dep:** `quatmath.py` must
  sit beside it (audit M3) or it ImportErrors — verify before the first run.
- **USE:** `python3 tau_solve_v2.py <compressed_moving_bag>` → the pipeline-current tau
  constant. Sandbox-validate anytime on a raw MOVING bag (e.g. `fusioncap_163005`) — that
  proves the tool end to end even though its number is the old-pipeline tau.

═══════════════════════════════════════════════════════════════════════════
## III-E. TAU IS A PER-PIPELINE CONSTANT (why the old ~180 ms doesn't carry)
═══════════════════════════════════════════════════════════════════════════
tau (τ_cam↔lidar) = the camera-timestamping latency — a property of the CAPTURE PIPELINE,
not the room. The old raw `gscam` path stamped frames with jittery arrival-time latency
(hence the II-C "~180 ms, not tightly localized"). The compressed bringup's
`rig_camera_compressed.py` adds an **"anchored capture clock"** step that stamps against a
stable clock → tau becomes a STABLE constant, but a DIFFERENT value than the old jittery
one. So tau must be (re)solved ONCE on a CURRENT compressed+moving bag; then it locks like
the extrinsic and is reused on every capture. (This is inferred from the anchored-clock
design intent — CONFIRMED by running `tau_solve_v2` on such a bag, which is exactly the
header capture.)

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-09-27:** Pipeline-hygiene + tau-unblock day (benched; rig OFF throughout).
  ROOT-CAUSED + FIXED the on-board-monitor/kiosk failure — the daily Desktop sweep vs the
  launcher's hard-coded path; deployed a self-healing launcher + re-blessed the vault
  (III-A), resolving the long-open monitor thread. Banked the full-run PIPELINE
  INTEGRATION AUDIT (III-B). Delivered `tau_solve_v2` (compressed decode + linear-speed;
  audit C1/H3; III-D). Found + fixed the empty-`storage_identifier` / rosbags seam that
  blocks the whole offline chain on killed bags (III-C). Inventoried `/mnt/rigdata`: NO
  compressed+moving bag exists (180728 static, 080826 corrupt) → tau needs ONE fresh clean
  MOVING capture on the current pipeline (III-E). NEXT: **CAPTURE TO PROVE TAU UNBLOCKED**
  — the Golden-method compressed moving capture (the header), then `tau_solve_v2` on it.

<!-- ============================================================================ -->
<!-- ##  END 20.13.71 LAYER. Additive on 20.13.70 (complete active layer: triad,   ## -->
<!-- ##  re-solve-first, two-tau, 15s init, L2 physics, freeze->kiosk-on-Shadow,    ## -->
<!-- ##  PART I 69-content). Deep lineage (both ADRs + STAGE 1-7 UE recipe) in      ## -->
<!-- ##  MASTER_REFERENCE_20_13_68_.md. Stone Clause: additive, nothing lost.       ## -->
<!-- ============================================================================ -->
