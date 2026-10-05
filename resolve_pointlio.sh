#!/bin/bash
# resolve_pointlio.sh (v2: records /cloud_registered) — OFFLINE re-solve of a raw fusioncap bag through Point-LIO on the Jetson.
# ADR-004 D2/D3. Rig OFF. Nothing else running (no driver, no camera, no kiosk, no browser).
#
#   ./resolve_pointlio.sh <BAG_DIR> <MODE> [RATE]
#     MODE:  stock          = the deployed launch exactly (use_imu_as_input False, init_map_size 10)
#            imuin          = ONE change: use_imu_as_input True   (gyro drives rotation, LiDAR corrects)
#            imuin_map1000  = imuin + init_map_size 1000          (HKU maintainer's startup-drift advice)
#     RATE:  bag replay rate (default 0.5 — half speed so an idle Jetson never falls behind)
#
# Modeled on point_lio_capture.sh (same launch, same PCD path, same group-SIGINT + fresh-mtime
# proof). Differences: input is `ros2 bag play` instead of the live sensor; a small bag of the
# RE-SOLVED /aft_mapped_to_init (+ the replayed /unilidar/imu) is recorded alongside so
# bag_health.py can compare gyro vs the NEW odometry on Shadow.
#
# OUTPUT (next to the input bag, under RECORD_BASE):
#   resolve_<bagname>_<mode>_scans.pcd      the re-solved cloud  -> Taildrop to Shadow -> top_down.py
#   resolve_<bagname>_<mode>/               bag: /aft_mapped_to_init + /unilidar/imu + /cloud_registered -> bag_health.py, TSDF
#   /tmp/resolve_<mode>.log                 Point-LIO's own log (init line, loop-back warnings, etc.)
#
# The variant launches are GENERATED from the deployed launch file by sed, into the package's
# install share dir, so `ros2 launch point_lio <variant>` finds them. They are NOT blessed and
# will vanish on a rebuild — by design: the deployed launch is never edited.

set -u
BAGDIR="${1:?usage: resolve_pointlio.sh <BAG_DIR> <stock|imuin|imuin_map1000> [RATE]}"
MODE="${2:?usage: resolve_pointlio.sh <BAG_DIR> <stock|imuin|imuin_map1000> [RATE]}"
RATE="${3:-0.5}"
BAGDIR="${BAGDIR%/}"
BAGNAME="$(basename "$BAGDIR")"

PLIO_WS="$HOME/point_lio_ws"
PCD_SRC="$PLIO_WS/src/point_lio_ros2/PCD/scans.pcd"
LAUNCH_DIR="$PLIO_WS/install/point_lio/share/point_lio/launch"
STOCK_LAUNCH="$LAUNCH_DIR/mapping_unilidar_l2.launch.py"
if mountpoint -q /mnt/rigdata; then RECORD_BASE="/mnt/rigdata"; else RECORD_BASE="$HOME/Desktop"; fi
OUT_PCD="$RECORD_BASE/resolve_${BAGNAME}_${MODE}_scans.pcd"
OUT_BAG="$RECORD_BASE/resolve_${BAGNAME}_${MODE}"
LOG="/tmp/resolve_${MODE}.log"

[ -d "$BAGDIR" ] || { echo "!!! bag dir not found: $BAGDIR"; exit 1; }
[ -f "$STOCK_LAUNCH" ] || { echo "!!! deployed launch not found: $STOCK_LAUNCH"; exit 1; }
[ -e "$OUT_BAG" ] && { echo "!!! output bag already exists: $OUT_BAG (remove or rename it first)"; exit 1; }

set +u
source ~/ros2_ws/install/setup.bash 2>/dev/null
source ~/point_lio_ws/install/setup.bash
set -u

# --- pick / generate the launch file for this MODE (deployed launch is never edited) ---
case "$MODE" in
  stock)
    LAUNCH="mapping_unilidar_l2.launch.py" ;;
  imuin)
    LAUNCH="mapping_unilidar_l2_imuin.launch.py"
    sed -e "s/'use_imu_as_input': False/'use_imu_as_input': True/" \
        "$STOCK_LAUNCH" > "$LAUNCH_DIR/$LAUNCH" ;;
  imuin_map1000)
    LAUNCH="mapping_unilidar_l2_imuin_map1000.launch.py"
    sed -e "s/'use_imu_as_input': False/'use_imu_as_input': True/" \
        -e "s/'init_map_size': 10,/'init_map_size': 1000,/" \
        "$STOCK_LAUNCH" > "$LAUNCH_DIR/$LAUNCH" ;;
  *) echo "!!! unknown MODE '$MODE' (stock|imuin|imuin_map1000)"; exit 1 ;;
esac
echo "=== MODE $MODE -> launch $LAUNCH"
grep -E "use_imu_as_input|init_map_size|filter_size" "$LAUNCH_DIR/$LAUNCH" | sed 's/^/    /'

# --- clean slate: nothing else may be feeding Point-LIO ---
echo "=== Clean slate ==="
pkill -f "pointlio_mapping" 2>/dev/null && echo "    killed a lingering pointlio_mapping" || true
pkill -x "rviz2" 2>/dev/null && echo "    killed a lingering rviz2" || true
if pgrep -f "unitree_lidar_ros2_node|rig_camera_compressed|rig_kiosk_server|ros2 bag record" >/dev/null; then
    echo "!!! live rig processes are running (driver/camera/kiosk/recorder). Stop them first — the"
    echo "!!! re-solve must see ONLY the replayed bag. Aborting."
    exit 1
fi
sleep 1
PCD_OLD_MTIME="$(stat -c %Y "$PCD_SRC" 2>/dev/null || echo 0)"

# --- launch Point-LIO (own process group, no RViz) ---
echo "=== Launching Point-LIO offline ($LAUNCH, rviz:=false) -> $LOG"
setsid ros2 launch point_lio "$LAUNCH" rviz:=false >"$LOG" 2>&1 &
PLIO_PID=$!
PLIO_PGID="$(ps -o pgid= -p "$PLIO_PID" | tr -d ' ')"
sleep 6

# --- record the RE-SOLVED odometry (+ replayed IMU) for bag_health ---
# /cloud_registered = Point-LIO's per-frame registered scans (world frame): the input TSDF / GS-SDF
# geometry needs (FORWARD_PLAN D6a). ~1.4 MB/s; fine.
setsid ros2 bag record -o "$OUT_BAG" /aft_mapped_to_init /unilidar/imu /cloud_registered >/tmp/resolve_rec.log 2>&1 &
REC_PID=$!
REC_PGID="$(ps -o pgid= -p "$REC_PID" | tr -d ' ')"
sleep 2

# --- replay the raw bag (cloud + imu only; the camera topic is irrelevant to geometry) ---
echo "=== Replaying $BAGNAME at rate $RATE (cloud + imu only) ==="
ros2 bag play "$BAGDIR" --rate "$RATE" --topics /unilidar/cloud /unilidar/imu
echo "=== Replay finished; letting Point-LIO drain its buffer (15 s) ==="
sleep 15
echo "--- init line (from log) ---"; grep -m1 "Initializing: 100" "$LOG" || echo "  (init line not seen)"
echo "--- warnings (count) ---"; grep -ciE "loop back|clear buffer|degenerat|no point" "$LOG" || true

# --- STOP in the proven order: recorder -> Point-LIO (wait for the PCD save) -> verify fresh ---
echo "=== STOP 1/3: stopping the odom recorder ==="
kill -INT -- "-${REC_PGID}" 2>/dev/null; wait "$REC_PID" 2>/dev/null
echo "=== STOP 2/3: SIGINT to Point-LIO group; waiting for the PCD save ==="
kill -INT -- "-${PLIO_PGID}" 2>/dev/null; wait "$PLIO_PID" 2>/dev/null; sleep 2
echo "=== STOP 3/3: verifying the PCD saved FRESH ==="
PCD_NEW_MTIME="$(stat -c %Y "$PCD_SRC" 2>/dev/null || echo 0)"
if [ "$PCD_NEW_MTIME" -gt "$PCD_OLD_MTIME" ]; then
    cp "$PCD_SRC" "$OUT_PCD"
    echo "=== SUCCESS ==="
    echo "   PCD  [ok]  $OUT_PCD  ($(stat -c %s "$OUT_PCD") bytes, md5 $(md5sum "$OUT_PCD" | cut -c1-8)…)"
    echo "   ODOM [ok]  $OUT_BAG"
    echo "   next: tailscale file cp $OUT_PCD shadow-qinc8ae6:   -> top_down.py on Shadow"
else
    echo "=== !!! PCD DID NOT SAVE FRESH !!! ==="
    echo "   Point-LIO did not write $PCD_SRC this run. Read $LOG (did it initialize? did it get frames?)."
    echo "   ODOM bag (may still be useful): $OUT_BAG"
    exit 1
fi
