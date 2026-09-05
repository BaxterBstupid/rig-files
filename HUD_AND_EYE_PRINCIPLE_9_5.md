# *** THE THESIS (the WHY above all the what) ***
THE PRODUCT IS TIME. Not scans, not previz images — TIME SAVED ON SET.
You spend CHEAP rig-time (one person, a quiet afternoon) to save CATASTROPHICALLY EXPENSIVE
set-time (full crew, cast, equipment, daylight, the clock). Trading cheap time for expensive
time IS the business case. Previz with the rig = crane heights, light placement, night-look,
'did I get it' — all DECIDED BEFORE the shooting day, so the day runs short instead of long.
THE IRONY/SPINE: the tool's internal mechanic is TIME (dwell to capture detail) and its external
value is TIME (previz to save shooting hours). Same currency in and out. Every principle below
(eye-is-arbiter, detail=time, HUD-did-I-get-it) is underneath a TIME argument.

---

# THE COVERAGE HUD + THE GOVERNING PRINCIPLE (design thread, 2026-09-05)

## *** GOVERNING PRINCIPLE (belongs at the top of the Master) ***
THE HUMAN EYE IS THE ARBITER. The deliverable is judged by eye, not by a metric.
- Instruments (HUD, numbers, coverage colors) are ADVISORIES that direct the eye's attention.
  They INFORM; they never DECIDE.
- "Looks good" beats "the numbers add up." If it looks good but numbers disagree -> trust the eye.
  If numbers are green but it looks wrong -> trust the eye.
- COROLLARY (applies to how we build + how Claude proposes): stop reaching for numeric gates,
  hard thresholds, automatic "you got it" verdicts. Those try to make a number do the eye's job.
  Every time we did that this project it lied (100%-green HUD, false "you got it", adaptive-
  threshold rabbit holes). Build instruments that POINT THE EYE, not ones that overrule it.

## THE THREE DETAIL SCENARIOS (the range the project must serve):
- LOW  — Ext Barn (establishing): mass/scale/placement. Swap sky, place crane lights, window glow.
         Coarse capture fine. Rig can be fairly static (shot is static).
- MED  — Int Office (wide interior night): SCOPE not detail. Overhead color shift, windows go dark,
         a few added lights. Whole-space coverage, minor surface detail.
- HIGH — Int Barn (busy cluttered interior): every surface interacts with light (wagons, tools,
         beams, plank floor). Kill door light, place practical lanterns, relight surface-by-surface.
         Dense coverage of everything. Takes the MOST time.

## THE KEY INSIGHT — DETAIL = TIME (self-scaling; no shot-type detection needed):
More dwell TIME on a surface = more points = denser = it goes green. The OPERATOR supplies the
detail judgment by HOW LONG they dwell (they know establishing vs. cluttered). The HUD does NOT
need to know the shot type or set adaptive thresholds. It just honestly shows ACCUMULATION.
=> This dissolves the hard problem (adaptive "is this enough for this shot" judgment that kept
   giving false-greens). Time is the control dial; the operator turns it; the reds show where
   time still needs spending.

## THE HUD, RE-SPECIFIED (its TRUE purpose — this is what camera/odom synthesis serves):
- A LIVE ACCUMULATION METER, registered to the real scene (camera + odometry + LiDAR fusion).
  Red = little accumulated here so far -> Green = lots accumulated. RELATIVE, not absolute count.
- Answers "have I spent enough TIME here?" — shown red->green as you work an area.
- "ENOUGH" is the OPERATOR'S call, learned with EXPERIENCE ("how tall is tall / how big is big" —
  not plannable now, develops with use). The HUD informs; the human decides; the EYE confirms.
- The camera/odom synthesis is the SUBSTRATE of this HUD (accumulation shown on the real scene the
  operator is looking at) — NOT the texture bake. This is why the synthesis mattered all along.

## STATUS / BUILD:
- Projection foundation PROVEN (LiDAR lands on real room, 180551 frame 1100, 50.8% on-screen).
- Per-frame density = wrong question (a frame almost always covers what it points at).
- Accumulation-over-time display = NOT YET BUILT. Next brick.
- VALIDATION NEEDS a deliberately-VARIED capture (dwell somewhere, rush elsewhere) so reds/greens
  differentiate by time-spent. 180551 is too uniform to show it.
- Files: hud_projection_test_9_4.py (proven projection), hud_coverage_9_4.py (grid density — 
  revealed the wrong-question + threshold lessons).

## TIME HAS TWO FACES — same currency, both matter:
1. LIVE CONTROL (operator, on set): dwell on a red area until it greens. Moment-to-moment.
2. PRODUCTION BUDGET (planning, before set): capture time is BUDGETABLE per shot, because
   detail-need scales with time-need. Allocate up front by shot complexity:
     - Field / establishing (Ext Barn)  -> MINUTES. Low detail, get in/out.
     - Office / mid (Int Office)         -> MODERATE. Cover scope, don't obsess.
     - Elaborate miniature / cluttered   -> the BIG time investment. High detail earns a long,
       (Int Barn)                           thorough capture — schedule for it, that's expected.
=> It's ONE currency: operator spends time live (HUD reds), producer budgets time up front
   (shot complexity) — SAME time, so they align naturally. No separate systems.
=> BONUS: the RATE reds->green could flag whether the time BUDGET was right ("this interior is
   greening slower than planned -> need more time here") — a heads-up BEFORE the truck leaves.
   That's "did I get it AND did I budget enough?" — answered on set.
