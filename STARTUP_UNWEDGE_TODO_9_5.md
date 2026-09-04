# TODO: Build camera-unwedge INTO rig_start.sh (operator-requested 2026-09-05)

## Why
Camera goes silent between sessions/runs; currently requires a MANUAL fix each time.
Should be automatic in startup, like the LiDAR-publishing check already is (rig_start.sh ~line 60).

## TWO failure modes (from 9-4 and 9-5 sessions) — different fixes:
- MODE 1 (gscam process wedge): node up, /dev/video0 fine, pipeline stuck, topic silent.
  FIX: kill -9 gscam + relaunch with exact GSCAM_CONFIG. (camera_unwedge_9_4.sh, md5 7c2bdfd3)
  -> AUTO-FIXABLE in rig_start.sh. SAFE.
- MODE 2 (device-state stall): "Could not get gstreamer sample" / "Opening in BLOCKING MODE";
  device itself not delivering; software gscam restart does NOT clear it.
  FIX (proven 9-5): PHYSICAL USB unplug/replug re-enumerates + clears it.
  Scriptable equivalent = USB unbind/rebind via /sys/bus/usb/drivers/usb/{unbind,bind}
  (sudo-level, device-path-specific) — UNTESTED as a script. Do NOT auto-add until proven cold.

## The build (do COLD, sandboxed — not hot before a capture):
1. Read rig_start.sh; find the camera-launch block (~line 77-79) + the LiDAR verify pattern (~line 60).
2. Add AFTER camera launch: verify /image_raw is PUBLISHING (timeout ros2 topic hz, like the LiDAR check).
   If silent -> run the Mode-1 unwedge (kill+relaunch gscam) ONCE -> re-verify.
   If STILL silent -> print a clear "CAMERA MODE-2 STALL: unplug/replug USB" message (don't auto-rebind yet).
3. DIAGNOSTIC to embed: v4l2-ctl raw-grab (--stream-count=1) tells Mode-1 (grab works, gscam wedged)
   from Mode-2 (grab fails, device stalled) — 614400-byte frame = device delivering.
4. Gate the edited script (bash -n + a dry logic check), back up original, deploy, test hot.
5. SEPARATELY + LATER: test the USB unbind/rebind cold; if reliable, add as the Mode-2 auto-path.

## Banked tools this relates to:
- camera_unwedge_9_4.sh (7c2bdfd3) = the Mode-1 fix, standalone
- v4l2-ctl raw-grab = the Mode-1-vs-Mode-2 discriminator
