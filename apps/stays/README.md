Stays (Hotels & Vacation Rentals) API — FastAPI service

Overview
- Minimal booking API for hotels/apartments: properties, units (room types), availability, and reservations.
- Mirrors other services (auth via OTP, models, routers, Docker, env, metrics, rate limiting).

Quick start
1) Copy env and set variables: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`

Defaults
- Port: 8088
- DB (in Docker): `postgresql+psycopg2://postgres:postgres@db:5432/stays`
- DB (local default in config): `postgresql+psycopg2://postgres:postgres@localhost:5441/stays`

API (MVP)
- Auth
  - `POST /auth/request_otp` — request OTP (dev: always 123456)
  - `POST /auth/verify_otp` — create user if needed, return JWT
- Public
  - `GET  /properties` — list properties (filters: `city`, `type`, `q`; includes `rating_avg`, `rating_count`, address/geo when available)
    - Extras: `min_rating`, sorting `sort_by=rating|popularity|created|name`, `sort_order=asc|desc`, pagination `limit`, `offset`, optional map bounds `min_lat,max_lat,min_lon,max_lon`.
  - `GET  /properties/{id}` — property details with units, images, aggregated ratings
    - Extras: `rating_histogram`, `similar` (top 6 similar properties in same city/type)
  - `POST /search_availability` — search by city / dates / guests
    - Filters: `min_price_cents`, `max_price_cents`, `capacity_min`, `property_type`, `amenities`, `amenities_mode=any|all`, `min_rating`, optional `property_ids`
    - Map: optional bounds `min_lat,max_lat,min_lon,max_lon`, or distance sorting requires `center_lat,center_lon`
    - Sorting: `sort_by=price|rating|popularity|distance|best_value|recommended`, `sort_order=asc|desc`
    - Grouping: `group_by_property=true` returns cheapest unit per property
    - Result extras: `property_image_url`, `property_rating_avg`, `property_rating_count`, `distance_km`
    - Facets: `amenities_counts`, `rating_bands`, `price_min_cents`, `price_max_cents`
    - Pagination: `limit`, `offset`; response includes `total`, `next_offset`.
  - `GET  /units/{unit_id}/calendar` — per-day availability and price for a date range
    - Query: `start`, `end` (ISO date). Defaults to next 30 days.
    - Response: `{ unit_id, days: [{date, available_units, price_cents}] }`
    - Availability accounts for maintenance blocks (unit‑blocking) and dynamic daily prices; total includes cleaning fee.
- Host (property owner)
  - `POST /host/properties` — create property
  - `GET  /host/properties` — list my properties
  - `POST /host/properties/{id}/units` — create unit (room type)
  - `GET  /host/properties/{id}/units` — list units
  - `PATCH /host/properties/{id}` — update property
  - `PATCH /host/units/{unit_id}` — update unit (name, capacity, total_units, price, min_nights, cleaning_fee_cents, active, amenities)
  - `GET  /host/reservations` — list reservations across my properties
  - `POST /host/reservations/{id}/confirm` — confirm reservation
  - `POST /host/reservations/{id}/cancel` — cancel reservation
  - `POST /host/properties/{id}/images` — add image URLs (array)
  - `GET  /host/properties/{id}/images` — list images
  - `DELETE /host/images/{image_id}` — delete image
  - `POST /host/units/{unit_id}/blocks` — create maintenance block (date range, blocked_units, reason)
  - `GET  /host/units/{unit_id}/blocks` — list blocks
  - `DELETE /host/blocks/{block_id}` — delete block
  - `PUT  /host/units/{unit_id}/prices` — upsert daily prices (list of {date, price_cents})
  - `GET  /host/units/{unit_id}/prices` — list daily prices (optional `start`, `end`)
- Reservations (guest)
  - `POST /reservations` — book unit for date range
  - `GET  /reservations` — list my reservations
  - `POST /reservations/{id}/cancel` — cancel my reservation (before check-in)
- Favorites
  - `POST /properties/{id}/favorite` — add property to favorites
  - `DELETE /properties/{id}/favorite` — remove from favorites
  - `GET  /properties/favorites` — list my favorite properties
- Reviews
  - `POST /properties/{id}/reviews` — add review (rating 1-5, comment)
  - `GET  /properties/{id}/reviews` — list reviews
- Webhooks (signed)
  - `GET  /webhooks/endpoints` — list endpoints
  - `POST /webhooks/endpoints` — add endpoint `{url, secret}`
  - `DELETE /webhooks/endpoints/{id}` — delete endpoint
  - `POST /webhooks/test` — emit `webhook.test`
 - Payments Integration
   - On reservation create, a Payment Request is created (host→guest) via Payments `/internal/requests` using HMAC headers. Stores `payment_request_id`.
   - Incoming payments webhook: `POST /payments/webhooks` — expects headers `X-Webhook-Ts`, `X-Webhook-Event`, `X-Webhook-Sign` (HMAC_SHA256(secret, ts + event + body)); on `requests.accept(ed)` it marks matching reservation as `confirmed` by `payment_request_id`.

Notes
- Availability is computed by subtracting overlapping reservations from `total_units` for a unit.
- Rate limiting supported (memory/Redis) via env.
- Notifications: events are emitted to log or Redis (`NOTIFY_MODE=log|redis`, `NOTIFY_REDIS_CHANNEL=stays.events`):
  - `reservation.created`, `reservation.confirmed`, `reservation.canceled`, `review.created`
- Payments integration: on reservation create, service calls Payments `/internal/requests` (HMAC‑signed) to create a Payment Request from host→guest. Requires in `.env`:
  - `PAYMENTS_BASE_URL` (e.g. http://host.docker.internal:8080)
  - `PAYMENTS_INTERNAL_SECRET` (must match Payments INTERNAL_API_SECRET)
- Webhook delivery: enable with `WEBHOOK_ENABLED=true`; headers `X-Webhook-Event`, `X-Webhook-Ts`, `X-Webhook-Sign` (HMAC_SHA256(secret, ts + event + body))
 - Payments inbound webhook verification: set `PAYMENTS_WEBHOOK_SECRET` to match Payments merchant endpoint secret.

Demo data (seed)
- Start DB + API first (see above or `make stays-up`).
- From repo root, run:
  - `make stays-seed` (uses DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5441/stays by default)
  - Or: `DB_URL=... python apps/stays/seed_demo.py`
- Creates 3 demo properties (Damascus/Aleppo/Latakia) with units, images, amenities and prices for the next 14 days.
