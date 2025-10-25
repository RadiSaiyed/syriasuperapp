#!/usr/bin/env bash
set -euo pipefail

# Full Payments → Doctors flow:
# - Doctor profile + slot
# - Patient books appointment (creates Payment Request via /internal)
# - Register Payments webhook endpoint (as DEV merchant on patient) pointing to Doctors
# - Top-up doctor wallet (payer)
# - Accept Payment Request via Payments (doctor token)
# - Payments delivers webhook to Doctors; Doctors marks appointment confirmed

DOCTORS_BASE=${DOCTORS_BASE:-http://localhost:8089}
PAY_BASE=${PAY_BASE:-http://localhost:8080}

log(){ echo -e "[doctors-payments] $*"; }

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

main(){
  log "Doctors: $(curl -s "$DOCTORS_BASE/health" || echo 'down')  Payments: $(curl -s "$PAY_BASE/health" || echo 'down')"

  # Read doctors webhook secret
  if [ -f apps/doctors/.env ]; then
    DSECRET=$(awk -F= '/^PAYMENTS_WEBHOOK_SECRET=/{print $2}' apps/doctors/.env | tr -d '\r')
  fi
  if [ -z "${DSECRET:-}" ]; then echo "Missing PAYMENTS_WEBHOOK_SECRET in apps/doctors/.env" >&2; exit 1; fi

  DOC_PHONE=${DOC_PHONE:-+963941100010}
  PAT_PHONE=${PAT_PHONE:-+963941100020}

  # Doctors side users
  TOK_DOC_D=$(token "$DOCTORS_BASE" "$DOC_PHONE" "Doctor")
  TOK_PAT_D=$(token "$DOCTORS_BASE" "$PAT_PHONE" "Patient")
  H_DOC_D="Authorization: Bearer $TOK_DOC_D"
  H_PAT_D="Authorization: Bearer $TOK_PAT_D"

  # Create doctor profile + slot
  curl -s -X POST "$DOCTORS_BASE/doctor/profile" -H "$H_DOC_D" -H 'Content-Type: application/json' --data '{"specialty":"general","city":"Damascus","clinic_name":"Demo Clinic"}' >/dev/null
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
  SLOT_ID=$(curl -s -X POST "$DOCTORS_BASE/doctor/slots" -H "$H_DOC_D" -H 'Content-Type: application/json' --data "{\"start_time\":\"$START\",\"end_time\":\"$END\",\"price_cents\":4000}" | json_get id)

  # Patient books appointment: creates PR in Payments
  APPT=$(curl -s -X POST "$DOCTORS_BASE/appointments" -H "$H_PAT_D" -H 'Content-Type: application/json' --data "{\"slot_id\":\"$SLOT_ID\"}")
  PRID=$(echo "$APPT" | json_get payment_request_id)
  AID=$(echo "$APPT" | json_get id)
  log "Appointment=$AID payment_request_id=$PRID"

  # Payments tokens
  TOK_DOC_P=$(token "$PAY_BASE" "$DOC_PHONE" "DoctorPay")
  TOK_PAT_P=$(token "$PAY_BASE" "$PAT_PHONE" "PatientPay")
  H_DOC_P="Authorization: Bearer $TOK_DOC_P"
  H_PAT_P="Authorization: Bearer $TOK_PAT_P"

  # Doctor becomes DEV merchant (webhook owner) and registers Doctors endpoint
  curl -s -X POST "$PAY_BASE/payments/dev/become_merchant" -H "$H_DOC_P" >/dev/null || true
  DOCTORS_EP="http://host.docker.internal:8089/payments/webhooks"
  curl -s -X POST "$PAY_BASE/webhooks/endpoints" -H "$H_DOC_P" --get --data-urlencode "url=$DOCTORS_EP" --data-urlencode "secret=$DSECRET" >/dev/null

  # Patient tops up wallet (payer)
  curl -s -X POST "$PAY_BASE/wallet/topup" -H "$H_PAT_P" -H 'Content-Type: application/json' \
    -d '{"amount_cents": 100000, "idempotency_key":"pat-topup-1"}' >/dev/null

  # Accept request as patient (target pays requester=doctor)
  curl -s -X POST "$PAY_BASE/requests/$PRID/accept" -H "$H_PAT_P" >/dev/null

  # Best-effort: sweep webhook deliveries
  curl -s -X POST "$PAY_BASE/webhooks/process_pending" -H "$H_PAT_P" >/dev/null || true

  # Verify Doctors appointment status
  curl -s "$DOCTORS_BASE/appointments" -H "$H_PAT_D" | python3 - <<'PY'
import sys, json
apps=json.load(sys.stdin).get('appointments',[])
for a in apps:
  print('[verify]', a.get('id'), a.get('status'), a.get('payment_request_id'))
PY
  log "Done."
}

main "$@"
