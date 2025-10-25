#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://localhost:8080}
PHONE=${PHONE:-+963900000111}

source "$(dirname "$0")/common.sh"
echo "[payments] Health check: $BASE/health"
wait_http_ok "$BASE/health" 60 || { echo "Health check failed" >&2; exit 1; }

echo "[payments] Request OTP"
curl -fsS -X POST "$BASE/auth/request_otp" -H 'Content-Type: application/json' -d '{"phone":"'"$PHONE"'"}' >/dev/null

echo "[payments] Verify OTP"
TOK=$(curl -fsS -X POST "$BASE/auth/verify_otp" -H 'Content-Type: application/json' -d '{"phone":"'"$PHONE"'","otp":"123456","name":"Smoke"}' | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
if [[ -z "$TOK" ]]; then echo "OTP verify failed" >&2; exit 1; fi

echo "[payments] Wallet"
curl -fsS -H "Authorization: Bearer $TOK" "$BASE/wallet" >/dev/null

echo "OK"
