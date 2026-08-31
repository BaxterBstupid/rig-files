#!/bin/bash
# RIG kiosk launcher: start server (real ROS), wait until it answers, open the kiosk in its OWN
# Firefox process (separate profile + --no-remote) and record its PID so Exit can kill just it.
cd "$HOME/Desktop"

source /opt/ros/humble/setup.bash 2>/dev/null
source "$HOME/ros2_ws/install/setup.bash" 2>/dev/null

# start the server only if it's not already running
if ! pgrep -f rig_kiosk_server.py >/dev/null; then
    python3 "$HOME/Desktop/rig_kiosk_server.py" >"$HOME/Desktop/kiosk.log" 2>&1 &
fi

# wait (up to ~15s) until the server actually answers
for i in $(seq 1 30); do
    if curl -s -o /dev/null http://localhost:8080/data; then break; fi
    sleep 0.5
done

# dedicated kiosk profile: makes the kiosk a SEPARATE Firefox process (not merged into your
# normal Firefox), so it has its own PID and its own session. Seed it once to skip first-run nags.
PROFILE="$HOME/.rigkiosk_profile"
if [ ! -d "$PROFILE" ]; then
    mkdir -p "$PROFILE"
    cat > "$PROFILE/user.js" <<'JSEOF'
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("browser.sessionstore.resume_from_crash", false);
JSEOF
fi

# launch the kiosk in the background and RECORD ITS PID for exit_kiosk
firefox --no-remote --profile "$PROFILE" --kiosk http://localhost:8080 &
echo $! > "$HOME/.kiosk_firefox.pid"
