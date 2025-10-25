Flights MVP — Scope & Notes

Goals
- Enable users to search domestic flights and book seats.
- Reuse Super-App patterns: OTP auth, JWT, rate limits, payment handoff.

Core Models
- User: phone-based identity.
- Airline: carrier name.
- Flight: airline, origin, destination, depart/arrive times, price, seat capacity.
- FlightSeat: seat_number reserved per booking.
- Booking: reserved|confirmed|canceled; optional payment_request_id.
- PromoCode/PromoRedemption: percentage/amount discounts with limits.

API Outline
- Auth: `/auth/request_otp`, `/auth/verify_otp`.
- Flights: `/flights/search`, `/flights/{id}`, `/flights/{id}/seats`.
- Bookings: `POST /bookings`, `GET /bookings`, `POST /bookings/{id}/cancel`, `GET /bookings/{id}/ticket`.
- Promos: `POST /promos` (admin gating TBD in MVP).

Payments Integration (Optional)
- If env set (`PAYMENTS_BASE_URL`, `PAYMENTS_INTERNAL_SECRET`), the service creates a Payment Request and auto-confirms the booking.

Local Dev
1) `cp apps/flights/.env.example apps/flights/.env`
2) `docker compose -f apps/flights/docker-compose.yml up -d db redis`
3) `docker compose -f apps/flights/docker-compose.yml up --build api`
4) Open http://localhost:8092/docs

Test
- From repo root: `DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/flights pytest -q apps/flights`
- Or use `tools/health_check.sh` to spin ephemeral Postgres and run tests across all apps.

Non-Goals (MVP)
- Complex seat maps/classes, pricing rules, baggage, multi-leg journeys.
- Real SMS OTP, production-grade RBAC, migrations.

