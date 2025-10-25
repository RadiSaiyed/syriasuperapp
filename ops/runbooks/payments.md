Payments On-Call Runbook

Overview
- Critical SLOs: uptime, 5xx ratio, request latency (p95), webhook delivery success.
- Dashboards: Grafana dashboards `payments.json` and `superapp_overview.json`.
- Alerts: see `ops/observability/prometheus/alerts.yml`.

Uptime and Errors
- Check `http_requests_total` 5xx ratio panel and `ServiceDown`/`HighErrorRate` alerts.
- Health endpoint: `GET /health` on the Payments API.
- Logs: container logs for the API; look for exceptions around payment flows.

Latency
- Watch `http_request_duration_seconds` p95/99 panels.
- Investigate spikes by endpoint (labels include method and route path template).

Rate Limits / Brute Force
- Monitor 429 counts and OTP velocity.
- Adjust runtime via Admin API (requires `X-Admin-Token`):
  `POST /admin/config/rate_limit` with `{ "per_minute": 120, "auth_boost": 2, "exempt_otp": true }`.
- In emergencies, raise limits temporarily and revert after incident.

Webhooks
- Delivery metrics: `payments_webhook_deliveries_total` and `payments_webhook_attempts_total`.
- If failures accumulate:
  - Verify target endpoints (TLS, DNS, firewalls).
  - Requeue failed deliveries: `apps/payments/scripts/webhooks_requeue.py` (filters by endpoint optional).
  - Consider increasing backoff base via env `WEBHOOK_BASE_DELAY_SECS` or poller `WEBHOOK_WORKER_POLL_SECS`.
- Idempotency: receivers should dedupe using `X-Delivery-ID` header.

Reconciliation / Settlement
- Verify ledger invariants and balances:
  - Dry run: `DB_URL=... python apps/payments/scripts/reconcile.py`
  - Fix balances (if approved): `DB_URL=... python apps/payments/scripts/reconcile.py --fix-balances`
- Generate merchant settlement CSV:
  `DB_URL=... python apps/payments/scripts/settlement_report.py --from 2025-09-01T00:00:00Z --to 2025-09-30T23:59:59Z > settlement.csv`

Backups & Restore
- On-demand backup: see `ops/backups/README.md`.
- Restore procedure:
  1) Stop API writes.
  2) Restore Postgres via `pg_restore`.
  3) Restore Redis snapshot if required.
  4) Run `reconcile.py` and sanity checks before resuming traffic.

Secrets & Key Rotation
- Rotate periodically and on membership changes.
- Payments secrets in `.env`: `JWT_SECRET`, `INTERNAL_API_SECRET`, `ADMIN_TOKEN`.
  - Rotate and restart API.
  - Ensure verticals update to the new `PAYMENTS_INTERNAL_SECRET` to match `INTERNAL_API_SECRET`.
- Merchant API keys: create new, migrate clients, then revoke old keys.
- See `ops/secrets/ROTATION.md` for detailed steps.

Incident Communication
- Page the on-call via Alertmanager routing.
- Capture timelines, customer impact, and mitigation in the incident doc.
- Open a follow-up issue for root cause and prevention actions.

