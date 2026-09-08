#!/bin/bash
# restore_kiosk.sh — restore the FULL kiosk stack to the Desktop after daily-cleanup sweeps it.
# The kiosk needs SIX files on the Desktop next to the server, or it silently breaks:
#   rig_kiosk_server.py  - the engine
#   rig_kiosk.html       - the face (served at /kiosk)
#   cloud.html           - the 3D SCAN/MAP/MESH viewer
#   launch.html          - the launcher landing page (served at /)
#   three.min.js         - three.js (3D render lib; missing = blank panel, "THREE undefined")
#   map_accumulator.py   - the coverage accumulator (missing = /cloud_registered dropped on
#                          ModuleNotFoundError -> MAP panel never fills red/green)
# History: three.min.js, launch.html, AND map_accumulator.py have each silently broken the kiosk
# when swept. This restores all six from the newest dated folder in one shot.
set -e
SRC="${1:-$HOME/Desktop/ALL FILES Sept 7}"   # pass the newest dated folder as arg 1 if different
DST="$HOME/Desktop"
echo "restoring kiosk stack from: $SRC"
for f in rig_kiosk.html cloud.html launch.html three.min.js map_accumulator.py; do
  if [ -f "$SRC/$f" ]; then cp "$SRC/$f" "$DST/$f" && echo "  OK  $f"; else echo "  !! MISSING in source: $f"; fi
done
# server: prefer the REGDIAG (throttled + /regdiag) version if present, else the dated one
if [ -f "$HOME/Desktop/rig_kiosk_server_REGDIAG.py" ]; then
  cp "$HOME/Desktop/rig_kiosk_server_REGDIAG.py" "$DST/rig_kiosk_server.py" && echo "  OK  rig_kiosk_server.py (REGDIAG)"
elif [ -f "$SRC/rig_kiosk_server.py" ]; then
  cp "$SRC/rig_kiosk_server.py" "$DST/rig_kiosk_server.py" && echo "  OK  rig_kiosk_server.py (dated)"
fi
echo "=== verify all 6 present on Desktop ==="
ok=1
for f in rig_kiosk_server.py rig_kiosk.html cloud.html launch.html three.min.js map_accumulator.py; do
  if [ -f "$DST/$f" ]; then echo "  present: $f"; else echo "  MISSING: $f"; ok=0; fi
done
[ $ok -eq 1 ] && echo "=== kiosk stack COMPLETE - safe to launch ===" || echo "=== INCOMPLETE - fix missing files before launch ==="
