#!/bin/bash
# ARDUCAM CONTROL PAD launcher: bring up the camera node (if it isn't already
# running) + the pad server, wait until the server answers, then open the pad
# fullscreen in its own Firefox. The camera node uses the SAME invocation as
# rig_start_compressed.sh, and is started ONLY if not already running — so it
# never double-opens /dev/arducam when the full rig is already up.
cd "$HOME/Desktop"

source /opt/ros/humble/setup.bash 2>/dev/null
source "$HOME/ros2_ws/install/setup.bash" 2>/dev/null

# --- camera node (needed for preview + record): start ONLY if not already running ---
if ! pgrep -f rig_camera_compressed >/dev/null; then
    mkdir -p "$HOME/rig_logs"
    for p in "$HOME/rig_camera_compressed.py" "$HOME/Desktop/rig_camera_compressed.py"; do
        if [ -f "$p" ]; then
            echo "[camctl_launch] starting camera node: $p" >> "$HOME/rig_logs/camera.log"
            python3 "$p" >> "$HOME/rig_logs/camera.log" 2>&1 &
            break
        fi
    done
fi

# --- pad server: start only if not already running ---
if ! pgrep -f camctl_server.py >/dev/null; then
    python3 "$HOME/Desktop/camctl_server.py" >"$HOME/Desktop/camctl.log" 2>&1 &
fi

# --- wait (up to ~15s) for the pad server to answer ---
for i in $(seq 1 30); do
    if curl -s -o /dev/null http://localhost:8081/ctrls; then break; fi
    sleep 0.5
done

# --- give the camera node a moment so the live preview is up when the pad opens ---
sleep 3

# --- dedicated Firefox profile: own PID/session, coexists with the :8080 kiosk ---
PROFILE="$HOME/.camctl_profile"
if [ ! -d "$PROFILE" ]; then
    mkdir -p "$PROFILE"
    cat > "$PROFILE/user.js" <<'JSEOF'
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("browser.sessionstore.resume_from_crash", false);
JSEOF
fi

firefox --no-remote --profile "$PROFILE" --kiosk http://localhost:8081 &
echo $! > "$HOME/.camctl_firefox.pid"
