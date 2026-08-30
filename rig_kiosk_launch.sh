#!/bin/bash
# RIG kiosk launcher: start server (real ROS mode), wait until it answers, open fullscreen Firefox.
cd "$HOME/Desktop"

# 1. source ROS so the real reader works (matches the server's own run instructions)
source /opt/ros/humble/setup.bash 2>/dev/null
source "$HOME/ros2_ws/install/setup.bash" 2>/dev/null

# 2. start the server only if it's not already running
if ! pgrep -f rig_kiosk_server.py >/dev/null; then
    python3 "$HOME/Desktop/rig_kiosk_server.py" >"$HOME/Desktop/kiosk.log" 2>&1 &
fi

# 3. wait (up to ~15s) until the server actually answers, then launch the browser
for i in $(seq 1 30); do
    if curl -s -o /dev/null http://localhost:8080/data; then break; fi
    sleep 0.5
done

# 4. open the kiosk fullscreen
firefox --kiosk http://localhost:8080
