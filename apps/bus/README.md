Bus Service

FastAPI service for intercity bus ticket search and bookings with seat selection, promo codes and tickets.

Run locally
1) Copy `.env.example` to `.env` and adjust.
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8082/docs

Auth (DEV)
- OTP is stubbed as 123456
- Use phone `+963xxxxxxxxx`

Features
- Search trips by origin, destination, date (seeded sample data in dev)
- View seat map per trip, see reserved seats
- Seat selection or auto-assignment on booking
- Promo codes (percent/fixed) with limits + reporting (DEV)
 - Payments integration (internal requests for bookings; verify on confirm)
- Booking ticket (QR text) endpoint
 - Operator admin endpoints (dev): manage trips, view bookings, simple reports, validate tickets

API
- Auth: `POST /auth/request_otp`, `POST /auth/verify_otp`
- Trips: `POST /trips/search`, `GET /trips/{trip_id}`
- Seat map: `GET /trips/{trip_id}/seats` → `{trip_id, seats_total, reserved: [..]}`
- Bookings: `POST /bookings`, `GET /bookings`, `POST /bookings/{id}/cancel`, `GET /bookings/{id}`
- Ticket: `GET /bookings/{id}/ticket` → `{qr_text}`
- Promos (DEV): `GET /promos`, `POST /promos`, `GET /promos/stats`
 - Operators (DEV):
   - `POST /operators/register` (create operator + assign current user as admin)
   - `GET /operators/me` (list memberships)
   - Trips: `GET/POST/PATCH/DELETE /operators/{operator_id}/trips[...]`
   - Bookings: `GET /operators/{operator_id}/bookings?status=...`, `POST /operators/{operator_id}/bookings/{id}/confirm|cancel`
   - Members (admin): `GET /operators/{operator_id}/members`, `POST /operators/{operator_id}/members` (JSON: {phone, role}), `POST /operators/{operator_id}/members/{member_id}/role` (JSON: {role}), `DELETE /operators/{operator_id}/members/{member_id}`
   - Reports: `GET /operators/{operator_id}/reports/summary?since_days=7`
   - Tickets: `GET /operators/{operator_id}/tickets/validate?qr=BUS|<id>`, `POST /operators/{operator_id}/tickets/board?booking_id=<id>`

Booking request example
`{ "trip_id": "...", "seats_count": 2, "seat_numbers": [5,6], "promo_code": "WELCOME10" }`

Payments Integration
- When a booking is created, the service attempts to create an internal Payment Request in the Payments service:
  - `from_phone = Operator.merchant_phone` (or fallback `FEE_WALLET_PHONE`)
  - `to_phone = <user phone>`
  - `amount_cents = total_price_cents`
- The `payment_request_id` is stored on the booking and returned to the client.
- On `POST /bookings/{id}/confirm`, if a `payment_request_id` exists, the service verifies the request status via Payments `/internal/requests/{id}` and only confirms if status is `accepted`.

Operator Notes (DEV)
- Register an operator: `POST /operators/register` with form fields `name` and optional `merchant_phone`.
- Set `PAYMENTS_BASE_URL` and `PAYMENTS_INTERNAL_SECRET` in `.env` to enable internal calls.
