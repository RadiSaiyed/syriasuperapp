Syria Super-App — Monorepo

This monorepo will host the different verticals of the Super‑App. We start with the Payments service as the foundation for identity, wallets, and merchant acceptance.

Structure
- apps/
  - payments/, taxi/, bus/, flights/, commerce/, utilities/, freight/, stays/, doctors/, food/, chat/, carmarket/, ai_gateway/, agriculture/, livestock/, carrental/ — vertical services
- clients/
  - superapp_flutter/ — unified Flutter client (the only end‑user app)
  - shared_core/, shared_ui/ — shared packages used by the super‑app
  - ops_admin_flutter/ — optional desktop Ops/Admin helper
- infra/ — Infra and local dev assets (added over time)
- docs/ — Architecture notes and ADRs
- demos/ — Minimal UI demos (open in browser)

Quick start (Payments API)
1) Copy `apps/payments/.env.example` to `.env` and adjust.
2) Start Postgres via Docker Compose: `docker compose -f apps/payments/docker-compose.yml up -d db`
3) Build and run the API: `docker compose -f apps/payments/docker-compose.yml up --build api`
4) Open Swagger UI at http://localhost:8080/docs

Notes
- This is an MVP scaffold: not for production. Missing: robust KYC/AML, rate limits, audit trails, key management, real OTP/SMS, proper secrets handling, migrations.
- Currency defaults to SYP; multi‑currency is out of scope for MVP.

Production
- See `docs/PRODUCTION.md:1` for a concise deployment guide.
- Shortcuts:
  - `make prod-env` — generate `ops/deploy/compose-traefik/.env.prod` with strong secrets
  - `ORG=myorg TAG=$(git rev-parse --short HEAD) make prod-build` — build and push images
  - `make prod-deploy` — start Traefik + services on the target host

Single‑Operator Workflow
- See `docs/ONE_PERSON_OPS.md:1` for a concise guide.
- Use the helper CLI `./sup` to run common actions:
  - `./sup bootstrap` — secrets → envs, start observability and Payments
  - `./sup apps` / `./sup up payments` / `./sup logs taxi`
  - Operators: `./sup op list` to list, `./sup op up food_operator` / `./sup op logs food_operator`
  - Seed: Food `./sup seed food` | Food+Operator `./sup seed food-operator` | Commerce `./sup seed commerce` | Doctors `./sup seed doctors` | Taxi `./sup seed taxi` | Bus `./sup seed bus` | Utilities `./sup seed utilities` | Freight `./sup seed freight` | Car Market `./sup seed carmarket` | Chat `./sup seed chat` | Stays `./sup seed stays`
  - `./sup doctor` — monorepo health check
  - `./sup deploy up` — run the Traefik compose bundle (requires `.env.prod`)
  - Runbooks: `./sup runbook operators-ui` | `./sup runbook taxi-webhooks` | `./sup runbook payments`

Operator UIs
- Each operator service exposes `/ui` for quick manual tests (paste JWT and use handy actions). See operators/README.md for details per app.
- Taxi webhook simulation: open `operators/taxi_partners` → `/ui` and use “Simulate Webhooks → Taxi” to send signed ride status and driver location webhooks to Taxi API (default base `http://localhost:8081`, overridable via UI or `TAXI_BASE`).

Unified API (BFF)
- BFF at `apps/bff` is the single entrypoint for the Super‑App.
  - `GET /health`, `GET /v1/features` (ETag), `GET /v1/me` (aggregated: Payments wallet/KYC/Merchant + Chat summary)
  - Path proxy `/<service>/*` and WS proxy `/{service}/ws` unify access to all verticals
  - Convenience endpoints with ETag/304 for Commerce and Stays (shops/products/orders; properties/reservations/favorites)
  - Push: device register, topics subscribe/list, dev send/broadcast by topic (see `apps/bff/README.md`)
  - Dev seeds (proxied): `POST /stays/dev/seed`, `POST /chat/dev/seed` (dev only) to stabilize local data
- Local: `make bff-up` (or `ENV=dev APP_PORT=8070 python -m apps.bff.app.main`)
- Super‑App (single base):
  - `--dart-define SUPERAPP_API_BASE=http://localhost:8070` routes all requests via BFF
  - Features: unified deep‑links, notifications with topics, ETag caching for lists

Embedded Payments (Handoff)
- Verticals create Payment Requests via the Payments internal API and deep‑link users to the Payments app to approve: `payments://request/<id>`.
- Backend env (per service): set in each app’s `.env` as applicable
  - `PAYMENTS_BASE_URL` e.g. `http://host.docker.internal:8080`
  - `PAYMENTS_INTERNAL_SECRET` must match Payments `INTERNAL_API_SECRET`
  - `FEE_WALLET_PHONE` for platform fee routing
  - If the service consumes inbound payment webhooks, also set `PAYMENTS_WEBHOOK_SECRET` (same value when registering merchant webhook in Payments)
- Flutter clients: enable deep‑link visibility for the `payments` scheme
  - Run each client’s `scripts/apply_deeplinks.sh` after `flutter create .` (adds iOS `LSApplicationQueriesSchemes` and Android `<queries>`)
  - Many clients include an “Open Payments” shortcut in the AppBar to launch the Payments app directly.

Flutter Client
- Unified app: see `clients/superapp_flutter/README.md:1` for setup and running.

Taxi API
- See `apps/taxi/README.md:1` and `docs/TAXI_MVP.md:1` for scope and setup.
Flutter client: `clients/taxi_flutter/README.md:1`

Bus API
- See `apps/bus/README.md:1` and `docs/BUS_MVP.md:1` for scope and setup.

Flights API
- See `apps/flights/README.md:1` and `docs/FLIGHTS_MVP.md:1` for scope and setup.

Commerce API
- See `apps/commerce/README.md:1` and `docs/COMMERCE_MVP.md:1` for scope and setup.

Utilities API
- See `apps/utilities/README.md:1` and `docs/UTILITIES_MVP.md:1` for scope and setup.

Freight API
- See `apps/freight/README.md:1` and `docs/FREIGHT_MVP.md:1` for scope and setup.

Car Market API
- See `apps/carmarket/README.md:1` and `docs/AUTOMARKET_MVP.md:1` for scope and setup.
Agriculture API
- See `apps/agriculture/README.md:1` and `docs/AGRICULTURE_MVP.md:1` for scope and setup.
Livestock API
- See `apps/livestock/README.md:1` and `docs/LIVESTOCK_MVP.md:1` for scope and setup.
Car Rental API
- See `apps/carrental/README.md:1` for scope and setup.

CI
- GitHub Actions run backend API tests and Flutter widget tests: `.github/workflows/ci.yml:1`
 - Nightly repo health check: `.github/workflows/nightly-health.yml:1`
 - Weekly prod audit: `.github/workflows/weekly-prod-audit.yml:1`

Local test helpers
- Run all Flutter client tests: `bash tools/run_flutter_tests.sh` (add `--continue` to run all even if one fails)
- Run backend health check (installs deps, starts Postgres via Docker, runs pytest across apps): `bash tools/health_check.sh`

Docker Images
- Build and push all app images to Docker Hub:
  - `ORG=myorg TAG=$(git rev-parse --short HEAD) bash tools/docker_push_all.sh`
  - Make sure you are logged in: `docker login`
- GitHub Actions publisher: `.github/workflows/docker-publish.yml`
  - Set secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` in the repo.
  - Runs on tag push or manual dispatch.

Observability
- Basic metrics endpoint at `/metrics` (Prometheus format)
 - App-specific counters added:
   - Commerce: `commerce_orders_total{status}`
   - Doctors: `doctors_appointments_total{status}`
- Grafana dashboards:
  - `ops/observability/grafana/dashboards/commerce.json`
  - `ops/observability/grafana/dashboards/doctors.json`
  - `ops/observability/grafana/dashboards/taxi.json`
  - `ops/observability/grafana/dashboards/taxi_wallet.json`
  - `ops/observability/grafana/dashboards/payments.json`
  - `ops/observability/grafana/dashboards/superapp_overview.json`
  - `ops/observability/grafana/dashboards/bff.json`
- Quick start (Prometheus + Grafana + Tempo):
  - `docker compose -f ops/observability/docker-compose.yml up -d`
  - Prometheus: http://localhost:9090 (scrapes local services)
  - Grafana: http://localhost:3000 (anonymous viewer)
  - Tempo (OTLP): http://localhost:4318 (HTTP OTLP), 4317 (gRPC). Grafana is preprovisioned with a Tempo datasource.
  - To export traces set in services: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` and optionally `OTEL_SERVICE_NAME`.
 - Alertmanager: http://localhost:9093 (webhook preconfigured to Ops‑Admin)
 - Alerts: rules in `ops/observability/prometheus/alerts.yml` (ServiceDown, HighErrorRate, Payments Webhook Retries)
  - Slack/Email: Receivers `slack`/`email` are defined in `ops/observability/alertmanager/alertmanager.yml`.
   - Set env: `SLACK_WEBHOOK_URL`, `SLACK_CHANNEL`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` and reload.

Shared Libs
- Python shared utilities live in `libs/superapp_shared` (OTP, rate limits, internal HMAC).
- AI SDK lives in `libs/superapp_ai` (AIGatewayClient). See `docs/AI_GATEWAY_SETUP.md`.

E2E Orchestrator
- Run core flows end-to-end (optional):
  - `python3 tools/e2e_orchestrator.py` (env: `COMMERCE_BASE_URL`, `DOCTORS_BASE_URL`, `PHONE_A`, `NAME_A`, `FLOWS=commerce,doctors`)

Makefile Targets
- Payments API E2E: `cd apps/payments && make e2e`
- Cash In/Out Demo: `cd apps/payments && make cash-demo`

Ops Admin (Read-only)
- Lightweight dashboard service that summarizes RPS/Error‑Rate/Payments KPIs from Prometheus.
  - Run: `cd apps/ops_admin && uvicorn app.main:app --reload --port 8099`
  - Env: `PROMETHEUS_BASE_URL` (default `http://localhost:9090`)
  - Basic Auth (optional): `OPS_ADMIN_BASIC_USER`, `OPS_ADMIN_BASIC_PASS`
  - Endpoints: `/health`, `/summary`, `/` (HTML View), `/alerts` (recent alerts), `/alert` (Alertmanager webhook)

macOS Admin App (Flutter Desktop)
- Path: `clients/ops_admin_flutter` — shows overview/alerts/links and admin actions:
  - Change fees, set rate limits, toggle+list webhook endpoints, manage merchants, admin refunds, live logs (Loki)
  - Start: `flutter create . && flutter pub get && flutter run -d macos`
- Demos
- Open `demos/ai_gateway_ui/index.html` to try assistant, tool execution, search, and OCR against the AI Gateway.
