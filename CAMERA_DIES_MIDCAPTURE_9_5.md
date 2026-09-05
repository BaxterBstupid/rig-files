# CRITICAL FINDING: THE CAMERA DIES ~14s INTO EVERY CAPTURE (2026-09-05, 8AI)

## The discovery
Testing "LiDAR+camera at the same instant" on 121219 revealed a 19.5-SECOND gap between the
mid-capture instant and the nearest camera frame. Investigation:
  fusioncap_121219: span 66.5s. CAMERA frames only cover 0.0s -> 13.7s, then NOTHING for ~53s.
  (Camera healthy in that window: 5.7Hz, max gap 0.2s. Then it just STOPS.)
  LiDAR ran the FULL 66.5s cleanly (11.8Hz). So it is SPECIFICALLY the camera that quits.
  Same signature on 112949: 713 frames/165s ~ 4Hz = frames clustered at the start, camera died early.

## What this means (reframes much of the project's camera pain)
- The camera does NOT just wedge at STARTUP (the known gscam hang, fixed by unwedge/replug).
  It ALSO DIES ~14s INTO the capture, SILENTLY. The bag "succeeds", looks fine, but the camera
  half is a stub from only the opening seconds.
- EVERY HUD / overlay / synthesis attempt has used camera data from only the first ~14s of each
  capture. If the operator dwelt on a subject LATER in the capture, there is NO camera frame of it.
- This explains a LOT: sparse/odd dumped frames, confusing overlay results, the sense that camera
  registration "didn't match what I did" — the camera was blind for most of every capture.
- At the wire the camera shows 20-27Hz; DURING capture it delivers ~4-6Hz then zero. The capture
  STACK is starving it.

## Likely cause: CPU STARVATION during capture (the real §8M issue)
Point-LIO + the two FUSION nodes (overlay_check + colorized_fusion) + bag recorder all load the
cores; gscam gets starved and its GStreamer pipeline stalls mid-capture (same "Could not get
gstreamer sample" wedge, but triggered by mid-capture LOAD, not at startup). ~14s in = when
accumulating load tips it over. Lean-capture doctrine addresses RViz but NOT the fusion nodes'
load on the camera.

## FIX DIRECTION (not done — next session):
- Run capture LEAN enough that gscam survives: DROP the fusion nodes during capture (they are the
  CPU thieves per §8M; they're debug/colorize, not needed for the raw bag), and/or give gscam CPU
  priority (nice/chrt), and/or verify camera Hz DURING capture and alarm if it drops.
- TEST: capture with fusion nodes killed, confirm camera frames span the WHOLE capture.
- Until fixed: NO capture has full-capture camera coverage. All camera/HUD/synthesis results are
  built on the first ~14s only. Treat accordingly.

## Diagnostic that finds it (bank as a check):
  read the bag, compare camera-frame time-range vs capture span. If camera range << span -> camera
  died mid-capture. (script: check camera it[0]..it[-1] vs t0..t1.)
