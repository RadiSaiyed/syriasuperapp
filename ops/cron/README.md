# Taxi maintenance cron

Use `taxi_maintenance.sh` to invoke assignment cleanup and scheduled ride dispatch via cron or systemd timers.

Example systemd timer:

```
[Unit]
Description=Taxi maintenance cron

[Service]
Type=oneshot
Environment=BASE_URL=http://localhost:9081
Environment=ADMIN_TOKEN=replace-with-admin-token
ExecStart=/usr/local/bin/taxi_maintenance.sh

[Install]
WantedBy=multi-user.target
```

Run every two minutes using a systemd timer or cron entry:

```
* * * * * BASE_URL=https://taxi-staging.example.com ADMIN_TOKEN=... /opt/syria-superapp/ops/cron/taxi_maintenance.sh >> /var/log/taxi_cron.log 2>&1
```

