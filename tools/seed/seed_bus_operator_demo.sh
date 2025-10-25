#!/usr/bin/env bash
set -euo pipefail

BUS_BASE=${BUS_BASE:-http://localhost:8082}
PAY_BASE=${PAY_BASE:-http://localhost:8080}

OP_ADMIN_PHONE=${OP_ADMIN_PHONE:-+963900099001}
OP_NAME=${OP_NAME:-"Demo Bus"}
OP_MERCHANT_PHONE=${OP_MERCHANT_PHONE:-+963999999999}

USER1_PHONE=${USER1_PHONE:-+963900010001}
USER2_PHONE=${USER2_PHONE:-+963900010002}

log(){ echo -e "[seed] $*"; }

bus_token(){
  local phone=$1
  curl -s -X POST "$BUS_BASE/auth/request_otp" \
    -H 'Content-Type: application/json' \
    -d "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$BUS_BASE/auth/verify_otp" \
    -H 'Content-Type: application/json' \
    -d "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"Seed\"}" \
    | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'
}

pay_token(){
  local phone=$1
  curl -s -X POST "$PAY_BASE/auth/request_otp" \
    -H 'Content-Type: application/json' \
    -d "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$PAY_BASE/auth/verify_otp" \
    -H 'Content-Type: application/json' \
    -d "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"Seed\"}" \
    | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p'
}

topup(){
  local tok=$1 amount=$2
  curl -s -X POST "$PAY_BASE/wallet/topup" \
    -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' \
    -d "{\"amount_cents\":$amount,\"idempotency_key\":\"seed-$(date +%s%N)\"}" >/dev/null
}

create_operator(){
  local tok=$1
  local id
  id=$(curl -s -X POST "$BUS_BASE/operators/register" \
    -H "Authorization: Bearer $tok" \
    --get --data-urlencode "name=$OP_NAME" --data-urlencode "merchant_phone=$OP_MERCHANT_PHONE")
  # If already exists, id will be empty; try read from memberships
  local op_id
  op_id=$(echo "$id" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
  if [[ -z "$op_id" ]]; then
    op_id=$(curl -s "$BUS_BASE/operators/me" -H "Authorization: Bearer $tok" \
      | sed -n "s/.*{\\\"operator_id\\\":\\\"\([^-\"]*-[^\"]*\)\\\",\\\"operator_name\\\":\\\"$OP_NAME\\\".*/\1/p")
  fi
  echo "$op_id"
}

create_trip(){
  local tok=$1 op_id=$2 origin=$3 dest=$4 depart_iso=$5 price=$6 seats=$7
  curl -s -X POST "$BUS_BASE/operators/$op_id/trips" \
    -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' \
    -d "{\"origin\":\"$origin\",\"destination\":\"$dest\",\"depart_at\":\"$depart_iso\",\"price_cents\":$price,\"seats_total\":$seats}" \
    | sed -n 's/.*"id":"\([^"]*\)".*/\1/p'
}

create_booking(){
  local tok=$1 trip_id=$2 seats=$3
  curl -s -X POST "$BUS_BASE/bookings" \
    -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' \
    -d "{\"trip_id\":\"$trip_id\",\"seats_count\":$seats}" \
    | sed -n 's/.*"id":"\([^"]*\)".*"payment_request_id":"\([^"]*\)".*/\1 \2/p'
}

confirm_booking_bus(){
  local tok=$1 booking_id=$2
  curl -s -X POST "$BUS_BASE/bookings/$booking_id/confirm" -H "Authorization: Bearer $tok" >/dev/null
}

accept_request(){
  local pay_tok=$1 req_id=$2
  curl -s -X POST "$PAY_BASE/requests/$req_id/accept" -H "Authorization: Bearer $pay_tok" >/dev/null
}

# --- run ---
log "Seeding Bus Operator demo..."

OP_TOK=$(bus_token "$OP_ADMIN_PHONE")
if [[ -z "$OP_TOK" ]]; then echo "failed to auth operator admin"; exit 1; fi
log "Operator admin token acquired for $OP_ADMIN_PHONE"

OP_ID=$(create_operator "$OP_TOK")
if [[ -z "$OP_ID" ]]; then echo "failed to create/find operator"; exit 1; fi
log "Operator: $OP_NAME ($OP_ID), merchant_phone=$OP_MERCHANT_PHONE"

# Depart times (UTC) for next day
DEP1=$(date -u -v+1d +"%Y-%m-%dT08:00:00Z" 2>/dev/null || date -u -d "+1 day" +"%Y-%m-%dT08:00:00Z")
DEP2=$(date -u -v+1d +"%Y-%m-%dT12:00:00Z" 2>/dev/null || date -u -d "+1 day" +"%Y-%m-%dT12:00:00Z")
DEP3=$(date -u -v+1d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d "+1 day" +"%Y-%m-%dT14:00:00Z")

T1=$(create_trip "$OP_TOK" "$OP_ID" Damascus Aleppo "$DEP1" 20000 40)
T2=$(create_trip "$OP_TOK" "$OP_ID" Damascus Aleppo "$DEP2" 22000 40)
T3=$(create_trip "$OP_TOK" "$OP_ID" Damascus Homs "$DEP3" 12000 40)
log "Trips created: $T1 $T2 $T3"

# Bookings by two demo users
U1_TOK=$(bus_token "$USER1_PHONE")
U2_TOK=$(bus_token "$USER2_PHONE")
U1_PAY_TOK=$(pay_token "$USER1_PHONE")
U2_PAY_TOK=$(pay_token "$USER2_PHONE")

topup "$U1_PAY_TOK" 100000 || true
topup "$U2_PAY_TOK" 100000 || true

read B1 PR1 <<< "$(create_booking "$U1_TOK" "$T1" 2)"
read B2 PR2 <<< "$(create_booking "$U2_TOK" "$T2" 1)"
log "Bookings created: $B1 ($PR1), $B2 ($PR2)"

if [[ -n "${PR1:-}" ]]; then accept_request "$U1_PAY_TOK" "$PR1"; fi
if [[ -n "${PR2:-}" ]]; then accept_request "$U2_PAY_TOK" "$PR2"; fi

confirm_booking_bus "$U1_TOK" "$B1" || true
confirm_booking_bus "$U2_TOK" "$B2" || true

log "Done. Open portal and check bookings + summary."

