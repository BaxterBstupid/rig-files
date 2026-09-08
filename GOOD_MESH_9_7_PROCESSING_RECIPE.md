# GOOD MESH 9 7 — EXACT PROCESSING RECIPE (how fusioncap_180551 became GOOD MESH 9 7.ply)
# Date processed: 2026-09-07 (Master 20.13.35 era). Companion to GOLDEN_CAPTURE_RECIPE_180551.md.
#
# SCOPE: GOLDEN_CAPTURE_RECIPE_180551.md tells you how the BAG was captured. THIS doc tells you
# EXACTLY how that existing bag was PROCESSED into the orbitable textured mesh "GOOD MESH 9 7.ply".
# These are two different procedures. This one starts AFTER the bag exists.
#
# HONEST HEADLINE: GOOD MESH 9 7 is the JETSON CEILING for a WALK capture — an INTACT, textured,
# orbitable MARCHING-CUBES mesh (2cm). It is NOT Poisson (Poisson SEGFAULTS on the Jetson's Open3D
# 0.18 on walk clouds — proven exhaustively 2026-09-07). Operator verdict: "better than before but
# miles from a deliverable." The deliverable-grade (crisp Poisson) mesh is CLOUD-STATION work.

=====================================================================================
## THE TOOL: bake_180551.py  (MARCHING CUBES version — NOT Poisson)
=====================================================================================
Content signature (verify you have the RIGHT file before running):
    grep -c marching_cubes ~/Desktop/bake_180551.py    # MUST be 4
    grep -c "open3d\|poisson" ~/Desktop/bake_180551.py # MUST be 0
    wc -c ~/Desktop/bake_180551.py                      # ~5108 bytes
If these don't match, you have the wrong bake_180551.py (there was an earlier Poisson v1, 4301 bytes,
that SEGFAULTS — do not use it). The correct v2 was transferred this session via a base64 blob
(bake_v2.b64 -> base64 -d) because direct download-to-Desktop kept failing.

Deps (all present on the Jetson, no Open3D): numpy, scipy, scikit-image (skimage.measure.marching_cubes),
opencv (cv2). It does NOT import open3d.

=====================================================================================
## INPUTS (must exist before processing — produced earlier in the pipeline)
=====================================================================================
1. /mnt/rigdata/fusioncap_180551_scans.npy   — the cloud as .npy, 1,812,190 pts (N,3 float32).
     Made by: pcd_to_npy.py from /mnt/rigdata/fusioncap_180551_scans.pcd
     (Reason: mesh tools read .npy; MeshLab & this bake do NOT read .pcd directly.)
     Command that made it:
        python3 ~/Desktop/pcd_to_npy.py /mnt/rigdata/fusioncap_180551_scans.pcd /mnt/rigdata/fusioncap_180551_scans.npy
2. ~/anchor_test/frames_180551/   — 2200 extracted camera frames, img_00000.png .. img_02199.png
3. ~/anchor_test/posed_180551.npz — 2200 matched poses (keys: pos, quat, ok; all ok=True)
     Both #2 and #3 made by pointlio_pose_matcher.py on the bag (earlier).

=====================================================================================
## THE ONE LOAD-BEARING EDIT: MAXDIM 900 -> 1400
=====================================================================================
bake_180551.py ships with MAXDIM=900 (an auto-coarsen guard: if the voxel grid would exceed
900 on any axis, it DOUBLES the voxel until it fits). 180551's room is ~18 x 16 m. At 2cm voxel
the grid needs ~912 x 823 — which EXCEEDS 900 — so at MAXDIM=900 the guard auto-coarsened the
request from 2cm to 4cm, giving a COARSER mesh (NOT GOOD MESH 9 7).
To let 2cm actually hold, MAXDIM was raised to 1400:
    sed -i 's/MAXDIM       = 900/MAXDIM       = 1400/' ~/Desktop/bake_180551.py
    grep MAXDIM ~/Desktop/bake_180551.py     # confirm it now reads 1400
*** THIS EDIT IS PART OF THE RECIPE. Without it you get the 4cm coarsened mesh, not GOOD MESH 9 7. ***
(NOTE: this edit was made ONLY on the Jetson copy. Any fresh download of bake_180551.py is back at
 900 and must be re-edited.)

=====================================================================================
## THE EXACT COMMAND
=====================================================================================
    python3 ~/Desktop/bake_180551.py 0.02 60
        arg1 = 0.02  -> 2cm voxel (downsample spacing AND occupancy-grid resolution)
        arg2 = 60    -> frame stride: use every 60th frame -> 37 frames

=====================================================================================
## EXACT EXPECTED OUTPUT (this IS the reproduction test — numbers must match)
=====================================================================================
    === STAGE 0: LOAD + VOXEL-DOWNSAMPLE (numpy) ===
      1,812,190 -> 754,633 voxel centers @ 0.02m
    === STAGE 1: OCCUPANCY GRID + MARCHING CUBES (mesh_check method) ===
      grid 912x823x182 @ 0.020m | 2,223,400 verts 4,577,476 faces     <-- @0.020m proves MAXDIM worked
    === STAGE 2: TEXTURE — per-vertex facing color, stride 60 ===
      2200 usable frames -> using 37 (stride 60)
      textured 1,691,675/2,223,400 (76.1%) from 37 frames
    === STAGE 3: EXPORT PLY ===
      wrote /home/fasterbybaxter/Desktop/bake_180551_textured_mesh.ply  (92.9MB)
    === DONE in ~74s ===

REPRODUCTION CHECK:
  - STAGE 1 MUST read "@ 0.020m" (NOT "@ 0.040m"). If 0.040m -> MAXDIM reverted to 900 -> re-do the edit.
  - Vert count MUST be 2,223,400. The marching-cubes path is DETERMINISTic (no randomness), so a
    correct repeat is byte-identical. A different vert count = something in the inputs/edit changed.

=====================================================================================
## PRESERVE THE RESULT
=====================================================================================
The script always writes the same filename (bake_180551_textured_mesh.ply). GOOD MESH 9 7 was the
operator's renamed/saved copy. To preserve:
    mv ~/Desktop/bake_180551_textured_mesh.ply ~/Desktop/"GOOD MESH 9 7.ply"
View:
    meshlab ~/Desktop/"GOOD MESH 9 7.ply"

=====================================================================================
## WHAT EACH STAGE ACTUALLY DID (the mechanism, for understanding not just repeating)
=====================================================================================
STAGE 0  Load 1.81M pts. VOXEL-mean downsample @2cm (numpy hash to voxel index, average members)
         -> 754,633 uniform-density centers. (Uniform density matters — random sampling scatters
          density and tears meshes; voxel keeps it even.)
STAGE 1  Build a boolean OCCUPANCY GRID at 2cm (grid dims from extent/voxel, guarded by MAXDIM=1400).
         Run skimage marching_cubes(level=0.5) on it -> surface at the occupied/empty boundary.
         Add grid origin back to return to world metres. Normals come from marching_cubes.
         -> 2,223,400 verts / 4,577,476 faces. Blocky at 2cm, but INTACT (cannot shred like Poisson).
STAGE 2  TEXTURE per vertex: for each of 37 frames, compose world->camera with the LOCKED extrinsic
         (R_L2C/T_L2C, identical to per_shot_texture.py AND extrinsic_20260816.yaml — C3 verified),
         project vertices, keep those in-front & in-frame, score by |normal . view| (head-on = best),
         and paint each vertex from the frame that sees it most head-on. -> 76.1% textured.
         (~90px extrinsic translation residual exists — expect color right-but-slightly-shifted, not
          random smear. That's calibration, not a bake bug.)
STAGE 3  Write binary PLY (xyz + per-vertex RGB + faces). 92.9MB.

=====================================================================================
## WHY THIS AND NOT POISSON (so nobody re-treads the crash)
=====================================================================================
Poisson (per_shot_texture.mesh_cloud / pointlio_to_texture / bake_proven_180551.py) makes CRISPER
meshes BUT segfaults on the Jetson's Open3D 0.18 on walk clouds (tried 426k, cleaned 404k, random
161k -> crash or shredded confetti). 0.18 is the Jetson's ceiling (no newer aarch64 wheel).
So on the JETSON, for a WALK capture, MARCHING CUBES (this recipe) is the working path.
Poisson-crisp is CLOUD-STATION work (Open3D >= 0.19), scripts already written: bake_proven_180551.py.

=====================================================================================
## KNOBS (if repeating and tuning)
=====================================================================================
  arg1 voxel:  0.02 = 2cm (GOOD MESH 9 7). Smaller = finer but bigger grid/RAM; needs higher MAXDIM.
               0.03 = 3cm = safer/coarser (~400k verts). 0.04 = what MAXDIM=900 auto-coarsened to.
  arg2 stride: 60 = 37 frames -> 76%. Lower stride = more frames = more coverage, slower texture.
               (Earlier 3cm/stride-150 gave 69%; 2cm/stride-60 gave 76%.)
  MAXDIM:      1400 lets 2cm hold on this 18x16m room. Raise for finer voxels (watch RAM).
