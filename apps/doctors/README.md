Doctors (Appointment Booking) API — FastAPI service

Overview
- Minimal doctor appointment booking: doctors, availability slots, and patient bookings.
- Mirrors other services (OTP auth, models, routers, Docker, env, metrics, rate limiting).

Quick start
1) Copy env and set variables: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`

Defaults
- Port: 8089
- DB (in Docker): `postgresql+psycopg2://postgres:postgres@db:5432/doctors`
- DB (local default in config): `postgresql+psycopg2://postgres:postgres@localhost:5442/doctors`

API (MVP)
- Auth
  - `POST /auth/request_otp` — request OTP (dev: 123456)
  - `POST /auth/verify_otp` — create user, return JWT
- Public
  - `GET  /doctors` — list doctors (filters: `city`, `specialty`, `q`; includes `rating_avg`, `rating_count`)
  - `GET  /doctors/{id}` — doctor profile (includes aggregated ratings)
  - `POST /search_slots` — search free slots by doctor/specialty/city and time range (supports `limit`, `offset`)
- Doctor
  - `POST /doctor/profile` — create/update profile (name, specialty, city)
    - Additional fields: `clinic_name`, `address`, `latitude`, `longitude`, `bio`
  - `POST /doctor/slots` — add availability slots (start/end)
  - `GET  /doctor/slots` — list my slots
  - `GET  /doctor/appointments` — list my appointments
  - `POST /doctor/appointments/{id}/status?status_value=confirmed|canceled|completed` — update appointment status
  - Images: `POST /doctor/images` (array `{url, sort_order}`), `GET /doctor/images`, `DELETE /doctor/images/{image_id}`
- Patient
  - `POST /appointments` — book a slot
  - `GET  /appointments` — list my appointments
  - `POST /appointments/{id}/cancel` — cancel my appointment (frees slot)
- Favorites
  - `POST /doctors/{id}/favorite`, `DELETE /doctors/{id}/favorite`, `GET /doctors/favorites`
- Reviews
  - `POST /doctors/{id}/reviews` (rating 1–5, comment), `GET /doctors/{id}/reviews`
- Webhooks (signed)
  - `GET/POST/DELETE /webhooks/endpoints`, `POST /webhooks/test`
- Payments inbound webhook:
  - `POST /payments/webhooks` — expects `X-Webhook-Ts`, `X-Webhook-Event`, `X-Webhook-Sign`; on `requests.accept(ed)` marks matching appointment as `confirmed` via `payment_request_id`.

Notes
- Slots are explicit time ranges (e.g., 30 minutes). Booking marks the slot as booked and creates an appointment.

E2E Flow (Doctors ↔ Payments)
- Setup
  - Set in doctors `.env`: `PAYMENTS_BASE_URL`, `PAYMENTS_INTERNAL_SECRET`, `PAYMENTS_WEBHOOK_SECRET`
  - In Payments, add a webhook endpoint pointing to doctors: `POST /webhooks/endpoints?url=http://host.docker.internal:8089/payments/webhooks&secret=$PAYMENTS_WEBHOOK_SECRET` (as merchant/dev)
- Book
  - Patient books slot: `POST /appointments` (see tests/README examples)
  - Doctors service creates a Payment Request via Payments internal API and stores `payment_request_id`.
- Confirm
  - Option A: Patient nimmt die Payment Request in Payments an (Zahler = Patient, Empfänger = Arzt); Payments sendet `requests.accept` inkl. `transfer_id`.
  - Option B: Simulate an inbound event: `curl -X POST http://localhost:8089/payments/webhooks -H 'X-Webhook-Event: requests.accept' -H "X-Webhook-Ts: $(date +%s)" -H "X-Webhook-Sign: $(python3 - <<'PY'\nimport hmac,hashlib,sys\nsecret=sys.argv[1]; ts=sys.argv[2]; ev='requests.accept'; body='{"type":"requests.accept","data":{"id":"PR_ID","transfer_id":"TR_ID"}}'\nprint(hmac.new(secret.encode(),(ts+ev).encode()+body.encode(),hashlib.sha256).hexdigest())\nPY\n$PAYMENTS_WEBHOOK_SECRET $(date +%s))" -H 'Content-Type: application/json' -d '{"type":"requests.accept","data":{"id":"PR_ID","transfer_id":"TR_ID"}}'`
  - Doctors marks appointment `confirmed` and stores `payment_transfer_id`.
- Cancel → Refund
  - Patient or Doctor cancels: doctors emits `refund.requested` webhook with `{transfer_id, amount_cents}` for orchestration.
  - When Payments sends `refunds.create` webhook with `{original: transfer_id}`, Doctors marks `refund_status=completed`.

Admin cURL (Images)
- Add images: `curl -X POST /doctor/images -H 'Authorization: Bearer $TOK' -H 'Content-Type: application/json' -d '[{"url":"https://.../1.jpg","sort_order":0}]'`
- List: `GET /doctor/images`, Delete: `DELETE /doctor/images/{image_id}`
