POS Integration Guide

This guide describes how any POS (cash register) can accept payments via the Payments API using vendor‑agnostic QR flows.

1) Merchant‑Presented Mode (QR on POS)
- Dynamic QR (preferred):
  - Create: `POST /payments/merchant/qr` with `{ amount_cents, currency_code?, mode:"dynamic" }`
  - Show the returned `code` (e.g., `PAY:v1;code=...`) as a QR on the POS screen or receipt.
  - Customer scans with the Payments app and approves the payment.
  - Confirm:
    - Webhook (recommended): Register once at `POST /webhooks/endpoints` and receive signed payment events.
    - Poll fallback: `GET /payments/merchant/qr_status?code=PAY:v1;code=...` until `status == used`.
  - Idempotency: If the POS must re‑issue a QR for the same basket, generate a new QR; no double charge occurs because payer approval is required.
- Static QR (fallback):
  - Generate once via `POST /payments/links` (mode static).
  - Customer scans, enters the amount in the app and pays. Minimal setup for small merchants.

2) Consumer‑Presented Mode (QR in App)
- Customer shows a QR on their device in format `CPM:v1;phone=+963...` (or `CPM:v1;id=<user_id>`).
- POS scans and calls: `POST /payments/merchant/cpm_request` with JSON `{ code:"CPM:v1;...", amount_cents: 12345 }`.
- API creates a Payment Request (rider approval flow). Response contains `{ id, deeplink: "payments://request/<id>" }`.
- Customer approves the incoming request in the Payments app. POS can poll `GET /requests/{id}` for status.

3) Webhooks
- Add endpoint: `POST /webhooks/endpoints` with `{ url, secret }` (per merchant).
- Receive signed events with headers `X-Webhook-Event`, `X-Webhook-Ts`, `X-Webhook-Sign` (HMAC SHA‑256 of `ts + event + body`).
- Retry/backoff handled by Payments; POS can ACK with 2xx.

4) Security & KYC
- Merchant endpoints require merchant authentication (+ KYC level if configured).
- Risk & KYC limits are enforced on the payer at approval time.

5) Minimal POS Implementation Matrix
- Android SmartPOS/Tablet: small app hits HTTP endpoints and renders QR; Webhook finishes sale.
- Windows/Linux POS: tray app/browser overlay to render QR; webhook/poll for completion.
- Legacy scanner only: use CPM flow (customer shows app QR), POS triggers `/merchant/cpm_request`.

6) API Cheatsheet
- Create QR: `POST /payments/merchant/qr` → `{ code, expires_at }`
- QR status: `GET /payments/merchant/qr_status?code=PAY:v1;code=...` → `{ status, mode, amount_cents, currency_code, expires_at }`
- Pay dynamic QR: `POST /payments/merchant/pay` by customer app
- Create CPM request: `POST /payments/merchant/cpm_request` → `{ id, deeplink }`
- Request status: `GET /requests/{id}` → `{ status: pending|accepted|rejected|... }`
- Merchant statement: `GET /payments/merchant/statement`

7) Webhook events (examples)
- `payments.qr_pay` (QR wurde bezahlt)
```
POST https://pos.example.com/webhooks
Headers:
  X-Webhook-Event: payments.qr_pay
  X-Webhook-Ts: 1732995300
  X-Webhook-Sign: <hex>
Body:
{ "type": "payments.qr_pay", "data": { "amount_cents": 1500 } }
```

- `requests.accept` (Zahlungsanfrage akzeptiert — CPM/Pay‑by‑Link)
```
POST https://pos.example.com/webhooks
Headers:
  X-Webhook-Event: requests.accept
  X-Webhook-Ts: 1732995400
  X-Webhook-Sign: <hex>
Body:
{ "type": "requests.accept", "data": { "id": "<request_id>", "transfer_id": "<transfer_id>" } }
```

Signature: `HMAC_SHA256(secret, (ts + event) + body)`, see also `/webhooks/test`.

Notes
- For production, prefer webhooks over polling and enable HSTS/TLS on POS side.
