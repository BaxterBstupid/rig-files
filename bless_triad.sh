#!/bin/bash
# bless_triad.sh — one-shot vault bless for the compressed capture pipeline (Master 20.13.72).
# Brings the sacred vault + manifest up to date so rig_check.sh COVERS the files you actually
# capture with. Idempotent (re-run just refreshes md5s).
#   BLESSES (deployed -> vault, record md5): rig_check.sh, rig_start_compressed.sh,
#     rig_camera_compressed.py, cam_preflight_gate.sh, rig_launch.sh, RigPreflight.desktop.
#   RESTORES (vault -> deployed): restore_kiosk.sh (deployed had drifted from the blessed copy).
#   DOES NOT TOUCH: point_lio_capture.sh (bless it AFTER the gate edit + the capture proves out).
set -u
VAULT="$HOME/rig_originals"
MAN="$VAULT/originals_manifest.txt"
[ -f "$MAN" ] || { echo "!! no manifest at $MAN — abort"; exit 2; }

cp "$MAN" "$MAN.bak_$(date +%Y%m%d_%H%M%S)"
echo "manifest backed up."

# ---- BLESS: deployed -> vault, then record the deployed md5 in the manifest ----
declare -A BLESS=(
  [rig_check.sh]="$HOME/rig_check.sh"
  [rig_start_compressed.sh]="$HOME/rig_start_compressed.sh"
  [rig_camera_compressed.py]="$HOME/rig_camera_compressed.py"
  [cam_preflight_gate.sh]="$HOME/cam_preflight_gate.sh"
  [rig_launch.sh]="$HOME/rig_launch.sh"
  [RigPreflight.desktop]="$HOME/Desktop/RigPreflight.desktop"
)
for name in "${!BLESS[@]}"; do
  live="${BLESS[$name]}"
  if [ ! -f "$live" ]; then echo "  SKIP $name — not found at $live"; continue; fi
  cp "$live" "$VAULT/$name"
  new=$(md5sum "$live" | cut -d' ' -f1)
  awk -v n="$name" '$2 != n' "$MAN" > "$MAN.tmp"
  printf '%s  %s\n' "$new" "$name" >> "$MAN.tmp"
  mv "$MAN.tmp" "$MAN"
  echo "  blessed  $name  ($new)"
done

# ---- RESTORE: restore_kiosk.sh (deployed drifted; the vault holds the known-good) ----
if [ -f "$VAULT/restore_kiosk.sh" ]; then
  cp "$VAULT/restore_kiosk.sh" "$HOME/restore_kiosk.sh"
  echo "  restored restore_kiosk.sh  (vault -> deployed)"
fi

echo
echo "=== re-running rig_check.sh ==="
bash "$HOME/rig_check.sh"
