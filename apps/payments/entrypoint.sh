#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Waiting for DB to be ready..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text
url = os.environ.get('DB_URL')
timeout = 60
start = time.time()
last_err = None
while True:
    try:
        e = create_engine(url, pool_pre_ping=True, future=True)
        with e.connect() as c:
            c.execute(text('select 1'))
        break
    except Exception as e:
        last_err = e
        if time.time() - start > timeout:
            raise
        time.sleep(1)
print('DB ready')
PY

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8080}"
WORKERS="${UVICORN_WORKERS:-1}"
LOG_LEVEL="${UVICORN_LOG_LEVEL:-info}"
EXTRA_ARGS="${UVICORN_EXTRA_ARGS:-}"

echo "[entrypoint] Starting API server on ${HOST}:${PORT} (workers=${WORKERS})..."
CMD=(uvicorn app.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" --workers "${WORKERS}")
if [[ -n "${EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206  # intentional splitting of extra args
  EXTRA_ARR=(${EXTRA_ARGS})
  CMD+=("${EXTRA_ARR[@]}")
fi
exec "${CMD[@]}"
