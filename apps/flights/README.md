Flights API (MVP)

Overview
- FastAPI service for flight search and ticket bookings.
- Mirrors the Bus app structure for consistency (auth via OTP, search, bookings, promos, metrics).

Quick Start
1) Copy `.env.example` to `.env` and adjust if needed.
2) Start Postgres + Redis: `docker compose -f apps/flights/docker-compose.yml up -d db redis`
3) Run the API: `docker compose -f apps/flights/docker-compose.yml up --build api`
4) Swagger UI: http://localhost:8092/docs

Endpoints (selection)
- `POST /auth/request_otp` — request OTP (dev mode uses 123456)
- `POST /auth/verify_otp` — verify OTP, returns JWT
- `POST /flights/search` — search flights by origin/destination/date
- `GET /flights/{flight_id}` — flight details
- `GET /flights/{flight_id}/seats` — reserved seats
- `POST /bookings` — create booking (auto-assign or pick seats)
- `GET /bookings` — list my bookings
- `POST /bookings/{id}/cancel` — cancel my booking
- `GET /bookings/{id}/ticket` — QR payload
- `POST /promos` — create promo code (admin scope omitted in MVP)

Notes
- Uses in-memory/Redis rate limiter from `libs/superapp_shared`.
- Payments integration is optional; if configured, a Payment Request is created and booking is auto-confirmed on success.

