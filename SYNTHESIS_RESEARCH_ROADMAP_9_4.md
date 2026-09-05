# SYNTHESIS RESEARCH ROADMAP — camera/odometry fusion, 4-paper review (2026-09-04/05)

## The question the operator was pulling on (across all 4 papers):
"Is there a way to do the camera/odom synthesis that does NOT depend on our
imperfect poses + unsynced clock (tau)?"  ANSWER: yes (pose-free joint reconstruction,
2025 frontier) — BUT it needs a big GPU, AND we probably don't need it (see KEY INSIGHT).

## THE THREE ARCHITECTURAL STANCES toward the camera:
1. OURS NOW — camera DOWNSTREAM, texture-only, poses trusted, tau must be corrected.
   Simplest. What we have. tau-afflicted. Runs on Jetson (small data) / station (full bake).
2. V-LOAM style (Zhang&Singh 2015) — camera IN the odometry loop, shared clock/coord system,
   tau dissolved at source. Classical, proven. Would mean RE-ARCHITECTING odometry (away from Point-LIO).
3. Pose-free JOINT reconstruction (MUP, NeurIPS 2025; also DVLO 2024 learned fusion) —
   poses become optimizable; tau/drift SELF-CORRECT via geometry-color consistency.
   The north star. NEEDS A GPU. Not our architecture yet.

## HARD FEASIBILITY FACTS (from the papers themselves):
- MUP (the pose-free ideal): trained on an RTX 3090 (24GB VRAM), 60K iterations PER SCENE,
  a scene = ~33 frames (~our 180551 scale). => 24GB dedicated GPU, tens-of-min-to-hours per capture.
  Our Jetson = 8GB SHARED, and it HARD-LOCKED on a NON-neural texture bake. MUP is orders beyond.
  => pose-free reconstruction is PERMANENTLY an off-rig workstation/cloud-GPU activity. Settled fact.
- DVLO (learned fusion, 2024): RTX 4090, KITTI-trained. Also GPU/training-bound. Not adoptable as a tool.
- Both KITTI-based papers use HARDWARE-SYNCED sensors (no tau) — the luxury we lack. Our tau is
  partly self-inflicted by unsynced hardware; the clean literature fixes assume sync we don't have.

## *** KEY INSIGHT — we may be over-reaching ***
MUP is ENGINEERED FOR TERRIBLE POSES: it recovers from perturbations of 20 deg rotation + 3m
translation. OUR Point-LIO poses are cm-level, not meter-level. We are in the EASY regime.
=> We likely do NOT need pose-free machinery for good texture. The SIMPLE path (project with our
good poses + V-LOAM-style tau timestamp-shift if smear appears) has a real chance of "good enough."
The frontier methods exist to rescue bad poses; ours are good. This ARGUES FOR the simple proof.

## ACTIONABLE EXTRACTIONS (usable now, on our architecture, no GPU):
- TAU CORRECTION (V-LOAM Eq.5 principle): interpolate the pose to (image_timestamp - tau).
  We already interpolate poses to image timestamps (matcher, self-tested 5e-16). tau = just a
  shift in the lookup time. If motion-smear appears in the proof, this is the fix. No new hardware.
- CAPTURE DOCTRINE (V-LOAM Table II): SLOW, deliberate translation ~0.7 m/s. FAST motion BLURS
  geometry + breaks tracking. There's a SPEED WINDOW: enough to feed odom, slow enough to avoid blur.
  Add to the "rig leaves stand + translates" doctrine: translate SLOWLY.
- CONSISTENCY METRIC (MUP Eq.9 / DVLO): the success test for our projection proof = do ADJACENT
  frames' projected colors AGREE on shared surfaces (photometric consistency across parallax).
  This is THE metric the field uses. Use it instead of eyeballing "looks right."
- BETTER PIXEL SAMPLING (DVLO, filed for texture-baker v2): cluster image pixels around each
  projected LiDAR point (similarity-weighted) instead of naive per-face nearest-pixel. Later refinement.

## THE STAGED LADDER (what runs where):
  Capture ...................... Jetson ......... DONE (180551)
  Anchoring (frames->poses) .... Jetson ......... DONE
  SIMPLE projection PROOF ...... Jetson (small) . NEXT — reachable now, un-run
    success test = MUP-style adjacent-frame color consistency
  Texture bake (deliverable) ... STATION ........ memory-walled off Jetson
  Pose-free joint recon ........ 24GB GPU/cloud .. NORTH STAR (MUP), likely NOT NEEDED given cm poses

## PAPERS: V-LOAM (ICRA 2015, Zhang&Singh) | DVLO (2024, Liu et al) |
##         MUP (NeurIPS 2025, pose-free multimodal NVS)
