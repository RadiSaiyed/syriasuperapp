#!/usr/bin/env bash
set -euo pipefail

FREIGHT_BASE=${FREIGHT_BASE:-http://localhost:8085}

log(){ echo -e "[freight-seed] $*"; }

token(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$FREIGHT_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$FREIGHT_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
import sys, json
print(json.load(sys.stdin).get('access_token',''))
PY
}

json_val(){ python3 - "$@" <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('id','') if isinstance(data, dict) else '')
PY
}

main(){
  log "Health: $(curl -s "$FREIGHT_BASE/health" || echo 'down')"

  # Shipper posts a load
  SHIP=${SHIPPER_PHONE:-+963980000010}
  SHIP_T=$(token "$SHIP" "Shipper")
  H_S="Authorization: Bearer $SHIP_T"
  LOAD_JSON=$(curl -s -X POST "$FREIGHT_BASE/shipper/loads" -H "$H_S" -H 'Content-Type: application/json' \
    --data '{"origin":"Damascus","destination":"Latakia","weight_kg":1200,"price_cents":250000}')
  LOAD_ID=$(echo "$LOAD_JSON" | json_val)
  log "Load=$LOAD_ID"

  # Carrier applies and bids
  CARR=${CARRIER_PHONE:-+963980000020}
  CARR_T=$(token "$CARR" "Carrier")
  H_C="Authorization: Bearer $CARR_T"
  curl -s -X POST "$FREIGHT_BASE/carrier/apply" -H "$H_C" -H 'Content-Type: application/json' --data '{"company_name":"ACME Logistics"}' >/dev/null
  BID_JSON=$(curl -s -X POST "$FREIGHT_BASE/bids/load/$LOAD_ID" -H "$H_C" -H 'Content-Type: application/json' --data '{"amount_cents":240000}')
  BID_ID=$(echo "$BID_JSON" | json_val)
  log "Bid=$BID_ID"

  # Shipper accepts bid
  curl -s -X POST "$FREIGHT_BASE/bids/$BID_ID/accept" -H "$H_S" >/dev/null

  # Carrier executes lifecycle
  curl -s -X POST "$FREIGHT_BASE/loads/$LOAD_ID/pickup" -H "$H_C" >/dev/null
  curl -s -X POST "$FREIGHT_BASE/loads/$LOAD_ID/in_transit" -H "$H_C" >/dev/null
  curl -s -X POST "$FREIGHT_BASE/loads/$LOAD_ID/deliver" -H "$H_C" >/dev/null
  curl -s -X POST "$FREIGHT_BASE/loads/$LOAD_ID/pod" -H "$H_C" --get --data-urlencode 'url=https://example.com/pod.jpg' >/dev/null

  log "Done."
}

main "$@"

