#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
COMMA_HOST="192.168.1.123"       # <-- IP del comma
COMMA_USER="comma"

FILEBROWSER="https://drive.farm.14bodhi.com"
FB_USER="user"
FB_PASSWORD="password"

REMOTE_PATH="/data/media/0/realdata"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP="/tmp/comma-${TIMESTAMP}.tar.gz"

echo "=== Test connessione al comma ==="
ssh -o BatchMode=yes \
    -o ConnectTimeout=10 \
    "${COMMA_USER}@${COMMA_HOST}" \
    "echo 'Comma connected'"

echo "=== Estrazione dati dal comma ==="

ssh -o BatchMode=yes \
    "${COMMA_USER}@${COMMA_HOST}" \
    "tar -C /data/media/0 -czf - realdata" \
    > "$BACKUP"

echo "Backup creato:"
ls -lh "$BACKUP"

echo "=== Login FileBrowser ==="

TOKEN=$(curl --fail -s \
    -X POST "${FILEBROWSER}/api/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${FB_USER}\",\"password\":\"${FB_PASSWORD}\"}")

if [ -z "$TOKEN" ]; then
    echo "ERRORE: impossibile ottenere token FileBrowser"
    exit 1
fi

echo "=== Upload ==="

curl --fail-with-body \
    -X POST \
    "${FILEBROWSER}/api/resources/comma-${TIMESTAMP}.tar.gz" \
    -H "X-Auth: ${TOKEN}" \
    --data-binary @"${BACKUP}"

echo
echo "=== Upload completato ==="

rm -f "$BACKUP"

echo "Backup locale eliminato."