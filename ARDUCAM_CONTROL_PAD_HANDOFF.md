# Arducam Interactive Control Pad — Build Handoff Spec
**Date:** 2026-09-30 · **Rig:** Unitree L2 + Arducam GS + Jetson Orin Nano (film-set predictive-lighting capture rig)
**Purpose of this file:** everything a fresh chat needs to build a **Rig-Kiosk-style web control pad** for live tuning of the Arducam (exposure, white balance, etc.), with a live preview and a saveable profile the capture pipeline loads automatically.

---

## 1. What to build
A single-page web "control pad" (same spirit as the existing Rig Kiosk) that:
- Shows a **slider + number box per camera control**, with the two auto/manual toggles.
- **Applies changes live** to the camera while it's streaming, so you see the effect immediately.
- Shows a **live preview** of the camera.
- **Saves/loads a profile** (chosen exposure/WB/etc.) so the capture pipeline always comes up with your settings, not auto.

---

## 2. The camera — exact identity (use these, do not guess)
- **Device path:** `/dev/arducam` — a **udev-pinned symlink**, not a raw `/dev/videoN`. Always address the camera as `/dev/arducam`. It re-enumerates (video0 ↔ video1) on cable swaps/reboots; the symlink follows it.
  - Rule: `/etc/udev/rules.d/99-arducam.rules` → `SUBSYSTEM=="video4linux", ATTRS{idVendor}=="0c45", ATTRS{idProduct}=="0578", ENV{ID_V4L_CAPABILITIES}=="*:capture:*", SYMLINK+="arducam"`.
- **USB id:** `0c45:0578` — Microdia **"Arducam-B0578-2.3MP-GS"** (2.3 MP **global shutter**, color, UVC-class).
- **ROS node:** `~/rig_camera_compressed.py` opens `/dev/arducam` (v4l2 MJPEG → jpegparse, no decode) and publishes **`/camera/image_raw/compressed`** (`sensor_msgs/CompressedImage`, ~19 Hz). Its `device` ROS param already defaults to `/dev/arducam`.

### ⚠ The single most important constraint
**Only one process can STREAM the device.** While `rig_camera_compressed.py` is running it owns the video stream — a second v4l2 *stream* open will fail with "busy" (or `VIDIOC_STREAMON` errors). **But setting controls with `v4l2-ctl` works fine concurrently** — controls are independent of streaming.

➡ Therefore the pad: **sets controls via `v4l2-ctl` (works live while the node streams)**, and gets its **preview from the ROS topic** (`/camera/image_raw/compressed`), *never* by opening the device a second time. See §6.

---

## 3. The controls — measured live (`v4l2-ctl -d /dev/arducam --list-ctrls-menus`, 2026-09-30)

| Control | v4l2 name | type | min | max | step | default | current | notes |
|---|---|---|---|---|---|---|---|---|
| Brightness | `brightness` | int | -64 | 64 | 1 | 0 | 0 | |
| Contrast | `contrast` | int | 0 | 64 | 1 | 32 | 32 | |
| Saturation | `saturation` | int | 0 | 128 | 1 | 64 | 64 | color sensor — real control |
| Hue | `hue` | int | -40 | 40 | 1 | 0 | 0 | |
| **WB auto** | `white_balance_automatic` | bool | 0 | 1 | — | 1 | **1 (auto ON)** | toggle; gates the temp control |
| Gamma | `gamma` | int | 72 | 500 | 1 | 100 | 100 | |
| Gain | `gain` | int | 0 | 100 | 1 | 0 | 0 | raises brightness + noise |
| Power-line freq | `power_line_frequency` | menu | 0 | 2 | — | 2 | 2 (60 Hz) | 0=Disabled, 1=50 Hz, 2=**60 Hz (US — keep)** |
| **WB temp** | `white_balance_temperature` | int | 2800 | 6500 | 1 | 4600 | 4600 | **`flags=inactive` until `white_balance_automatic=0`** |
| Sharpness | `sharpness` | int | 0 | 6 | 1 | 3 | 3 | |
| Backlight comp | `backlight_compensation` | int | 0 | 2 | 1 | 1 | 1 | |
| **Auto-exposure** | `auto_exposure` | menu | 0 | 3 | — | 3 | **3 (Aperture Priority)** | only **1=Manual** and **3=Aperture Priority** are valid |
| **Exposure time** | `exposure_time_absolute` | int | 1 | 5000 | 1 | 157 | 157 | **units = 0.1 ms** (157 ≈ 1/64 s). **`flags=inactive` until `auto_exposure=1`** |

Raw output is in the Appendix (verbatim) for parsing reference.

---

## 4. Reading & setting controls — `v4l2-ctl` reference
```bash
# read everything (with menu options + flags):
v4l2-ctl -d /dev/arducam --list-ctrls-menus
# read one:
v4l2-ctl -d /dev/arducam --get-ctrl=exposure_time_absolute
# set one:
v4l2-ctl -d /dev/arducam --set-ctrl=gain=8
```

### Dependency ordering (critical — set the auto toggle FIRST)
A value control is `inactive` (ignored) while its auto mode owns it. Always set the toggle, then the value:
```bash
# lock EXPOSURE to manual, then set it (0.1 ms units; keep short for moving capture):
v4l2-ctl -d /dev/arducam --set-ctrl=auto_exposure=1
v4l2-ctl -d /dev/arducam --set-ctrl=exposure_time_absolute=200      # ~1/50 s

# lock WHITE BALANCE to manual, then set temp (Kelvin):
v4l2-ctl -d /dev/arducam --set-ctrl=white_balance_automatic=0
v4l2-ctl -d /dev/arducam --set-ctrl=white_balance_temperature=5000
```
The server should encode this rule: if the user moves the exposure slider, first ensure `auto_exposure=1`; if they move WB temp, first ensure `white_balance_automatic=0`. Grey out the value slider (disabled) whenever its auto toggle is ON, and read the `flags=inactive` marker to drive that.

### Parsing tip
`v4l2-ctl --list-ctrls` lines are regular: `name 0x........ (type) : min=.. max=.. step=.. default=.. value=.. [flags=inactive]`. Regex out `name`, `value=`, `min/max/step`, and the `flags=inactive` presence → build `{name:{value,min,max,step,default,inactive}}` JSON for the UI.

---

## 5. Architecture — mirror the existing Rig Kiosk
**Reference implementation to copy the shape of:**
- `~/Desktop/rig_kiosk_server.py` — a **Python stdlib `http.server`** on **port 8080** that serves the kiosk HTML (`/kiosk`), a JSON status endpoint (`/data`), etc., and shells out for live data. Single file, **no external deps**.
- `~/rig_kiosk_launch.sh` — self-heals the kiosk files from the vault, then launches Firefox `--kiosk`.
- HTML is a **single self-contained page** that polls `/data`.

**Recommended camera pad (same shape, new port):**
- `camctl_server.py` — Python `http.server` on **port 8081** (8080 is taken by the rig kiosk; or make it a *tab* in the existing kiosk if you want one surface). Endpoints:
  - `GET /` → the control-pad HTML.
  - `GET /ctrls` → JSON of current controls (run `v4l2-ctl -d /dev/arducam --list-ctrls`, parse per §4).
  - `POST /set?ctrl=<name>&val=<n>` → validate `n` against min/max/step, apply dependency ordering, run `v4l2-ctl --set-ctrl=<name>=<n>`, return refreshed JSON.
  - `POST /save` → write current values to `~/arducam_profile.json`. `GET /load` → apply that file.
- HTML/JS: one slider + number box per control; a toggle for `auto_exposure` and `white_balance_automatic`; disable dependent sliders when their auto is ON; a **presets row** (e.g. "Indoor daylight", "Lock current", "Reset to auto"); a preview pane (see §6).

Keep it stdlib-only (no Flask) to match the kiosk and avoid install friction on the Jetson.

---

## 6. The live preview (the one non-trivial part)
The device can't be opened twice for streaming (§2), so pull the preview from ROS, best option first:
- **(A) `web_video_server` (ROS pkg), least code.** If installed (or `apt install ros-humble-web-video-server`), run it and point an `<img>` at its MJPEG stream of the topic:
  `http://<jetson>:8080/stream?topic=/camera/image_raw/compressed` *(it uses its own port; pick one that doesn't collide)*. It serves ROS image topics as MJPEG out of the box.
- **(B) Tiny relay node.** An `rclpy` subscriber to `/camera/image_raw/compressed` that keeps the latest JPEG bytes in memory; the http server serves them at `/preview.jpg` (browser refreshes an `<img>` every ~100 ms) or as multipart `multipart/x-mixed-replace` MJPEG at `/stream.mjpg`. **The topic is already `CompressedImage` (JPEG) — relay the bytes, no re-encode.**
- **(C) Only if the node is NOT running:** the pad may open `/dev/arducam` itself for preview — but then it conflicts with Start Rig. Prefer A/B so the pad coexists with the live capture node.
- Preview is for *tuning*; control changes apply to the hardware whether or not the preview is up.

---

## 7. Persistence — make settings STICK for the capture (do not skip)
v4l2 controls are **device state**: they persist until changed, **but a USB re-enumeration / unplug / reboot resets them to defaults**, and you can't assume they survive a node restart. So:
1. The pad **saves a profile** → `~/arducam_profile.json` (all chosen control values).
2. **`rig_camera_compressed.py` applies that profile on startup** — right after it opens `/dev/arducam`, run the `v4l2-ctl --set-ctrl` calls (respecting dependency order) or the equivalent V4L2 ioctls — so **every Start Rig comes up with your locked exposure/WB**. Without this, a capture can silently run on auto again.
3. (Alternative) a pre-capture hook applies the profile before `point_lio_capture.sh`. Either way, **the capture must never depend on someone having opened the pad.**

---

## 8. Integration with this rig's discipline
- **Ports:** 8080 = rig kiosk. Use **8081** for the camera pad (or add a tab to the kiosk).
- **Never hard-code `/dev/video0`.** Always `/dev/arducam` (the symlink is the only stable handle; the raw node number changes).
- **Vault / wholeness check.** The rig keeps a "sacred vault" `~/rig_originals/` + `originals_manifest.txt`, checked by `~/rig_check.sh` (md5 of deployed vs vault; GREEN/RED). If `camctl_server.py` + its HTML become part of the launched stack, **bless them into the vault + manifest and add them to `rig_check.sh`'s `LIVE` map** (mark them **advisory**, not CRITICAL — a tuning pad isn't required for a capture).
- **Desktop sweep.** Web files that live on `~/Desktop` get swept into dated folders daily; that's why `rig_kiosk_launch.sh` self-heals from the vault before launching. If the pad's files live on the Desktop, mirror that self-heal, or keep the pad's files in `~/` instead.
- **Camera gate coexistence.** The capture pipeline already hard-blocks on a silent camera (`cam_preflight_gate.sh` at Pre-Flight; a topic-rate gate in `rig_start_compressed.sh` and `point_lio_capture.sh`). The pad doesn't change any of that — it only tunes image controls.

---

## 9. Global-shutter / capture-quality notes (why this pad matters)
- **Global shutter** = no rolling-shutter skew, but a **long exposure still motion-blurs** during a walk/pan. For moving captures keep `exposure_time_absolute` **as short as light allows** (~150–200 = ~1/64–1/50 s is a sane starting band); trade brightness with `gain` (adds noise) only as needed.
- For photogrammetry + Unreal relighting, **LOCK exposure and white balance** so a given surface looks the same across frames — auto that hunts produces inconsistent textures and a useless relight reference.
- **Windows will clip** (scene dynamic range far exceeds the sensor) — that's expected; expose for the interior surfaces you're texturing.
- Keep `power_line_frequency = 60 Hz` (US AC) to avoid flicker banding.

---

## 10. Current state snapshot (starting point for tuning)
Bench view today (daytime bedroom): **in focus, global-shutter clean, windows blown, interior slightly dim with a green cast** — both `auto_exposure` and `white_balance_automatic` were **ON (auto)**. So the pad's first useful job is: `auto_exposure=1` + `exposure_time_absolute≈200`, and `white_balance_automatic=0` + `white_balance_temperature≈5000`, then tune from the live preview.

---

## Appendix — raw `v4l2-ctl -d /dev/arducam --list-ctrls-menus` (verbatim, 2026-09-30)
```
User Controls

                     brightness 0x00980900 (int)    : min=-64 max=64 step=1 default=0 value=0
                       contrast 0x00980901 (int)    : min=0 max=64 step=1 default=32 value=32
                     saturation 0x00980902 (int)    : min=0 max=128 step=1 default=64 value=64
                            hue 0x00980903 (int)    : min=-40 max=40 step=1 default=0 value=0
        white_balance_automatic 0x0098090c (bool)   : default=1 value=1
                          gamma 0x00980910 (int)    : min=72 max=500 step=1 default=100 value=100
                           gain 0x00980913 (int)    : min=0 max=100 step=1 default=0 value=0
           power_line_frequency 0x00980918 (menu)   : min=0 max=2 default=2 value=2 (60 Hz)
                0: Disabled
                1: 50 Hz
                2: 60 Hz
      white_balance_temperature 0x0098091a (int)    : min=2800 max=6500 step=1 default=4600 value=4600 flags=inactive
                      sharpness 0x0098091b (int)    : min=0 max=6 step=1 default=3 value=3
         backlight_compensation 0x0098091c (int)    : min=0 max=2 step=1 default=1 value=1

Camera Controls

                  auto_exposure 0x009a0901 (menu)   : min=0 max=3 default=3 value=3 (Aperture Priority Mode)
                1: Manual Mode
                3: Aperture Priority Mode
         exposure_time_absolute 0x009a0902 (int)    : min=1 max=5000 step=1 default=157 value=157 flags=inactive
```
