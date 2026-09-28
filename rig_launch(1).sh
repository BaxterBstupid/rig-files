#!/bin/bash
# rig_launch.sh — the LAUNCHER: cold-check the stack + camera, then (only if whole) guide to bring-up.
# ADDITIVE, read-only-gating: it runs rig_check.sh and cam_preflight_gate.sh and reports; it does NOT
# auto-heal, does NOT edit anything. Eye-is-arbiter: RED -> it stops and shows the fix; GREEN -> proceeds.
# Works on the Jetson directly OR driven from the PC over SSH (same script, same truth).
#
# 2026-09-28 (Master 20.13.72 triad-link): three linkage fixes so the triad runs as one whole —
#   (1) Stage 1 now blocks ONLY on RED (CRITICAL); GREEN or AMBER (advisory-only) PROCEEDS
#       (the old "ALL GREEN"-only test hard-stopped on any advisory diff, e.g. an unblessed
#        point_lio_capture.sh edit).
#   (2) NEW Stage 1.5 — Arducam device gate (cam_preflight_gate.sh): hard-block if /dev/arducam
#       is not streaming (catches the Mode-2 / USB re-enumeration stall that records 0 frames).
#   (3) Stage 2 now routes to rig_start_compressed.sh (the /dev/arducam compressed pipeline) —
#       NOT rig_start_lean.sh (raw path: wrong topic, recorder choke, /dev/arducam fix unused).
#
# WHAT IT DOES NOT DO (deliberately): it does not power the L2 (physical), does not start a capture,
# does not walk. It gets you to a VERIFIED-WHOLE, camera-live, launchable rig. The capture is the operator's job.

CHECK="$HOME/rig_check.sh"
CAMGATE="$HOME/cam_preflight_gate.sh"
VAULT="$HOME/rig_originals"

echo "########################################################"
echo "#  RIG LAUNCH  —  pre-flight (stack + camera) then rig  #"
echo "########################################################"

# ---- STAGE 1 (COLD): stack wholeness ----
echo
echo ">>> STAGE 1: stack wholeness check (cold — no rig needed)"
if [ ! -f "$CHECK" ]; then
  echo "  !! $CHECK not found. Cannot verify the stack. Aborting."
  exit 2
fi
CHECK_OUT="$(bash "$CHECK")"
echo "$CHECK_OUT"
if echo "$CHECK_OUT" | grep -q "RED (CRITICAL)"; then
  echo
  echo ">>> STAGE 1 FAILED — a MANDATORY file is missing/wrong (see RED [CRITICAL] lines + FIX above)."
  echo "    The launcher STOPS here. Fix the RED CRITICAL file(s), then re-run rig_launch.sh."
  echo "    (Tip: restore_kiosk.sh / cp from $VAULT — the FIX lines name the exact command.)"
  exit 1
elif echo "$CHECK_OUT" | grep -q "ALL GREEN"; then
  echo
  echo ">>> STAGE 1 PASSED — stack is whole (ALL GREEN)."
else
  echo
  echo ">>> STAGE 1 PASSED (AMBER) — only advisory files differ; safe to bring the rig up."
  echo "    (Review any advisory FIX lines above when convenient — no mandatory file is broken.)"
fi

# ---- STAGE 1.5 (COLD): Arducam device gate — camera is USB-powered, testable before the L2 ----
echo
echo ">>> STAGE 1.5: Arducam device gate (cold — camera is USB-powered, no L2 needed)"
if [ ! -f "$CAMGATE" ]; then
  echo "  !! $CAMGATE not found — cannot verify the camera. Aborting."
  echo "     (This gate catches the Arducam Mode-2 / USB re-enumeration stall that silently"
  echo "      records 0 camera frames. Do NOT skip it — it is the point of this launcher.)"
  exit 3
fi
if bash "$CAMGATE"; then
  echo ">>> STAGE 1.5 PASSED — Arducam live and streaming at /dev/arducam."
else
  echo
  echo ">>> STAGE 1.5 FAILED — the Arducam is NOT streaming (Mode-2 stall / re-enum)."
  echo "    The launcher STOPS here. Fix per the [cam-preflight] FIX lines above, then re-run."
  echo "    A capture now would record 0 camera frames."
  exit 1
fi

# ---- STAGE 2 (WARM): is the rig up? (advisory — the operator powers the L2 physically) ----
echo
echo ">>> STAGE 2: is the rig responding? (power the L2 + run rig_start_compressed.sh if not)"
RIG="192.168.0.204"     # the Jetson serves the kiosk here; from the PC this is the target
# When run ON the Jetson, localhost works; from the PC, use the IP. Try localhost first, then IP.
served=""
for host in "localhost" "$RIG"; do
  if curl -s -m 3 "http://$host:8080/data" >/dev/null 2>&1; then served="$host"; break; fi
done
if [ -n "$served" ]; then
  echo "  GREEN — kiosk server responding at http://$served:8080"
  # show live sensor truth so the operator sees the warm state
  curl -s -m 3 "http://$served:8080/data" | head -c 160; echo
else
  echo "  AMBER — no kiosk server answering yet."
  echo "    If the rig is up: launch the kiosk server (rig_kiosk_launch.sh) and re-run."
  echo "    If the rig is down: power the L2, run rig_start_compressed.sh, then rig_kiosk_launch.sh."
  echo "    (Stack + camera verified — you're clear to bring the rig up.)"
fi

echo
echo ">>> READY. Stack verified whole + Arducam live. Open the kiosk at:  http://${served:-$RIG}:8080/kiosk"
echo "    Capture (terminal): run  point_lio_capture.sh   (records cloud + odom + imu + compressed cam)."
echo "    Kiosk MAP tab shows coverage filling as you WALK."
