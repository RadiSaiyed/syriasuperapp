#!/usr/bin/env bash
set -euo pipefail

BUS_BASE=${BUS_BASE:-http://localhost:8082}

log(){ echo -e "[bus-seed] $*"; }

token(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$BUS_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$BUS_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
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

now_iso(){ python3 - "$@" <<'PY'
from datetime import datetime, timedelta, timezone
print(datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
PY
}

add_hours(){ python3 - "$@" <<'PY'
from datetime import datetime, timedelta, timezone
import sys
hrs=int(sys.argv[1])
print((datetime.now(timezone.utc)+timedelta(hours=hrs)).isoformat().replace('+00:00','Z'))
PY
}

main(){
  log "Health: $(curl -s "$BUS_BASE/health" || echo 'down')"

  # Operator admin
  OP_PHONE=${OP_PHONE:-+963960000010}
  OP_TOK=$(token "$OP_PHONE" "Bus Admin")
  H_OP="Authorization: Bearer $OP_TOK"

  log "Register operator (dev)…"
  OP_JSON=$(curl -s -X POST "$BUS_BASE/operators/register" -H "$H_OP" --get --data-urlencode 'name=Demo Bus Co.')
  OP_ID=$(echo "$OP_JSON" | json_val)
  if [ -z "$OP_ID" ]; then echo "Operator registration failed: $OP_JSON" >&2; exit 1; fi
  log "Operator=$OP_ID"

  # Create a trip 3 hours from now, 2-hour duration
  DEP=$(add_hours 3)
  ARR=$(add_hours 5)
  TRIP_JSON=$(curl -s -X POST "$BUS_BASE/operators/$OP_ID/trips" -H "$H_OP" -H 'Content-Type: application/json' \
    --data "{\"origin\":\"Damascus\",\"destination\":\"Aleppo\",\"depart_at\":\"$DEP\",\"arrive_at\":\"$ARR\",\"price_cents\":15000,\"seats_total\":40,\"bus_model\":\"Volvo\",\"bus_year\":2015}")
  TRIP_ID=$(echo "$TRIP_JSON" | json_val)
  if [ -z "$TRIP_ID" ]; then echo "Trip create failed: $TRIP_JSON" >&2; exit 1; fi
  log "Trip=$TRIP_ID"

  # Customer booking
  CUST_PHONE=${CUST_PHONE:-+963960000020}
  C_TOK=$(token "$CUST_PHONE" "Passenger")
  H_C="Authorization: Bearer $C_TOK"
  BOOK_JSON=$(curl -s -X POST "$BUS_BASE/bookings" -H "$H_C" -H 'Content-Type: application/json' --data "{\"trip_id\":\"$TRIP_ID\",\"seats_count\":1}")
  BID=$(echo "$BOOK_JSON" | json_val)
  log "Booking=$BID"
  log "Done."
}

main "$@"

