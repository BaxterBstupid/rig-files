#!/bin/bash
# Close the kiosk from anywhere (SSH from the PC, or a terminal). Needs no server.
PID=$(cat "$HOME/.kiosk_firefox.pid" 2>/dev/null)
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" && echo "kiosk closed (pid $PID)"; exit 0
fi
# pidfile stale/missing -> close any Firefox using the kiosk profile, else any Firefox
pkill -f "rigkiosk_profile" 2>/dev/null && { echo "kiosk closed (by profile)"; exit 0; }
pkill -f "/usr/lib/firefox/firefox" && echo "closed all firefox (fallback)" || echo "no kiosk/firefox running"
