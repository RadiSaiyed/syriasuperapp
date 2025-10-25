#!/usr/bin/env bash
set -euo pipefail

UTIL_BASE=${UTIL_BASE:-http://localhost:8084}

log(){ echo -e "[utilities-seed] $*"; }

token(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$UTIL_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$UTIL_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
import sys, json
print(json.load(sys.stdin).get('access_token',''))
PY
}

first_id(){ python3 - "$@" <<'PY'
import sys, json
data=json.load(sys.stdin)
print((data[0]['id']) if isinstance(data, list) and data else '')
PY
}

main(){
  log "Health: $(curl -s "$UTIL_BASE/health" || echo 'down')"
  PHONE=${PHONE:-+963970000010}
  TOK=$(token "$PHONE" "Utilities User")
  H="Authorization: Bearer $TOK"

  # Seed billers (GET triggers dev seed) and pick mobile operator
  log "Listing billers…"
  BIL=$(curl -s "$UTIL_BASE/billers" -H "$H")
  MBIL=$(curl -s "$UTIL_BASE/billers?category=mobile" -H "$H")
  OP_ID=$(echo "$MBIL" | first_id)
  log "Mobile biller id: $OP_ID"

  # Refresh bills for a dummy account and pay first
  ACC=${ACC:-ACC-12345}
  curl -s -X POST "$UTIL_BASE/bills/refresh?account_id=$ACC" -H "$H" >/dev/null
  BILLS=$(curl -s "$UTIL_BASE/bills" -H "$H")
  BILL_ID=$(echo "$BILLS" | python3 - <<'PY'
import sys, json
data=json.load(sys.stdin)
rows=data.get('bills', []) if isinstance(data, dict) else []
print(rows[0]['id'] if rows else '')
PY
)
  if [ -n "$BILL_ID" ]; then
    log "Paying bill $BILL_ID (creates payment request in dev)…"
    curl -s -X POST "$UTIL_BASE/bills/$BILL_ID/pay" -H "$H" >/dev/null || true
  fi

  # Create a mobile topup
  if [ -n "$OP_ID" ]; then
    log "Creating topup via $OP_ID …"
    curl -s -X POST "$UTIL_BASE/topups" -H "$H" -H 'Content-Type: application/json' \
      --data "{\"operator_biller_id\":\"$OP_ID\",\"target_phone\":\"+963900000000\",\"amount_cents\":5000}" >/dev/null || true
  fi
  log "Done."
}

main "$@"

