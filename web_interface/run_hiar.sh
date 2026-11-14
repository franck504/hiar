#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERREUR : fichier .env introuvable."
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

if [[ -z "${HIAR_STAFF_API_TOKEN:-}" ]]; then
    echo "ERREUR : jeton du personnel absent."
    exit 1
fi

DOCTOR_SECRETS="$PROJECT_ROOT/web_interface/.doctor-secrets"
if [[ ! -f "$DOCTOR_SECRETS" ]]; then
    echo "ERREUR : fichier .doctor-secrets introuvable."
    exit 1
fi

source "$DOCTOR_SECRETS"

for code in A B C D; do
    name="HIAR_DOCTOR_TOKEN_$code"
    if [[ -z "${!name:-}" ]]; then
        echo "ERREUR : jeton du médecin $code absent."
        exit 1
    fi
done

cd "$PROJECT_ROOT/web_interface"
exec python3 app.py
