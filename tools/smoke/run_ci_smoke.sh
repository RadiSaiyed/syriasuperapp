#!/usr/bin/env bash
set -euo pipefail

APPS=${APPS:-"payments food"}
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
cd "$ROOT_DIR"

echo "[smoke] Bringing up: $APPS"
APPS="$APPS" bash tools/docker_up_all.sh

fail=0
for app in $APPS; do
  case "$app" in
    payments)
      bash tools/smoke/payments_otp_check.sh || fail=1
      ;;
    food)
      bash tools/smoke/food_otp_check.sh || fail=1
      ;;
    *)
      echo "[smoke] No script for app: $app (skipping)";;
  esac
done

if [[ "$fail" -ne 0 ]]; then
  echo "[smoke] Failure detected, showing recent logs:" >&2
  for name in payments-api-1 food-api-1; do
    docker logs --tail=200 "$name" 2>&1 | sed -e "1s/^/[${name}] /" || true
  done
fi

echo "[smoke] Tearing down: $APPS"
APPS="$APPS" bash tools/docker_down_all.sh || true

exit "$fail"

