#!/usr/bin/env bash
set -euo pipefail

# Toggle RATE_LIMIT_BACKEND=redis for all apps' .env files.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

changed=0
for env in apps/*/.env; do
  [ -f "$env" ] || continue
  if grep -qE '^RATE_LIMIT_BACKEND=memory' "$env"; then
    sed -i.bak 's/^RATE_LIMIT_BACKEND=memory/RATE_LIMIT_BACKEND=redis/' "$env" && rm -f "$env.bak"
    echo "[rate-limit] $env -> redis"
    changed=$((changed+1))
  elif ! grep -qE '^RATE_LIMIT_BACKEND=' "$env"; then
    printf "\nRATE_LIMIT_BACKEND=redis\n" >> "$env"
    echo "[rate-limit] $env -> added RATE_LIMIT_BACKEND=redis"
    changed=$((changed+1))
  fi
done

echo "[rate-limit] Done. $changed files updated."
