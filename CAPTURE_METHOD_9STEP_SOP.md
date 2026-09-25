# CAPTURE METHOD — THE 9-STEP SOP (governing frame for EVERY capture)
### Ratified 2026-09-24. Source of truth: github.com/BaxterBstupid/rig-files/CAPTURE_METHOD(2).md.
### The STEPS are invariant. The script filling a slot can change; the sequence and its GATES cannot.

> WHY THIS EXISTS: on 2026-09-24 a capture (141733) drifted into a fanned, tripled-wall map.
> Root cause was NOT a mystery bug — we ran OFF this method: skipped Start Rig in the
> instructions, and used a capture fork (`capture_walk`→`capture_pointlio_texture`) that
> DROPPED STEP 4's dead-still IMU-init gate and did a continuous "WALK NOW" pan. Every
> capture is now held to these 9 steps, in order, so that cannot recur.

---

## THE 9 STEPS (do them in order, honor every gate)

**STEP 0 — PRECONDITIONS.** Rig assembled, L2 powered, camera connected. **START RIG already
running** and publishing `/unilidar/cloud`, `/unilidar/imu`, and the camera image topic.
Disk space OK, sensor not overheated, room light adequate. **Coverage plan chosen** (single
vantage vs multi-view; and see the MOTION rule below).

**STEP 1 — LAUNCH THE CAPTURE** (one action).

**STEP 2 — PRE-FLIGHT GATE.** Verify `/unilidar/cloud` is publishing (sensor OK). If it
fails, Start Rig is not up — fix and retry. NON-NEGOTIABLE.

**STEP 3 — CLEAN SLATE.** Clear orphaned `rviz2` / `pointlio_mapping`. Expect one clean run.

**STEP 4 — LAUNCH + DEAD-STILL IMU INIT.** Hold the rig DEAD STILL and WAIT for
**`IMU Initializing: 100.0%`** — the gravity-alignment green light — BEFORE ANY MOTION.
This is the gate whose absence caused the 141733 drift. NON-NEGOTIABLE. Gravity sits on
body-X on this rig, so a real static window is required for Point-LIO to find "down."

**STEP 5 — CAPTURE.** Move per the coverage plan. MOTION RULE (2026-09-24): no continuous
sweep from a moving start — **stop-and-go** (rotate ~20°, STOP ~2s, repeat) so each frame
lands on a settled heading.

**STEP 6 — ONE CTRL-C, THEN HANDS OFF.** Extra signals are ignored by design.

**STEP 7 — THE FOUR STOPS (must appear in order):** (1) stop bag / flush to disk →
(2) SIGINT Point-LIO, WAIT for PCD save (never SIGKILL) → (3) verify PCD saved FRESH →
(4) SUCCESS (prints bag path, PCD path, size). The shutdown order is load-bearing.

**STEP 8 — THE ARTIFACTS.** Timestamped `bag/` + `scans_<stamp>.pcd` on `~/Desktop`.

**STEP 9 — VERIFY.** `ls -lh` the bag dir + PCD; multi-MB, no 0-byte files. Any 0-byte = failed run.

---

## SLOT → SCRIPT MAPPING (slots can change; steps cannot)

| Step | Canonical (raw) | Compressed pipeline (current) |
|---|---|---|
| 0 Start Rig | `START RIG` (raw `/image_raw`) | **`rig_start_compressed.sh`** (`/camera/image_raw/compressed`) |
| 1 Launch | click `PointLIOCapture.desktop` | `capture_walk*.sh` wrapper / `capture_pointlio_texture.sh` |
| 2 Pre-flight | sensor OK gate | gate on `/unilidar/cloud` + `/unilidar/imu` + image topic |
| 3 Clean slate | clears rviz/pointlio | same |
| 4 IMU init | waits **`IMU Initializing: 100.0%`** | **MUST wait for the same line** (the fork dropped this — restore it) |
| 5 Capture | move per plan | stop-and-go pan, from a settled init |
| 6 Stop | one Ctrl-C | wrapper auto-SIGINTs after duration |
| 7 Four stops | bag→PLIO→verify→success | same trap in `capture_pointlio_texture.sh` |
| 8 Artifacts | `fusioncap_*` + `_scans.pcd` | `plio_texcap_*` + `scans_*.pcd` |
| 9 Verify | `ls -lh` | same + drift gate (below) |

**The one open reconciliation:** the compressed capture must WAIT for `IMU Initializing:
100.0%` at STEP 4 (canonical does; our fork gates only on odometry publishing). Fix pending:
patch the compressed capture to watch Point-LIO's log for that line before signalling GO.
Do NOT regress to raw `/image_raw` (ADR-002 choke) to get the gate.

## GATES THAT STOP A CAPTURE (never skip)
- STEP 2: sensor publishing, or stop.
- STEP 4: `IMU Initializing: 100.0%` reached DEAD STILL, or do not move.
- STEP 7: all four stops in order, PCD verified FRESH, or the run is not trusted.
- STEP 9 + drift gate (post): wall-normal azimuth histogram — top-4 bins >55% of wall points
  = clean rectilinear room; ~15% = drift, reject the bag.

## VERSION DISCIPLINE
"Right name + wrong contents is a trap." Verify the script in each slot by md5/byte-count
before trusting a run. Recovery: re-fetch from the rig-files repo.
