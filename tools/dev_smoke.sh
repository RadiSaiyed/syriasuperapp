#!/usr/bin/env bash
set -euo pipefail

BFF_BASE="${1:-http://localhost:8070}"
PHONE="${PHONE:-+963901234569}"
NAME="${NAME:-Dev User}"

echo "[smoke] BFF: $BFF_BASE"

echo "[smoke] OTP verify via BFF…"
TOK=$(curl -fsS -X POST "$BFF_BASE/auth/verify_otp" -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"otp\":\"123456\",\"name\":\"$NAME\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
echo "[smoke] Token (len=${#TOK})"

echo "[smoke] POST /stays/dev/seed"
curl -fsS -X POST "$BFF_BASE/stays/dev/seed" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' | jq -c '.'

echo "[smoke] GET /v1/me"
curl -fsS "$BFF_BASE/v1/me" -H "Authorization: Bearer $TOK" | jq -c '{user, services: {payments: .services.payments, chat: (.services.chat|{conversations: (.conversations|length)})}}'

echo "[smoke] GET /v1/commerce/shops (auth)"
curl -fsS "$BFF_BASE/v1/commerce/shops" -H "Authorization: Bearer $TOK" | jq '.[0:2]'

echo "[smoke] GET /v1/stays/properties"
curl -fsS "$BFF_BASE/v1/stays/properties" | jq '.[0:2]'

echo "[smoke] GET /chat/messages/inbox (auth)"
curl -fsS "$BFF_BASE/chat/messages/inbox" -H "Authorization: Bearer $TOK" | jq -c '.'

echo "[smoke] OK"

