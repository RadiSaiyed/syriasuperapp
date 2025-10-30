Backups

Postgres (und optional Redis) Backups für Super‑App Services.

Option A — Lokal (generisch)
- Env: set either `DB_URL` or `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`.
- Optional: set `REDIS_URL` to also export an RDB snapshot.
- Optional: set `S3_BUCKET` (and AWS credentials) to upload artifacts.

Run (generisch)
- Local file backups in `./backups`:
  `DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/payments ops/backups/pg_backup.sh FILE_PREFIX=payments`

- Upload zu S3:
  `DB_URL=... S3_BUCKET=my-backups-bucket S3_PREFIX=superapp/prod ops/backups/pg_backup.sh FILE_PREFIX=payments`

Spezifisch (Payments)
- Historisch: `ops/backups/payments_pg_backup.sh` bleibt verfügbar und ist äquivalent zu obigem generischen Script mit `FILE_PREFIX=payments`.

Option B — Auf dem Deploy‑Host (Docker Compose Netzwerk)
- Im Traefik‑Deploy Ordner:
  - Einzelnes DB‑Backup: `make -C ops/deploy/compose-traefik backup APP=payments`
  - Mehrere: `make -C ops/deploy/compose-traefik backup-all`
- Output: `ops/deploy/compose-traefik/backups/<app>_YYYYmmdd_HHMMSS.dump`
- Hinweis: Standard‑Credentials sind `postgres/postgres` (siehe docker‑compose). Überschreibe via `PGPASSWORD=...`.

Restore (Postgres)
- Beispiel:
  `pg_restore -c -d payments ./backups/payments_YYYYmmdd_HHMMSS.dump`

Automation
- Cron/systemd Timer auf dem Host oder CI‑Jobs.
- Retention über Storage‑Lifecycle (z. B. S3 Lifecycle Policies) sicherstellen.
- Notifications: Deploy‑Backups verwenden ops/backups/run_backup.sh und können bei Fehlern via Slack benachrichtigen (setze BACKUP_SLACK_WEBHOOK_URL in .env.prod).
