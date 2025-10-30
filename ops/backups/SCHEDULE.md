Backup Scheduling (Cron/Systemd)

This doc shows how to schedule periodic DB backups for the Super‑App deploy.

Prereqs
- Deploy stack lives at a fixed path, e.g. /opt/superapp (contains ops/deploy/compose-traefik/.env.prod)
- Docker installed (for pg_dump container) and network "internal" from deploy is present.
- Optional S3 upload configured in .env.prod (S3_BUCKET, S3_PREFIX, AWS_*).

Option A — Cron
- Edit root crontab: `sudo crontab -e`
- Example: daily at 02:15 UTC, all apps

  15 2 * * * cd /opt/superapp && make -C ops/deploy/compose-traefik backup-all >> /var/log/superapp-backup.log 2>&1

- Single app (payments) hourly at minute 5

  5 * * * * cd /opt/superapp && make -C ops/deploy/compose-traefik backup APP=payments >> /var/log/superapp-backup-payments.log 2>&1

Option B — systemd timers
- Quick setup (recommended): use the installer script to copy templates and create per‑app schedules via drop‑ins

  sudo BASE_DIR=/opt/superapp bash /opt/superapp/ops/backups/install_timers.sh

- Manual setup — create unit templates under /etc/systemd/system/

  File: /etc/systemd/system/superapp-backup@.service
  [Unit]
  Description=SuperApp DB Backup (%i)
  Wants=docker.service
  After=docker.service

  [Service]
  Type=oneshot
  WorkingDirectory=/opt/superapp
  EnvironmentFile=/opt/superapp/ops/deploy/compose-traefik/.env.prod
  ExecStart=/usr/bin/make -C ops/deploy/compose-traefik backup APP=%i
  Nice=10

  File: /etc/systemd/system/superapp-backup@.timer
  [Unit]
  Description=Timer for SuperApp DB Backup (%i)

  [Timer]
  OnCalendar=daily
  Persistent=true

  [Install]
  WantedBy=timers.target

- Enable for specific apps (examples):
  sudo systemctl daemon-reload
  sudo systemctl enable --now superapp-backup@payments.timer
  sudo systemctl enable --now superapp-backup@commerce.timer
  sudo systemctl enable --now superapp-backup@taxi.timer

- Check status/logs:
  systemctl list-timers | grep superapp-backup@
  journalctl -u superapp-backup@payments -n 200 -f

Notes
- S3 upload happens automatically if S3_BUCKET is set in .env.prod.
- Backup files are written to ops/deploy/compose-traefik/backups/ and git‑ignored.
- Slack notifications: set BACKUP_SLACK_WEBHOOK_URL in .env.prod. Success notifications can be enabled with BACKUP_SLACK_NOTIFY_SUCCESS=true.
