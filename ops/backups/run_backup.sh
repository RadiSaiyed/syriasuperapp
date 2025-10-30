#!/usr/bin/env bash
set -euo pipefail

APP="${1:-}"
if [[ -z "$APP" ]]; then
  echo "Usage: $0 <app>" >&2
  exit 2
fi

# Load deploy env for S3/AWS and other variables
if [[ -f ops/deploy/compose-traefik/.env.prod ]]; then
  set -a; . ops/deploy/compose-traefik/.env.prod; set +a
fi

LOG_DIR="/tmp"
TS=$(date -u +%Y%m%d_%H%M%S)
HOST=$(hostname -f 2>/dev/null || hostname)
LOG_FILE="$LOG_DIR/superapp-backup-${APP}-${TS}.log"

echo "[run] $(date -u +%FT%TZ) backup start: app=${APP} host=${HOST}" | tee -a "$LOG_FILE"
set +e
make -C ops/deploy/compose-traefik backup APP="$APP" >>"$LOG_FILE" 2>&1
CODE=$?
set -e

# Extract output file path from log if present
OUT_FILE=$(grep -Eo "backups/[a-z_]+_[0-9]{8}_[0-9]{6}\.dump" "$LOG_FILE" | tail -n1 || true)

notify_slack() {
  local status="$1"; shift
  local color emoji
  if [[ "$status" == "ok" ]]; then
    emoji=":white_check_mark:"
  else
    emoji=":x:"
  fi
  if [[ -n "${BACKUP_SLACK_WEBHOOK_URL:-}" ]]; then
    local text
    text="${emoji} backup ${status} — app=${APP} host=${HOST} time=$(date -u +%FT%TZ)"
    if [[ -n "$OUT_FILE" ]]; then
      text+=" file=$OUT_FILE"
    fi
    # Tail last lines on failure for context
    if [[ "$status" != "ok" ]]; then
      local tail_txt
      tail_txt=$(tail -n 40 "$LOG_FILE" | sed 's/"/\"/g')
      text+="\n\n\`\n${tail_txt}\n\`"
    fi
    curl -fsS -X POST -H 'Content-Type: application/json' \
      --data "{\"text\": \"${text}\"}" \
      "$BACKUP_SLACK_WEBHOOK_URL" >/dev/null 2>&1 || true
  fi
}

# Basic health check: exit code and output file existence
if [[ $CODE -ne 0 ]]; then
  echo "[run] backup failed with exit code $CODE" | tee -a "$LOG_FILE"
  notify_slack fail
  exit $CODE
fi

if [[ -n "$OUT_FILE" && -f "ops/deploy/compose-traefik/$OUT_FILE" ]]; then
  # size check (>1KB)
  sz=$(stat -f %z "ops/deploy/compose-traefik/$OUT_FILE" 2>/dev/null || stat -c %s "ops/deploy/compose-traefik/$OUT_FILE" 2>/dev/null || echo 0)
  if [[ "${sz}" -lt 1024 ]]; then
    echo "[run] backup file too small (${sz} bytes): $OUT_FILE" | tee -a "$LOG_FILE"
    notify_slack fail
    exit 1
  fi
fi

echo "[run] backup success: ${OUT_FILE:-unknown}" | tee -a "$LOG_FILE"
if [[ "${BACKUP_SLACK_NOTIFY_SUCCESS:-false}" == "true" ]]; then
  notify_slack ok
fi

exit 0

