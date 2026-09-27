# PIPELINE INTEGRATION AUDIT — 2026-09-27
### Full-run fit check: capture → re-solve → tau → bundle → fuse → mesh/UE
**Lenses:** system-design (stage contracts) · code-review (defects) · debug (root-cause the blocker)
**Method:** static review of the *actual* deployed/vault scripts + drift check vs `SYSTEM_DESIGN_pipeline_v2.md`. No fresh capture; existing scripts + session data only.
**Scripts read in full:** `fuse_pano.py`, `make_full_pan_anchor.py`, `tau_solve.py`, `fuse_to_fbx.py`, `mesh_check.py`, `check_pan_heading.py`, `point_lio_capture.sh`, `capture_pointlio_texture.sh`, `capture_walk.sh`, `rig_kiosk_server.py`, `rig_kiosk_launch.sh`, `restore_kiosk.sh`.

---

## 0. VERDICT

The pipeline **fits together on the math** — coordinate convention, projection, and occlusion gating are consistent across every fusion tool. That's the hard part, and it's right.

It does **not** fit together on the **contracts**. Three real seams:

1. **CRITICAL — the tau blocker is now a *decode* bug, not a dropout bug.** `tau_solve.py` can only read a **raw** `/image_raw` stream, but every capture path now records **compressed** `/camera/image_raw/compressed`. So a clean compressed bag *cannot* solve tau as-is. **This revises "the compressed capture unblocks tau" — it doesn't, until `tau_solve` is patched.**
2. **HIGH — three divergent frame-bundle formats.** The pano baker, the FBX baker, and the texture-capture's matcher each expect different frame filenames. Feeding one path's bundle to another fails.
3. **HIGH — the auto-timer walk path is not re-solvable.** `capture_pointlio_texture.sh` (wrapped by `capture_walk.sh`) drops `/unilidar/cloud`, so kiss-icp can't re-solve those bags.

And the implementation has **drifted from your own v2 design**: the single shared "B1" bundle contract and the bundle-adjustment pose-refinement hinge (v2's stated linchpin) are **not built** — the fusers run on raw odom-interpolated poses.

Geometry path: sound. Colour/tau path: has a real break that changes the capture plan.

---

## 1. SYSTEM-DESIGN VIEW — the run as it actually is

```
 JETSON (capture)                          SHADOW / SANDBOX (offline)
 ────────────────                          ──────────────────────────
 rig_start_compressed.sh   ── compressed camera (/camera/image_raw/compressed)
   or rig_start_lean.sh    ── RAW /image_raw  ← 40 GiB/3.6min CHOKE (avoid)
        │
        ▼
 CAPTURE (two divergent scripts):
   point_lio_capture.sh          capture_walk.sh → capture_pointlio_texture.sh
   records: odom, compressed,      records: odom, compressed, imu
            imu, cloud, cloud_reg           (NO cloud, NO cloud_registered)
   → fusioncap_<t> bag + scans.pcd  → plio_texcap_<t> bag + scans.pcd
   ✅ RE-SOLVABLE                   ❌ NOT re-solvable
        │                                   │
        ▼                                   ▼
   ┌───────────────── bag + scans.pcd ─────────────────┐
   │                                                    │
   ▼                     ▼                    ▼          ▼
 kiss-icp            tau_solve.py       make_full_pan   pointlio_pose_
 (geometry           (needs RAW img!)   _anchor.py      matcher.py
  re-solve)          ✗ compressed       → panbundle     (texcap NEXT)
                                         img_%03d.jpg     img_?????
                                            │
                    ┌───────────────────────┼────────────────────┐
                    ▼                        ▼                    ▼
              fuse_pano.py            fuse_to_fbx.py         mesh_check.py
              embedded calib          yaml calib             coverage mesh
              img_%03d.jpg  ✅        img_%05d.png ✗ mismatch  (kiosk MESH)
              → equirect PNG          → OBJ/FBX (UE)
```

### Stage contracts (emits → consumes), and where they break

| Stage | Emits | Next stage consumes | Fit? |
|---|---|---|---|
| `point_lio_capture.sh` | bag: odom + **compressed** + imu + **cloud** + cloud_registered; `scans.pcd` | kiss-icp needs `cloud` ✅; tau needs img; bundle needs odom+img | cloud ✅, **tau ✗ (compressed)** |
| `capture_pointlio_texture.sh` | bag: odom + compressed + imu (**no cloud**) | kiss-icp needs `cloud` | **✗ not re-solvable** |
| `tau_solve.py` | tau (ms) | applied when building poses | **✗ can't read compressed input** |
| `make_full_pan_anchor.py` | `poses.npz`(pos,R,quat,ok) + `img_%03d.jpg` | `fuse_pano.py` (img_%03d.jpg) ✅ / `fuse_to_fbx.py` (img_%05d.png) ✗ | pano ✅, **FBX ✗** |
| `fuse_pano.py` | equirect PNG | eyeball gate | ✅ (embedded calib is a latent risk) |
| `fuse_to_fbx.py` | OBJ/MTL/atlas → UE | UE import | ✅ if fed its own bundle format |

---

## 2. FINDINGS BY SEVERITY

| # | Sev | File | Issue | Impact | Fix |
|---|---|---|---|---|---|
| C1 | 🔴 CRIT | `tau_solve.py` | Reads raw `Image` only: default `--image-topic /image_raw`, decodes via `frombuffer→reshape(m.height,m.width)`. `CompressedImage` has no `.height/.width` and holds JPEG bytes → crash/garbage. | Compressed bags (all current capture paths) **cannot solve tau**. Tau stays blocked — by decode, not dropouts. | Add a `CompressedImage` branch: `cv2.imdecode(...)` (copy `make_full_pan_anchor.decode_selected`), grayscale, keep the block-diff math. Pass `--image-topic /camera/image_raw/compressed`. |
| H1 | 🟠 HIGH | `make_full_pan_anchor.py` vs `fuse_to_fbx.py` | Frame filename mismatch: pano writes `img_%03d.jpg`; FBX globs `*.png` and reads `img_%05d.png`. | Panbundle → FBX baker = "no usable frames" exit. Two incompatible bundles. | One bundle schema (v2 B1: `img_%05d.png` undistorted + `posed_images.npz`); adapter for the pano viewer. |
| H2 | 🟠 HIGH | `capture_pointlio_texture.sh` | Records only `odom, img, imu` — **no `/unilidar/cloud`, no `/cloud_registered`**. | Bags from the `capture_walk` auto-timer path are **not re-solvable** on Shadow; breaks re-solve-first discipline. | Add `/unilidar/cloud` (+`/cloud_registered`) to its record list — or just use `point_lio_capture.sh` for the walk (already complete). |
| H3 | 🟠 HIGH | `tau_solve.py` | Odom motion signal uses **angular speed only** (`sp_v.append(ang/dt)`); computes `lin` but never uses it. Comment claims "angular+linear." | On a **translation-dominant walk** (the prescribed motion) the camera signal responds to translation the odom signal ignores → weak/failed tau on exactly the right captures. | Fold linear in: e.g. `sp_v = ang/dt + k*lin/dt`, or z-score each and sum. |
| M1 | 🟡 MED | `fuse_pano.py` | **Embeds** K/R_L2C/T_L2C; `fuse_to_fbx.py` **loads** them from yaml. | A re-calibration updates the yaml and silently leaves `fuse_pano` stale → colour shift nobody notices. | `fuse_pano` loads the same yaml (single source of truth), or regenerates the embedded block with a checked hash. |
| M2 | 🟡 MED | `~/point_lio_capture.sh` | Deployed script (records compressed) ≠ vault copy (manifest md5 `b34ca62…`). The script that **runs** is unblessed. | Vault no longer reflects reality; a Rig Check would flag it, or a restore would revert your compressed capture. | Reconcile: the deployed compressed version is the one you want → bless it into the vault (file + manifest md5). |
| M3 | 🟡 MED | `tau_solve.py` | `from quatmath import matrix_from_quat` — local module dependency. | If `quatmath.py` isn't beside `tau_solve` on the run machine → `ModuleNotFoundError` (same class as the kiosk `map_accumulator` break). | Confirm `quatmath.py` ships with `tau_solve`; add to vault + manifest. |
| M4 | 🟡 MED | `fuse_to_fbx.py` | Docstring: "You solved tau to 2.8 ms." Master §2: tau **NOT SOLVED**. | Provenance contradiction — the record disagrees with itself. | Reconcile; if 2.8 ms was never gate-passed, mark it aspirational/remove. |
| L1 | ⚪ LOW | vault manifest | `RigPreflight.desktop` listed but missing (md5sum -c FAILED). | Cosmetic integrity nick; Rig Check will always warn. | Restore the file or drop the manifest line. |
| L2 | ⚪ LOW | `capture_pointlio_texture.sh` | In-script motion advice: "stop-and-go **pan**… tau irrelevant." | Contradicts Golden Method (translate; a pan-in-place is odometry-starved — the 141733 fan). | Align the printed guidance to the recipe: translate, don't pan in place. |
| L3 | ⚪ LOW | `capture_walk.sh` | Hardcodes `~/Downloads/capture_pointlio_texture.sh` — a Downloads-folder dependency for a capture path. | Fragile; not vault-backed; a Downloads cleanup breaks the walk (same class as the kiosk sweep). | Move `capture_pointlio_texture.sh` to a stable/vault location; reference that. |

---

## 3. DEBUG DEEP-DIVE — the tau blocker (C1)

**Reproduce**
- *Expected:* run `tau_solve.py <compressed_bag>` → a tau estimate with pass/weak gate.
- *Actual:* it can't consume the bag. Default topic `/image_raw` isn't in a compressed bag; and even pointed at `/camera/image_raw/compressed`, `motion_signals` does `raw8.reshape(m.height, m.width, -1)` — a `CompressedImage` message has **no `height`/`width`** and its `data` is a JPEG blob, so it errors (or, if it didn't, would diff JPEG bytes, which is meaningless).

**Root cause**
`tau_solve.py` was written against the **raw** camera era (v2 B0 records `/image_raw`). The choke fix moved capture to **compressed** to survive the SD write budget — but `tau_solve` never got the matching decode. `make_full_pan_anchor.py` *did* get it (`if 'CompressedImage' in con.msgtype: cv2.imdecode(...)`). So the bundle stage handles compressed; the tau stage doesn't. The pipeline moved; one tool didn't.

**Fix** (small, and there's a working model to copy)
In `motion_signals`, branch on message type:
```python
if 'CompressedImage' in conn.msgtype:
    img = cv2.imdecode(np.frombuffer(bytes(m.data), np.uint8), cv2.IMREAD_GRAYSCALE)
    g = img.astype(np.float32)
else:
    g = np.frombuffer(bytes(m.data), np.uint8).astype(np.float32).reshape(m.height, m.width, -1).mean(2)
```
Then the existing 12×16 block-diff and cross-correlation are unchanged. Default `--image-topic` should become `/camera/image_raw/compressed` (or auto-detect like `make_full_pan_anchor`).

**Prevention**
- One decode helper shared by `tau_solve` and `make_full_pan_anchor` (don't maintain two).
- A tiny fixture test: run each consumer against a 2-second existing compressed bag in the sandbox; any "can't read topic / wrong shape" is caught before a field capture. (This is exactly the dynamic sandbox pass, scoped to one check.)

---

## 4. DRIFT vs `SYSTEM_DESIGN_pipeline_v2.md`

| v2 design intent | Implemented reality | Gap |
|---|---|---|
| **B0** records `/image_raw` (raw) | records `/camera/image_raw/compressed` | tau_solve still expects the old raw topic (C1) |
| **B1** one shared bundle: `posed_images.npz` + `img_%05d.png` + calib from yaml; *"everything downstream reads only from B1"* | 3 bundle formats; `fuse_pano` embeds calib | single-spine contract not enforced (H1, M1) |
| **B0 gate:** odom-coverage ≥ 0.80, reject below | capture scripts gate only "is odom publishing" (binary) | the 80% coverage gate isn't at capture time (check with `check_capture.py`/`frame_qc.py`) |
| **B2h** BA pose-refinement hinge — *"the linchpin the inversion turns on"* | not built; fusers use raw odom-interpolated (SLERP/LERP) poses | **biggest gap** — v2 says BA is required for seam-free texture/splat; it's skipped |
| capture keeps per-frame scans + poses | `point_lio_capture` ✅; `capture_pointlio_texture` drops cloud | H2 |

**Read:** v2 is a good design that already anticipated these problems (the BA hinge would resolve pose/tau/seam issues at once). The seams above are the *implementation lagging the design*, not the design being wrong. Converging toward v2 — one bundle schema, calib from yaml, decide whether to build or explicitly defer the BA hinge — closes most of this.

---

## 5. WHAT FITS TOGETHER (positives — leave alone)

- **Coordinate convention is consistent** end-to-end: `T_lidar_in_map` (body→map), extrinsic applied downstream, identical projection (`map→lidar` via `Rᵀ`, `lidar→cam` via `R_L2C,T_L2C`) in `make_full_pan_anchor`, `fuse_pano`, `fuse_to_fbx`. The hard part is correct.
- **Occlusion gating (z-buffer)** present in both `fuse_pano` and `fuse_to_fbx`.
- **`make_full_pan_anchor` already decodes compressed** — the model to copy into `tau_solve`.
- **`point_lio_capture.sh` is a genuinely robust capture**: single-instance lock, records `/unilidar/cloud` for recoverability, 4-stage clean stop with fresh-PCD verify, honest failure. **This is the capture script to use.**
- **Geometry is tau-independent** (mesh always safe); only colour needs tau — consistent across `fuse_to_fbx`, the Master, and `fuse_pano`.

---

## 6. FIX ORDER (before the next capture / tau attempt)

1. **C1 — patch `tau_solve` to decode compressed** and point it at the compressed topic. *Without this, no compressed bag solves tau.* Smallest change, biggest unblock.
2. **H3 — fold linear speed into `tau_solve`'s odom signal** so a translation walk can actually correlate.
3. **H2 — use `point_lio_capture.sh` for the walk** (it already records `/unilidar/cloud`), or add cloud to `capture_pointlio_texture`. Keeps re-solvability.
4. **M2 — bless the deployed compressed `point_lio_capture.sh`** into the vault so reality == vault.
5. Later, before the FBX/UE bake (not before capture): **H1/M1** — unify the bundle format and the calibration source.

Then run the **dynamic sandbox**: replay one existing bag through the patched chain (tau → bundle → fuse) and confirm each hand-off. Scope decisions still open: **which fixture bag** (114136 / 180551 / the pano one) and **where** (Shadow vs upload intermediates to the cloud sandbox).

---

## 7. OPEN VERIFICATION ITEMS
- `RigPreflight.desktop` missing from vault (L1).
- Deployed vs vault `point_lio_capture.sh` bless (M2).
- `quatmath.py` presence beside `tau_solve` (M3).
- Whether `check_capture.py` / `frame_qc.py` implement the v2 B0 odom-coverage gate (not yet read).
- The dynamic replay itself (the other half of "sandbox the entire run").

*Static audit only — the operator's eye on the actual replayed artifacts remains the final gate.*
