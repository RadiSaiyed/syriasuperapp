#!/usr/bin/env bash
set -euo pipefail

# Replace weak defaults in apps/*/.env with strong random secrets.
# - Replaces JWT_SECRET=change_me_in_prod
# - Replaces PAYMENTS_INTERNAL_SECRET=dev_secret

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 - <<'PY'
import secrets; print(secrets.token_hex(32))
PY
  fi
}

updated=0
for env in apps/*/.env; do
  [ -f "$env" ] || continue
  jwt=$(grep -E '^JWT_SECRET=' "$env" | cut -d= -f2- || true)
  pay=$(grep -E '^PAYMENTS_INTERNAL_SECRET=' "$env" | cut -d= -f2- || true)
  if [[ "$jwt" == "change_me_in_prod" ]]; then
    new_jwt=$(gen_secret)
    sed -i.bak "s|^JWT_SECRET=.*$|JWT_SECRET=$new_jwt|" "$env" && rm -f "$env.bak"
    echo "[secrets] $env -> JWT_SECRET updated"
    updated=$((updated+1))
  fi
  if [[ -n "${pay:-}" && "$pay" == "dev_secret" ]]; then
    new_pay=$(gen_secret)
    sed -i.bak "s|^PAYMENTS_INTERNAL_SECRET=.*$|PAYMENTS_INTERNAL_SECRET=$new_pay|" "$env" && rm -f "$env.bak"
    echo "[secrets] $env -> PAYMENTS_INTERNAL_SECRET updated"
    updated=$((updated+1))
  fi
done

echo "[secrets] Done. $updated updates applied."

