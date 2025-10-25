Payments Backups

Postgres (and optional Redis) backups for the Payments service.

Quick start
- Env: set either `DB_URL` or `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`.
- Optional: set `REDIS_URL` to also export an RDB snapshot.
- Optional: set `S3_BUCKET` (and AWS credentials) to upload artifacts.

Run
- Local file backups in `./backups`:
  `DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/payments ops/backups/payments_pg_backup.sh`

- Upload to S3:
  `DB_URL=... S3_BUCKET=my-backups-bucket S3_PREFIX=superapp/prod ops/backups/payments_pg_backup.sh`

Restore (Postgres)
- Example:
  `pg_restore -c -d payments ./backups/payments_YYYYmmdd_HHMMSS.dump`

Automation
- Use cron or systemd timers to run the backup script periodically.
- Retention: handle pruning in the storage backend (e.g., S3 lifecycle policies).

