## 8P. FIELD KIOSK UI + THERMAL GAUGES + SERVER GAUGE DATA (Stage 8, 2026-08-30)

Built the Waveshare field UI to completion (Plan A kiosk), closing the "crowded desktop / tiny icons"
blocker. Worked slow, one verified command at a time; every file backed up before edit, every server
change dry-run in sandbox before touching the Jetson.

### SERVER (`~/Desktop/rig_kiosk_server.py`) — 5 additive edits, backed up as `.orig`
- Added `THERMAL` spec table (module-level): Jetson floor 35 / ceiling 104.5 / green 68 / yellow 80 /
  ticks 68·70·99; L2 floor 30 / ceiling 85 / green 70 / yellow 78 / ticks 70·78.
- Added `gauge()` helper (returns temp, frac, state, ticks, floor, ceiling) — same color logic as
  `band()`, per-device thresholds.
- Wired `d["jetson"]`/`d["l2"]` to `gauge()`; updated `mock_reader` to emit the gauge shape too
  (L2 baseline corrected 38→61 to match measured operating temp).
- Added 4th action verb: `start_lean → ~/rig_start_lean.sh`.
- Verified by execution in sandbox (mock mode): /data emits full gauge shape, tick positions in-range,
  all four routes dispatch, backward-compatible with the old page.

### HTML (`~/Desktop/rig_kiosk.html`) — rebuilt, backed up as `.bak*`
- Four-button 2×2 grid (Start Rig / Start Lean / Capture / Stop Rig), fat-finger sized.
- Two real-scale thermal gauges with tick marks + scale numbers (Jetson on kernel trips, L2 on
  manual-85 with 78 prevention line).
- Camera-reference panel removed (per §8 point-cloud-over-camera finding).
- Capture-drive slot (reads RECORD_PATH free space; drive-aware/mount logic deferred to flash-drive arrival).
- Tap-to-exit ✕ (top-right) → confirm overlay → `window.close()`. CONFIRMED exits Firefox by tap on
  the Waveshare — no keyboard needed.
- Fill-the-window: 1024×600 canvas scaled to viewport on both axes (`fit()`); fills edge-to-edge on any resolution.
- Verified file md5: 5295982e68dd7c030a81ff7a776f276d
  (paste-delivery required gzip+base64+checksum after plain paste mangled the file twice).

### LAUNCHER (`~/Desktop/rig_kiosk_launch.sh`)
Sources ROS → starts server if not running (`pgrep` guard) → polls until `/data` answers →
`firefox --kiosk`. Confirmed working (Firefox is plain /usr/bin/firefox 154, not Snap).

### JETSON THERMAL — real kernel trip points (measured, replaces earlier guesses)
- cpu/gpu/soc/cv zones: trip 70 (throttle onset) / 99 (hard) / 104.5 (shutdown).
- tj-thermal (junction): 74 / 95 / 104.5.
- Confirms the conservative 68/80 operator bands sit safely below hardware limits.
- COLORING DECISION: Option B — 68/80 bands drive the color; real trips shown as reference ticks only.

### POWER CORRECTION (supersedes §8H "Jetson = straight USB-C PD, no trigger")
- Jetson confirmed = Orin Nano ENGINEERING REFERENCE Dev Kit (from System>About).
- The reference dev kit's USB-C is DATA-ONLY, NOT a power input (NVIDIA docs/forums).
- Powered via DC BARREL JACK, 7–20V (stock adapter 19V/2.37A, 5.5×2.5mm center-positive).
- From the Ugreen this REQUIRES a PD trigger (USB-C → fixed-V → barrel). The standby 20V-max trigger
  is the MAIN LINE, not a fallback.
- Ugreen bank (25000mAh PD3.1): OUT1 USB-C 140W → Jetson (via trigger); OUT2 USB-C 100W → L2 (12V);
  OUT3 USB-A unused (5V only). Total-output table tops at 20V=10A; combined Jetson+L2 draw ~35W = tiny.
- A3 BENCH TEST STILL PENDING: 15V baseline first, My meter the trigger output (V + center-positive
  polarity) BEFORE connecting to the Jetson, then dual-load with L2, hold-under-load in MAXN SUPER.
  Use the Ugreen TFT readout as an independent second meter.

### STORAGE — resolved, no crisis
- SD card (mmcblk0p1): 234G total, 141G free, 38% used. Card is sealed inside a case (disassembly to remove).
- 48 GB in `Desktop/Fusioncap scans` = 8 tracked capture sessions (Aug 21–27), SINGLE-COPY on the sealed card.
  Biggest: fusioncap_175244 = 22 GB. `152121` metadata confirmed rich (image_raw + odom + imu, Point-LIO ran live).
- Tests-to-date are NOT the space problem (~1–2 GB of actual capture artifacts elsewhere); the Desktop bulk is.
- NO FREEZE ON TESTS: 141 GB is ample for Stage 8 validation + bounded captures. Flash drive still the right
  call for the sustained campaign.
- STANDING ACTION: back up the capture sessions OFF the sealed card when a destination exists (insurance,
  not urgent). Offload = rsync (verifies + resumes), NOT GitHub (48 GB, per-file 100MB limit).
- OFFLOAD TARGET: USB SSD (NOT a flash stick — sustained write must clear the §8J 70–100 MB/s fill rate;
  flash sticks collapse after cache), formatted EXT4 (no 4GB file cap, clean Linux perms), secured to the
  rig body with a SLACK cable (Jetson has only USB out; direct-plug stick = vibration/leverage risk).
  Considered SSK 1TB "push-pull" (genuine TLC-NAND SSD, fine; confirm 1000 read AND write, not 550-write sibling).
  Internal M.2 NVMe on the carrier board noted as the more robust alternative IF the case allows access.

### OPEN (next session)
- KIOSK COSMETIC BUGS (2): gauge scale labels overlap where ticks are close (68/70, 99/104.5);
  L2 APD shows `??`/empty when rig is OFF (L2 not publishing) — confirm it fills on Start Rig.
- Kiosk NOT yet a boot autostart (still launched manually) — deferred until stable + exit proven in field.
- PUSH TO GITHUB PENDING (highest-value first task): rig_start_lean.sh, rig_stop.sh, new rig_kiosk.html,
  rig_kiosk_server.py, rig_kiosk_launch.sh, .desktop files — all unpushed; repo confirmed stale on these.
- A3 power test (Ugreen → trigger → Jetson) not yet run.
- B1 flow-bar hot re-test / lean camera ~28Hz confirmation still owed.
