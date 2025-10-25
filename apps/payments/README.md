Payments Service (MVP)

A FastAPI service providing user wallets, P2P transfers, and merchant QR payments.

Run locally (dev)
1) Copy `.env.example` to `.env` and adjust.
2) Start Postgres: `docker compose -f docker-compose.dev.yml up -d db`
3) Run API: `docker compose -f docker-compose.dev.yml up --build api`
4) Open http://localhost:8080/docs

Production notes
- Copy `.env.example` to `.env` and replace every placeholder with production values (e.g. `ENV=prod`, explicit `ALLOWED_ORIGINS`, secure secrets, managed Postgres/Redis URLs).
- Use the hardened compose file (`docker compose up -d`) for production deploys; the entrypoint runs Alembic migrations automatically and disables auto-reload.
- Set `UVICORN_WORKERS` (default 4) and `APP_PORT` to control published ports; use `UVICORN_EXTRA_ARGS` for TLS or access log tweaks.
- Disable dev toggles (`DEV_ENABLE_TOPUP`, `DEV_RESET_USER_STATE_ON_LOGIN`, `AUTO_CREATE_SCHEMA`) before promoting to prod; the service now refuses to boot with insecure combinations.
- If Postgres or Redis run externally (e.g. Hetzner Managed DB), remove the bundled service and point `DB_URL` / `REDIS_URL` to the managed endpoints.

Auth & OTP
- DEV: default `OTP_MODE=dev` akzeptiert OTP `123456`.
- PROD: setze `OTP_MODE=redis` und `REDIS_URL=redis://...`. OTPs werden serverseitig generiert, in Redis mit TTL gespeichert und bei Verifikation konsumiert; Rate‑Limit greift global.
- Use phone `+963xxxxxxxxx`

Quick test (cURL)
- Request OTP:
  `curl -X POST http://localhost:8080/auth/request_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000001"}'`
- Verify OTP, get token:
  `TOKEN=$(curl -s http://localhost:8080/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000001","otp":"123456","name":"Ali"}' | jq -r .access_token)`
- Check wallet:
  `curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/wallet`
- Dev topup 50,000 SYP:
  `curl -X POST http://localhost:8080/wallet/topup -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"amount_cents":5000000, "idempotency_key":"topup-1"}'`
- Become merchant (dev):
  `curl -X POST http://localhost:8080/payments/dev/become_merchant -H "Authorization: Bearer $TOKEN"`
- Create QR for 10,000 SYP:
  `curl -X POST http://localhost:8080/payments/merchant/qr -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"amount_cents":1000000}'`
- From another user, pay QR:
  - Create second user and top up, then:
  `curl -X POST http://localhost:8080/payments/merchant/pay -H "Authorization: Bearer $TOKEN_2" -H 'Content-Type: application/json' -d '{"code":"PAY:v1;code=<paste from previous>", "idempotency_key":"qr-pay-1"}'`

Payment Requests (cURL)
- Create request (A → B):
  `curl -X POST http://localhost:8080/requests -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' -H 'Idempotency-Key: pr-1' -d '{"to_phone":"+963900000002","amount_cents":12345, "expires_in_minutes": 30, "metadata": {"order_id": "abc"}}'`
- List (incoming/outgoing):
  `curl http://localhost:8080/requests -H "Authorization: Bearer $TOKEN_B"`
- Accept (B pays A):
  `curl -X POST http://localhost:8080/requests/<id>/accept -H "Authorization: Bearer $TOKEN_B"`
- Reject:
  `curl -X POST http://localhost:8080/requests/<id>/reject -H "Authorization: Bearer $TOKEN_B"`
- Cancel:
  `curl -X POST http://localhost:8080/requests/<id>/cancel -H "Authorization: Bearer $TOKEN_A"`
- Alembic (Migrations)
  - Generate initial migration (autogenerate from models):
    `cd apps/payments && DB_URL=postgresql+psycopg2://postgres:postgres@db:5432/payments alembic revision --autogenerate -m "init"`
  - Apply migrations: `DB_URL=postgresql+psycopg2://postgres:postgres@db:5432/payments alembic upgrade head`
  - Latest:
    - Add Payment Requests `expires_at`, `metadata_json` and Webhook Delivery backoff fields: `alembic upgrade head`

Internal (DEV) Integration
- Set in `.env`: `INTERNAL_API_SECRET=dev_secret` (or your value). Optionally enforce HMAC via `INTERNAL_REQUIRE_HMAC=true`.
- Endpoints:
  - `POST /internal/requests` — create payment request by phone: `{from_phone,to_phone,amount_cents}` (optional: `expires_in_minutes`, `metadata`, header `X-Idempotency-Key`).
  - `POST /internal/transfer` — immediate debit/credit between wallets: `{from_phone,to_phone,amount_cents}` (optional header `X-Idempotency-Key`).
  - `GET /internal/wallet?phone=+963...` — fetch `{phone,wallet_id,balance_cents,currency_code}`.

Refunds (cURL)
- Create refund (merchant → payer):
  - Get original transfer id (e.g., from statement or `/wallet/transactions`)
  - `curl -X POST http://localhost:8080/refunds -H "Authorization: Bearer $TOKEN_MERCHANT" -H 'Content-Type: application/json' -H 'Idempotency-Key: refund-1' -d '{"original_transfer_id":"<transfer_id>","amount_cents":1000}'`
- Get refund details:
  - `curl http://localhost:8080/refunds/<refund_id> -H "Authorization: Bearer $TOKEN_MERCHANT"`

Merchant Statement (cURL)
- JSON: `curl 'http://localhost:8080/payments/merchant/statement?from=2025-09-01T00:00:00Z&to=2025-09-30T23:59:59Z' -H "Authorization: Bearer $TOKEN_MERCHANT"`
- CSV:  `curl -H "Authorization: Bearer $TOKEN_MERCHANT" 'http://localhost:8080/payments/merchant/statement?format=csv'`

Payment Links (Pay-by-Link)
- Create dynamic link (fixed amount, one-time):
  `curl -X POST http://localhost:8080/payments/links -H "Authorization: Bearer $TOKEN_MERCHANT" -H 'Content-Type: application/json' -d '{"amount_cents":1500, "expires_in_minutes": 60}'`
- Create static link (variable amount, reusable):
  `curl -X POST http://localhost:8080/payments/links -H "Authorization: Bearer $TOKEN_MERCHANT" -H 'Content-Type: application/json' -d '{"expires_in_minutes": 1440}'`
- Pay dynamic link:
  `curl -X POST http://localhost:8080/payments/links/pay -H "Authorization: Bearer $TOKEN_PAYER" -H 'Content-Type: application/json' -d '{"code":"LINK:v1;code=...","idempotency_key":"link-pay-1"}'`
- Pay static link (amount required):
  `curl -X POST http://localhost:8080/payments/links/pay -H "Authorization: Bearer $TOKEN_PAYER" -H 'Content-Type: application/json' -d '{"code":"LINK:v1;code=...","amount_cents":2000, "idempotency_key":"link-pay-2"}'`

Subscriptions (MVP)
- Create: `curl -X POST http://localhost:8080/subscriptions -H "Authorization: Bearer $TOKEN_PAYER" -H 'Content-Type: application/json' -d '{"merchant_phone":"+963...","amount_cents":3000, "interval_days":30}'`
- List: `curl http://localhost:8080/subscriptions -H "Authorization: Bearer $TOKEN_PAYER"`
- Cancel: `curl -X POST http://localhost:8080/subscriptions/<id>/cancel -H "Authorization: Bearer $TOKEN_PAYER"`
- Dev process due: `curl -X POST http://localhost:8080/subscriptions/process_due -H "Authorization: Bearer $TOKEN_ANY"`

Invoices (eBill-like)
- Create invoice (merchant → payer):
  `curl -X POST http://localhost:8080/invoices -H "Authorization: Bearer $TOKEN_MERCHANT" -H 'Content-Type: application/json' -d '{"payer_phone":"+963900000002","amount_cents":2500, "due_in_days":10, "reference":"INV-1001", "description":"Electricity Sep"}'`
- List invoices (incoming/outgoing):
  `curl http://localhost:8080/invoices -H "Authorization: Bearer $TOKEN"`
- Payer pays invoice (manual approval):
  `curl -X POST http://localhost:8080/invoices/<id>/pay -H "Authorization: Bearer $TOKEN_PAYER" -H 'Idempotency-Key: inv-pay-1'`
- Autopay mandate (payer opts in per issuer):
  `curl -X POST http://localhost:8080/invoices/mandates -H "Authorization: Bearer $TOKEN_PAYER" -H 'Content-Type: application/json' -d '{"issuer_phone":"+963900000001","autopay":true, "max_amount_cents":100000}'`
- Process due invoices with autopay (dev/manual trigger):
  `curl -X POST http://localhost:8080/invoices/process_due -H "Authorization: Bearer $TOKEN_PAYER"`

KYC (cURL)
- Get: `curl http://localhost:8080/kyc -H "Authorization: Bearer $TOKEN"`
- Submit: `curl -X POST http://localhost:8080/kyc/submit -H "Authorization: Bearer $TOKEN"`
- Dev Approve: `curl -X POST http://localhost:8080/kyc/dev/approve -H "Authorization: Bearer $TOKEN"`

Fees & Policy
- Defaults (see `.env.example`):
  - KYC min level for merchant QR/pay: 1 (`KYC_MIN_LEVEL_FOR_MERCHANT_QR`, `KYC_MIN_LEVEL_FOR_MERCHANT_PAY`)
  - Per‑Tx/Daily limits by KYC level (`KYC_L0_*`, `KYC_L1_*`)
  - Fees (basis points): `MERCHANT_FEE_BPS=150` (1.5%), `CASHIN_FEE_BPS=100` (1.0%), `CASHOUT_FEE_BPS=500` (5.0%)
  - Fee wallet owner phone: `FEE_WALLET_PHONE` (auto‑provisioned)
- Merchant fee is charged to merchant after settlement. Cash‑in Fee vom Agenten, Cash‑out Fee vom Nutzer.

Make targets
- `make e2e` — complete flow (OTP→Topup→P2P→Merchant QR→Pay→Payment Request→Accept)
- `make cash-demo` — agent cash‑in/out demo including ledger entries

Rate Limiting & Request IDs
- In‑memory (default): `RATE_LIMIT_BACKEND=memory`
- Redis‑based: set `RATE_LIMIT_BACKEND=redis` and `REDIS_URL=redis://redis:6379/0`; compose includes `redis`.
- Limits: `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_AUTH_BOOST`
- Every response includes `X-Request-ID`; requests are JSON‑logged (logger `app.request`).
Cash In/Out (cURL)
- Become Agent (dev): `curl -X POST http://localhost:8080/cash/agents/dev/become_agent -H "Authorization: Bearer $TOKEN_AGENT"`
- Create Cash-In: `curl -X POST http://localhost:8080/cash/cashin/request -H "Authorization: Bearer $TOKEN_USER" -H 'Content-Type: application/json' -d '{"amount_cents":20000}'`
- Create Cash-Out: `curl -X POST http://localhost:8080/cash/cashout/request -H "Authorization: Bearer $TOKEN_USER" -H 'Content-Type: application/json' -d '{"amount_cents":15000}'`
- List (user/agent): `curl http://localhost:8080/cash/requests -H "Authorization: Bearer $TOKEN"`
- Agent Accept: `curl -X POST http://localhost:8080/cash/requests/<id>/accept -H "Authorization: Bearer $TOKEN_AGENT"`
- Agent Reject: `curl -X POST http://localhost:8080/cash/requests/<id>/reject -H "Authorization: Bearer $TOKEN_AGENT"`
- User Cancel: `curl -X POST http://localhost:8080/cash/requests/<id>/cancel -H "Authorization: Bearer $TOKEN_USER"`
Internal (DEV) Integration
- Enable an internal endpoint to create payment requests by phone (for service-to-service in dev):
  - Set in `.env`: `INTERNAL_API_SECRET=dev_secret` (or your value)
  - Endpoint: `POST /internal/requests` with header `X-Internal-Secret: <secret>` and body `{ "from_phone":"+963...", "to_phone":"+963...", "amount_cents":12345 }`
  - Direct internal transfer (immediate debit/credit): `POST /internal/transfer` with same auth/body. Optional `X-Idempotency-Key`.
  - Returns `{ "id": "<request_id>" }`
  - Optional fields: `expires_in_minutes`, `metadata`, and `X-Idempotency-Key` for idempotency.

Env & Tuning
- REQUEST_EXPIRY_MINUTES: Default TTL for new payment requests (mins)
- WEBHOOK_BASE_DELAY_SECS (default 2), WEBHOOK_BACKOFF_FACTOR (default 2), WEBHOOK_MAX_ATTEMPTS (default 5)
- INTERNAL_REQUIRE_HMAC=true to force HMAC for `/internal/requests` (otherwise shared secret allowed)

Merchant API HMAC
- Python/JS Snippets: see `docs/SDK_MERCHANT_HMAC.md:1`

Links & QR SDK
- Client snippets for creating/paying Links & QR: see `docs/SDK_MERCHANT_LINKS_QR.md:1`

Admin API (secure)
- Enable via `ADMIN_TOKEN` in `.env`. Endpoints require header `X-Admin-Token: <token>`.
- Endpoints:
  - `GET /admin/config/fees` — current fees (BPS, fee wallet)
  - `POST /admin/config/fees` — set `{merchant_fee_bps, cashin_fee_bps, cashout_fee_bps, fee_wallet_phone}`
  - `POST /admin/config/rate_limit` — set `{per_minute, auth_boost, exempt_otp}` (runtime overrides via env)
  - `POST /admin/webhooks/endpoints/{id}/toggle` — activate/deactivate endpoint (force)
  - `POST /admin/refunds` — admin refund for an original transaction
  - `POST /admin/airdrop_starting_credit` — pay starting credit to existing users (idempotent per user)
    - Body optional: `{ "amount_cents": <override>, "limit": 10000, "offset": 0 }`
    - Uses idempotency key `airdrop:<user_id>` on `transfers`, creates `ledger_entries` and increases `wallet.balance_cents`.

Starting credit (airdrop)
- Configurable via env `STARTING_CREDIT_CENTS` (dev default `10000000`; production default `0`). Set explicitly if you need a launch promotion.
- A new account (first wallet creation) automatically receives a credit transfer (system → wallet) incl. ledger entry.
- Existing accounts can be credited via the admin endpoint:
  - Example: `curl -X POST http://localhost:8080/admin/airdrop_starting_credit -H "X-Admin-Token: $ADMIN_TOKEN" -H 'Content-Type: application/json' -d '{"amount_cents":10000000}'`

Invoice autopay scheduler
- Optional background loop in Payments processes due invoices with active autopay mandate:
  - Enable via env: `INVOICES_AUTOPAY_POLL_SECS=30` (interval seconds; `0` disables)
  - Sweep logic: checks due `invoices` and mandates, pays using `auto-invoice-<id>` idempotency.

Internal (DEV) — Invoices
- `POST /internal/invoices` (HMAC/Secret wie `/internal/requests`):
  - Body: `{ "from_phone":"+963...", "to_phone":"+963...", "amount_cents":1234, "due_in_days": 5, "reference":"...", "description":"..." }`
  - Header optional: `X-Idempotency-Key: <key>`
  - Response: `{ "id": "<invoice_id>" }`
- POS/QR Integration
  - Merchant QR (MPM):
    - `POST /payments/merchant/qr` → display `code` (QR). Customer scans and pays in the app.
    - Webhook (recommended) or fallback: `GET /payments/merchant/qr_status?code=PAY:v1;code=...` until `status=used`.
  - Customer QR (CPM):
    - Customer shows `CPM:v1;phone=+963...` in the app.
    - POS scans and calls `POST /payments/merchant/cpm_request` with `{code, amount_cents}`. Response includes `{id, deeplink}`. Customer confirms the payment request in the app.
  - See details in `docs/POS_INTEGRATION.md`
  - Fetch customer app QR: `GET /payments/cpm_qr?format=phone|id` → `{ qr_text }`
  - POS demo CLI: `tools/pos_demo/pos_cli.py` (env: `PAYMENTS_BASE_URL`, `PAYMENTS_MERCHANT_TOKEN`)

Monitoring & Metrics
- Endpoints:
  - `GET /health` — liveness check
  - `GET /metrics` — Prometheus metrics (counters + latency histogram)
- Key metrics:
  - `http_requests_total{method,path,status}`
  - `http_request_duration_seconds{method,path}` (Histogram)
  - Domain counters (e.g., `payments_qr_total`, `payments_transfers_total`, `payments_webhook_*`)
- Alerts & Dashboards: see `ops/observability/` (Prometheus, Alertmanager, Grafana)
  - Dashboards now include Payments HTTP p95/p99 latency panels.

Webhooks
- Outbound webhooks use HMAC headers (`X-Webhook-Ts`, `X-Webhook-Sign`) and include `X-Delivery-ID` for idempotency on receivers.
- Delivery is persisted in `webhook_deliveries` with exponential backoff retry.
- Dev worker (opt-in): enable `WEBHOOK_WORKER_POLL_SECS>0` to process pending deliveries in-process.
 - Production worker (recommended): use Celery worker + beat for periodic processing.
   - Start with Docker Compose: `docker compose up -d worker beat`
   - Configure via env: `WEBHOOK_PROCESS_INTERVAL_SECS` (seconds), `CELERY_BROKER_URL` (defaults to `REDIS_URL`).

Reconciliation & Settlement
- Reconcile ledger vs wallet balances, and transfers invariants:
  - Dry-run: `DB_URL=... python apps/payments/scripts/reconcile.py`
  - Fix balances: `DB_URL=... python apps/payments/scripts/reconcile.py --fix-balances`
- Settlement CSV for merchants:
  `DB_URL=... python apps/payments/scripts/settlement_report.py --from ... --to ... > settlement.csv`

Ops: Backups & Rotation
- Backups: `ops/backups/payments_pg_backup.sh` (supports S3 upload and optional Redis dump).
- Secrets rotation steps: `ops/secrets/ROTATION.md`; helper `tools/rotate_payments_secrets.sh` for local `.env`.

Supply Chain (SBOM, Audit, Licenses)
- Local helpers in `apps/payments/Makefile`: `make -C apps/payments sbom audit licenses`.
- CI runs SBOM generation, pip-audit, and license reporting (see `.github/workflows/payments-ci.yml`).
 - To enforce CI gating, add required status check for the job `supply-chain` in your repo branch protection (Settings → Branches → Rules).
