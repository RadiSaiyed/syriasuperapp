#!/usr/bin/env bash
set -euo pipefail

wait_http_ok() {
  local url="$1"; shift || true
  local timeout="${1:-60}"; shift || true
  local start=$(date +%s)
  echo "[wait] $url (timeout ${timeout}s)"
  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "[wait] ok: $url"; return 0;
    fi
    local now=$(date +%s)
    if (( now - start >= timeout )); then
      echo "[wait] timeout: $url" >&2; return 1;
    fi
    sleep 1
  done
}

