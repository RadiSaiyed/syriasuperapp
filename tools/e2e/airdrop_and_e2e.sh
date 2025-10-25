#!/usr/bin/env bash
set -euo pipefail

PAY_BASE=${PAY_BASE:-http://localhost:8080}
TAXI_BASE=${TAXI_BASE:-http://localhost:8081}

echo "[E2E] Checking Payments health..."
curl -fsS "$PAY_BASE/health" >/dev/null

ADMIN_TOKEN=${ADMIN_TOKEN:-}
if [ -z "$ADMIN_TOKEN" ]; then
  if [ -f "apps/payments/.env" ]; then
    ADMIN_TOKEN=$(awk -F= '/^ADMIN_TOKEN=/{print $2}' apps/payments/.env | tr -d '\r' || true)
  fi
fi

if [ -n "$ADMIN_TOKEN" ]; then
  echo "[E2E] Admin airdrop starting credit (limited batch)..."
  curl -fsS -X POST "$PAY_BASE/admin/airdrop_starting_credit" \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"limit": 1000}' | sed -n '1p'
else
  echo "[E2E] ADMIN_TOKEN not set; skipping airdrop"
fi

echo "[E2E] Running Taxi↔Payments scenario..."
bash tools/e2e/taxi_payments_e2e.sh

