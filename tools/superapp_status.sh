#!/usr/bin/env bash
set -euo pipefail

# Simple status dashboard for all Super‑App services.
# Pings /health of each API and prints a one‑line summary.
# Usage: bash tools/superapp_status.sh [--base http://localhost]

BASE="${1:-}"
if [[ "$BASE" == "--base" ]]; then
  BASE="$2"; shift 2 || true
fi
BASE=${BASE:-http://localhost}

services=(payments taxi bus commerce utilities freight automarket jobs stays doctors food chat)
ports=(8080 8081 8082 8083 8084 8085 8086 8087 8088 8089 8090 8091)

printf "%-12s %-8s %-8s %-24s\n" SERVICE STATUS CODE ENV
printf "%-12s %-8s %-8s %-24s\n" -------- ------ ---- ---

for i in "${!services[@]}"; do
  svc=${services[$i]}
  port=${ports[$i]}
  url="$BASE:$port/health"
  code=000
  body=""
  if out=$(curl -sS -m 2 -w "\n%{http_code}" "$url" 2>/dev/null); then
    body=$(echo "$out" | sed -n '1p')
    code=$(echo "$out" | sed -n '2p')
  fi
  status="DOWN"
  env="-"
  if [[ "$code" == "200" ]]; then
    status="UP"
    env=$(echo "$body" | python3 - <<'PY'
import sys, json
try:
  d=json.load(sys.stdin)
  print(d.get('env','-'))
except Exception:
  print('-')
PY
)
  fi
  printf "%-12s %-8s %-8s %-24s\n" "$svc" "$status" "$code" "$env"
done
