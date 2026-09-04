# FINDING: Full texture bake HARD-LOCKS the 8GB Jetson (2026-09-05)

## What happened
Ran pointlio_to_texture.py on fusioncap_180551 (the first real translating capture):
  56MB PCD (~1M+ points) + posed_180551.npz (2200 anchored frames) + frames_180551/.
Process climbed to 2.3GB RES at 100% CPU, only 141MB free, dipped into swap (542MB),
then the ENTIRE JETSON LOCKED UP — not just the process; the machine froze and needed
a hard reset. Data survived (read-only processing): bag, npz, frames all intact.

## The definitive answer (resolves the §8I open question)
The Master's §8I banked: "d9 mesh ran in ~3GB (8.4s) — the >8GB assumption may be WRONG,
re-test on Jetson." NOW RE-TESTED, DEFINITIVELY:
- GEOMETRY meshing alone (~3GB) may fit — that was the §8I optimism.
- But the FULL TEXTURE BAKE (mesh-from-full-dense-cloud + hold 2200 images + per-face
  projection in memory) does NOT fit. It exhausts 8GB + swap and hard-locks the OS.
=> The texture bake is a PROCESSING-STATION task, NOT a Jetson task.
=> The Jetson's job ENDS at CAPTURE + ANCHORING (pose-matching). Both proven to fit.
=> This is the clean division for the "onboard processing / closer to finished product"
   goal: rig captures + anchors (fits 8GB); station bakes texture + Unreal (needs the RAM/GPU).

## The specific memory killer
NOT the render frame count (--render-idx picks ONE view). It's the MESH BUILD on the full
~1M-point cloud inside run() (line 148), which happens BEFORE any projection. A single
--render-idx does NOT save you — the mesh build blows up first.

## SAFE PATH for a cold synthesis PROOF on the Jetson (not a full bake)
The synthesis proof needs only a FEW frames projected onto geometry across parallax — not a
2200-frame bake. To do it memory-safe:
  1. PRE-DOWNSAMPLE the PCD first (voxel downsample ~1M -> a few hundred K points) so the
     mesh build fits well under 8GB. (open3d voxel_down_sample, or CloudCompare offline.)
  2. THEN render one/a-few viewpoints with --render-idx.
Alternatively: do the projection test as a POINT-projection (project cloud points into the
image, no mesh) — far lighter, tests anchoring directly, no mesh-build memory blowup.

## RULE
Do NOT run the full pointlio_to_texture bake on the Jetson again — it hard-locks the machine.
Full bakes go to the processing station. On the Jetson: pre-downsample + few-frame proof only.

## Data (all survived the reset)
- fusioncap_180551 = first REAL translating capture: poses span 2.65m (spread 1.57x2.08x0.45m),
  2200 camera frames @ ~27Hz, 100% anchored WITH REAL CONTENT (validated: poses step through
  space, not degenerate). THE milestone bag — seed for all synthesis work.
- posed_180551.npz (303KB) = the 2200 anchored poses. frames_180551/ = dumped frames.
