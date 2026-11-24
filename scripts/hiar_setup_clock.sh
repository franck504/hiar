#!/usr/bin/env bash
# Configure l'horloge du Raspberry Pi pour HIAR (à lancer UNE fois sur le Pi, avec sudo).
#
#   sudo ./scripts/hiar_setup_clock.sh                 # fuseau + NTP + autorisation du recalage
#   sudo ./scripts/hiar_setup_clock.sh "2026-11-24 14:30"   # idem + mise à l'heure immédiate
#
# Pourquoi : le Pi n'a pas de pile d'horloge (RTC). Sans Internet (point d'accès Wi-Fi du robot),
# il redémarre à la dernière date connue et date les rendez-vous de travers.
#  1. fuseau Indian/Antananarivo (celui des rendez-vous) ;
#  2. synchronisation NTP dès qu'Internet est disponible ;
#  3. règle sudoers étroite : l'utilisateur qui lance HIAR peut exécuter `date -s` sans mot de passe,
#     pour que le pont WebSocket recale le Pi sur l'heure de la tablette Android (toujours à l'heure).
# Solution matérielle définitive : un module RTC DS3231 (~2 €) sur le bus I2C du Pi.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Lancez ce script avec sudo." >&2
    exit 1
fi

HIAR_USER="${SUDO_USER:-${HIAR_USER:-}}"
if [[ -z "$HIAR_USER" || "$HIAR_USER" == "root" ]]; then
    echo "Utilisateur HIAR inconnu : lancez via sudo depuis le compte qui démarre HIAR (ou HIAR_USER=...)." >&2
    exit 1
fi
DATE_BIN="$(command -v date)"

echo "1) Fuseau horaire : Indian/Antananarivo"
timedatectl set-timezone Indian/Antananarivo

echo "2) Synchronisation NTP (active quand Internet est disponible)"
timedatectl set-ntp true || echo "   (NTP indisponible sur ce système : le recalage par la tablette prendra le relais)"

echo "3) Autorisation du recalage par la tablette pour l'utilisateur '$HIAR_USER'"
RULE_FILE=/etc/sudoers.d/hiar-clock
TMP="$(mktemp)"
echo "$HIAR_USER ALL=(root) NOPASSWD: $DATE_BIN -s *" > "$TMP"
if visudo -cf "$TMP" >/dev/null; then
    install -m 0440 "$TMP" "$RULE_FILE"
    echo "   règle installée : $RULE_FILE"
else
    echo "   règle sudoers invalide, rien n'a été installé." >&2
fi
rm -f "$TMP"

if [[ $# -ge 1 ]]; then
    echo "4) Mise à l'heure : $1"
    "$DATE_BIN" -s "$1"
fi

echo
timedatectl
echo
echo "Terminé. Redémarrez HIAR (./hiar_start.sh) : à la connexion de la tablette, le pont recale l'heure si besoin."
