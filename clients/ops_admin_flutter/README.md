SuperApp Admin (macOS) — Flutter Desktop

A compact macOS admin app (Flutter Desktop) that consumes the Ops‑Admin service and shows core metrics + alerts.

Requirements
- Flutter SDK (3.x) with macOS Desktop support (`flutter config --enable-macos-desktop`)
- Ops‑Admin service: `cd apps/ops_admin && uvicorn app.main:app --port 8099`
- Optional: Prometheus+Grafana via `docker compose -f ops/observability/docker-compose.yml up -d`

Run (macOS)
1) `cd clients/ops_admin_flutter`
2) Falls `macos/` fehlt: `flutter create .`
3) `flutter pub get`
4) `flutter run -d macos`

Usage
- Set base URL top right (default `http://localhost:8099`).
- Tabs:
  - Overview: error rate, Payments rates (QR/P2P/Topup), RPS per service.
  - Alerts: incoming alerts (via Alertmanager webhook to Ops‑Admin).
  - Links: quick links to Grafana, Prometheus, Alertmanager, Ops‑Admin.
  - Admin: actions against Payments Admin API (base URL + admin token required):
    - Change fees (merchant/cashin/cashout BPS, fee wallet)
    - Set rate limit (per_minute, auth_boost, exempt_otp)
    - Toggle webhook endpoint (by endpoint ID)
    - Trigger refund (admin) (original_transfer_id, amount_cents)

Admin token
- In Payments `.env` set `ADMIN_TOKEN` and restart the service.
- In the app (Admin tab), set the Payments API base URL and token.
