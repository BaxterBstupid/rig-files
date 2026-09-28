<!-- ============================================================================ -->
<!-- ***** READ THIS FIRST — ACTIVE STATE (Master 20.13.72, 2026-09-27 PM) *****      -->
<!-- Additive layer on 20.13.71 (Stone Clause: nothing lost).                          -->
<!--   20.13.71 holds: CAPTURE-TO-PROVE-TAU header, III-A kiosk root-cause+self-heal,  -->
<!--     III-B pipeline audit, III-C storage_identifier seam, III-D tau_solve_v2,      -->
<!--     III-E tau-is-per-pipeline-constant.                                           -->
<!--   20.13.70 holds: OPERATIONAL TRIAD, re-solve-first, two-tau, 15 s init, L2       -->
<!--     physics (360x90), freeze->kiosk-on-Shadow (II-I), PART I golden recipe+tools. -->
<!--   20.13.68 holds both ADRs + the STAGE 1-7 RealityScan->UE recipe verbatim.       -->
<!-- THIS 20.13.72 LAYER banks the 2026-09-27 PM Arducam Mode-2 root-cause + PERMANENT  -->
<!--   fix (udev symlink + node repoint + two gates), and opens the next two fronts.    -->
<!-- ============================================================================ -->


═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════
#  ⭐ TO BE COMPLETED — TAU 360 SAMPLE — WAVESHARE INTEGRATION BEGINS ⭐
═══════════════════════════════════════════════════════════════════════════
═══════════════════════════════════════════════════════════════════════════

The camera blocker that silently ate `fusioncap_183145` (0 camera frames) is
**ROOT-CAUSED and PERMANENTLY FIXED** this session (PART IV). Two fronts remain:

**FRONT 1 — TAU 360 SAMPLE (finish what 20.13.71 started, now unblocked).**
Run ONE Golden-method compressed MOVING capture — dead-still **15 s init → tip
DOWN → tip UP → slow WALK with a 360 pan** — then `python3 tau_solve_v2.py <bag>`.
Everything in the 20.13.71 header still applies (tau is per-pipeline; no
compressed+moving bag exists yet), with ONE thing now different and proven:
**the Arducam actually streams into the bag.** `183145` gave us the geometry
half (2.2M odom, 75 MB PCD, 360 motion PRESENT) but 0 camera frames because of
the Mode-2 stall; that stall can no longer happen silently (PART IV). This is
the "360 sample" — the pan+walk bag that finally carries BOTH cloud and image.
PRE-CAPTURE: run `cam_preflight_gate.sh` (must print `OK … /dev/arducam`) and
keep the III-C post-capture `storage_identifier` guard.

**FRONT 2 — WAVESHARE INTEGRATION BEGINS.**
The camera gate protects the TERMINAL launch path only. The Waveshare (on-board
touchscreen → `rig_kiosk.html` served by `rig_kiosk_server.py`) is a SEPARATE
launch surface and currently runs NO camera gate — a stall there is as invisible
as it was on `183145`. Begin wiring the kiosk to surface the fail on-screen: a
RED "CAMERA: STALLED — capture blocked" tile that DISABLES the capture/START
button until green. Device-grab check BEFORE bring-up; switch to TOPIC-rate
(`/camera/image_raw/compressed` fps in `/data`) AFTER the node owns the device
(a v4l2 grab returns "busy" once the node is up — do not false-alarm on it).
NEEDS: `rig_kiosk_server.py` + `rig_kiosk.html` in hand to wire the tile + lockout.

**CARRIED CURRENT-STATE:** THE RIG IS OFF until a clear command powers the L2.
Vault discipline (Rig Check GREEN = deployed == `~/rig_originals` by md5). Files
edited this session show RED until blessed AFTER a capture proves out (PART IV).


╔═══════════════════════════════════════════════════════════════════════════╗
║  PART IV — 2026-09-27 (PM) ARDUCAM MODE-2 STALL: ROOT-CAUSE + PERMANENT FIX ║
║  (rig OFF; camera is USB-powered so all of this was done cold, no L2.)      ║
╚═══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
## IV-A. ROOT CAUSE — the Arducam RE-ENUMERATES itself (this is the "Mode-2 stall")
═══════════════════════════════════════════════════════════════════════════
The "camera node alive but silent → 0 frames" wall is NOT a code bug and NOT a
power issue. **The Arducam spontaneously re-enumerates on the USB bus** — with NO
physical action by the operator. Measured 2026-09-27:
- `/dev/video0` VANISHED; the same camera reappeared as `/dev/video1` (+ `/dev/video2`
  the UVC metadata node), both created at the same new timestamp.
- `v4l2-ctl` grab: `/dev/video1` streamed 10/10 frames (grab_exit=0) → the hardware
  is perfectly healthy; `/dev/video2` timed out (124) → normal for a metadata node.
- The pipeline was HARD-PINNED to `/dev/video0`. After the re-enum:
  - the running node kept a handle to a device that no longer existed → **alive but
    silent, 0 frames** (this is exactly what `fusioncap_183145` recorded), and
  - any relaunch tried to open `/dev/video0` (gone) → **Exit 1** (the "[1]+ Exit 1"
    we saw when the software restart failed).
- USB identity: **`0c45:0578` Microdia `Arducam-B0578-2.3MP-GS`** (the Global Shutter).
Everything previously filed as "Mode-2 stall" is this re-enumeration. It needs NO
physical unplug when it happens — the device is fine on the new node; the pipeline
just has to stop hard-coding a node number.

═══════════════════════════════════════════════════════════════════════════
## IV-B. PERMANENT FIX — udev symlink /dev/arducam (deployed + verified)
═══════════════════════════════════════════════════════════════════════════
**`/etc/udev/rules.d/99-arducam.rules`** pins a stable symlink `/dev/arducam` to the
camera's VIDEO-CAPTURE node by USB id, so whatever `videoN` the kernel assigns,
`/dev/arducam` always resolves to the real camera:
```
SUBSYSTEM=="video4linux", ATTRS{idVendor}=="0c45", ATTRS{idProduct}=="0578", \
  ENV{ID_V4L_CAPABILITIES}=="*:capture:*", SYMLINK+="arducam", GROUP="video", MODE="0660"
```
The `ID_V4L_CAPABILITIES=="*:capture:*"` match keeps the symlink OFF the metadata node.
Installed, reloaded, triggered → **verified `/dev/arducam -> video1`.** Survives reboot
and re-enumeration. This kills the root cause; it does not need re-running.

═══════════════════════════════════════════════════════════════════════════
## IV-C. NODE REPOINT — rig_camera_compressed.py now defaults to /dev/arducam
═══════════════════════════════════════════════════════════════════════════
- `rig_camera_compressed.py` line 115: `declare_parameter('device', '/dev/video0')`
  → **`'/dev/arducam'`**. Backup saved `~/rig_camera_compressed.py.bak_<HHMMSS>`.
- Launcher `rig_start_compressed.sh` line 81 runs `python3 ~/rig_camera_compressed.py`
  with **NO `-p device:=` override** → the new default governs. No launcher edit needed.
- STATUS: this `.py` edit is UNBLESSED (Rig Check will show it RED) — bless AFTER the
  TAU 360 capture proves live frames (per "don't bank until we see an image").

═══════════════════════════════════════════════════════════════════════════
## IV-D. THE GATES — device-level + topic-level (both delivered)
═══════════════════════════════════════════════════════════════════════════
Two complementary gates, because the camera has two states (device free vs node-owned):

**`cam_preflight_gate.sh` (device-level, PRE-Start-Rig).** Probes `/dev/arducam` with a
short v4l2 grab; symlink-aware (compares resolved devices). Default `CAM_EXPECT=/dev/arducam`.
- Exit 0: `OK — Arducam live at /dev/arducam -> /dev/video1`. **VALIDATED GREEN this session.**
- Exit 1 (no node streams): `!!! NO video node streams — truly wedged` → **physical replug.**
- Exit 1 (live but symlink stale): `Camera is live on /dev/videoN but /dev/arducam stale`
  → **`sudo udevadm trigger --subsystem-match=video4linux`** (software re-point, no touch).
- The two messages are deliberately distinct so the operator fixes the RIGHT layer.
- CAVEAT: run it BEFORE Start Rig; once the node owns the device a v4l2 grab returns "busy".

**`camera_gate.sh` (topic-level, PRE-record).** Measures `/camera/image_raw/compressed`
Hz; fails on 0 (stall) or < 10 Hz (starving). This is the one that would have caught
`183145`, because that stall developed AFTER pre-flight — so it must run **right before
`ros2 bag record` inside `point_lio_capture.sh`** and abort the capture on fail.

Files delivered to chat this session: `camera_gate.sh`, `cam_preflight_gate.sh` (v2,
symlink-aware), `99-arducam.rules`.

═══════════════════════════════════════════════════════════════════════════
## IV-E. WHY THE OLD GATES ALL MISSED IT (the operator's own point, banked)
═══════════════════════════════════════════════════════════════════════════
`183145` sailed past Pre-Flight, Rig Check, AND the Kiosk and still recorded 0 camera
frames. Each is blind to a live-camera stall: **Rig Check** compares md5 only (file
identity, not liveness); **Pre-Flight** (`rig_launch.sh`) ran before the stall and never
tested the camera at all; **Rig Kiosk** shows a rate but does not BLOCK. The fix is
liveness gating at the two moments that matter (IV-D) — not another file-identity check.

═══════════════════════════════════════════════════════════════════════════
## IV-F. WIRING STILL TO DO (carried into next session)
═══════════════════════════════════════════════════════════════════════════
- **`cam_preflight_gate.sh` into `rig_launch.sh`** as "STAGE 1.5" (cold check, camera is
  USB-powered) — hard-stop `exit 1` on fail, between Stage 1 (stack) and Stage 2 (warm).
  Editing `rig_launch.sh` changes its md5 → if the vault tracks it, Stage 1 self-fails →
  **re-bless right after** (needs `~/rig_originals/originals_manifest.txt` — was the next
  step when the session paused). Install the gate at `~/cam_preflight_gate.sh` (home, not
  Desktop — Desktop sweep is what broke the kiosk).
- **`camera_gate.sh` before `ros2 bag record`** in `point_lio_capture.sh` (the real
  hole-closer, IV-D).
- **WAVESHARE (Front 2):** the kiosk camera tile + button lockout (needs the two kiosk files).
- **Carried vault nick:** `RigPreflight.desktop` missing from `~/rig_originals` (III-A).
- **Bless after capture proves out:** `rig_camera_compressed.py` (IV-C), and
  `point_lio_capture.sh` (compressed edit, carried from 20.13.71).

═══════════════════════════════════════════════════════════════════════════
## SESSION LOG LINE
═══════════════════════════════════════════════════════════════════════════
- **2026-09-27 (PM):** Arducam Mode-2 day (rig OFF; camera USB-powered → all cold).
  ROOT-CAUSED the "0 camera frames" stall to spontaneous USB **re-enumeration**
  (`/dev/video0`→`/dev/video1`, no physical action) orphaning a node hard-pinned to
  video0 (IV-A) — this is what emptied `fusioncap_183145`. PERMANENT FIX deployed +
  verified: udev symlink **`/dev/arducam`** by USB id `0c45:0578`, capture-node-restricted
  (IV-B); repointed `rig_camera_compressed.py` default to `/dev/arducam`, launcher passes
  no override (IV-C). Built + delivered TWO gates — `cam_preflight_gate.sh` (device,
  validated GREEN) and `camera_gate.sh` (topic, pre-record) — IV-D; banked why the old
  triad missed it (IV-E). NEXT: **TAU 360 SAMPLE** (the now-unblocked compressed moving
  capture → `tau_solve_v2`) and **WAVESHARE INTEGRATION BEGINS** (kiosk camera tile +
  button lockout). Nothing blessed yet — the image is the proof.

<!-- ============================================================================ -->
<!-- ##  END 20.13.72 LAYER. Additive on 20.13.71 (CAPTURE-TO-PROVE-TAU, III-A..E). ## -->
<!-- ##  20.13.70: triad, re-solve-first, two-tau, 15s init, L2 physics, freeze->    ## -->
<!-- ##  kiosk-on-Shadow, PART I. Deep lineage (ADRs + STAGE 1-7 UE) in 20.13.68.    ## -->
<!-- ##  Stone Clause: additive, nothing lost.                                       ## -->
<!-- ============================================================================ -->
