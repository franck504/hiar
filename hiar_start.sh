#!/usr/bin/env bash
set -o pipefail

PROJECT_ROOT="$HOME/projects/hospital_assistant_robot"
LOG_DIR="$HOME/hiar_logs"
LOG_FILE="$LOG_DIR/launch_$(date +%Y%m%d_%H%M%S).log"
NODE_PATTERN="install/hospital_robot/lib/hospital_robot"
NODES_LIST="esp32_interface obstacle_detector robot_supervisor navigation_decision hmi_request_receiver"
mkdir -p "$LOG_DIR"

if ! ls /dev/ttyUSB0 >/dev/null 2>&1; then
    echo "ERREUR : ESP32 introuvable (/dev/ttyUSB0)."
    echo "PowerShell administrateur : usbipd list, puis usbipd attach --wsl --busid <BUSID>"
    exit 1
fi

# Refuser de démarrer si des noeuds HIAR tournent déjà (évite les doublons)
if pgrep -f "$NODE_PATTERN" >/dev/null; then
    echo "ERREUR : des noeuds HIAR tournent déjà."
    echo "Arrête-les avec : pkill -f \"$NODE_PATTERN\""
    exit 1
fi

# Libérer le port 5000 par son numéro
PIDS="$(ss -ltnp 'sport = :5000' 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2)"
for pid in $PIDS; do kill "$pid" 2>/dev/null; done
sleep 1
for pid in $PIDS; do kill -9 "$pid" 2>/dev/null; done

source /opt/ros/humble/setup.bash
source "$PROJECT_ROOT/install/setup.bash"

setsid ros2 launch hospital_robot hiar_robot.launch.py >"$LOG_FILE" 2>&1 &
LAUNCH_PID=$!
ln -sf "$LOG_FILE" "$LOG_DIR/latest.log"

cleanup() {
    trap - EXIT
    echo
    echo "Arrêt de HIAR..."
    kill -INT -- "-$LAUNCH_PID" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        pgrep -f "$NODE_PATTERN" >/dev/null || break
        sleep 0.5
    done
    pkill -f "$NODE_PATTERN" 2>/dev/null
    kill "$LAUNCH_PID" 2>/dev/null
    sleep 1
    if pgrep -f "$NODE_PATTERN" >/dev/null; then
        echo "ATTENTION : des noeuds tournent encore."
    else
        echo "Tous les noeuds sont arrêtés."
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

echo "Vérification des noeuds..."
for _ in $(seq 1 10); do
    NODES="$(ros2 node list --no-daemon 2>/dev/null)"
    MISSING=0
    for n in $NODES_LIST; do
        echo "$NODES" | grep -q "/$n\$" || MISSING=1
    done
    [ "$MISSING" -eq 0 ] && break
    sleep 1
done
for n in $NODES_LIST; do
    if echo "$NODES" | grep -q "/$n\$"; then echo "OK  $n"; else echo "KO  $n"; fi
done
echo "Journal des noeuds : $LOG_FILE (raccourci : $LOG_DIR/latest.log)"

"$PROJECT_ROOT/web_interface/run_hiar.sh"
