#!/usr/bin/env bash
set -euo pipefail

OP_BASE=${OP_BASE:-http://localhost:8095}
PHONE=${PHONE:-+963900000012}

echo "[2FA] Login (dev OTP)"
TOK=$(curl -fsS -X POST "$OP_BASE/auth/verify_otp" \
  -H 'Content-Type: application/json' \
  -d '{"phone":"'"$PHONE"'","otp":"123456","name":"Operator"}')
JWT=$(python3 - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())['access_token'])
PY
<<<"$TOK")
H="Authorization: Bearer $JWT"

echo "[2FA] Setup secret"
SETUP=$(curl -fsS -X POST "$OP_BASE/auth/totp/setup" -H "$H")
SECRET=$(python3 - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())['secret'])
PY
<<<"$SETUP")
echo "Secret: $SECRET"

echo "[2FA] Generate TOTP via operator container"
CODE=$(docker exec food_operator-api-1 python - <<PY
import pyotp,os
print(pyotp.TOTP(os.environ.get('SECRET')).now())
PY
)

echo "[2FA] Enable TOTP"
curl -fsS -X POST "$OP_BASE/auth/totp/enable" -H "$H" --data-urlencode code="$CODE" >/dev/null
echo "Enabled. Now login requires TOTP:"

echo "[2FA] Login with phone OTP + TOTP"
TOK2=$(curl -fsS -X POST "$OP_BASE/auth/verify_otp" \
  -H 'Content-Type: application/json' \
  -d '{"phone":"'"$PHONE"'","otp":"123456","totp":"'"$CODE"'","name":"Operator"}')
echo "$TOK2"

