#!/bin/bash
# camera_unwedge_9_4.sh
# PURPOSE: Clear the recurring gscam HANG (the "camera 0 Hz" failure, Master "top of hardware
#   queue"). Symptom: gscam running + /dev/video0 present + /image_raw topic present, but NO
#   frames flowing (ros2 topic hz silent). Node is up but the GStreamer pipeline is wedged.
# PROVEN 2026-09-04: killed wedged gscam (PIDs 22919/22921), relaunched, frames resumed at 25.9 Hz.
# NOTE: standalone relaunch (outside rig_start.sh). GSCAM_CONFIG copied EXACTLY from rig_start.sh
#   line 78. Kills ONLY gscam — does not touch LiDAR/Point-LIO. Safe mid-session.
# DIAGNOSIS FIRST (confirm it's a wedge, not dead hardware): pgrep gscam (running?),
#   ls /dev/video0 (device present?), lsusb | grep 0c45:0578 (USB enumerated?). If all yes but
#   topic silent -> wedge -> run this. If device/USB missing -> hardware/cable, NOT this.
source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash 2>/dev/null
pkill -9 -f gscam; sleep 2
pgrep -af gscam | grep -v grep || echo "gscam cleared"
export GSCAM_CONFIG="v4l2src device=/dev/video0 do-timestamp=true ! image/jpeg,width=1920,height=1200,framerate=30/1 ! jpegparse ! nvv4l2decoder mjpeg=1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert"
ros2 run gscam gscam_node --ros-args -r /camera/image_raw:=/image_raw -r /camera/camera_info:=/camera_info > ~/Desktop/camera_relaunch.log 2>&1 &
sleep 5
timeout 8 ros2 topic hz /image_raw 2>&1 | grep -m1 average || echo "STILL SILENT — check ~/Desktop/camera_relaunch.log"
