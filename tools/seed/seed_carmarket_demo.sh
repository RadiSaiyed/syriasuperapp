#!/usr/bin/env bash
set -euo pipefail

CARMARKET_BASE=${CARMARKET_BASE:-http://localhost:8086}

log(){ echo -e "[carmarket-seed] $*"; }

token(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$CARMARKET_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$CARMARKET_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
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
  log "Health: $(curl -s "$CARMARKET_BASE/health" || echo 'down')"

  SELL=${SELLER_PHONE:-+963990000010}
  BUY=${BUYER_PHONE:-+963990000020}
  S_T=$(token "$SELL" "Seller")
  B_T=$(token "$BUY" "Buyer")
  H_S="Authorization: Bearer $S_T"
  H_B="Authorization: Bearer $B_T"

  # Create listing
  L_JSON=$(curl -s -X POST "$CARMARKET_BASE/listings" -H "$H_S" -H 'Content-Type: application/json' \
    --data '{"title":"Toyota Corolla","make":"Toyota","model":"Corolla","year":2018,"price_cents":450000000,"description":"Well kept","mileage_km":65000,"condition":"used","city":"Damascus"}')
  L_ID=$(echo "$L_JSON" | json_val)
  log "Listing=$L_ID"

  # Add image
  curl -s -X POST "$CARMARKET_BASE/listings/$L_ID/images" -H "$H_S" -H 'Content-Type: application/json' --data '{"url":"https://example.com/car.jpg"}' >/dev/null

  # Buyer offers
  O_JSON=$(curl -s -X POST "$CARMARKET_BASE/offers/listing/$L_ID" -H "$H_B" -H 'Content-Type: application/json' --data '{"amount_cents":430000000}')
  O_ID=$(echo "$O_JSON" | json_val)
  log "Offer=$O_ID"

  # Seller accepts
  curl -s -X POST "$CARMARKET_BASE/offers/$O_ID/accept" -H "$H_S" >/dev/null

  # Optional chat message
  curl -s -X POST "$CARMARKET_BASE/chats/listing/$L_ID" -H "$H_B" -H 'Content-Type: application/json' --data '{"content":"Thanks! When can I pick it up?"}' >/dev/null || true

  log "Done."
}

main "$@"

