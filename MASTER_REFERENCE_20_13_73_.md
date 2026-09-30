<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.73, 2026-09-30) *****          -->
<!-- Additive layer on 20.13.72 (Stone Clause: nothing lost).                           -->
<!--   20.13.72 holds: Arducam Mode-2 root-cause + PERMANENT fix (udev /dev/arducam by   -->
<!--     USB 0c45:0578, node repoint, two gates), TAU-360 + WAVESHARE fronts opened.     -->
<!--   20.13.71 holds: tau_solve_v2, pipeline audit, storage_identifier seam, kiosk fix. -->
<!--   20.13.70 holds: OPERATIONAL TRIAD, re-solve-first, two-tau, 15 s init, L2 physics,-->
<!--     freeze->kiosk-on-Shadow (II-I), PART I golden recipe+tools.                     -->
<!--   20.13.68 holds both ADRs + the STAGE 1-7 RealityScan->UE recipe verbatim.         -->
<!-- THIS 20.13.73 LAYER banks the 2026-09-28..30 work: the TRIAD LINKED (four patched   -->
<!--   files + vault bless), the USB-cable signal finding, the Arducam Control Pad, and  -->
<!--   THE BIG ONE — exposure-time motion blur PROVEN as the root of the alignment       -->
<!--   problem, with the fix: LOCK THE SHUTTER SHORT.                                    -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ EXPOSURE TIME IS THE BLUR — LOCK THE SHUTTER SHORT ⭐   (root cause SOLVED)
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

**THE FINDING (proven by eye, 2026-09-30):** the reason the camera images "would
not line up" — and looked worse than an iPhone — is **motion blur from a long
exposure time.** Every capture ran the Arducam on **auto exposure** (Aperture
Priority, the device default), and in our dim interiors an auto loop lengthens the
shutter to brighten the scene. A long shutter open during a walk/pan smears every
moving frame. The global shutter we fought for kills *skew*, not *blur* — and this
is blur.

**PROVEN, not theorized** — two contact sheets of the SAME rapid pan, only the
shutter changed (camctl pad REC → `cam_contact.sh` stitch):
- **A — long shutter (~500 ms):** ~47 frames over 20 s (~2 fps — a long shutter
  FORCES the camera slow). Middle of the pan = unreadable comet-tail smears.
  Evidence: `rec_contact.png`.
- **B — short shutter (512 = 51.2 ms ≈ 1/20 s):** 600 frames over 20 s (~30 fps).
  The pan is LEGIBLE frame to frame — framed art, window mullions, rug, molding all
  hold their edges. Evidence: `rec_contact_B.png`.
Long → slow + smeared; short → fast + sharp. Nothing is clamped; the shutter does
exactly what it should. **The camera, focus, and 15 ' cable are all fine** — A's
static frames and all of B are sharp. The only fault was shutter-vs-motion.

**THE FIX (now part of the Golden Method):** for any moving capture,
**LOCK exposure SHORT** — manual, ~1/20 s (≈512 in `exposure_time_absolute`, units
0.1 ms) or shorter as light allows — freeze the motion first, then buy the lost
brightness back with **gain** (noise) or **added light**, and keep the pan
controlled. NEVER let auto grow the shutter to chase brightness on a moving take.
Windows will clip; that's fine — expose for the surfaces you texture.

**STILL TO DO (the durable half):** the control pad SAVES the chosen values to
`~/arducam_profile.json`, but **`rig_camera_compressed.py` must APPLY that profile
on startup** (it currently sets NO exposure control — pipeline is
`v4l2src ! image/jpeg ! jpegparse ! appsink`, so the camera runs on whatever the
device default is = auto). Until the node bakes the profile, a capture can silently
run on auto again. This is the one open action before the TAU-360 capture.


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART V — 2026-09-28..30 (triad link, USB cable, control pad, exposure)     ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## V-A. TRIAD LINKED — Pre-Flight → Start Rig → Rig Kiosk now run as ONE whole
═══════════════════════════════════════════════════════════════════════════
Full static audit of the triad found four real breakpoints; all fixed, deployed,
re-blessed, Rig Check = **ALL GREEN**:
- **`rig_launch.sh` (Pre-Flight):** (1) Stage 1 now blocks ONLY on `RED (CRITICAL)` —
  GREEN or AMBER proceeds (the old "ALL GREEN"-only test hard-stopped on any advisory
  drift, e.g. an unblessed point_lio edit). (2) NEW **Stage 1.5 Arducam gate** —
  `cam_preflight_gate.sh`, hard-block. (3) Stage 2 routes to `rig_start_compressed.sh`
  + `point_lio_capture.sh` — NOT `rig_start_lean.sh` (raw path: wrong topic, choke).
  The `RIG PRE-FLIGHT` icon runs this same file in a gnome-terminal, so the gate's
  RED is visible from the icon path too.
- **`rig_start_compressed.sh` (Start Rig):** LiDAR + camera verifies are now HARD
  GATES (abort + teardown on a silent sensor); next-step corrected to
  `point_lio_capture.sh` (NOT capture_pointlio_texture.sh, which drops /unilidar/cloud).
- **`rig_check.sh` + vault:** now COVERS the compressed pipeline —
  `rig_start_compressed.sh`, `rig_camera_compressed.py`, `cam_preflight_gate.sh` added
  as CRITICAL and blessed into `~/rig_originals` + manifest. (Before, Rig Check verified
  the LEAN pipeline + kiosk but was BLIND to what we actually capture with.)
- **`point_lio_capture.sh` (recorder):** INLINE camera gate, checked TWICE — pre-flight
  fail-fast AND right before `ros2 bag record` — refuses to record a 0-camera bag
  (the 183145 failure). Records the compressed cam topic. Blessed.
- **`cam_preflight_gate.sh` is v3 (NODE-AWARE):** checks the ROS topic FIRST (a running
  node = proof of life), falls back to the device grab only when the topic is silent —
  so Pre-Flight passes with rqt / the camera node left running (a v4l2 grab would else
  report "busy"). Re-blessed.
- Vault nicks closed: `restore_kiosk.sh` deployed re-synced from vault;
  `RigPreflight.desktop` blessed into the vault.

═══════════════════════════════════════════════════════════════════════════
## V-B. USB CABLE — 50 ' passive FAILS; 15 ' good (signal integrity)
═══════════════════════════════════════════════════════════════════════════
Swapping the Arducam to a **50 ' passive USB** cable: the camera ENUMERATES
(`/dev/arducam` resolves) but **cannot stream** — `VIDIOC_STREAMON returned -1
(Protocol error / EPROTO)`, 0 frames. Passive USB-2 tops out ~16 ', so 50 ' droops
VBUS under streaming load and/or loses signal integrity. **Back on the 15 ' it
streams clean (~30 fps).** For longer reach use an ACTIVE/powered USB-2 extension
or a USB-over-Cat6 extender — a plain long passive will not carry the video. NOTE:
this is also the first live proof the Pre-Flight/Start-Rig camera gates earn their
keep — a can't-stream camera hard-blocks instead of recording a 0-frame bag.

═══════════════════════════════════════════════════════════════════════════
## V-C. ARDUCAM CONTROL PAD — camctl_server.py (:8081)
═══════════════════════════════════════════════════════════════════════════
A Rig-Kiosk-style web pad (`~/camctl_server.py`, port **8081**; open on the Jetson
or over tailnet/LAN). Sliders/toggles for every v4l2 control applied LIVE via
`v4l2-ctl`; live preview + a camera-only **REC / scrub-replay** (600-frame RAM cap),
all fed from the ROS topic (the device is never opened twice — the ONE hard rule).
Buttons: Lock for capture / Reset to auto / Save profile / Load profile. Profile →
`~/arducam_profile.json`. Build spec is banked as
**`claude/ARDUCAM_CONTROL_PAD_HANDOFF.md`**. This pad is the instrument for the
eye-arbiter exposure call and the vehicle for the profile the node must load (header).

═══════════════════════════════════════════════════════════════════════════
## V-D. THE EXPOSURE FINDING — full chain (see header for the short version)
═══════════════════════════════════════════════════════════════════════════
- **Node never sets exposure.** `rig_camera_compressed.py` pipeline is
  `v4l2src device=/dev/arducam ! image/jpeg,W,H,framerate=30 ! jpegparse ! appsink` —
  no exposure/gain/WB. So every capture ran on the device's own default = auto.
- **Auto ran the shutter LONG** in dim rooms — the pad in Manual needed ~2017
  (201.7 ms) to expose one dim framing; auto produced that same brightness, so it was
  sitting in that neighbourhood. On a walk/pan that long shutter smears everything.
- **A vs B proved it by eye** (see header): 500 ms = smear + ~2 fps; 51 ms = sharp +
  30 fps. The exposure control is real and is THE lever.
- **You cannot read what auto used.** On auto, `exposure_time_absolute` reports its
  default (157) and `flags=inactive` — it does NOT report the live shutter, and the
  JPEGs carry no exposure metadata. So a past capture's exposure is unrecoverable, and
  the ONLY way to KNOW (and record) the shutter is to LOCK it (Manual). That is a
  second reason to lock for capture beyond frame-to-frame consistency: provenance.
- **Global shutter:** kills skew, not blur. Short exposure is still mandatory for
  moving takes; the GS just means no jello on top of the smear.
- **Residual, honest:** B (51 ms) still shows slight softness on the very fastest
  sweeps — it is a RAPID pan. A normal capture pan will be tighter. Open data point if
  wanted: a slow/medium pan at ~512 shows the clean ceiling.

═══════════════════════════════════════════════════════════════════════════
## V-E. CAMERA CONTROL QUICK-REF (full detail in ARDUCAM_CONTROL_PAD_HANDOFF.md)
═══════════════════════════════════════════════════════════════════════════
- Device: `/dev/arducam` (udev symlink, USB 0c45:0578, 2.3 MP GS, color, UVC).
- `auto_exposure`: 1 = Manual, 3 = Aperture Priority (auto). `exposure_time_absolute`:
  units **0.1 ms**, range 1–5000 (0.1–500 ms), INACTIVE until auto_exposure=1.
- `white_balance_automatic` 0/1; `white_balance_temperature` 2800–6500 K, INACTIVE
  until wb_auto=0. `power_line_frequency` = 60 Hz (US — keep, kills flicker banding).
- Dependency rule: set the auto TOGGLE first, then the value. The pad handles this.
- CAPTURE DISCIPLINE: **lock exposure short + lock white balance**, save the profile,
  bake it into the node startup so every capture comes up locked (not auto).

═══════════════════════════════════════════════════════════════════════════
## NEXT (carried)
═══════════════════════════════════════════════════════════════════════════
1. **Bake `~/arducam_profile.json` into `rig_camera_compressed.py` startup** — the one
   open action so captures come up locked-short, not auto (header).
2. **TAU-360 capture** — now with a live camera AND a locked short shutter: Golden walk
   (15 s init → tip DOWN → tip UP → controlled pan) → `tau_solve_v2`. This is the bag
   that finally carries sharp cloud + image.
3. **WAVESHARE integration** — kiosk camera tile + capture-button lockout (Front 2).

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-09-28..30:** LINKED the triad — four patched files + vault bless, Rig Check
  ALL GREEN, node-aware camera gate (V-A). Found the 50 ' passive USB fails to stream
  (EPROTO); 15 ' good (V-B). Built the Arducam Control Pad :8081 (V-C). **ROOT-CAUSED
  the alignment problem: exposure-time motion blur** — auto ran the shutter long in
  dim rooms; proven by A(500 ms, smeared) vs B(51 ms, sharp) contact sheets of the same
  rapid pan; camera/focus/cable are fine (V-D). FIX = lock the shutter short. NEXT:
  bake the exposure profile into the node startup, then the TAU-360 capture.

<!-- ============================================================================ -->
<!-- ##  END 20.13.73 LAYER. Additive on 20.13.72 (Arducam Mode-2 fix, /dev/arducam).## -->
<!-- ##  20.13.71: tau_solve_v2, audit, storage-id. 20.13.70: triad, two-tau, 15s.   ## -->
<!-- ##  Deep lineage (ADRs + STAGE 1-7 UE) in 20.13.68. Stone Clause: nothing lost. ## -->
<!-- ============================================================================ -->
