#!/usr/bin/env bash
set -euo pipefail

BASE_TAXI=${BASE_TAXI:-http://localhost:9081}
BASE_PAYMENTS=${BASE_PAYMENTS:-http://localhost:9080}
ADMIN_TOKEN=${ADMIN_TOKEN:-$(grep -E '^ADMIN_TOKEN=' ops/staging/taxi.env 2>/dev/null | cut -d'=' -f2-)}

log() {
  echo "[taxi-e2e] $*" >&2
}

wait_for() {
  local name=$1
  local url=$2
  local depth=${3:-60}
  for i in $(seq 1 "$depth"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$name ready after $i checks"
      return 0
    fi
    sleep 2
  done
  log "ERROR: $name did not become ready at $url"
  return 1
}

json() {
  python3 - "$@"
}

wait_for taxi "$BASE_TAXI/health"
wait_for payments "$BASE_PAYMENTS/health"

TS=$(date +%s)
RIDER="+96390$((TS % 1000000 + 100000))"
DRIVER="+96391$((TS % 1000000 + 100000))"
log "Using rider $RIDER and driver $DRIVER"

curl -fsS -X POST "$BASE_TAXI/auth/request_otp" \
  -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$RIDER\"}" > /dev/null
curl -fsS -X POST "$BASE_TAXI/auth/request_otp" \
  -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$DRIVER\"}" > /dev/null

OTP_RIDER=${OTP_RIDER:-123456}
OTP_DRIVER=${OTP_DRIVER:-123456}

TOKEN_RIDER=$(curl -fsS -X POST "$BASE_TAXI/auth/verify_otp" \
  -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$RIDER\",\"otp\":\"$OTP_RIDER\",\"name\":\"Rider\"}" | \
  python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
TOKEN_DRIVER=$(curl -fsS -X POST "$BASE_TAXI/auth/verify_otp" \
  -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$DRIVER\",\"otp\":\"$OTP_DRIVER\",\"name\":\"Driver\"}" | \
  python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

HDR_RIDER=("-H" "Authorization: Bearer $TOKEN_RIDER" "-H" "Content-Type: application/json")
HDR_DRIVER=("-H" "Authorization: Bearer $TOKEN_DRIVER" "-H" "Content-Type: application/json")

curl -fsS -X POST "$BASE_TAXI/driver/apply" "${HDR_DRIVER[@]}" \
  -d '{"vehicle_make":"Kia","vehicle_plate":"STG"}' > /dev/null
curl -fsS -X PUT "$BASE_TAXI/driver/status" "${HDR_DRIVER[@]}" \
  -d '{"status":"available"}' > /dev/null
curl -fsS -X PUT "$BASE_TAXI/driver/location" "${HDR_DRIVER[@]}" \
  -d '{"lat":33.5138,"lon":36.2765}' > /dev/null

RID_JSON=$(curl -fsS -X POST "$BASE_TAXI/rides/request" "${HDR_RIDER[@]}" \
  -d '{"pickup_lat":33.5138,"pickup_lon":36.2765,"dropoff_lat":33.5200,"dropoff_lon":36.2800,"prepay":true}')
RIDE_ID=$(python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])' <<<"$RID_JSON")
log "Ride requested $RIDE_ID"

ACCEPT=$(curl -fsS -o /dev/null -w '%{http_code}' -X POST "$BASE_TAXI/rides/$RIDE_ID/accept" "${HDR_DRIVER[@]}")
if [[ "$ACCEPT" != "200" ]]; then
  log "Driver accept blocked, fetching wallet"
  WALLET=$(curl -fsS "$BASE_TAXI/driver/taxi_wallet" "${HDR_DRIVER[@]}")
  REQUIRED=$(python3 -c 'import sys,json; js=json.load(sys.stdin); import math; print(max(500, int(js.get("balance_cents",0) + 500)))' <<<"$WALLET")
  log "Top up taxi wallet by $REQUIRED"
  curl -fsS -X POST "$BASE_TAXI/driver/taxi_wallet/topup" "${HDR_DRIVER[@]}" \
    -d "{\"amount_cents\":$REQUIRED}" > /dev/null
  curl -fsS -X POST "$BASE_TAXI/rides/$RIDE_ID/accept" "${HDR_DRIVER[@]}" > /dev/null
fi

curl -fsS -X POST "$BASE_TAXI/rides/$RIDE_ID/start" "${HDR_DRIVER[@]}" > /dev/null
COMPLETE=$(curl -fsS -X POST "$BASE_TAXI/rides/$RIDE_ID/complete" "${HDR_DRIVER[@]}")
log "Ride complete: $COMPLETE"

if [[ -n "$ADMIN_TOKEN" ]]; then
  curl -fsS -X POST "$BASE_TAXI/rides/dispatch_scheduled" \
    -H "X-Admin-Token: $ADMIN_TOKEN" > /dev/null || true
fi

log "Taxi wallet + escrow flow complete"
