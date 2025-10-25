Agriculture API — Farmers, Seasonal Jobs, Produce Market

Overview
- FastAPI service combining three simple domains:
  - Farmers manage a farm, publish produce listings
  - Seasonal workers browse/apply to farm jobs
  - Buyers browse produce and place orders

Quick start
1) Copy env and set variables: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8093/docs

Defaults
- Port: 8093
- DB (in Docker): `postgresql+psycopg2://postgres:postgres@db:5432/agriculture`
- DB (local default in config): `postgresql+psycopg2://postgres:postgres@localhost:5445/agriculture`

API (selection)
- Auth: `POST /auth/request_otp`, `POST /auth/verify_otp` (dev OTP 123456)
- Health: `GET /health`
- Farmer
  - `POST /farmer/farm` — create my farm (name, location, description)
  - `GET  /farmer/farm` — get my farm
  - `POST /farmer/listings` — create produce listing (produce_name, category, quantity_kg, price_per_kg_cents)
  - `GET  /farmer/listings` — list my listings
  - `PATCH /farmer/listings/{id}` — update listing (quantity_kg, price_per_kg_cents, status)
  - `POST /farmer/jobs` — create seasonal job (title, wage_per_day_cents, dates)
  - `GET  /farmer/jobs` — list my jobs
  - `GET  /farmer/jobs/{id}/applications` — list applications for my job
  - `PATCH /farmer/applications/{id}` — update application status (applied|reviewed|accepted|rejected)
  - `GET  /farmer/orders` — list orders for my listings
- Market
  - `GET  /market/listings` — browse active listings (filters: q, category, location)
  - `GET  /market/listings/{id}` — listing details
  - `POST /market/listings/{id}/order` — place order (qty_kg)
  - `GET  /market/orders` — my orders (buyer)
- Jobs
  - `GET  /jobs` — list open jobs (filters: farm_id, q, location)
  - `GET  /jobs/{id}` — job details
  - `POST /jobs/{id}/apply` — apply (message optional)
  - `GET  /jobs/my_applications` — list my applications
  - `POST /jobs/my_applications/{id}/withdraw` — withdraw my application

Notes
- MVP scope; no payments enforcement in API. Integrate with Payments service later via internal API if desired.
- OTP is dev-friendly by default; set `OTP_MODE=redis` to use Redis storage and random codes.
