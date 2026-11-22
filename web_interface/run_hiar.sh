#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$PROJECT_ROOT/.env.example" ]]; then
        echo "⚠️ .env introuvable, création automatique depuis .env.example..."
        cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
    else
        echo "ERREUR : fichier .env introuvable."
        exit 1
    fi
fi

set -a
source "$ENV_FILE"
set +a

export HIAR_STAFF_API_TOKEN="${HIAR_STAFF_API_TOKEN:-hiar_default_staff_token_2026}"
export HIAR_WEB_PIN="${HIAR_WEB_PIN:-1234}"

DOCTOR_SECRETS="$PROJECT_ROOT/web_interface/.doctor-secrets"
if [[ ! -f "$DOCTOR_SECRETS" ]]; then
    echo "Création automatique de .doctor-secrets avec jetons par défaut..."
    cat << 'EOF' > "$DOCTOR_SECRETS"
export HIAR_DOCTOR_TOKEN_A='wOBSF8JfiwWVfcDaeSYyxHU7Z530o2BwXlfF6tWZBss'
export HIAR_DOCTOR_TOKEN_B='7iG_xhLoTcOfbppd6LTxwtuTwQjwE_eKtHKYbE69GKA'
export HIAR_DOCTOR_TOKEN_C='JqtfOWu0M1Blu7aYeKx-sVQx8huEte41n734tLroaps'
export HIAR_DOCTOR_TOKEN_D='owykW-nd1meLRSMowaKT999c00c7zsZkhexmnFIs_dI'
EOF
fi

source "$DOCTOR_SECRETS"

for code in A B C D; do
    name="HIAR_DOCTOR_TOKEN_$code"
    if [[ -z "${!name:-}" ]]; then
        export "HIAR_DOCTOR_TOKEN_$code"="doctor_token_${code}_default"
    fi
done

cd "$PROJECT_ROOT/web_interface"
exec python3 app.py
