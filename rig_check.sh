#!/bin/bash
# rig_check.sh — COLD WHOLENESS CHECK (read-only diagnostic; the Trouble-Box cold tier).
# Compares the DEPLOYED kiosk stack against the sacred vault manifest (~/rig_originals).
# Reports GREEN/RED per file and NAMES the fix. Does NOT edit, restore, or launch anything.
# Eye-is-arbiter: it tells the truth; the operator decides. Pure cold — no rig, no L2 needed.
#
# WHY THIS EXISTS: on 2026-09-08 map_accumulator.py was missing from the Desktop -> the server
# ran, /data answered 200, but coverage silently never accumulated (ModuleNotFoundError swallowed).
# This check catches exactly that class of failure BEFORE launch, by comparing deployed vs. vault md5.

VAULT="$HOME/rig_originals"
MAN="$VAULT/originals_manifest.txt"

# Where each file must be DEPLOYED (its live location) to map manifest-name -> live-path.
declare -A LIVE=(
  [rig_kiosk_server.py]="$HOME/Desktop/rig_kiosk_server.py"
  [rig_kiosk.html]="$HOME/Desktop/rig_kiosk.html"
  [cloud.html]="$HOME/Desktop/cloud.html"
  [launch.html]="$HOME/Desktop/launch.html"
  [three.min.js]="$HOME/Desktop/three.min.js"
  [map_accumulator.py]="$HOME/Desktop/map_accumulator.py"
  [point_lio_capture.sh]="$HOME/point_lio_capture.sh"
  [rig_start_lean.sh]="$HOME/rig_start_lean.sh"
  [rig_stop.sh]="$HOME/rig_stop.sh"
  [restore_kiosk.sh]="$HOME/restore_kiosk.sh"
)

# Which files are MANDATORY for the coverage kiosk to work (RED = don't launch) vs advisory.
declare -A CRITICAL=(
  [rig_kiosk_server.py]=1 [rig_kiosk.html]=1 [cloud.html]=1
  [launch.html]=1 [three.min.js]=1 [map_accumulator.py]=1
)

if [ ! -f "$MAN" ]; then
  echo "!! NO MANIFEST at $MAN — run the vault setup first. Cannot verify. !!"
  exit 2
fi

echo "=== RIG CHECK — deployed stack vs. sacred vault ($VAULT) ==="
allgood=1; crit_bad=0
while read -r want name; do
  [ -z "$name" ] && continue
  live="${LIVE[$name]}"
  crit="${CRITICAL[$name]:-0}"
  tag=$([ "$crit" = 1 ] && echo "[CRITICAL]" || echo "[advisory]")
  if [ -z "$live" ]; then
    echo "  ? $name — no live path mapped (skipped)"; continue
  fi
  if [ ! -f "$live" ]; then
    echo "  RED  $tag $name — MISSING at $live"
    echo "         FIX: cp $VAULT/$name $live"
    allgood=0; [ "$crit" = 1 ] && crit_bad=1
    continue
  fi
  got=$(md5sum "$live" | cut -d' ' -f1)
  if [ "$got" = "$want" ]; then
    echo "  GREEN $tag $name"
  else
    echo "  RED  $tag $name — WRONG VERSION (deployed $got, want $want)"
    echo "         FIX: cp $VAULT/$name $live   (restores the known-good original)"
    allgood=0; [ "$crit" = 1 ] && crit_bad=1
  fi
done < <(grep -v '^#' "$MAN")

echo "=== VERDICT ==="
if [ "$allgood" = 1 ]; then
  echo "  ALL GREEN — deployed stack matches the vault. Safe to launch the kiosk."
elif [ "$crit_bad" = 1 ]; then
  echo "  RED (CRITICAL) — a mandatory kiosk file is missing/wrong. Do NOT launch until fixed (see FIX lines)."
else
  echo "  AMBER — only advisory files differ; kiosk will work, but review the FIX lines."
fi
