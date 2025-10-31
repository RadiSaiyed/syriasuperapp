Operators micro-apps

This folder contains standalone entrypoints for operator-facing apps split out from the main domain services. Each service imports the corresponding domain code (models, auth, DB, etc.) and only exposes the operator/driver/courier routes required for that role.

Available services

- Taxi Driver API: operators/taxi_driver (auth, driver, driver taxi wallet, push)
- Taxi Partners API: operators/taxi_partners (auth, partners)
- Food Operator API: operators/food_operator (auth, operator)
- Food Courier API: operators/food_courier (auth, courier)
- Bus Operators API: operators/bus_operators (auth, operators)
- Stays Host API: operators/stays_host (auth, host)
- Real Estate Owner API: operators/realestate_owner (auth endpoints inline, owner)
- Doctors Doctor API: operators/doctors_doctor (auth, doctor)
- Livestock Seller API: operators/livestock_seller (auth, seller)
- Freight Shipper API: operators/freight_shipper (auth, shipper)
- Freight Carrier API: operators/freight_carrier (auth, carrier)
- Jobs Employer API: operators/jobs_employer (auth, employer)
- Payments Merchant API: operators/payments_merchant_api (merchant-api only)

How to run (Docker Compose)

- Taxi Driver: cd operators/taxi_driver && docker compose up -d db redis api
- Taxi Partners: cd operators/taxi_partners && docker compose up -d db redis api
- Food Operator: cd operators/food_operator && docker compose up -d db redis api
- Food Courier: cd operators/food_courier && docker compose up -d db redis api
- Bus Operators: cd operators/bus_operators && docker compose up -d db redis api
- Stays Host: cd operators/stays_host && docker compose up -d db redis api
- Real Estate Owner: cd operators/realestate_owner && docker compose up -d db api
- Doctors (Doctor): cd operators/doctors_doctor && docker compose up -d db redis api
- Livestock Seller: cd operators/livestock_seller && docker compose up -d db redis api
- Freight Shipper: cd operators/freight_shipper && docker compose up -d db redis api
- Freight Carrier: cd operators/freight_carrier && docker compose up -d db redis api
- Jobs Employer: cd operators/jobs_employer && docker compose up -d db redis api
- Agriculture Farmer: cd operators/agriculture_farmer && docker compose up -d db redis api
- Payments Merchant: cd operators/payments_merchant_api && docker compose up -d db redis api

Notes

- These services reuse the domain app code via PYTHONPATH and import it directly, avoiding duplication. Use the corresponding domain .env files for configuration.
- Ports are distinct to avoid conflicts with the full domain APIs (Taxi 8081, Food 8090, Bus 8082). See each docker-compose.yml for the chosen port.
- Migrations: where Alembic migrations exist (Taxi, Payments), they are executed automatically on container start (see command in docker-compose.yml). Other services without versioned migrations rely on AUTO_CREATE_SCHEMA to create tables at startup.
- You can also run migrations explicitly via a dedicated compose service:
  - Taxi Driver: `cd operators/taxi_driver && docker compose run --rm migrate`
  - Taxi Partners: `cd operators/taxi_partners && docker compose run --rm migrate`
  - Payments Merchant: `cd operators/payments_merchant_api && docker compose run --rm migrate`

Common endpoints

- `GET /` — quick links and service info (non‑schema)
- `GET /ui` — minimal HTML tester (paste JWT, call /me)
- `GET /health` — liveness
- `GET /health/deps` — dependencies readiness (DB, Redis)
- `GET /metrics` — Prometheus metrics
- Security headers are enabled (nosniff, DENY, no‑referrer, strict Permissions‑Policy). `Cache-Control: no-store` for write operations.
- Optional OpenTelemetry tracing: set `OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4318` (or your collector) and (optional) `OTEL_SERVICE_NAME` to export traces.
- `GET /me` — role-aware summary for the current operator user (counts, quick profile)
  - Returns 403 if caller lacks the required role/membership for that operator app
- `GET /info` — static service metadata (name, version, env)
- Taxi Driver additionally provides WebSockets from the domain app:
  - `GET /ws/driver?token=JWT`
  - `GET /ws/rides/{ride_id}?token=JWT`
- Payments Merchant adds: `GET /merchant/api/ping` (HMAC headers required)

UI helpers (highlights)

- Bus Operators `/ui`
  - Trips list, CSV export, Trip Manifest, Reports summary.
  - Tickets: QR validate (`BUS|<booking_id>`) and Board actions.
  - Admin: Branches (list/create/update/delete), Vehicles (list/create/update/delete), Promos (list/create/update/delete), Clone Trip (date range + weekdays).
- Food Operator `/ui`
  - Operator actions (categories, modifiers, items, stations, bulk stock CSV/XLSX, KDS, orders bulk status, reports/payout).
  - Admin extras: Create Restaurant, Hours get/set (JSON + override), Menu Item create, Restaurant Images add/list.
- Doctors (Doctor) `/ui`
  - Profile upsert, Slots list/create, Appointments list/status, Images add/list/delete.
- Stays Host `/ui`
  - Properties/Units, Reservations confirm/cancel.
  - Admin extras: Property Images add/list/delete, Unit Blocks add/list/delete, Unit Prices set/get.
- Freight Carrier `/ui`
  - Loads (available) filter, set location; Bids: create + list my bids.
- Freight Shipper `/ui`
  - Loads post/list; Bids per Load: list, accept/reject.
- Jobs Employer `/ui`
  - Company create/get, Jobs create/list/status, Applications list/status; update Tags via PATCH.
  - CSV export for Jobs (planned), bulk status updates, tagging presets.

Taxi Webhook Simulation (Taxi Partners)

- In `operators/taxi_partners` open `/ui` and use “Simulate Webhooks → Taxi”.
  - Defaults: Taxi API Base `http://localhost:8081` (override via field or `TAXI_BASE`).
  - Ride Status webhook: partner_key_id, external_trip_id, status (accepted|enroute|completed|canceled), optional final_fare_cents.
  - Driver Location webhook: partner_key_id, external_driver_id, lat, lon.
  - Requests are HMAC‑signed server‑side using the Partner secret and sent to Taxi API endpoints:
    - `POST /partners/{partner_key_id}/webhooks/ride_status`
    - `POST /partners/{partner_key_id}/webhooks/driver_location`
