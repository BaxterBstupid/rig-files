<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.76, 2026-09-30 late PM) *****    -->
<!-- Additive layer on 20.13.75 (Stone Clause: nothing lost).                            -->
<!--   20.13.75 holds: SHADOW stood up as the Windows/Anaconda offline STATION, toolset   -->
<!--     certified vs the static bag, portable-anchor + tau-guard fixes, and the VII-C     -->
<!--     tau TIME-BASE flag (raised there, RESOLVED here).                                 -->
<!--   20.13.74: profile-load baked into the node; pad self-start; shutter angle/speed;    -->
<!--     hardware external-trigger research thread. 20.13.73: triad/USB/pad/exposure.      -->
<!--   20.13.72: Mode-2 /dev/arducam. 20.13.71: tau_solve_v2. 20.13.68: ADRs + UE recipe. -->
<!-- THIS 20.13.76 LAYER banks the moving-bag DRY RUN on Shadow: tau_solve_v2 proven on    -->
<!--   real motion, the VII-C time-base question RESOLVED, and the confirmation that the    -->
<!--   tau bag must be HANDHELD (tremor), not a smooth pano pan.                            -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ✅ MOVING-BAG DRY RUN ON SHADOW — tool certified, time-base cleared, tau needs tremor
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

Ran the recipe's known-good moving bag `plio_texcap_20260924_141733` (2.0 GB db3 +
`scans_20260924_141733.pcd`) through `tau_solve_v2` on Shadow. Three results, in order of
weight:

1. **The VII-C tau TIME-BASE question is RESOLVED, in our favor.** Sample counts: on the
   static `180728` the odom collapsed to **51** speed samples; on this real moving bag it's
   **4510** (camera 1942). The odom `/aft_mapped_to_init` header stamps DO carry real time
   on a genuine capture — the ~1 s collapse was specific to the static test bag. **No
   bag-time rewrite is needed;** `tau_solve_v2` keying off header time is fine for real
   captures. VII-C (20.13.75) is cleared.
2. **`tau_solve_v2` ran end to end on Windows on a real moving bag** — full read → motion
   signals → correlation → gates, 1942 frames decoded, no crash. The solver is **certified
   on Shadow for moving data**.
3. **The tau came back WEAK — and that is the CORRECT answer for this bag, not a failure.**
   Result: offset −20.7 ms, **peak corr 0.04**, halves differ **618 ms** → WEAK, do not
   trust. Why: `141733` is a slow, smooth pan **on the stand** (built as a *pano* bag). Tau's
   signal rides on **hand tremor (6–12 Hz)**; a tripod / smooth stand pan is **tau-blind**
   (documented, 20.13.17: "a silk-smooth trajectory is tau-blind; so is a tripod"). The gates
   looked, found no tremor-carried peak, and honestly flagged WEAK. **The gates did their
   job. A pano bag is not a tau bag.**


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART VIII — 2026-09-30 late (moving-bag dry run; VII-C resolved; transfer)  ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## VIII-A. CERTIFICATION STATUS — Shadow offline station
═══════════════════════════════════════════════════════════════════════════
- `make_full_pan_anchor.py` — proven end to end on Windows (static bag, 20.13.75).
- `tau_solve_v2.py` — proven end to end on Windows on a **moving** bag (this layer): reads
  the compressed topic, builds the shared timeline, correlates, gates, no crash.
- `fuse_pano.py` — STILL only import-verified; needs a `scans.pcd` + a `panbundle`. Both are
  now staged on Shadow for `141733` (the pcd is there; the bundle is one `make_full_pan_anchor`
  run away). Running anchor + fuse on `141733` certifies `fuse_pano` AND yields the reference
  360 — and it needs **no tremor**, so it can be done anytime (target: 88.5 % coloured / 275°).

═══════════════════════════════════════════════════════════════════════════
## VIII-B. WHAT THE TAU BAG MUST BE (re-confirmed, load-bearing for tomorrow)
═══════════════════════════════════════════════════════════════════════════
The TAU-360 capture must be **HANDHELD** — the Golden walk: 15 s dead-still settle → tip
DOWN → tip UP → controlled walking pan. That delivers tremor (the tau carrier) + angular
(the tips) + linear (the walk) motion all at once — exactly the signal `141733` lacked.
`tau_solve_v2` and the clock are now proven ready for it; the capture is what's missing.
Do NOT try to solve tau from a stand/tripod pan — it is tau-blind by physics, not by bug.

═══════════════════════════════════════════════════════════════════════════
## VIII-C. TRANSFER PATH — Jetson → Shadow over tailscale (learned, works)
═══════════════════════════════════════════════════════════════════════════
- Both on the tailnet: Jetson `fasterbybaxter-desktop` (100.85.175.10), Shadow
  `shadow-qinc8ae6` (100.109.61.120).
- `sudo tailscale set --operator=$USER` ONCE on the Jetson → the user can `tailscale file cp`
  (Taildrop) without sudo thereafter (incl. tomorrow's real capture).
- Send: `tar cf` the bag dir + its `scans.pcd` (no gzip — db3 barely compresses), then
  `tailscale file cp <tar> shadow-qinc8ae6:`. 2.0 GB verified intact by md5 (`3d82b1e6…`).
- **Windows Taildrop GOTCHA:** received files auto-save to `C:\Users\Shadow\Downloads\`, NOT
  where `tailscale file get <dir>` looks. Grab the tar from Downloads and `tar -xf` it into
  `C:\rig\fusioncaps\`.

═══════════════════════════════════════════════════════════════════════════
## NEXT (carried)
═══════════════════════════════════════════════════════════════════════════
1. **TAU-360 capture (TOMORROW)** — handheld Golden walk, locked short shutter (20.13.74).
   This bag solves tau for real AND re-certifies the chain on fresh data. Process on Shadow.
2. **Certify `fuse_pano` on `141733`** — quick, anytime, no tremor needed: `make_full_pan_anchor`
   → `fuse_pano` → the reference 360 (compare to 88.5 % / 275°).
3. **Push the offline toolset to `rig-files`** (SSOT; 20.13.75 VII-D).
4. **Migrate the archive to Shadow** — fusioncaps, Masters, screenshots off the Jetson.
5. **WAVESHARE integration**; **external hardware trigger** research (20.13.74 VI-D).

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-09-30 late:** Dry-ran the moving bag `141733` on Shadow. RESOLVED the VII-C
  time-base question — odom header stamps carry real time on a real capture (4510 speed
  samples vs 51 on the static bag); no bag-time fix needed (VIII-A/§1). `tau_solve_v2`
  certified end-to-end on Windows for moving data. Tau came back WEAK (corr 0.04, halves
  618 ms) — CORRECT for a smooth stand pano pan; tau rides on hand tremor, so the TAU-360
  must be handheld (VIII-B). Transfer path Jetson→Shadow proven over tailscale/Taildrop,
  2 GB md5-verified (VIII-C). NEXT: the handheld TAU-360 capture tomorrow.

<!-- ============================================================================ -->
<!-- ##  END 20.13.76 LAYER. Additive on 20.13.75 (Shadow station stood up).          ## -->
<!-- ##  20.13.74: profile-load/pad/shutter/trigger. 20.13.73: triad/USB/pad/exposure.## -->
<!-- ##  Deep lineage (ADRs + STAGE 1-7 UE) in 20.13.68. Stone Clause: nothing lost.  ## -->
<!-- ============================================================================ -->
