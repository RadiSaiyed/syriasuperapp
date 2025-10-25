#!/usr/bin/env bash
set -euo pipefail

# Taxi Wallet smoke flow:
# - Requires Taxi API running locally (or docker compose target starts it)
# - Demonstrates: topup on insufficient balance at accept, then start/complete, then wallet history

BASE=${TAXI_BASE:-http://localhost:8081}

echo "[SMOKE] Checking Taxi health at $BASE ..."
curl -fsS "$BASE/health" >/dev/null

ts=$(date +%s)
RIDER="+9639${ts: -7}01"
DRIVER="+9639${ts: -7}02"

tok() { curl -s "$BASE/auth/verify_otp" -H 'Content-Type: application/json' -d "{\"phone\":\"$1\",\"otp\":\"123456\",\"name\":\"Smoke\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'; }

TOK_A=$(tok "$RIDER")
TOK_B=$(tok "$DRIVER")

echo "[SMOKE] Setting up driver $DRIVER ..."
curl -fsS -X POST "$BASE/driver/apply" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json' -d '{"vehicle_make":"Toyota","vehicle_plate":"SMK-001"}' >/dev/null
curl -fsS -X PUT "$BASE/driver/status" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json' -d '{"status":"available"}' >/dev/null
curl -fsS -X PUT "$BASE/driver/location" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json' -d '{"lat":33.5138, "lon":36.2765}' >/dev/null

echo "[SMOKE] Requesting ride ..."
RID=$(curl -s -X POST "$BASE/rides/request" -H "Authorization: Bearer $TOK_A" -H 'Content-Type: application/json' -d '{"pickup_lat":33.5138,"pickup_lon":36.2765,"dropoff_lat":33.52,"dropoff_lon":36.28}' | python3 - <<'PY'
import sys,json
try:
  print((json.load(sys.stdin) or {}).get("id",""))
except Exception:
  print("")
PY
)
if [ -z "$RID" ]; then echo "[SMOKE] Failed to create ride"; exit 1; fi
echo "[SMOKE] Ride: $RID"

echo "[SMOKE] Attempting accept ..."
ACC=$(curl -s -w "\n%{http_code}" -X POST "$BASE/rides/$RID/accept" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json')
ACC_BODY=$(echo "$ACC" | sed '$d')
ACC_CODE=$(echo "$ACC" | tail -n1)

if [ "$ACC_CODE" != "200" ]; then
  CODE=$(echo "$ACC_BODY" | python3 - <<'PY'
import sys,json
try:
  d=json.load(sys.stdin).get('detail',{})
  print(d.get('code',''))
except Exception:
  print('')
PY
)
  if [ "$CODE" = "insufficient_taxi_wallet_balance" ]; then
    SHORT=$(echo "$ACC_BODY" | python3 - <<'PY'
import sys,json
try:
  d=json.load(sys.stdin).get('detail',{})
  print(d.get('shortfall_cents',0))
except Exception:
  print(0)
PY
)
    echo "[SMOKE] Insufficient wallet. Topping up shortfall: ${SHORT} cents ..."
    TOP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/driver/taxi_wallet/topup" -H "Authorization: Bearer $TOK_B" -H 'Content-Type: application/json' -d "{\"amount_cents\":$SHORT}")
    TOP_BODY=$(echo "$TOP" | sed '$d')
    TOP_CODE=$(echo "$TOP" | tail -n1)
    if [ "$TOP_CODE" != "200" ]; then
      echo "[SMOKE] Topup failed (HTTP $TOP_CODE). If TAXI_POOL_WALLET_PHONE is set, ensure Payments is running or unset it for offline dev. Response: $TOP_BODY"
      exit 1
    fi
    echo "[SMOKE] Retrying accept ..."
    curl -s -X POST "$BASE/rides/$RID/accept" -H "Authorization: Bearer $TOK_B" | sed -n '1p'
  else
    echo "[SMOKE] Accept failed: $ACC_BODY"; exit 1
  fi
else
  echo "$ACC_BODY" | sed -n '1p'
fi

echo "[SMOKE] Starting and completing ride ..."
curl -s -X POST "$BASE/rides/$RID/start" -H "Authorization: Bearer $TOK_B" | sed -n '1p'
curl -s -X POST "$BASE/rides/$RID/complete" -H "Authorization: Bearer $TOK_B" | sed -n '1p'
# Idempotency: repeat complete
curl -s -X POST "$BASE/rides/$RID/complete" -H "Authorization: Bearer $TOK_B" >/dev/null

echo "[SMOKE] Fetching taxi wallet ..."
curl -s "$BASE/driver/taxi_wallet" -H "Authorization: Bearer $TOK_B" | python3 - <<'PY'
import sys,json
js=json.load(sys.stdin)
bal=js.get('balance_cents')
entries=js.get('entries',[])
fee=next((e for e in entries if e.get('type')=='fee'), None)
print('[SMOKE] Balance (cents):', bal)
if fee:
  print('[SMOKE] Last fee entry:')
  print('  amount_cents_signed=', fee.get('amount_cents_signed'))
  print('  original_fare_cents=', fee.get('original_fare_cents'))
  print('  fee_cents=', fee.get('fee_cents'))
  print('  driver_take_home_cents=', fee.get('driver_take_home_cents'))
  cnt=sum(1 for e in entries if e.get('type')=='fee')
  print('[SMOKE] Fee entries count:', cnt)
else:
  print('[SMOKE] No fee entry found.')
PY

echo "[SMOKE] Done."
