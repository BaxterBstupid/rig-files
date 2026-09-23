# PERFECT ROOM CAPTURE — v2 recipe (the formal living room)
### Environment · Dimensions · Time, balanced for the LiDAR-dimensions / photos-graphics pipeline
**Date:** 2026-09-22 · **Feeds:** SYSTEM_DESIGN_pipeline_v2 (B0 capture → B1 registration) · **Room:** the formal living/dining room in the reference photos (windows, mirror over the fireplace, paintings, chair-rail).

---

## 0. THE ONE CORRECTION THAT DEFINES THE CAPTURE

You said it has to be **360° and floor-to-ceiling**. The *coverage goal* is exactly right. But the *method* cannot be a 360° spin from the middle of the room — that is a static rotation, and by your own ratified rule it **starves Point-LIO** (angle alone produces no odometry; poses collapse to ~0 and the bag is dead). This is the single most expensive mistake available here.

**360° coverage is produced by ORBITING, not spinning.** You walk a translating loop and let the outward-facing sensor sweep the walls as you move. Floor-to-ceiling is produced by **tilt passes** (tip up, tip down) layered on the orbit, using the L2's 90° vertical field. So:

> **Environment = continuous slow movement — a walked orbit with pan-while-walking and deliberate tip up/down. Never a static hold, never an in-place spin.**

Everything below is the disciplined version of that.

---

## 1. ENVIRONMENT — static vs movement, and what kind

**Static: ruled out.** Movement is mandatory for tracking.

**The movement, precisely:**

- **Translate to track, pan to cover.** Walk a loop; simultaneously pan the sensor outward toward the walls ("pan while walking"). Translation feeds the odometry; the pan paints the 360°.
- **Speed: ~0.7 m/s, deliberate.** Fast enough to feed odom, slow enough to avoid motion blur (blur kills both tracking and the photo-graphics). This is a speed *window*, not "as slow as possible."
- **Two kinds of motion, both needed (your ratified tip-vs-walk synthesis):**
  - **WALK = new positions** → parallax + tracking (the orbit).
  - **TIP = new angles** → kills specular glare, fills oblique faces, reaches floor/ceiling (the vertical bands).
- **Parallax on the foreground.** For the fireplace, the furniture groupings, anything a virtual camera will move past — add a small local orbit so those surfaces are seen from several angles (the photos-graphics branch and any splat need this; a flat dolly past them caps reconstruction).
- **Loop closure by hand.** There is no automatic loop closure, so **start and end at the same corner** and overlap the beginning of the path at the end. A closed loop bounds drift on a room-scale capture.
- **Init ritual:** rig in hand (never the stand), hold **dead still ~10 s** for Point-LIO IMU/gravity init, *then* move.

**Light discipline for THIS room (critical, and specific):**

- The windows are blowing out to pure white — 15+ stops from the dim interior. For the **relight (delight) path**, that dynamic range is poison: Agisoft can't delight strong baked shadow, and a clipped window carries no usable graphics anyway. **Capture under flat light** — overcast day, or early/soft light, or **close the sheers** to knock the window down. Expose for the *room surfaces*, not the glass.
- **The window will be a LiDAR hole no matter what** (glass returns nothing). Do not spend dwell trying to fill it. Get sharp *photos* of the frame, sill, and curtains for the graphics; you will insert the window light yourself in Unreal — that spot is where you take control anyway.
- **The mirror over the fireplace will produce a phantom room behind the glass** in the LiDAR (specular reflection). The planar_shell coherence report will flag a stray plane there. Options: cover the mirror for the LiDAR pass (cleanest shell), or leave it and mask the phantom plane in post. Either way, keep its photo for the graphics.

**What NOT to do:** stand in the center and rotate; hold still and pan; dolly in a straight line through the room; rush past a wall so its rosette never densifies; capture with the windows blown.

---

## 2. DIMENSIONS — the room you've seen

**Working estimate (confirm against the planar_shell bbox):** a formal living/dining room, roughly **5.0–5.5 m × 4.0–4.5 m × 2.7 m** (≈ 9-ft ceiling — consistent with the crown molding, tall windows, and the ~2.88 m Z-extent seen in the 163005 cloud). Treat these as planning figures; **the first `planar_shell` run prints the true metric bbox and squares this.**

**How the dimensions set the path:**

- **Orbit radius:** walk a loop ~1.0–1.5 m inside the walls (close enough to densify wall detail, far enough for the 90° cone to catch the wall top-to-bottom). Loop length ≈ **~9–10 m** → **~13–15 s per lap** at 0.7 m/s before dwell.
- **Vertical bands:** the L2's 90° vertical FOV covers most of a 2.7 m wall from 1.2 m out in one pass, but the ceiling directly overhead and the floor directly underfoot need tilt. → **three effective bands: mid-level orbit, tip-up orbit (ceiling + upper walls + window heads), tip-down orbit (floor + baseboards + lower furniture).**
- **Dwell allocation (density follows dwell — the L2's non-repetitive scan fills in with time):** spend dwell on the **complex/foreground** surfaces (fireplace, furniture, textured walls, moldings) and **move steadily past** the plain flat walls — they cross the planar-fit density threshold quickly. Every surface needs *some* dwell; none needs to be stared at except the ones with real geometry.

---

## 3. TIME — balanced against GB → processing → cost

This is the constraint you asked me to hold tightest, so here is the reasoning, not just a number.

**The forces:**
- **Too short** → incomplete coverage, thin parallax, under-dense surfaces, and higher odom-cutoff exposure on a single long roll.
- **Too long** → GB balloons, the variable Point-LIO odom-cutoff is more likely to bite, the L2 heats, and — the real cost — **BA and splat training scale with frame count**, so processing time and cost climb fast.
- **The hidden lever:** at 30 fps a slow walk produces *enormous frame redundancy*. You do **not** need 2200 frames for a room; that number is what made processing take hours and starved earlier passes. Good multi-view reconstruction wants ~70–80% overlap, which for this room is **~400–600 well-distributed sharp keyframes**, not thousands.

**The balanced design — capture generously, extract sparsely, split to dodge the cutoff:**

| Lever | Setting | Why |
|---|---|---|
| Capture frame rate | 27–30 fps (as-is) | motion-robustness; cheap to throw frames away later |
| **Keyframe extraction** | **~1 per 12 cm travel / ~5° rotation → target ~500 keyframes** | decouples capture robustness from processing cost; **this is the main cost control** |
| Capture structure | **2 overlapping passes, ~45–60 s each** | each under the proven-safe odom window; overlap bounds drift and dodges the variable cutoff; matches the system-design "overlapping passes, not one continuous roll" |
| Total capture time | **~110 s of recording** (2× ~50 s + 2× ~10 s init) | complete coverage without the long-roll cutoff risk |
| Raw bag size | **~1.5–2 GB total** (compressed image + cloud + IMU + odom, ~15–20 MB/s) | modest; SSD-relayed, wired |
| Extracted working set | ~500 keyframes + one raw cloud | what BA/texture/splat actually consume |
| Processing on Shadow | shell: minutes · BA(~500): ~10–30 min · texture: minutes · splat(optional): ~30–60 min | ~1–2 h end-to-end; several-fold worse if you feed it all 2200 frames |

**Pass split:**
- **Pass A — shell + mid-level graphics (~50 s):** perimeter orbit at chest height, pan-while-walking, close the loop. Gives the dimensions (walls/floor/ceiling planes) + the primary wall/foreground photos.
- **Pass B — verticals + foreground parallax (~50 s):** same start corner (overlap for registration); tip-up orbit (ceiling, upper walls, window heads), tip-down orbit (floor, baseboards), plus small local orbits of the fireplace and furniture.
- Registered together by ICP (your proven ~19 mm), which also bounds drift better than one long roll.

*(If/when the odom-cutoff is actually fixed, this collapses to a single ~90 s pass — 180551 proved 81 s holds. Until then, two short overlapping passes is the safe, balanced choice.)*

---

## 4. THE EXECUTABLE RECIPE

**Setup**
1. Flat/soft light: overcast, or early light, or sheers closed. Expose for the room, not the windows. (Cover the mirror if you want a clean shell.)
2. Rig in hand, braced. Verify green FLOW bars — **confirm camera Hz** (a lean start declares success over a dead camera). SSD mounted, wired.

**Pass A (~50 s)**
3. Stand at the chosen start corner, rig at chest height. **Hold dead still 10 s** (watch the IMU-init).
4. Walk the perimeter loop slowly (~0.7 m/s), ~1.2 m off the walls, **panning the sensor outward** to sweep each wall floor-to-mid as you pass. Dwell a beat on the fireplace wall and any detailed surface (watch the coverage map go green); keep moving past plain walls.
5. Return to the **start corner** to close the loop. Single clean Ctrl-C.

**Pass B (~50 s)**
6. Same start corner, still 10 s init.
7. Orbit again, this time **tipping up ~30°** for the ceiling, upper walls, crown molding, window heads.
8. Second lap **tipping down ~30°** for the floor, baseboards, lower furniture.
9. Add a small **local orbit** of the fireplace group and each furniture cluster (parallax for the graphics/splat).
10. Return to start corner. Single clean Ctrl-C. Stop Rig → L2 off.

**Do not:** spin in place, pan while static, dolly straight through, or let any pass run long enough to risk the odom-cutoff.

---

## 5. VERIFICATION GATES (before you trust the capture)

Run these on Shadow *before* processing further — rigor is a constant, not a surprise at the end:

1. **B0 odom-coverage gate:** odom_span / capture_duration ≥ 0.80 per pass. Below that, the odom-cutoff bit — **recapture**, don't process a starved bag.
2. **B2 planar_shell coherence** (run it on the merged cloud): plane thickness ≤ 30 mm (drift), wall orthogonality < 6° (no collapse). This confirms the dimensions are sound *and* prints the true room bbox.
3. **Parallax read-out:** the shell's trajectory report should show real lateral spread on both axes (the orbit worked), not a single-axis dolly.
4. **Eye check:** the coverage map is mostly green; the reference photos of the foreground are sharp (not blurred).

Pass all four → the capture is deliverable-grade and feeds B1. Fail any → the recipe tells you which knob (light, speed, loop, pass length).

---

## 6. THE PERFECT-CAPTURE SPEC (summary)

| | Setting |
|---|---|
| **Environment** | continuous slow movement — walked orbit, pan-while-walking, tip up/down; **never static, never in-place spin** |
| **Motion** | ~0.7 m/s; translate to track + pan to cover + tip for verticals + local orbits for foreground parallax; closed loop |
| **Coverage** | 360° via orbit (not spin); floor-to-ceiling via 3 tilt bands (mid / up / down) |
| **Light** | flat/overcast, expose for room; windows = accepted holes; mirror covered or masked |
| **Dimensions** | ~5×4.5×2.7 m (confirm with shell bbox); orbit ~1.2 m off walls, ~9–10 m loop |
| **Time** | 2 overlapping passes ~45–60 s each (~110 s total recording); split to dodge odom-cutoff + bound drift |
| **Data** | capture 30 fps → **extract ~500 sharp keyframes**; ~1.5–2 GB bag; ~1–2 h Shadow processing |
| **Cost control** | keyframe extraction, not recapture, is the lever; never feed BA/splat all 2200 frames |
| **Gates** | odom-coverage ≥ 80% · shell thickness ≤ 30 mm · walls < 6° · green coverage · sharp foreground |

---
*The capture that serves the new architecture is a slow, closed-loop orbit with tilt bands and foreground parallax, shot in flat light, split into two short overlapping passes, and thinned to ~500 keyframes before processing. It gives the LiDAR its dimensions (a clean planar shell), the photos their graphics (parallax-rich sharp frames), and the wallet a break (bounded GB and processing). The window and mirror are designed-around, not fought.*

---

## 7. EXECUTABLE COMMAND SEQUENCE (terminal-only — no Rig Monitor)

Trigger = **`capture_pointlio_texture.sh`** (the texture-bridge capture: it auto-selects the COMPRESSED
camera topic, gates cloud/imu/camera live, launches Point-LIO `rviz:=false` itself, gates `/aft_mapped_to_init`,
records, and on clean Ctrl-C saves the PCD + prints the next pose-matcher command). PREREQ it assumes: the rig
is already up LEAN (no fusion node) — i.e. `rig_start_lean.sh`.

```bash
# ── PRE-FLIGHT (cold, no L2) ──
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
pgrep -af 'pointlio|ros2 bag|unilidar|gscam|fusion' | grep -v grep || echo "all down ✓"
df -h /mnt/rigdata | tail -1                                  # SSD mounted, has room

# ── 1. POWER THE L2 (physical). Wait ~15s spin-up. ──

# ── 2. START RIG — LEAN (no fusion nodes → full-rate camera) ──
~/rig_start_lean.sh
#   leave this terminal running; wait for "ALL SYSTEMS STARTED".

# ── 3. RIG CHECK — confirm the CAMERA is live (2nd terminal) ──
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
timeout 8 ros2 topic hz /image_raw 2>&1 | grep -m1 average    # camera MUST be live (lean-start guard)
#   (capture_pointlio_texture.sh re-gates cloud/imu/camera itself; confirm camera here first.)

# ── 4. PASS A — capture_pointlio_texture.sh IS the Point-LIO trigger ──
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
~/capture_pointlio_texture.sh
#   → gates streams, launches Point-LIO, gates odom, then records to ~/Desktop/plio_texcap_<stamp>/
#   → execute Pass A motion (§4) → back to start corner → ONE clean Ctrl-C
#   → on Ctrl-C it saves ~/Desktop/scans_<stamp>.pcd and PRINTS the next pose-matcher command.

# ── 5. PASS B — run the trigger again ──
~/capture_pointlio_texture.sh
#   → execute Pass B motion (§4) → back to start corner → ONE clean Ctrl-C

# ── 6. SHUT DOWN ──
#   stop the rig (kill rig_start_lean / Stop Rig), L2 off.

# ── 7. POST (cold) — the script prints this exact line per bag ──
#   pointlio_pose_matcher.py <BAGDIR> --image-topic <IMG_TOPIC> --dump-frames <BAGDIR>/frames
```

**Notes**
- The trigger prefers `/camera/image_raw/compressed` (raw /image_raw can overrun the SD → dropped frames).
- It launches Point-LIO itself — do NOT run a separate Point-LIO launch, and do NOT run the fusion node.
- Clean Ctrl-C only (it SIGINTs Point-LIO so scans.pcd saves; never SIGKILL).
- Outputs per pass: bag `~/Desktop/plio_texcap_<stamp>/`, geometry `~/Desktop/scans_<stamp>.pcd`.
- Then run the verification gates (§5) before processing.
