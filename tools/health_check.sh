#!/usr/bin/env bash
set -euo pipefail

PY_BIN="python3.11"
if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  PY_BIN="python3"
fi

echo "[health] Using Python: $("$PY_BIN" -V 2>/dev/null || echo 'python not found')"

pip_cmd="$PY_BIN -m pip"
pytest_cmd="$PY_BIN -m pytest"

if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  echo "python not found. Please install Python 3.11+ and rerun." >&2
  exit 1
fi

echo "[health] Installing requirements for all apps"
for d in apps/*; do
  if [ -f "$d/requirements.txt" ]; then
    echo "[health] pip install -r $d/requirements.txt"
    $pip_cmd install -q -r "$d/requirements.txt"
  fi
done

PG_PORT=""
if command -v docker >/dev/null 2>&1; then
  # Find a free host port for Postgres (prefer 5432, otherwise scan 5540-5599)
  if nc -z localhost 5432 >/dev/null 2>&1; then
    for p in $(seq 5540 5599); do
      if ! nc -z localhost "$p" >/dev/null 2>&1; then PG_PORT="$p"; break; fi
    done
  else
    PG_PORT=5432
  fi
  if [[ -z "$PG_PORT" ]]; then
    echo "[health] No free port for Postgres found (checked 5432 and 5540-5599)." >&2
    exit 1
  fi
  echo "[health] Starting Postgres 16 on host port ${PG_PORT} via Docker"
  docker rm -f health-postgres >/dev/null 2>&1 || true
  docker run -d --name health-postgres -e POSTGRES_PASSWORD=postgres -p ${PG_PORT}:5432 postgres:16-alpine >/dev/null
  echo -n "[health] Waiting for Postgres"
  for i in $(seq 1 60); do
    if docker exec health-postgres pg_isready -U postgres >/dev/null 2>&1; then echo " ready"; break; fi
    echo -n "."; sleep 1;
  done
else
  echo "[health] Docker not available. Ensure a local Postgres is running on 5432."
  PG_PORT=5432
fi

REDIS_PORT=""
if command -v docker >/dev/null 2>&1; then
  # Find free host port for Redis (prefer 6379 else 6380-6399)
  if nc -z localhost 6379 >/dev/null 2>&1; then
    for p in $(seq 6380 6399); do
      if ! nc -z localhost "$p" >/dev/null 2>&1; then REDIS_PORT="$p"; break; fi
    done
  else
    REDIS_PORT=6379
  fi
  if [[ -z "$REDIS_PORT" ]]; then
    echo "[health] No free port for Redis found (checked 6379 and 6380-6399)." >&2
    exit 1
  fi
  echo "[health] Starting Redis 7 on host port ${REDIS_PORT} via Docker"
  docker rm -f health-redis >/dev/null 2>&1 || true
  docker run -d --name health-redis -p ${REDIS_PORT}:6379 redis:7-alpine >/dev/null
  # Expose both REDIS_TEST_URL (preferred by shared libs) and REDIS_URL (used by some tests)
  export REDIS_TEST_URL="redis://localhost:${REDIS_PORT}/0"
  export REDIS_URL="$REDIS_TEST_URL"
else
  echo "[health] Docker not available. Ensure a local Redis is running on 6379."
  export REDIS_TEST_URL="redis://localhost:6379/0"
  export REDIS_URL="$REDIS_TEST_URL"
fi

echo "[health] Running pytest per app"
# Ensure shared libs are importable from repo root
REPO_ROOT="$(pwd)"
export PYTHONPATH="$REPO_ROOT/libs/superapp_shared${PYTHONPATH:+:$PYTHONPATH}"
FAILED=0
for d in apps/*; do
  if [ -d "$d/tests" ]; then
    echo "[health] ==> $d"
    export DB_URL="postgresql+psycopg2://postgres:postgres@localhost:${PG_PORT}/$(basename "$d")"
    # If using our dockerized Postgres, ensure per-app DB exists
    if docker ps --format '{{.Names}}' | grep -q '^health-postgres$'; then
      if ! docker exec health-postgres psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$(basename "$d")'" | grep -q 1; then
        docker exec health-postgres createdb -U postgres "$(basename "$d")"
      fi
    fi
    (cd "$d" && $pytest_cmd -q) || FAILED=1
  fi
done

if [ "$FAILED" -ne 0 ]; then
  echo "[health] Some tests failed." >&2
  exit 1
fi

echo "[health] All backend tests passed."

# Cleanup ephemeral Postgres if we started it
if docker ps --format '{{.Names}}' | grep -q '^health-postgres$'; then
  docker rm -f health-postgres >/dev/null 2>&1 || true
fi
# Cleanup ephemeral Redis if we started it
if docker ps --format '{{.Names}}' | grep -q '^health-redis$'; then
  docker rm -f health-redis >/dev/null 2>&1 || true
fi
