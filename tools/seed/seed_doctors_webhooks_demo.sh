#!/usr/bin/env bash
set -euo pipefail

# Seeds Doctors <-> Payments webhook flow:
# - Creates doctor profile + slot
# - Patient books appointment (creates payment_request_id)
# - Simulates acceptance webhook from Payments to Doctors with correct HMAC

DOCTORS_BASE=${DOCTORS_BASE:-http://localhost:8089}
PAY_BASE=${PAY_BASE:-http://localhost:8080}

log(){ echo -e "[doctors-webhooks] $*"; }

token(){
  local base=$1 phone=$2 name=$3
  curl -s -X POST "$base/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$base/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
import sys, json
print(json.load(sys.stdin).get('access_token',''))
PY
}

json_get(){ python3 - "$@" <<'PY'
import sys, json
data=json.load(sys.stdin)
key=sys.argv[1]
print(data.get(key,'') if isinstance(data, dict) else '')
PY
}

ts_now(){ python3 - "$@" <<'PY'
import time
print(int(time.time()))
PY
}

hmac_sign(){ python3 - "$@" <<'PY'
import sys, hmac, hashlib
secret=sys.argv[1]; ts=sys.argv[2]; ev=sys.argv[3]; body=sys.argv[4]
print(hmac.new(secret.encode(), (ts+ev).encode()+body.encode(), hashlib.sha256).hexdigest())
PY
}

main(){
  log "Doctors: $(curl -s "$DOCTORS_BASE/health" || echo 'down')  Payments: $(curl -s "$PAY_BASE/health" || echo 'down')"

  # Load webhook secret from doctors .env
  if [ -f apps/doctors/.env ]; then
    SECRET=$(awk -F= '/^PAYMENTS_WEBHOOK_SECRET=/{print $2}' apps/doctors/.env | tr -d '\r')
  fi
  SECRET=${SECRET:-}
  if [ -z "$SECRET" ]; then
    echo "PAYMENTS_WEBHOOK_SECRET not found in apps/doctors/.env" >&2
    exit 1
  fi

  # Doctor profile + slots
  DOC_PHONE=${DOC_PHONE:-+963941000010}
  PAT_PHONE=${PAT_PHONE:-+963942000020}
  TOK_DOC=$(token "$DOCTORS_BASE" "$DOC_PHONE" "Doctor")
  TOK_PAT=$(token "$DOCTORS_BASE" "$PAT_PHONE" "Patient")
  H_DOC="Authorization: Bearer $TOK_DOC"
  H_PAT="Authorization: Bearer $TOK_PAT"
  curl -s -X POST "$DOCTORS_BASE/doctor/profile" -H "$H_DOC" -H 'Content-Type: application/json' --data '{"specialty":"general","city":"Damascus","clinic_name":"Demo Clinic"}' >/dev/null
  # add a near-future slot (30min window)
  START=$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat().replace('+00:00','Z'))
PY
)
  END=$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc)+timedelta(minutes=45)).isoformat().replace('+00:00','Z'))
PY
)
  SLOT_ID=$(curl -s -X POST "$DOCTORS_BASE/doctor/slots" -H "$H_DOC" -H 'Content-Type: application/json' --data "{\"start_time\":\"$START\",\"end_time\":\"$END\",\"price_cents\":4000}" | json_get id)

  # Book appointment (generates payment_request_id if Payments connected)
  APPT=$(curl -s -X POST "$DOCTORS_BASE/appointments" -H "$H_PAT" -H 'Content-Type: application/json' --data "{\"slot_id\":\"$SLOT_ID\"}")
  PRID=$(echo "$APPT" | json_get payment_request_id)
  AID=$(echo "$APPT" | json_get id)
  log "Appointment=$AID  payment_request_id=$PRID"

  # Simulate Payments webhook: requests.accept
  TS=$(ts_now)
  EVENT="requests.accept"
  BODY=$(python3 - <<PY
import json, os
print(json.dumps({"type": "$EVENT", "data": {"id": "$PRID", "transfer_id": "TR_DEMO"}}, separators=(',',':')))
PY
)
  SIGN=$(hmac_sign "$SECRET" "$TS" "$EVENT" "$BODY")
  curl -s -X POST "$DOCTORS_BASE/payments/webhooks" \
    -H "X-Webhook-Ts: $TS" -H "X-Webhook-Event: $EVENT" -H "X-Webhook-Sign: $SIGN" \
    -H 'Content-Type: application/json' --data "$BODY" >/dev/null

  # Verify status
  curl -s "$DOCTORS_BASE/appointments" -H "$H_PAT" | python3 - <<'PY'
import sys, json
apps=json.load(sys.stdin).get('appointments',[])
for a in apps:
  print('[verify]', a.get('id'), a.get('status'), a.get('payment_request_id'))
PY
  log "Done."
}

main "$@"

