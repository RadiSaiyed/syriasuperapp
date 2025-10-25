#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://localhost:8090}
PHONE=${PHONE:-+963900000112}

source "$(dirname "$0")/common.sh"
echo "[food] Health check: $BASE/health"
wait_http_ok "$BASE/health" 60 || { echo "Health check failed" >&2; exit 1; }

echo "[food] Request OTP"
curl -fsS -X POST "$BASE/auth/request_otp" -H 'Content-Type: application/json' -d '{"phone":"'"$PHONE"'"}' >/dev/null

echo "[food] Verify OTP"
TOK=$(curl -fsS -X POST "$BASE/auth/verify_otp" -H 'Content-Type: application/json' -d '{"phone":"'"$PHONE"'","otp":"123456","name":"Smoke"}' | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
if [[ -z "$TOK" ]]; then echo "OTP verify failed" >&2; exit 1; fi

echo "OK"
