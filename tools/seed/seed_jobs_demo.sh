#!/usr/bin/env bash
set -euo pipefail

JOBS_BASE=${JOBS_BASE:-http://localhost:8087}

log(){ echo -e "[jobs-seed] $*"; }

token(){
  local phone=$1 name=${2:-Seed}
  curl -s -X POST "$JOBS_BASE/auth/request_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\"}" >/dev/null || true
  curl -s -X POST "$JOBS_BASE/auth/verify_otp" -H 'Content-Type: application/json' --data "{\"phone\":\"$phone\",\"otp\":\"123456\",\"name\":\"$name\"}" | python3 - "$@" <<'PY'
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

main(){
  log "Health: $(curl -s "$JOBS_BASE/health" || echo 'down')"

  # Employer creates company and job
  EMP=${EMPLOYER_PHONE:-+963960000100}
  EMP_T=$(token "$EMP" "Employer")
  H_E="Authorization: Bearer $EMP_T"
  curl -s -X POST "$JOBS_BASE/employer/company" -H "$H_E" -H 'Content-Type: application/json' --data '{"name":"Demo Co","description":"We build things"}' >/dev/null || true
  J_JSON=$(curl -s -X POST "$JOBS_BASE/employer/jobs" -H "$H_E" -H 'Content-Type: application/json' \
    --data '{"title":"Backend Engineer","description":"FastAPI + Postgres","location":"Remote","salary_cents":0,"category":"engineering","employment_type":"full_time","is_remote":true,"tags":["python","fastapi"]}')
  JOB_ID=$(echo "$J_JSON" | json_val)
  log "Job=$JOB_ID"

  # Seeker applies
  SEEK=${SEEKER_PHONE:-+963960000200}
  SK_T=$(token "$SEEK" "Seeker")
  H_S="Authorization: Bearer $SK_T"
  curl -s -X POST "$JOBS_BASE/jobs/$JOB_ID/apply" -H "$H_S" -H 'Content-Type: application/json' --data '{"cover_letter":"I love Python."}' >/dev/null
  log "Done."
}

main "$@"

