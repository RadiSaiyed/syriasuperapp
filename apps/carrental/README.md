Car Rental API — Autovermietung

Overview
- FastAPI service for car rental marketplace:
  - Companies list vehicles (make/model, year, seats, transmission, price per day)
  - Renters browse/filter and create bookings

Quick start
1) Copy env: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8095/docs

Defaults
- Port: 8095
- DB (Docker): `postgresql+psycopg2://postgres:postgres@db:5432/carrental`
- DB (local dev): `postgresql+psycopg2://postgres:postgres@localhost:5447/carrental`

API (selection)
- Auth: `POST /auth/request_otp`, `POST /auth/verify_otp`
- Health: `GET /health`
- Company (seller)
  - `POST /company` — create company for current user (becomes seller)
  - `GET  /company` — my company
  - `POST /vehicles` — add vehicle
  - `GET  /vehicles` — list my vehicles
  - `PATCH /vehicles/{id}` — update vehicle (price, status, details)
  - `GET  /orders` — bookings for my vehicles
- Market
  - `GET  /market/vehicles` — browse available vehicles (filters: q, location, make, transmission, seats>=, price range, date window)
  - `GET  /market/vehicles/{id}` — vehicle details
  - `POST /market/vehicles/{id}/book` — create booking `{start_date, end_date}`
  - `GET  /market/bookings` — my bookings

Notes
- Optional Payments handoff on booking with webhook confirmation of bookings.
- OTP in dev uses code `123456`.

