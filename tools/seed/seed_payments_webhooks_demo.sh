#!/usr/bin/env bash
set -euo pipefail

# Payments merchant webhook pipeline demo using app://echo

PAY_BASE=${PAY_BASE:-http://localhost:8080}

log(){ echo -e "[payments-webhooks] $*"; }

tok(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$PAY_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$PAY_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
import sys, json
print(json.load(sys.stdin).get('access_token',''))
PY
}

main(){
  log "Payments: $(curl -s "$PAY_BASE/health" || echo 'down')"
  PHONE=${PHONE:-+963900777777}
  T=$(tok "$PHONE" "Merchant")
  H="Authorization: Bearer $T"
  curl -s -X POST "$PAY_BASE/payments/dev/become_merchant" -H "$H" >/dev/null || true
  # Register echo endpoint
  EP=$(curl -s -X POST "$PAY_BASE/webhooks/endpoints" -H "$H" --get --data-urlencode 'url=app://echo' --data-urlencode 'secret=demo' | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
  log "Endpoint=$EP"
  # Send test event and process pending deliveries
  curl -s -X POST "$PAY_BASE/webhooks/test" -H "$H" >/dev/null
  curl -s -X POST "$PAY_BASE/webhooks/process_pending" -H "$H" >/dev/null
  # List deliveries
  curl -s "$PAY_BASE/webhooks/deliveries" -H "$H" | sed -n '1,200p'
  log "Done."
}

main "$@"

