#!/usr/bin/env bash
set -o pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/hiar_logs"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/launch_${STAMP}.log"
WEB_LOG_FILE="$LOG_DIR/web_${STAMP}.log"
NODES_LIST="esp32_interface obstacle_detector robot_supervisor navigation_decision hmi_request_receiver hmi_websocket_bridge"
mkdir -p "$LOG_DIR"

if ! ls /dev/ttyUSB0 >/dev/null 2>&1; then
    echo "⚠️ AVERTISSEMENT : ESP32 introuvable (/dev/ttyUSB0)."
fi

# Libérer les ports 5000 (WebSocket) et 5001 (Web) si occupés
for port in 5000 5001; do
    PIDS="$(ss -ltnp "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 || true)"
    for pid in $PIDS; do kill "$pid" 2>/dev/null || true; done
    for pid in $PIDS; do kill -9 "$pid" 2>/dev/null || true; done
done

# Arrêter proprement les anciens processus éventuels
ps aux | grep -E 'app\.py|hiar_robot\.launch\.py|install/hospital_robot/lib/hospital_robot' | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
sleep 1

source /opt/ros/humble/setup.bash
source "$PROJECT_ROOT/install/setup.bash"

# Charger les variables d'environnement locales (clés API Gemini, jeton staff, etc.)
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

echo "=========================================================="
echo "🤖 Démarrage des nœuds ROS 2 + Serveur Web HIAR..."
echo "=========================================================="

setsid ros2 launch hospital_robot hiar_robot.launch.py >"$LOG_FILE" 2>&1 < /dev/null &
LAUNCH_PID=$!
ln -sf "$LOG_FILE" "$LOG_DIR/latest.log"

PORT=5001 setsid "$PROJECT_ROOT/web_interface/run_hiar.sh" >"$WEB_LOG_FILE" 2>&1 < /dev/null &
WEB_PID=$!
ln -sf "$WEB_LOG_FILE" "$LOG_DIR/web_latest.log"

cleanup() {
    trap - EXIT
    echo
    echo "🛑 Arrêt complet de HIAR (ROS 2 + Serveur Web)..."
    kill -INT -- "-$LAUNCH_PID" 2>/dev/null || true
    kill -TERM -- "-$WEB_PID" 2>/dev/null || true
    sleep 1
    ps aux | grep -E 'app\.py|hiar_robot\.launch\.py|install/hospital_robot/lib/hospital_robot' | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
    echo "✅ Tous les processus HIAR sont arrêtés."
}
trap cleanup EXIT
trap 'exit 130' INT TERM

echo "⏳ Vérification des nœuds ROS 2..."
for _ in $(seq 1 12); do
    NODES="$(ros2 node list --no-daemon 2>/dev/null || true)"
    MISSING=0
    for n in $NODES_LIST; do
        echo "$NODES" | grep -q "/$n\$" || MISSING=1
    done
    [ "$MISSING" -eq 0 ] && break
    sleep 1
done

for n in $NODES_LIST; do
    if echo "$NODES" | grep -q "/$n\$"; then
        echo "  [OK] $n"
    else
        echo "  [..] $n (démarrage en cours)"
    fi
done

WIFI_IP="$(ip -4 -o addr show wlan0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1 || true)"
echo ""
echo "📡 WebSocket HMI : ws://${WIFI_IP:-192.168.10.2}:5000/ws"
echo "🌐 Web Médecin   : http://${WIFI_IP:-192.168.10.2}:5001/"
echo "📄 Logs bruts    : $LOG_DIR/latest.log  |  $LOG_DIR/web_latest.log"
echo "🛑 Appuyez sur Ctrl+C pour tout arrêter proprement."
echo "=========================================================="
echo ""

python3 "$PROJECT_ROOT/scripts/hiar_log_monitor.py" \
    --ros-log "$LOG_FILE" \
    --web-log "$WEB_LOG_FILE" \
    --lines 100 \
    "$@"
