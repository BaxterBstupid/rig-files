<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.74, 2026-09-30) *****           -->
<!-- Additive layer on 20.13.73 (Stone Clause: nothing lost).                            -->
<!--   20.13.73 holds: TRIAD LINKED (four patched files + vault bless), 50' USB fails,   -->
<!--     Arducam Control Pad :8081, and THE BIG ONE — exposure-time motion blur PROVEN    -->
<!--     as the root of the alignment problem; fix = LOCK THE SHUTTER SHORT.              -->
<!--   20.13.72 holds: Arducam Mode-2 root-cause + PERMANENT fix (udev /dev/arducam).     -->
<!--   20.13.71 holds: tau_solve_v2, pipeline audit, storage_identifier, kiosk fix.       -->
<!--   20.13.70 holds: OPERATIONAL TRIAD, re-solve-first, two-tau, 15 s init, L2 physics. -->
<!--   20.13.68 holds both ADRs + the STAGE 1-7 RealityScan->UE recipe verbatim.          -->
<!-- THIS 20.13.74 LAYER banks the 2026-09-30 work: the ONE OPEN ACTION from 20.13.73 is  -->
<!--   now CLOSED — rig_camera_compressed.py APPLIES the saved profile on startup          -->
<!--   (blessed, Rig Check ALL GREEN). Plus: CAMERA PAD launcher now self-starts the node, -->
<!--   the shutter-angle vs shutter-speed clarification, and the HARDWARE TRIGGER finding. -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ✅ THE SHUTTER LOCK IS NOW DURABLE — the node comes up locked, on every path
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**WHAT CHANGED (2026-09-30):** the one open action carried in 20.13.73 — "bake the
exposure profile into the node startup" — is **DONE and BLESSED.**
`rig_camera_compressed.py` now reads **`~/arducam_profile.json`** and applies it to
the camera **before the GStreamer stream opens**, so the camera comes up in the
operator's saved locked state instead of the device auto-default. Because EVERY path
to a live camera runs this same one file — a CAMERA PAD tap, Start Rig, or a
reboot-recovery bring-up — patching the single node makes "comes up locked" true
everywhere. There is no path that dodges it.

- **Verified byte-exact:** deployed + vault md5 = **`894328fd6bae0fa5d7e165705952ac46`**
  (pre-patch original was `98f3d74a3aa626f84847cf5c3896317a`). Rig Check = **ALL GREEN**.
- **Owners-first:** it sets `auto_exposure` and `white_balance_automatic` FIRST, then the
  gated children (`exposure_time_absolute`, `white_balance_temperature`), mirroring the
  pad's own save/load order so the two never disagree.
- **Never crashes / inert by default:** no profile file → it logs
  `no camera profile … -> device default` and behaves exactly as before. A missing or
  bad profile, or a control that won't set, just logs and carries on.
- **Backup:** original preserved at `~/rig_camera_compressed.py.bak_preprofile`.

**WHAT THIS IS — AND IS NOT (operator's framing, 2026-09-30):** this is a **seatbelt for
persistence, NOT a preset.** On the day you still dial the camera BY EYE on the pad for
the room and light in front of you — "my eye is the ultimate arbiter." The node does not
prescribe a shutter and does not override a live pad tweak; it only re-asserts a saved
profile at *startup / recovery*. Its ONLY job: if you tap **Save profile** after dialing,
a glitch — a Mode-2 re-enumeration, or a freeze/reboot like the one on 2026-09-30 that
brought the camera back on AUTO — won't silently throw your by-eye setting away. It does
NOTHING unless a profile is saved, and a profile is per-location, never universal. Seatbelt
in the car; you decide if you ever buckle it.


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART VI — 2026-09-30 (profile-load, pad self-start, shutter theory, trigger)║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## VI-A. PROFILE-LOAD baked into rig_camera_compressed.py  (open action → CLOSED)
═══════════════════════════════════════════════════════════════════════════
The node gained a `profile` parameter (default `~/arducam_profile.json`) and an
`_apply_profile(dev)` method called immediately before `Gst.init` / pipeline PLAYING.
It reads the flat `{control_name: value}` JSON the pad writes on "Save profile", applies
owners first then the rest via `v4l2-ctl -d /dev/arducam`, logs
`applied camera profile … N ok / M failed`, and returns quietly on any error.

- **Why before the stream opens:** configure the device, then capture — the camera comes
  up already locked with no auto flicker. UVC holds controls across STREAMON, so it sticks.
  (LIVE-CONFIRMED 2026-09-30: node restarted, logged the profile line + `publishing NATIVE
  JPEG` + `anchored capture clock`, streamed clean. If a future driver ever wipes controls
  on STREAMON, the one-line fallback is to move the call to just AFTER set_state(PLAYING).)
- **Blessed:** surgical single-file bless — copied to `~/rig_originals/`, manifest hash
  updated (with a timestamped manifest `.bak_`), Rig Check re-run → `rig_camera_compressed.py`
  GREEN [CRITICAL], VERDICT ALL GREEN.

═══════════════════════════════════════════════════════════════════════════
## VI-B. CAMERA PAD launcher self-starts the node (camctl_launch.sh)
═══════════════════════════════════════════════════════════════════════════
`camctl_launch.sh` now brings up the camera node (`python3 ~/rig_camera_compressed.py`,
logging to `~/rig_logs/camera.log`) **only if not already running** (`pgrep -f
rig_camera_compressed`), then the pad server, waits for `:8081/ctrls`, and opens Firefox
kiosk. So after a reboot, tapping **CAMERA PAD** brings the camera up on its own — no
Start Rig needed for a camera-only session. **No device collision, in either order:**
- Rig up first, then pad → the pad's `pgrep` guard sees the node and skips.
- Pad up first, then Start Rig → `rig_start_compressed.sh` KILLS any existing
  `rig_camera_compressed` (its clean-restart kill-list + `teardown_partial`) then starts
  a fresh one, so it reclaims `/dev/arducam` cleanly (LiDAR launch sits between kill and
  camera-start — no EBUSY race).
The pad never opens the device for video (single-open rule): preview + REC come from the
ROS topic, controls go straight to the device via `v4l2-ctl`. Bouncing the node never
conflicts with pad operation — the preview blinks out ~8 s and reconnects; controls stay live.

═══════════════════════════════════════════════════════════════════════════
## VI-C. SHUTTER — angle vs speed, and why blur is capture-side only
═══════════════════════════════════════════════════════════════════════════
- **The Arducam has NO mechanical shutter angle.** A global shutter switches pixel
  integration on for a set duration then reads out — a *duration* (speed), not an *arc*.
  Its one and only shutter knob is `exposure_time_absolute` (units 0.1 ms). `156` = 15.6 ms
  ≈ 1/64 s.
- **Angle is derivable, not settable:** `angle° = exposure × frame_rate × 360`. At 30 fps:
  180° ≈ `167`, 90° ≈ `83`, 45° ≈ `42`, and 500 ms @ ~2 fps = 360° (wide open = the smear).
  Formula: `units = (angle ÷ 360) ÷ fps × 10000`.
- **Standard cine convention (for talking to vendors):** 360° = fully OPEN = most smear;
  0° = closed = least; 180° = the classic look. (Bigger angle → longer open → more blur.)
- **The pad speaks shutter SPEED (1/D chips), which is the correct lever for us** —
  absolute exposure is what physically governs smear on a still frame, independent of frame
  rate. Tapping a chip auto-locks Manual.
- **Blur is capture-side and IRREVERSIBLE.** A long exposure *averages* the moving scene
  into each frame; that information is gone. Deblur tools *hallucinate* detail and, for
  photogrammetry, invent FALSE features that poison alignment. There is no "clean it in
  post." The only fix is short shutter + controlled pan, in the glass. (Fits eye-arbiter:
  get it right in-camera, not in the math afterward.)

═══════════════════════════════════════════════════════════════════════════
## VI-D. HARDWARE TRIGGER — exists in the silicon, not reachable on Linux (yet)
═══════════════════════════════════════════════════════════════════════════
Investigated whether the Arducam has a true shutter/trigger beyond exposure time.
- **YES, a hardware capability exists.** Our unit exposes an Arducam **vendor Extension
  Unit** (`bUnitID 3`, GUID `28f03370-6311-4a2e-ba2c-6890eb334016`) — a control channel
  outside the 13 standard v4l2 controls. And the **AR0234 supports external trigger mode**
  in principle: the module family has a **TRIGGER / FLASH / IO** pin header. Trigger =
  fire each exposure on an external pulse; FLASH = a strobe pulse emitted AT exposure.
- **Why it matters:** this is the gold-standard sync path — fire camera + LiDAR on a shared
  signal (tau becomes hardware-deterministic instead of solved by cross-correlation), and
  the FLASH pin could timestamp the exact instant each frame integrates.
- **The catch (honest):** enabling it on Linux is UNRESOLVED. Per Arducam's own forum for
  the closely-matched B0495 (AR0234 USB3), V4L2 has no trigger controls, the EVK SDK didn't
  recognize the device, XU I2C probing echoed without a real transaction, vendor USB
  requests stalled, and pulsing the TRIGGER pin didn't switch it out of free-run; support
  deferred to sales. Our unit is the **USB-2 B0578 (0c45:0578, enclosed)** — need to confirm
  it even breaks out the pins and that Arducam supports trigger on this exact SKU.
- **Status: OPEN RESEARCH THREAD.** Does not change today's plan (exposure time is still the
  only usable shutter; lock short + controlled pan). A drafted question to Arducam
  (sales/support) is ready: external trigger on B0578, how to enable over the XU on
  Jetson/Linux, per-trigger exposure control, FLASH electrical spec, exposure range.

═══════════════════════════════════════════════════════════════════════════
## NEXT (carried)
═══════════════════════════════════════════════════════════════════════════
1. **TAU-360 capture** — now with a live camera, a durable short-shutter lock, and a
   controlled pan: Golden walk (15 s init → tip DOWN → tip UP → controlled pan) →
   `tau_solve_v2`. The bag that finally carries sharp cloud + image.
2. **WAVESHARE integration** — kiosk camera tile + capture-button lockout (Front 2).
3. **[NEW] External hardware trigger** — research thread: confirm the B0578 exposes
   TRIGGER/FLASH and how to enable trigger mode on Jetson/Linux (email Arducam). If it
   works, upgrades the whole sync story (tau) from correlation to hardware.
   (DONE this layer: profile-load baked into the node — was #1 in 20.13.73.)

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-09-30:** CLOSED the profile-load open action — `rig_camera_compressed.py` applies
  `~/arducam_profile.json` on startup (owners-first, before stream open), byte-verified
  `894328fd…`, blessed, Rig Check ALL GREEN (VI-A). CAMERA PAD launcher now self-starts the
  node, collision-free in both orders (VI-B). Clarified shutter angle vs speed and that
  motion blur is capture-side/irreversible — no post fix (VI-C). Found the Arducam vendor
  Extension Unit + AR0234 external-trigger capability, but enabling on Linux is an open
  research thread for the B0578 (VI-D). NEXT: TAU-360 capture.

<!-- ============================================================================ -->
<!-- ##  END 20.13.74 LAYER. Additive on 20.13.73 (triad link, USB, pad, exposure).  ## -->
<!-- ##  20.13.72: Mode-2 fix /dev/arducam. 20.13.71: tau_solve_v2. 20.13.70: triad. ## -->
<!-- ##  Deep lineage (ADRs + STAGE 1-7 UE) in 20.13.68. Stone Clause: nothing lost. ## -->
<!-- ============================================================================ -->
