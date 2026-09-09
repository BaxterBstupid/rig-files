#!/bin/bash
# setup_rig_originals.sh — create the ORIGINALS VAULT: a stable, sweep-proof folder holding
# pristine known-good copies of every load-bearing rig file, plus a manifest of their md5s.
# ADDITIVE + SAFE: this only COPIES existing files INTO the vault. It never edits, moves, or
# deletes anything. Run it once to establish the vault; re-run to refresh a deliberately-updated original.
#
# THE RULE THIS ENFORCES: anything to be rewritten/edited is CLONED from the vault, edited as a
# new file, tested, deployed. The vault original is never touched — it is the md5-verified fallback.
#
# Location: ~/rig_originals  (HOME, NOT the Desktop — the Desktop gets swept daily; the vault must not.)

VAULT="$HOME/rig_originals"
mkdir -p "$VAULT"
echo "=== ORIGINALS VAULT: $VAULT ==="

# The load-bearing files (edit this list as the canonical set grows). Sources are where each
# currently lives; we COPY into the vault only if the source exists (never fail on a missing one).
declare -A SRC=(
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

MAN="$VAULT/originals_manifest.txt"
echo "# ORIGINALS MANIFEST - canonical known-good files + md5s. Generated $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$MAN"
echo "# These ARE the originals. Restore/clone FROM here. Verify AGAINST these md5s." >> "$MAN"

for name in "${!SRC[@]}"; do
  src="${SRC[$name]}"
  if [ -f "$src" ]; then
    cp -n "$src" "$VAULT/$name" 2>/dev/null   # -n = never overwrite an existing vault copy (safety)
    if [ ! -f "$VAULT/$name" ]; then cp "$src" "$VAULT/$name"; fi
    m=$(md5sum "$VAULT/$name" | cut -d' ' -f1)
    printf "%s  %s\n" "$m" "$name" >> "$MAN"
    echo "  vaulted: $name ($m)"
  else
    echo "  !! source not found (skipped): $name  <- $src"
  fi
done

echo "=== manifest written: $MAN ==="
cat "$MAN"
echo "=== NOTE: cp used -n (no-clobber): an existing vault original is NEVER overwritten by a re-run."
echo "    To deliberately update an original: remove the vault copy first, then re-run. Intentional only."
