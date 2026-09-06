# SOLVED: CAMERA-DIES-AT-14s = THE FUSION NODES (2026-09-06, 8AJ)

## The fix (proven)
Killing the two fusion nodes before capture — overlay_check_node.py + colorized_fusion_node.py —
FIXES the camera-dies-mid-capture bug completely.
  BEFORE (fusion nodes running): camera died ~14s in, ~4-6Hz, first-14s-only. (121219, 112949, etc.)
  AFTER (fusion nodes killed): fusioncap_115614 — camera survived the FULL 66.1s, 1809 frames @ 27.4Hz,
    covers 0.1s->66.1s. FIRST capture in project history with FULL-DURATION camera coverage.

## The mechanism (corrected by tegrastats — NOT what we assumed)
It is NOT CPU/RAM/GPU starvation. tegrastats during the fixed capture: RAM 3.6/7.6GB (half free), SWAP 0,
CPU cores 20-60% (never pinned), GPU 0-62%, temps ~53C. Plenty of headroom throughout.
=> The fusion nodes were BACK-PRESSURING gscam: they SUBSCRIBE to /image_raw and their per-frame
   processing couldn't keep up; the backlog stalled the camera's publish pipeline after ~14s.
   Remove the can't-keep-up subscribers -> gscam flows freely. (Not starvation; back-pressure.)

## Permanent fix to bake in
The fusion nodes (overlay_check + colorized_fusion) are DEBUG/colorize — NOT needed for the raw bag
(bag records /image_raw, /unilidar/cloud, /unilidar/imu, /aft_mapped_to_init; none come from them).
OPTIONS: (a) remove them from rig_start.sh entirely, OR (b) kill them in point_lio_capture.sh's
clean-slate step before recording. Either way: DO NOT run the fusion nodes during a capture.

## Consequence (big)
Every prior capture had camera coverage of only the first ~14s. 115614 is the first FULL-camera capture.
=> All prior camera/HUD/synthesis results were on first-14s-only data. NOW we can capture full data,
   which unblocks the HUD and the camera/odom synthesis for the first time.

## Diagnostic (bank as a check): after any capture, compare camera-frame time-range vs capture span.
Full coverage = camera range ~ full span. Died = range << span. (One-liner over the bag's /image_raw timestamps.)

## MECHANISM CONFIRMED (not hypothesized): ApproximateTimeSynchronizer back-pressure
Both fusion nodes subscribe via message_filters.ApproximateTimeSynchronizer on /image_raw + /unilidar/cloud
(colorized_fusion_node.py:82, overlay_check_node.py:70). The synchronizer BUFFERS both streams waiting to
match image+cloud timestamp pairs. It can't process pairs as fast as they arrive (27Hz cam + 12Hz cloud +
per-frame projection) -> its internal queues fill -> back-pressure propagates to gscam -> camera stalls ~14s
(time for queues to fill). tegrastats already ruled out CPU/RAM/GPU. So: the QUEUING/BLOCKING sync is the cause,
definitively.

## *** HUD DESIGN RULE (proven, must not violate) ***
The live camera+LiDAR HUD (Waveshare "did I get it?") is the SAME operation that killed the camera
(overlay_check_node WAS a live camera+overlay publisher). Building it naively RE-KILLS the camera. RULES:
- HUD must NOT use ApproximateTimeSynchronizer or any queuing/blocking subscription on /image_raw.
- Subscribe best-effort, depth=1 (KEEP_LAST 1): middleware hands only the NEWEST frame, drops the rest ->
  no queue to fill -> CANNOT back-pressure gscam.
- Grab the LATEST cloud at display time (not synchronized-paired) — good-enough alignment for a coverage HUD,
  and non-blocking.
- Result: HUD renders ~15fps of freshest data (smooth for the eye), camera records full 27Hz untouched, gscam
  never stalls. (Operator's 15-fps viewing instinct == the technical non-back-pressure fix. Same requirement.)
- A "did I get it?" HUD that kills the camera it monitors is the worst regression — this rule prevents it.

## PERMANENT-FIX TODO
- Bake "fusion nodes OFF during capture" into the workflow (remove from rig_start.sh OR kill in
  point_lio_capture.sh clean-slate). Currently a manual kill — fragile, easy to forget = silent 14s regression.
- Add a camera-Hz-DURING-capture guard that alarms if the rate drops (catch regressions loudly, on set).
- colorized_fusion_node.py is a REFERENCE for the projection math (intrinsics/extrinsic loaders + image->cloud
  projection) — mine it when building the HUD/synthesis projection.
