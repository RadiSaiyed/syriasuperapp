Syria Super‑App — Production Readiness

Scope: Backend services under `apps/*`, shared lib `libs/superapp_shared`, CI/CD (`.github/workflows`), and deploy templates under `ops/`.

Summary
- Strong: service guardrails for prod (CORS, OTP, dev toggles), Dockerfiles per app, Prometheus metrics, CI for tests and Docker publish, Traefik deploy bundle, backups for Payments.
- Gaps: secrets committed (.env in many apps), migrations missing for several services while `AUTO_CREATE_SCHEMA` is blocked in prod, inconsistent rate‑limit enforcement, internal HMAC not required by default, logging/retention, secret scanning, and DB backups for non‑Payments apps.

P0 — Must Do Before Prod
- Secrets hygiene
  - Remove committed `.env` files under `apps/*`. Keep only `.env.example`. Inject real secrets via CI or host env/secrets.
  - Rotate any leaked secrets (JWT, admin tokens, internal secrets, API keys). Search committed files and GH history.
  - Add a secret scanning step in CI (e.g., Gitleaks). Block on findings.
- DB schema/migrations
  - Add Alembic migrations for all services that set `AUTO_CREATE_SCHEMA=false` in prod and rely on SQLAlchemy `create_all` at boot.
    - Examples lacking Alembic: `apps/commerce`, `apps/food`, `apps/doctors`, etc.
    - Existing: `apps/payments`, `apps/taxi`.
  - Update entrypoints (or deploy runbooks) to run migrations on startup where available.
- Rate limiting
  - Enforce `RATE_LIMIT_BACKEND=redis` in prod across all services (some already enforce; unify the rest).
  - Ensure `REDIS_URL` is set to a managed Redis or hardened local instance.
- Internal API auth
  - Require HMAC on Payments internal endpoints by setting `INTERNAL_REQUIRE_HMAC=true` and update callers to sign (`libs/superapp_shared/superapp_shared/internal_hmac.py:18`).
  - For idempotent internal endpoints, retries are allowed when `X-Idempotency-Key` is sent; the HMAC replay TTL is bypassed only in that case (see `apps/payments/app/routers/internal.py:1`). Keep short TTLs (e.g., 60–300s) otherwise.
- CORS and proxy headers
  - Set explicit `ALLOWED_ORIGINS` per API; no `*` in prod.
  - Behind Traefik, pass `UVICORN_EXTRA_ARGS=--proxy-headers --forwarded-allow-ips='*'` (or restricted to proxy IPs).
- Observability & backups
  - Enable and scrape `/metrics` for all services (Prometheus). Deploy `ops/observability` or integrate with managed monitoring.
  - Add DB backup scripts/policies for non‑Payments services similarly to `ops/backups/payments_pg_backup.sh:1`.
  - Prometheus client is included by default; endpoints expose `http_requests_total` counters. Payments adds latency histograms.

P1 — Should Do Next
- Logs & tracing
  - Ship container logs to a central sink (Loki, ELK, or CloudWatch). Include request IDs in logs (middleware exists).
  - Consider basic error tracking (e.g., Sentry) for APIs and clients.
- CI/CD hardening
  - Add secret scanning and SCA (Dependency Review) to CI.
  - Pin base images and Python dependency versions where feasible; review Dockerfiles for non‑root user if needed.
- Admin/ops
  - Standardize admin token handling; prefer hashed tokens where supported (e.g., `ADMIN_TOKEN_SHA256` in Taxi).
  - Expand runbooks in `ops/runbooks` for common incidents (rate‑limit tuning, webhook failures, DB failover, restores).
- Webhooks
  - Payments: run Celery worker and beat in prod; validate retry/backoff and idempotency in downstream consumers.

P2 — Nice to Have
- Multi‑region readiness: document strategy for DB/Redis managed services and DNS failover.
- JWKS option for JWT validation across services (Taxi supports `JWT_JWKS_URL`; consider adding to others).
- Canary releases and blue/green using labels in the Traefik stack.

Service‑Specific Notes
- Payments (`apps/payments`)
  - Good: Alembic migration on start via `entrypoint.sh:1`, Celery worker/beat in compose, prod guards in `app/config.py:87`.
  - Set `INTERNAL_REQUIRE_HMAC=true` and rotate all secrets. Set `STARTING_CREDIT_CENTS=0` for prod unless launching promo.
- Taxi (`apps/taxi`)
  - Good: robust prod checks (`app/config.py:...`), requires Redis rate limit and JWKS or strong secrets, TomTom API key required.
  - Ensure reaper sidecar configured with admin token in deploy bundle.
- Others (Commerce, Food, Doctors, Stays, etc.)
  - Add Alembic migrations or provision schema out‑of‑band before disabling `AUTO_CREATE_SCHEMA` in prod.
  - Enforce Redis rate limit and explicit CORS.

Observability
- Dashboards: `ops/observability/grafana/dashboards/*`
  - Existing: `payments.json`, `taxi.json`, `commerce.json`, `doctors.json`, `taxi_wallet.json`, `superapp_overview.json`
  - Added (minimal: Req/s + p90/p99): `bus.json`, `flights.json`, `stays.json`, `utilities.json`, `freight.json`, `chat.json`, `agriculture.json`, `carmarket.json`, `carrental.json`, `ai_gateway.json`, `livestock.json`, `realestate.json`
- Alerts: `ops/observability/prometheus/alerts.yml`
  - Generic: `ServiceDown`, `HighErrorRate`, latency `HighLatencyP99` (>1s), `HighLatencyP99Critical` (>2s)
  - Payments‑specific: webhook retries
- Alertmanager: `ops/observability/alertmanager/alertmanager.yml`
  - Receivers: `ops-admin` (webhook), `slack` (warning/info/critical), `email` (critical only)
  - Required env: `SLACK_WEBHOOK_URL`, `SLACK_CHANNEL`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`

Deploy Templates
- Traefik bundle: `ops/deploy/compose-traefik/docker-compose.yml:1`
  - Set `INTERNAL_REQUIRE_HMAC=true` under payments API env.
  - Set `ALLOWED_ORIGINS` per service and, optionally, `UVICORN_EXTRA_ARGS`.

Automation
- Run the static prod audit: `make prod-audit`
  - Checks for committed `.env`, Alembic presence vs. `create_all`, config hardening, and HMAC flag in the deploy template.
- Scaffold migrations (templates): `make scaffold-alembic`
  - Then per service: `cd apps/<service> && DB_URL=... alembic revision --autogenerate -m "init" && DB_URL=... alembic upgrade head`
