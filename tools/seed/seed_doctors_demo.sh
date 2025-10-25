#!/usr/bin/env bash
set -euo pipefail

DOCTORS_BASE=${DOCTORS_BASE:-http://localhost:8089}

log(){ echo -e "[doctors-seed] $*"; }

token(){
  local phone=$1 name=$2 role=${3:-patient}
  curl -s -X POST "$DOCTORS_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$DOCTORS_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\",\"role\":\"$role\"}" | python3 - "$@" <<'PY'
import sys, json
print(json.load(sys.stdin).get('access_token',''))
PY
}

json_val(){ python3 - "$@" <<'PY'
import sys, json
data=json.load(sys.stdin)
import sys
key=sys.argv[1] if len(sys.argv)>1 else 'id'
print(data.get(key,'') if isinstance(data, dict) else '')
PY
}

now_iso(){ python3 - "$@" <<'PY'
from datetime import datetime, timedelta, timezone
print(datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
PY
}

add_mins(){ python3 - "$@" <<'PY'
from datetime import datetime, timedelta, timezone
import sys
mins=int(sys.argv[1])
print((datetime.now(timezone.utc)+timedelta(minutes=mins)).isoformat().replace('+00:00','Z'))
PY
}

main(){
  log "Health: $(curl -s "$DOCTORS_BASE/health" || echo 'down')"

  # Doctor auth
  DOC_PHONE=${DOC_PHONE:-+963940000010}
  DOC_TOK=$(token "$DOC_PHONE" "Dr Seed" "doctor")
  H_DOC="Authorization: Bearer $DOC_TOK"

  # Upsert profile
  curl -s -X POST "$DOCTORS_BASE/doctor/profile" -H "$H_DOC" -H 'Content-Type: application/json' --data '{"specialty":"cardiology","city":"Damascus","clinic_name":"Heart Center","address":"Main 10","bio":"Cardio specialist"}' >/dev/null

  # Add 3 future slots (30min spacing)
  S1=$(curl -s -X POST "$DOCTORS_BASE/doctor/slots" -H "$H_DOC" -H 'Content-Type: application/json' --data "{\"start_time\":\"$(add_mins 30)\",\"end_time\":\"$(add_mins 60)\",\"price_cents\":5000}" | json_val id)
  S2=$(curl -s -X POST "$DOCTORS_BASE/doctor/slots" -H "$H_DOC" -H 'Content-Type: application/json' --data "{\"start_time\":\"$(add_mins 90)\",\"end_time\":\"$(add_mins 120)\",\"price_cents\":6000}" | json_val id)
  S3=$(curl -s -X POST "$DOCTORS_BASE/doctor/slots" -H "$H_DOC" -H 'Content-Type: application/json' --data "{\"start_time\":\"$(add_mins 150)\",\"end_time\":\"$(add_mins 180)\",\"price_cents\":7000}" | json_val id)
  log "Slots: $S1 $S2 $S3"

  # Patient auth and booking first slot
  PAT_PHONE=${PAT_PHONE:-+963950000020}
  PAT_TOK=$(token "$PAT_PHONE" "Patient Seed" "patient")
  H_PAT="Authorization: Bearer $PAT_TOK"
  if [ -n "$S1" ]; then
    curl -s -X POST "$DOCTORS_BASE/appointments" -H "$H_PAT" -H 'Content-Type: application/json' --data "{\"slot_id\":\"$S1\"}" >/dev/null
  fi
  log "Done."
}

main "$@"

