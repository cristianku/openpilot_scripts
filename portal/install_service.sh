#!/usr/bin/env bash
# Installs or updates the ops-web service on this server: unit, /etc/ops-web.env and start. Safe to run again: the
# sign-in code is made once and kept. --dry-run prints the unit and changes nothing.
#   OPS_WEB_PROXY_IPS   the address the proxy reaches this server from (default raspy)
set -euo pipefail

PORTAL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE=/etc/ops-web.env
UNIT=/etc/systemd/system/ops-web.service
PROXY_IPS="${OPS_WEB_PROXY_IPS:-192.168.200.161}"

unit="$(sed "s|@PORTAL@|${PORTAL}|g" "${PORTAL}/ops-web.service.in")"
if [[ "${1:-}" == "--dry-run" ]]; then
  printf '%s\n' "${unit}"
  exit 0
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  ( umask 077
    printf 'OPS_WEB_TOKEN=%s\nOPS_WEB_PROXY_IPS=%s\nOPS_WEB_HOSTS=ops.farm.14bodhi.com\n' \
      "$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')" "${PROXY_IPS}" > "${ENV_FILE}" )
elif [[ -n "${OPS_WEB_PROXY_IPS:-}" ]]; then
  sed -i "s|^OPS_WEB_PROXY_IPS=.*|OPS_WEB_PROXY_IPS=${PROXY_IPS}|" "${ENV_FILE}"
fi
if ! grep -q '^OPS_WEB_PROXY_SECRET=' "${ENV_FILE}"; then
  printf 'OPS_WEB_PROXY_SECRET=%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> "${ENV_FILE}"
fi
chmod 600 "${ENV_FILE}"

printf '%s\n' "${unit}" > "${UNIT}"
systemctl daemon-reload
systemctl enable --now ops-web
systemctl restart ops-web
systemctl --no-pager --lines=0 status ops-web
