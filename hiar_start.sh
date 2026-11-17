#!/usr/bin/env bash
set -o pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/hiar_logs"
LOG_FILE="$LOG_DIR/launch_$(date +%Y%m%d_%H%M%S).log"
NODE_PATTERN="hospital_robot"
NODES_LIST="esp32_interface obstacle_detector robot_supervisor navigation_decision hmi_request_receiver hmi_websocket_bridge"
mkdir -p "$LOG_DIR"

if ! ls /dev/ttyUSB0 >/dev/null 2>&1; then
    echo "⚠️ AVERTISSEMENT : ESP32 introuvable (/dev/ttyUSB0)."
fi

# Libérer le port 5000 (WebSocket) et 5001 (Web) si occupés
for port in 5000 5001; do
    PIDS="$(ss -ltnp "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 || true)"
    for pid in $PIDS; do kill "$pid" 2>/dev/null || true; done
    for pid in $PIDS; do kill -9 "$pid" 2>/dev/null || true; done
done

# Arrêter les anciens nœuds éventuels
pkill -9 -f "hiar_robot.launch.py" 2>/dev/null || true
pkill -9 -f "hospital_robot" 2>/dev/null || true
pkill -9 -f "app.py" 2>/dev/null || true
sleep 1

source /opt/ros/humble/setup.bash
source "$PROJECT_ROOT/install/setup.bash"

echo "=========================================================="
echo "🤖 Démarrage des nœuds ROS 2 de HIAR..."
echo "=========================================================="
setsid ros2 launch hospital_robot hiar_robot.launch.py >"$LOG_FILE" 2>&1 &
LAUNCH_PID=$!
ln -sf "$LOG_FILE" "$LOG_DIR/latest.log"

cleanup() {
    trap - EXIT
    echo
    echo "🛑 Arrêt complet de HIAR (ROS 2 et Serveur Web)..."
    kill -INT -- "-$LAUNCH_PID" 2>/dev/null || true
    pkill -9 -f "hiar_robot.launch.py" 2>/dev/null || true
    pkill -9 -f "hospital_robot" 2>/dev/null || true
    pkill -9 -f "app.py" 2>/dev/null || true
    echo "✅ Tous les processus sont arrêtés."
}
trap cleanup EXIT
trap 'exit 130' INT TERM

echo "⏳ Attente et vérification des nœuds ROS 2..."
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
echo "📄 Journal ROS 2 : $LOG_FILE (lien : $LOG_DIR/latest.log)"
echo ""
echo "=========================================================="
echo "🌐 Lancement du serveur Web HIAR (Port 5001)..."
echo "=========================================================="
PORT=5001 exec "$PROJECT_ROOT/web_interface/run_hiar.sh"
