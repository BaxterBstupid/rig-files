<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.69, 2026-09-24) ***** -->
<!-- *** THE CLEAN COMPRESSED CAPTURE HAPPENED — AND PASSED THE VISUAL GATE.        -->
<!-- ***   Capture 114136 (2026-09-24) produced the first full-ring 360 FUSED        -->
<!-- ***   PANORAMA: real photo colour on LiDAR geometry, all the way around the      -->
<!-- ***   room (77.7% coloured, 306° heading, 35 frames, ONE clean bag). The image   -->
<!-- ***   reads as the real room in real colour and the colour LANDS on the          -->
<!-- ***   geometry. Every blocker the Master 20.13.68 header named is now cleared.    -->
<!-- -->
<!-- *** WHAT THIS CERTIFIES (new): (a) compressed capture + a MOVING odom work end    -->
<!-- ***   to end on hardware — dense odom, no hole, 309° pan with 60×87 cm parallax,  -->
<!-- ***   95% poseable; (b) the EXTRINSIC is real-world CORRECT — colour registers    -->
<!-- ***   on geometry across 306°, not just a checkerboard wedge (closes the          -->
<!-- ***   long-open "extrinsic code-verified, real-world UNCERTIFIED" item).          -->
<!-- -->
<!-- *** THE RATIFIED REPEATABLE PROCESS is its own doc: GOLDEN_360_FUSED_RECIPE.md   -->
<!-- ***   (every step, every tool md5, the reproduction targets, the visual gate).    -->
<!-- ***   NEXT STEP: RE-RUN THE EXACT SAME PAN (rig has not moved) FOLLOWING THAT     -->
<!-- ***   RECIPE AND CONFIRM THE IMAGE REPRODUCES. Then move on (geometry branch →    -->
<!-- ***   Unreal walkable; optional exposure-equalization pass for the 360 seams).    -->
<!-- -->
<!-- *** FULL PRIOR LINEAGE (ADR-001, ADR-002, the 20.13.68→20.13.33 session layers,  -->
<!-- ***   and the STAGE 1–7 RealityScan→UE5 recipe) IS PRESERVED VERBATIM in          -->
<!-- ***   MASTER_REFERENCE_20_13_68_.md — read it for the ADRs and history. This      -->
<!-- ***   20.13.69 layer folds ON TOP of it (Stone Clause: additive, nothing lost).  -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ 20.13.69 — THE 360 FUSED PANORAMA PASSED THE VISUAL GATE (capture 114136)  ⭐
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**The image exists.** For the first time the whole chain — capture → geometry → anchor →
photo colour — produced a picture that passes the eye: a full-ring 360 of the room, in
real colour, colour landing on the geometry, all the way around. The rule is honored:
*progress is the image, not the numbers* — and the image is good.

## THE PROVEN RUN (114136, 2026-09-24) — every number, for reproduction

- **Bag:** `plio_texcap_20260924_114136`, 87.4 s.
- **Camera:** `/camera/image_raw/compressed` (compressed fix live), 2047 frames.
- **Odom:** 1,700,640 msgs on `/aft_mapped_to_init` @ ~20 kHz — **dense, NO hole** (the
  raw-recording 127 s hole is dead).
- **Motion:** heading swept **309°**; translation **60 × 87 × 4 cm** — a real pan WITH
  parallax, not single-vantage. (`check_pan_heading.py` → VERDICT: PAN PRESENT.)
- **Anchor:** `make_full_pan_anchor.py` → **95% poseable** (1941/2047), **35** frames
  spread by HEADING (306° coverage), `panbundle.tar.gz` ~10 MB.
- **Cloud:** `scans_20260924_114136.pcd`, 2,038,351 pts (x y z intensity + normals).
- **Fusion:** `fuse_pano.py` → **77.7%** of the cloud coloured → the full-ring 360 PNG
  (`pano_360_fullring_114136.png`). Reproduced byte-for-byte in coverage by the canonical
  tool (only the debug title differs).

## THE RATIFIED PROCESS

The meticulous, step-by-step, md5-locked **repeatable process** lives in
**`GOLDEN_360_FUSED_RECIPE.md`** (banked alongside this file). It is the "do it again"
list: machine division, fixed calibration, the 6 steps (one command each), the
reproduction targets, the known-good blemishes, and the visual acceptance test. Follow it
exactly; the next pan should be a REPEAT, not a re-derivation.

## NEW CANONICAL TOOLS (born on 114136, md5-locked, banked to the project)

- **`make_full_pan_anchor.py`** (`f015c4a746cd2347b7d7ca11192ef1fe`, Jetson) — exports a
  HEADING-spread posed-frame bundle from ONE bag (fixes the old time-spread selection that
  gave a single-heading wedge). Pose math verbatim from `pointlio_pose_matcher.py` v2.
- **`fuse_pano.py`** (`d6246c2caecc39aab043ec43514846a6`, station) — self-contained,
  calibration-embedded full-ring render (occlusion-gated best-camera projection →
  equirectangular). The step that passed the gate. **Never run on the Jetson.**
- **`check_pan_heading.py`** (`20af111e90eff4abf1696aee62143a63`, Jetson) — read-only
  pan-confirm: does the bag's odom actually sweep heading + translate? The pre-export gate.

Prior-session tools still canonical: `rig_start_compressed.sh` (`10b2bb66…`) +
`rig_camera_compressed.py` (`446e6b5a…`) for compressed bringup; `capture_walk.sh`
(`46a4bd7e…`) wrapping the in-place-edited `capture_pointlio_texture.sh` for the hands-off
pan; `pointlio_pose_matcher.py` v2 (`6827341d…`) as the pose-math source of truth.

## WHAT IS NOW CLOSED vs STILL OPEN

- **CLOSED:** compressed capture + moving-odom (proven on hardware); the anchor→colour
  fusion (a real full-ring image); the EXTRINSIC's real-world certification (colour lands
  on geometry across 306°). Master 20.13.68's entire "NEXT STEP: clean capture" premise is
  satisfied.
- **STILL OPEN:** (1) REPRODUCE 114136 from the recipe (the point of this bank — prove it's
  repeatable, not a one-off); (2) the geometry branch to a walkable/relightable Unreal
  asset (`planar_shell` shell + occlusion-gated texture bake on the STATION, then the
  preserved STAGE 1–7 UE recipe in _68); (3) optional: exposure-equalization pass to remove
  the 360's teal auto-exposure seams (cosmetic; a render pass, not a capture problem).

## HONEST BOUNDARIES (do not overclaim)

- This artifact is a **360 FUSED PANORAMA** (colour on the point cloud), the *see-what-we-
  captured* proof — **NOT** yet the walkable Unreal mesh. It certifies the capture is good
  enough to build one; building it is the next arc.
- **Known-good blemishes** (expected, not failures): teal/cyan exposure seams between
  frames; grayscale caps straight up/down (level pan + L2 blind cones). See the recipe §6.

## SESSION LOG LINE
- **2026-09-24:** Confirmed the 114136 bag holds a real 309° pan + parallax (not single-
  vantage). Built + md5-locked `make_full_pan_anchor.py` (heading-spread anchor export) and
  `fuse_pano.py` (self-contained full-ring render); exported 35 heading-spread frames,
  fused onto the 114136 cloud → the first full-ring 360 (77.7% coloured) — PASSED the visual
  gate. Certified the extrinsic in the real world (colour on geometry across 306°). Banked
  the repeatable process as `GOLDEN_360_FUSED_RECIPE.md`. NEXT: reproduce the same pan from
  the recipe, then take the geometry branch to Unreal.

<!-- ============================================================================ -->
<!-- ##  END 20.13.69 LAYER. FULL LINEAGE (ADRs + 20.13.68 → earliest + the        ## -->
<!-- ##  RealityScan→UE5 recipe) IS IN MASTER_REFERENCE_20_13_68_.md, VERBATIM.     ## -->
<!-- ============================================================================ -->
