#!/usr/bin/env bash
set -euo pipefail

# Seed test rider and driver with sufficient balances in Payments and Taxi Wallet.
# Requirements: Payments API (8080) and Taxi API (8081) running locally in dev mode.

PAY_BASE=${PAY_BASE:-http://localhost:8080}
TAXI_BASE=${TAXI_BASE:-http://localhost:8081}

RIDER_PHONE=${RIDER_PHONE:-+963900001111}
DRIVER_PHONE=${DRIVER_PHONE:-+963900001112}

RIDER_NAME=${RIDER_NAME:-Test Rider}
DRIVER_NAME=${DRIVER_NAME:-Test Driver}

RIDER_TOPUP=${RIDER_TOPUP:-1000000}      # cents (10,000 SYP)
DRIVER_TOPUP=${DRIVER_TOPUP:-1000000}    # cents
TAXI_TOPUP=${TAXI_TOPUP:-200000}         # cents for taxi wallet (2,000 SYP)

echo "[SEED] Health checks..."
curl -fsS "$PAY_BASE/health" >/dev/null
curl -fsS "$TAXI_BASE/health" >/dev/null

tok_pay() { curl -s "$PAY_BASE/auth/verify_otp" -H 'Content-Type: application/json' -d "{\"phone\":\"$1\",\"otp\":\"123456\",\"name\":\"$2\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'; }
tok_taxi() { curl -s "$TAXI_BASE/auth/verify_otp" -H 'Content-Type: application/json' -d "{\"phone\":\"$1\",\"otp\":\"123456\",\"name\":\"$2\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'; }

echo "[SEED] Verify OTP in Payments..."
TOK_PAY_R=$(tok_pay "$RIDER_PHONE" "$RIDER_NAME")
TOK_PAY_D=$(tok_pay "$DRIVER_PHONE" "$DRIVER_NAME")

echo "[SEED] Topup Payments wallets (dev mint)..."
curl -fsS -X POST "$PAY_BASE/wallet/topup" -H "Authorization: Bearer $TOK_PAY_R" -H 'Content-Type: application/json' -d "{\"amount_cents\":$RIDER_TOPUP,\"idempotency_key\":\"seed-rider-$RIDER_PHONE\"}" >/dev/null || true
curl -fsS -X POST "$PAY_BASE/wallet/topup" -H "Authorization: Bearer $TOK_PAY_D" -H 'Content-Type: application/json' -d "{\"amount_cents\":$DRIVER_TOPUP,\"idempotency_key\":\"seed-driver-$DRIVER_PHONE\"}" >/dev/null || true

echo "[SEED] Verify OTP in Taxi..."
TOK_TAXI_R=$(tok_taxi "$RIDER_PHONE" "$RIDER_NAME")
TOK_TAXI_D=$(tok_taxi "$DRIVER_PHONE" "$DRIVER_NAME")

echo "[SEED] Setup driver in Taxi..."
curl -fsS -X POST "$TAXI_BASE/driver/apply" -H "Authorization: Bearer $TOK_TAXI_D" -H 'Content-Type: application/json' -d '{"vehicle_make":"Toyota","vehicle_plate":"TEST-DRIVER"}' >/dev/null || true
curl -fsS -X PUT "$TAXI_BASE/driver/status" -H "Authorization: Bearer $TOK_TAXI_D" -H 'Content-Type: application/json' -d '{"status":"available"}' >/dev/null
curl -fsS -X PUT "$TAXI_BASE/driver/location" -H "Authorization: Bearer $TOK_TAXI_D" -H 'Content-Type: application/json' -d '{"lat":33.5138, "lon":36.2765}' >/dev/null

echo "[SEED] Topup Taxi Wallet from main wallet (if TAXI_POOL_WALLET_PHONE configured)..."
TOP=$(curl -s -w "\n%{http_code}" -X POST "$TAXI_BASE/driver/taxi_wallet/topup" -H "Authorization: Bearer $TOK_TAXI_D" -H 'Content-Type: application/json' -d "{\"amount_cents\":$TAXI_TOPUP}")
TOP_BODY=$(echo "$TOP" | sed '$d')
TOP_CODE=$(echo "$TOP" | tail -n1)
if [ "$TOP_CODE" != "200" ]; then
  echo "[SEED] Taxi topup failed (HTTP $TOP_CODE). Response: $TOP_BODY"
  echo "[SEED] Continuing; if TAXI_POOL_WALLET_PHONE is set, ensure Payments is running and INTERNAL secrets match."
else
  echo "[SEED] Taxi wallet topup ok"
fi

echo "[SEED] Summary:"
echo "  Rider:  $RIDER_PHONE  (Payments topup: $RIDER_TOPUP cents)"
echo "  Driver: $DRIVER_PHONE  (Payments topup: $DRIVER_TOPUP cents, Taxi wallet topup: $TAXI_TOPUP cents)"

echo "[SEED] Current balances:"
curl -s "$PAY_BASE/wallet" -H "Authorization: Bearer $TOK_PAY_R" | sed -n '1p'
curl -s "$PAY_BASE/wallet" -H "Authorization: Bearer $TOK_PAY_D" | sed -n '1p'
curl -s "$TAXI_BASE/driver/taxi_wallet" -H "Authorization: Bearer $TOK_TAXI_D" | sed -n '1p'

echo "[SEED] Done."

