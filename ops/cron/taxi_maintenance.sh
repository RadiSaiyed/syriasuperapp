#!/usr/bin/env bash
# Trigger Taxi maintenance endpoints (reassign/dispatch) - suitable for cron/systemd timers.
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:9081}
ADMIN_TOKEN=${ADMIN_TOKEN:?ADMIN_TOKEN env required}
ACCEPT_TIMEOUT_SECS=${ACCEPT_TIMEOUT_SECS:-120}
START_TIMEOUT_SECS=${START_TIMEOUT_SECS:-300}
SCAN_LIMIT=${SCAN_LIMIT:-200}
WINDOW_MINUTES=${WINDOW_MINUTES:-15}

call() {
  local path=$1
  curl -fsS -X POST "$BASE_URL$path" \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -H "Content-Type: application/json" || true
}

call "/rides/reap_timeouts?accept_timeout_secs=$ACCEPT_TIMEOUT_SECS&limit=$SCAN_LIMIT"
call "/rides/reap_start_timeouts?start_timeout_secs=$START_TIMEOUT_SECS&limit=$SCAN_LIMIT"
call "/rides/dispatch_scheduled?window_minutes=$WINDOW_MINUTES"
