#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Waiting for DB to be ready..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text
url = os.environ.get('DB_URL')
timeout = 60
start = time.time()
while True:
    try:
        e = create_engine(url, pool_pre_ping=True, future=True)
        with e.connect() as c:
            c.execute(text('select 1'))
        break
    except Exception:
        if time.time() - start > timeout:
            raise
        time.sleep(1)
print('DB ready')
PY

if [ -d "/app/alembic" ]; then
echo "[entrypoint] Bootstrapping schema if empty..."
python - <<'PY'
import os
from sqlalchemy import create_engine, inspect
url = os.environ.get('DB_URL')
e = create_engine(url, pool_pre_ping=True, future=True)
ins = inspect(e)
tables = set(ins.get_table_names())
if 'users' not in tables or 'shops' not in tables:
    print('[bootstrap] creating base schema via SQLAlchemy create_all()')
    from app.models import Base
    Base.metadata.create_all(bind=e)
else:
    print('[bootstrap] base schema present')
PY

echo "[entrypoint] Running Alembic migrations..."
if ! alembic upgrade head; then
  echo "[entrypoint] Alembic migration failed; continuing to start app" >&2
fi
fi

echo "[entrypoint] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8083

