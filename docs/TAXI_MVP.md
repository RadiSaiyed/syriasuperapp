Taxi MVP — Scope and Architecture

Goals (Phase 1)
- Rider can request a ride (pickup/dropoff)
- Nearby online driver is assigned (simple nearest-
  neighbor within radius)
- Driver can accept, start, and complete ride
- Fare calculation (distance/time stub, per‑km + base)
- Ride history for rider/driver

Non‑Goals (Phase 1)
- Navigation/turn‑by‑turn, surge pricing
- In‑app chat/calls, cancellations with fees
- Payments integration (stub): show payable fare; actual payment via Payments app

Architecture
- API: FastAPI + SQLAlchemy + Postgres
- Auth: phone + dev OTP (shared approach with payments)
- Driver location: periodic REST updates (no WS in MVP)
- Matching: naive lookup of nearest AVAILABLE driver within X km

Data Model (MVP)
- users(id, phone, name, role: rider/driver, created_at)
- drivers(id, user_id, status: offline/available/busy, vehicle_make, vehicle_plate)
- driver_locations(id, driver_id, lat, lon, updated_at)
- rides(id, rider_user_id, driver_id?, status, pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
        quoted_fare_cents, final_fare_cents, distance_km, started_at, completed_at, created_at)

Ride Lifecycle
- requested → assigned → accepted → enroute → completed
  - Cancellation paths: canceled_by_rider, canceled_by_driver (out-of-scope for MVP)

API Surface (MVP)
- POST /auth/request_otp; POST /auth/verify_otp (returns JWT)
- POST /driver/apply (dev)
- PUT  /driver/status (offline/available)
- PUT  /driver/location (lat/lon)
- POST /rides/request (pickup/dropoff)
- POST /rides/{id}/accept (driver)
- POST /rides/{id}/start (driver)
- POST /rides/{id}/complete (driver)
- GET  /rides (my rides)
- WS   /ws/rides/{ride_id} — subscribe to live ride status (broadcast on accept/start/complete)

Payments Integration (DEV)
- On ride completion, service attempts to create a Payment Request in Payments via `/internal/requests` with `X-Internal-Secret` header.
- Configure `PAYMENTS_BASE_URL` and `PAYMENTS_INTERNAL_SECRET` in Taxi; set `INTERNAL_API_SECRET` in Payments.

Fare Calculation (MVP)
- fare = base_fee + per_km * distance_km; distance_km via haversine on pickup/dropoff
- defaults: BASE=1000, PER_KM=500 (cents)

Security Notes
- JWT dev auth; require driver role for driver endpoints
- Validate coordinates and ensure driver availability rules
