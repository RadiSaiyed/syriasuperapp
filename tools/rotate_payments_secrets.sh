#!/usr/bin/env bash
set -euo pipefail

# Rotate JWT_SECRET and INTERNAL_API_SECRET in apps/payments/.env

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_FILE="$ROOT_DIR/apps/payments/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "apps/payments/.env not found" >&2
  exit 2
fi

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 - <<'PY'
import secrets; print(secrets.token_hex(32))
PY
  fi
}

JWT_NEW=$(gen_secret)
INT_NEW=$(gen_secret)

sed -i.bak "s|^JWT_SECRET=.*$|JWT_SECRET=$JWT_NEW|" "$ENV_FILE"
if grep -q '^INTERNAL_API_SECRET=' "$ENV_FILE"; then
  sed -i.bak "s|^INTERNAL_API_SECRET=.*$|INTERNAL_API_SECRET=$INT_NEW|" "$ENV_FILE"
else
  echo "INTERNAL_API_SECRET=$INT_NEW" >> "$ENV_FILE"
fi
rm -f "$ENV_FILE.bak"

echo "[rotate] Updated JWT_SECRET and INTERNAL_API_SECRET in apps/payments/.env"
echo "[rotate] Remember to restart the Payments API and update verticals' PAYMENTS_INTERNAL_SECRET."

