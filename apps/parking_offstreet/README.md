Parking Off‑Street Service (MVP)

Facilities directory, reservations (QR), and entry/exit session handling for garages and lots.

Quick start
- Copy `.env.example` to `.env`
- Start DB: `docker compose up -d db`
- Run API: `docker compose up --build api`
- Swagger: http://localhost:8097/docs

Payments Integration (optional)
- Configure in `.env`:
  - `PAYMENTS_BASE_URL` (e.g., `http://host.docker.internal:8080`)
  - `PAYMENTS_INTERNAL_SECRET`
  - `FEE_WALLET_PHONE` (merchant/fee wallet for garage operator)
  - `PAYMENTS_WEBHOOK_SECRET`
- Flow
  - `POST /reservations` creates a reservation and, wenn konfiguriert, einen Payment Request in Payments (Anzahlung/Reservierung). Die Antwort enthält `payment_request_id`.
  - `POST /entries/{id}/stop` berechnet den Endpreis und erstellt optional einen Payment Request für den Ausstieg; die Antwort enthält `payment_request_id` der Session.
  - Payments sendet bei Annahme `requests.accept`; der Service trägt `payment_transfer_id` in die passende Reservation oder Entry ein.
- Register webhook in Payments to Off‑Street:
  - `POST /webhooks/endpoints` with `url=http://host.docker.internal:8097/payments/webhooks` and `secret=$PAYMENTS_WEBHOOK_SECRET`.

Operator
- `GET /operator/payment_status?request_id=...` — liefert lokale Zuordnung (Reservation/Entry + Transfer‑ID) und, falls konfiguriert, den Remote‑Status aus Payments `/internal/requests/{id}`.

Make targets (Dev)
- `make up` — startet Payments + Off‑Street (DB/Redis/API)
- `make payments-webhook` — registriert den Off‑Street Webhook in Payments (Fee‑Wallet als Merchant)
- `make e2e-reservation` — Reservation → Payment Request → Acceptance → Status
- `make e2e-exit` — Entry/Stop → Payment Request → Acceptance → Status
- `make e2e` — führt alles in Reihenfolge aus (up → webhook → reservation → exit)

Dev cURL
1) Token (dev): falls `JWT_SECRET` gesetzt ist, einen HS256‑JWT lokal erzeugen:
```
TOK=$(python3 - <<'PY'
import jwt,time,os
secret=os.environ.get('JWT_SECRET','change_me_in_dev')
print(jwt.encode({"sub":"00000000-0000-0000-0000-000000000001","phone":"+963900000001","exp":int(time.time())+3600}, secret, algorithm="HS256"))
PY
)
```
2) Create reservation:
   curl -s -X POST http://localhost:8097/reservations -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
     -d '{"facility_id":"FACILITY_ID","from_ts":"2025-01-01T10:00:00Z","to_ts":"2025-01-01T12:00:00Z"}' | jq .
3) Simulate webhook accept:
```
ts=$(date +%s)
PR=PR_ID
body='{"type":"requests.accept","data":{"id":"'"$PR"'","transfer_id":"TR_ID"}}'
sig=$(python3 - <<'PY'
import hmac,hashlib,os
secret=os.environ.get('PAYMENTS_WEBHOOK_SECRET','demo_secret')
ts=os.environ.get('TS','%s')
event='requests.accept'
body=os.environ.get('BODY','%s')
print(hmac.new(secret.encode(),(ts+event).encode()+body.encode(),hashlib.sha256).hexdigest())
PY
)
curl -s -X POST http://localhost:8097/payments/webhooks \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Event: requests.accept" \
  -H "X-Webhook-Ts: $ts" \
  -H "X-Webhook-Sign: $sig" \
  -d "$body" | jq .
```
