#!/bin/bash
set -euo pipefail

# =========================
# CONFIG
# =========================

COMMA_HOST="192.168.1.XXX"
COMMA_USER="comma"

FB_URL="https://drive.farm.14bodhi.com"
FB_USER="user"
FB_PASSWORD="PASSWORD"

REMOTE_DIR="/data/media/0/realdata"

# =========================
# TROVA ULTIMO LOG
# =========================

echo "Cerco ultimo log sul comma..."

LATEST=$(ssh -o BatchMode=yes "${COMMA_USER}@${COMMA_HOST}" \
  "find '${REMOTE_DIR}' -type f \( -name 'rlog*' -o -name 'qlog*' \) \
   -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-")

if [ -z "$LATEST" ]; then
    echo "ERRORE: nessun rlog/qlog trovato"
    exit 1
fi

echo "Trovato:"
echo "$LATEST"

# =========================
# COPIA DAL COMMA
# =========================

BASENAME=$(basename "$LATEST")
ROUTE=$(basename "$(dirname "$LATEST")")

LOCAL_FILE="/tmp/${ROUTE}-${BASENAME}"

echo
echo "Copio:"
echo "$LOCAL_FILE"

scp -q \
  "${COMMA_USER}@${COMMA_HOST}:${LATEST}" \
  "$LOCAL_FILE"

ls -lh "$LOCAL_FILE"

# =========================
# LOGIN FILEBROWSER
# =========================

echo
echo "Login FileBrowser..."

TOKEN=$(curl --fail -s \
  -X POST "${FB_URL}/api/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${FB_USER}\",\"password\":\"${FB_PASSWORD}\"}")

if [ -z "$TOKEN" ]; then
    echo "ERRORE: token FileBrowser vuoto"
    exit 1
fi

# =========================
# UPLOAD
# =========================

UPLOAD_NAME="${ROUTE}-${BASENAME}"

echo
echo "Upload:"
echo "$UPLOAD_NAME"

curl --fail-with-body \
  -X POST \
  "${FB_URL}/api/resources/${UPLOAD_NAME}" \
  -H "X-Auth: ${TOKEN}" \
  --data-binary @"${LOCAL_FILE}"

echo
echo "Upload completato."

# =========================
# CLEANUP
# =========================

rm -f "$LOCAL_FILE"

echo "File temporaneo eliminato."