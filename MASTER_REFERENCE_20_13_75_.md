<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.75, 2026-09-30 PM) *****         -->
<!-- Additive layer on 20.13.74 (Stone Clause: nothing lost).                            -->
<!--   20.13.74 holds: profile-load baked into rig_camera_compressed.py (comes up locked  -->
<!--     on every path; blessed 894328fd); CAMERA PAD launcher self-starts the node;       -->
<!--     shutter angle-vs-speed; hardware external-trigger finding (open research thread).  -->
<!--   20.13.73 holds: TRIAD LINKED, 50' USB fails, Control Pad, exposure = the blur.      -->
<!--   20.13.72: Mode-2 fix /dev/arducam. 20.13.71: tau_solve_v2. 20.13.70: triad.         -->
<!--   20.13.68: both ADRs + STAGE 1-7 RealityScan->UE recipe verbatim.                     -->
<!-- THIS 20.13.75 LAYER banks the 2026-09-30 PM work: SHADOW stood up as the offline       -->
<!--   STATION (Windows/Anaconda), the toolset certified against a real bag, two fixes      -->
<!--   (Windows-portable anchor + tau_solve crash guard), and THE TAU TIME-BASE FLAG.       -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  🖥️ SHADOW IS THE STATION — offline chain stood up + certified on real data
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**ARCHITECTURE RATIFIED (operator, 2026-09-30):** the Jetson was only ever meant to be a
**capture appliance.** Everything after capture — tau, fusion, mesh, Masters, archive —
lives on **Shadow**, and all files (fusioncaps, Masters, screenshots) migrate off the
Jetson to Shadow. This matches the machine-division the GOLDEN_360 recipe already demands
("never bake or fuse on the Jetson"). This session stood up and **certified** the Shadow
side of that split.

**Shadow = Windows + Anaconda.** The offline tools read ROS2 bags through the pure-Python
`rosbags` lib (NO ROS install needed on Windows). Env `rigstation` built and working:
`numpy 2.4.6`, `opencv-python 5.0.0.93`, `rosbags 0.11.5` (+ apsw/lz4/zstandard/ruamel).
Kit delivered as `shadow_station_kit.zip` (md5 `7c526062…`), extracted to `C:\rig\station\`.

**CERTIFICATION STATUS (against `fusioncap_180728`, the static compressed test bag):**
- `make_full_pan_anchor.py` — **proven end to end on Windows**: auto-detected the compressed
  topic, read 719 images + 27,152 odom msgs, 99% poseable, decoded a compressed JPEG, wrote
  the bundle to `%TEMP%`. (1 frame / 0° coverage = the correct answer for a static bag.)
- `tau_solve_v2.py` — **read path proven**; now fails honestly on degenerate input.
- `fuse_pano.py` — import-verified only; needs a real `scans.pcd` → certifies on the first
  live capture that produces a cloud.


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART VII — 2026-09-30 PM (Shadow station: stand-up, fixes, tau time-base)   ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## VII-A. SHADOW STATION — setup that works (Windows / Anaconda)
═══════════════════════════════════════════════════════════════════════════
- One-time: `conda env create -f environment.yml` → `conda activate rigstation`. Env spec
  ships in the kit; deps are pip `numpy`, `opencv-python`, `rosbags` (open3d deliberately
  LEFT OUT of the base env — it's only for the later mesh/UE branch, and a numpy/open3d
  version tussle must not jeopardize tau + 360).
- Folder layout on Shadow: `C:\rig\station\` (tools — keep every .py together; `quatmath.py`
  MUST sit beside `tau_solve_v2.py`), `C:\rig\fusioncaps\`, `C:\rig\out\`, `C:\rig\masters\`,
  `C:\rig\screenshots\`.
- Transfer Jetson→Shadow over the **tailnet**: `tar` the bag dir on the Jetson, then
  `tailscale file cp` (Taildrop) it across; for the 360 only the ~10 MB `panbundle.tar.gz`
  + `scans.pcd` are needed. Bag gotcha (III-C seam): if a tool errors `Storage plugin ''
  not supported`, set `storage_identifier: sqlite3` in the bag's `metadata.yaml`.

═══════════════════════════════════════════════════════════════════════════
## VII-B. TWO FIXES (Windows-portability + robustness)
═══════════════════════════════════════════════════════════════════════════
- **`make_full_pan_anchor.py` → Windows-portable** (md5 `5c059210…`). Was hardcoded to
  `/tmp/panbundle.tar.gz` (dead on Windows). Now uses `tempfile.gettempdir()` (→ `%TEMP%`
  on Shadow, still `/tmp` on the Jetson — identical behaviour, ONE canonical tool, not two),
  with env `PANBUNDLE_OUT` to override; prints the exact output path.
- **`tau_solve_v2.py` → crash guard** (md5 `012117b1…`, was `8af33996…`). On the static bag
  it tracebacked (`ValueError: a cannot be empty`) — `solve()` built an empty resample grid
  and `np.convolve` on an empty array threw. The *original* `tau_solve.py` had an
  insufficient-data guard; v2 had dropped it. Restored: `solve()` returns `None` when the
  shared timeline is < ~1 s, and `main()` prints a clean `CANNOT SOLVE` with the cause and
  exits 2 instead of crashing. Verified: degenerate input → clean; a synthetic +120 ms lag
  still solves to +118 ms (normal path intact).
- Both files updated in the kit; the offline toolset still is NOT in the `rig-files` repo.

═══════════════════════════════════════════════════════════════════════════
## VII-C. ⭐ THE TAU TIME-BASE FLAG — resolve on the first moving bag ⭐
═══════════════════════════════════════════════════════════════════════════
On `fusioncap_180728`, `tau_solve_v2` reported `odom speed samples 51` and could not build a
resample grid. Root cause: the odom `/aft_mapped_to_init` **header stamps span only ~1 s**
(the decimator computes `step` from messages ÷ time-span; a ~1 s span over 27k messages
collapses it to ~50 samples). The camera header stamps (anchored capture clock) span the
real 31.6 s, so the two timelines overlapped by less than the 2×max_lag (1.2 s) margin.

The deeper issue this exposes — **a time-base mismatch between the two offline tools:**
- `tau_solve_v2` keys BOTH signals off ROS `header.stamp`.
- `make_full_pan_anchor` keys off **bag-record time** (`bt`) and applies tau as a bag-time
  offset (`PAN_TAU_S`, default 0.180 s).

So the tau `tau_solve_v2` *measures* (a header-stamp offset) may not be the tau
`make_full_pan_anchor` *consumes* (a bag-time offset). **MUST be reconciled before trusting
tau on a real capture.** Do NOT fix blind — resolve with a real MOVING bag in hand, where
the actual header vs bag stamps and the actual numbers are visible. Likely resolution: point
`tau_solve_v2`'s odom (and possibly camera) signal at bag-record time to match the anchor,
OR confirm `/aft_mapped_to_init` header stamps carry real time on a good capture. **This is
the first thing to check the moment the TAU-360 moving bag lands.**

═══════════════════════════════════════════════════════════════════════════
## VII-D. INTEGRITY / SSOT NICKS (carried)
═══════════════════════════════════════════════════════════════════════════
- **Offline tools are not in `rig-files`.** The repo clone carries only `quatmath.py` and
  `pointlio_pose_matcher.py`; `tau_solve_v2`, `fuse_pano`, `make_full_pan_anchor`,
  `check_pan_heading` are not committed. For "the repo is the single source of truth," push
  the kit so Shadow can pull rather than rely on a chat hand-off.
- **`pointlio_pose_matcher.py` md5 mismatch:** repo `f9519ac9…` vs the recipe-locked
  `6827341d…` (the version staged in the kit). The fusers embed their own math and don't
  import it, so it doesn't affect tau or the 360 — but reconcile which is canonical.

═══════════════════════════════════════════════════════════════════════════
## NEXT (carried)
═══════════════════════════════════════════════════════════════════════════
1. **TAU-360 capture** — the moving bag does TRIPLE duty now: exercises `tau_solve_v2`'s
   actual solving, **resolves the VII-C time-base question with real data**, and produces the
   `scans.pcd` that certifies `fuse_pano`. Golden walk (15 s init → tip DOWN → tip UP →
   controlled 360 pan), locked short shutter (VI, 20.13.74), then process on Shadow.
2. **Push the offline toolset to `rig-files`** so Shadow pulls from the SSOT (VII-D).
3. **Migrate the archive to Shadow** — fusioncaps, Masters, screenshots off the Jetson.
4. **WAVESHARE integration** — kiosk camera tile + capture-button lockout (Front 2).
5. **External hardware trigger** — research thread (20.13.74 VI-D): confirm the B0578 exposes
   TRIGGER/FLASH and how to enable trigger mode on Jetson/Linux (email Arducam).

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-09-30 PM:** Stood up SHADOW as the offline station (Windows/Anaconda; env
  `rigstation`; kit `7c526062…`) and certified the toolset against `fusioncap_180728`:
  `make_full_pan_anchor` proven end to end on Windows (VII-A/C), made Windows-portable
  (`5c059210…`, VII-B); `tau_solve_v2` crash-guarded (`012117b1…`, VII-B). ROOT-CAUSED the
  solve failure: odom header stamps span ~1 s on that bag, exposing a header-vs-bag TIME-BASE
  mismatch between the two tools — flagged to resolve on the first moving bag (VII-C).
  Architecture ratified: Jetson = capture only, Shadow = everything else. NEXT: the TAU-360
  capture (now triple-duty).

<!-- ============================================================================ -->
<!-- ##  END 20.13.75 LAYER. Additive on 20.13.74 (profile-load, pad self-start).     ## -->
<!-- ##  20.13.73: triad/USB/pad/exposure. 20.13.72: Mode-2 /dev/arducam. 20.13.71:   ## -->
<!-- ##  tau_solve_v2. Deep lineage (ADRs + STAGE 1-7 UE) in 20.13.68. Nothing lost.  ## -->
<!-- ============================================================================ -->
