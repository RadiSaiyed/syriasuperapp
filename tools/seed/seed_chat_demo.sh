#!/usr/bin/env bash
set -euo pipefail

CHAT_BASE=${CHAT_BASE:-http://localhost:8091}

log(){ echo -e "[chat-seed] $*"; }

token(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$CHAT_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$CHAT_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
import sys, json
print(json.load(sys.stdin).get('access_token',''))
PY
}

user_id(){
  python3 - "$@" <<'PY'
import sys, json, jwt
tok=sys.stdin.read().strip()
try:
  # decode without verify
  payload=jwt.decode(tok, options={"verify_signature": False, "verify_aud": False, "verify_iss": False})
  print(payload.get('sub',''))
except Exception:
  print('')
PY
}

main(){
  log "Health: $(curl -s "$CHAT_BASE/health" || echo 'down')"

  A=${CHAT_USER_A:-+963970000100}
  B=${CHAT_USER_B:-+963970000200}
  TOK_A=$(token "$A" "Alice")
  TOK_B=$(token "$B" "Bob")
  H_A="Authorization: Bearer $TOK_A"
  H_B="Authorization: Bearer $TOK_B"

  UID_A=$(echo -n "$TOK_A" | user_id)
  UID_B=$(echo -n "$TOK_B" | user_id)
  log "Users: A=$UID_A  B=$UID_B"

  # Publish device keys (dummy)
  curl -s -X POST "$CHAT_BASE/keys/publish" -H "$H_A" -H 'Content-Type: application/json' --data '{"device_id":"devA","public_key":"PUB_A"}' >/dev/null
  curl -s -X POST "$CHAT_BASE/keys/publish" -H "$H_B" -H 'Content-Type: application/json' --data '{"device_id":"devB","public_key":"PUB_B"}' >/dev/null

  # Send messages both ways
  curl -s -X POST "$CHAT_BASE/messages/send" -H "$H_A" -H 'Content-Type: application/json' --data "{\"recipient_user_id\":\"$UID_B\",\"sender_device_id\":\"devA\",\"ciphertext\":\"hello bob\"}" >/dev/null
  curl -s -X POST "$CHAT_BASE/messages/send" -H "$H_B" -H 'Content-Type: application/json' --data "{\"recipient_user_id\":\"$UID_A\",\"sender_device_id\":\"devB\",\"ciphertext\":\"hi alice\"}" >/dev/null
  log "Done."
}

main "$@"

