#!/usr/bin/env bash
set -euo pipefail

# Postgres backup for Payments database.
# Requires PG* env vars (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE) or DB_URL.
# Optionally uploads to S3 if AWS CLI is configured and S3_BUCKET is set.
# Optionally backs up Redis if REDIS_URL is set (writes dump.rdb).

parse_db_url() {
  # Very simple parser for postgresql://user:pass@host:port/db
  python3 - "$1" <<'PY'
import os,sys
from urllib.parse import urlparse
u = urlparse(sys.argv[1].replace('postgresql+psycopg2','postgresql'))
print("PGHOST=%s" % (u.hostname or ''))
print("PGPORT=%s" % (u.port or '5432'))
print("PGUSER=%s" % (u.username or ''))
print("PGPASSWORD=%s" % (u.password or ''))
print("PGDATABASE=%s" % (u.path.lstrip('/') or ''))
PY
}

if [[ -n "${DB_URL:-}" ]]; then
  eval "$(parse_db_url "$DB_URL")"
fi

if [[ -z "${PGDATABASE:-}" ]]; then
  echo "Set PG* env vars or DB_URL" >&2
  exit 2
fi

TS=$(date -u +%Y%m%d_%H%M%S)
OUT_DIR=${OUT_DIR:-backups}
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/payments_${TS}.dump"

echo "[backup] Dumping Postgres to $OUT_FILE"
pg_dump -Fc -Z 9 -f "$OUT_FILE" || { echo "pg_dump failed" >&2; exit 1; }

if [[ -n "${S3_BUCKET:-}" ]]; then
  KEY="${S3_PREFIX:-payments}/$(basename "$OUT_FILE")"
  echo "[backup] Uploading to s3://$S3_BUCKET/$KEY"
  aws s3 cp "$OUT_FILE" "s3://$S3_BUCKET/$KEY" --only-show-errors || echo "[warn] S3 upload failed"
fi

if [[ -n "${REDIS_URL:-}" ]]; then
  echo "[backup] Exporting Redis RDB (if local redis-cli configured)"
  if command -v redis-cli >/dev/null 2>&1; then
    # redis-cli supports: redis-cli -u $REDIS_URL --rdb file
    RDB_FILE="$OUT_DIR/redis_${TS}.rdb"
    redis-cli -u "$REDIS_URL" --rdb "$RDB_FILE" || echo "[warn] Redis dump failed"
    if [[ -n "${S3_BUCKET:-}" ]]; then
      KEY="${S3_PREFIX:-payments}/$(basename "$RDB_FILE")"
      aws s3 cp "$RDB_FILE" "s3://$S3_BUCKET/$KEY" --only-show-errors || echo "[warn] S3 upload (redis) failed"
    fi
  else
    echo "[warn] redis-cli not found; skipping Redis backup"
  fi
fi

echo "[backup] Done"

