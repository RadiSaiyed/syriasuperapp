#!/usr/bin/env bash
set -euo pipefail

# Cross-service E2E: Taxi ↔ Payments
# Requires both services running locally via docker compose on default ports.
# Taxi:    http://localhost:8081
# Payments:http://localhost:8080

TAXI_BASE=${TAXI_BASE:-http://localhost:8081}
PAY_BASE=${PAY_BASE:-http://localhost:8080}

echo "[E2E] Checking health..."
curl -fsS "$TAXI_BASE/health" >/dev/null
curl -fsS "$PAY_BASE/health" >/dev/null

ts=$(date +%s)
RIDER="+9639${ts: -7}01"
DRIVER="+9639${ts: -7}02"

echo "[E2E] Rider: $RIDER  Driver: $DRIVER"

tok() { curl -s "$TAXI_BASE/auth/verify_otp" -H 'Content-Type: application/json' -d "{\"phone\":\"$1\",\"otp\":\"123456\",\"name\":\"E2E\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'; }

TOK_A=$(tok "$RIDER")
TOK_B=$(tok "$DRIVER")

echo "[E2E] Setting up driver..."
curl -fsS -X POST "$TAXI_BASE/driver/apply" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json' -d '{"vehicle_make":"Toyota","vehicle_plate":"E2E-001"}' >/dev/null
curl -fsS -X PUT "$TAXI_BASE/driver/status" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json' -d '{"status":"available"}' >/dev/null
curl -fsS -X PUT "$TAXI_BASE/driver/location" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json' -d '{"lat":33.5138, "lon":36.2765}' >/dev/null

echo "[E2E] Requesting ride..."
RID=$(curl -s -X POST "$TAXI_BASE/rides/request" -H "Authorization: Bearer $TOK_A" -H 'Content-Type: application/json' -d '{"pickup_lat":33.5138,"pickup_lon":36.2765,"dropoff_lat":33.52,"dropoff_lon":36.28}' | python3 -c 'import sys,json; print((json.load(sys.stdin) or {}).get("id",""))')
if [ -z "$RID" ]; then echo "[E2E] Failed to create ride"; exit 1; fi
echo "[E2E] Ride: $RID"

echo "[E2E] Attempting accept/start/complete..."
curl -s -X POST "$TAXI_BASE/rides/$RID/accept" -H "Authorization: Bearer $TOK_B" | sed -n '1p'
# Idempotency: accept again should be OK and return current status
ACC2=$(curl -s -w "\n%{http_code}" -X POST "$TAXI_BASE/rides/$RID/accept" -H "Authorization: Bearer $TOK_B")
echo "$ACC2" | sed -n '1p' >/dev/null
ACC2_CODE=$(echo "$ACC2" | tail -n1)
if [ "$ACC2_CODE" != "200" ]; then echo "[E2E] Accept idempotency failed ($ACC2_CODE)"; exit 1; fi
curl -s -X POST "$TAXI_BASE/rides/$RID/start" -H "Authorization: Bearer $TOK_B" | sed -n '1p'
COMP=$(curl -s -X POST "$TAXI_BASE/rides/$RID/complete" -H "Authorization: Bearer $TOK_B")
echo "$COMP" | sed -n '1p'
# Idempotency: complete again should be OK
COMP2=$(curl -s -w "\n%{http_code}" -X POST "$TAXI_BASE/rides/$RID/complete" -H "Authorization: Bearer $TOK_B")
echo "$COMP2" | sed -n '1p' >/dev/null
COMP2_CODE=$(echo "$COMP2" | tail -n1)
if [ "$COMP2_CODE" != "200" ]; then echo "[E2E] Complete idempotency failed ($COMP2_CODE)"; exit 1; fi

FEE=$(echo "$COMP" | python3 - <<'PY'
import sys,json
try:
  js=json.load(sys.stdin)
  print(js.get("platform_fee_cents",""))
except Exception:
  print("")
PY
)

SECRET=$(awk -F= '/INTERNAL_API_SECRET/{print $2}' apps/payments/.env 2>/dev/null || echo "")
if [ -n "$SECRET" ]; then
  echo "[E2E] Checking driver wallet via Payments..."
  curl -s -H "X-Internal-Secret: $SECRET" "$PAY_BASE/internal/wallet" --get --data-urlencode "phone=$DRIVER" | sed -n '1p'
fi

echo "[E2E] Done. Fee (cents): ${FEE}"
