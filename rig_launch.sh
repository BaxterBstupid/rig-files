#!/bin/bash
# rig_launch.sh — the LAUNCHER: cold-check the stack, then (only if whole) guide to the kiosk.
# ADDITIVE, read-only-gating: it runs rig_check.sh and reports; it does NOT auto-heal, does NOT
# edit anything. Eye-is-arbiter: RED -> it stops and shows the fix; GREEN -> it proceeds.
# Works on the Jetson directly OR driven from the PC over SSH (same script, same truth).
#
# WHAT IT DOES NOT DO (deliberately): it does not power the L2 (physical), does not start a capture,
# does not walk. It gets you to a VERIFIED-WHOLE, launchable kiosk. The capture is the operator's job.

CHECK="$HOME/rig_check.sh"
VAULT="$HOME/rig_originals"

echo "########################################################"
echo "#  RIG LAUNCH  —  pre-flight then kiosk                 #"
echo "########################################################"

# ---- STAGE 1 (COLD): stack wholeness ----
echo
echo ">>> STAGE 1: stack wholeness check (cold — no rig needed)"
if [ ! -x "$CHECK" ] && [ ! -f "$CHECK" ]; then
  echo "  !! $CHECK not found. Cannot verify the stack. Aborting."
  exit 2
fi
bash "$CHECK"
check_rc=$?
# rig_check.sh prints its own verdict; we re-derive pass/fail from a re-run grep (simple + robust)
if bash "$CHECK" | grep -q "ALL GREEN"; then
  echo
  echo ">>> STAGE 1 PASSED — stack is whole."
else
  echo
  echo ">>> STAGE 1 FAILED — the stack is NOT whole (see RED lines + FIX above)."
  echo "    The launcher STOPS here. Fix the RED file(s), then re-run rig_launch.sh."
  echo "    (Tip: restore_kiosk.sh / cp from $VAULT — the FIX lines name the exact command.)"
  exit 1
fi

# ---- STAGE 2 (WARM): is the rig up? (advisory — the operator powers the L2 physically) ----
echo
echo ">>> STAGE 2: is the rig responding? (power the L2 + run rig_start_lean.sh if not)"
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
  echo "    If the rig is down: power the L2, run rig_start_lean.sh, then rig_kiosk_launch.sh."
  echo "    (Stack is verified whole — you're clear to bring the rig up.)"
fi

echo
echo ">>> READY. Stack verified whole. Open the kiosk at:  http://${served:-$RIG}:8080/kiosk"
echo "    Then: MAP tab -> start a capture -> WALK -> watch coverage fill."
