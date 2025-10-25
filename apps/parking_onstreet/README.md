Parking On‑Street Service (MVP)

FastAPI service providing on‑street parking features: zones near you, tariffs, start/stop sessions with transparent service fee, and simple reminders queue (to be added). Designed to integrate with the Super‑App and the existing Payments service for settlement.

Quick start
- Copy `.env.example` to `.env` and adjust.
- Start Postgres: `docker compose up -d db`
- Run API: `docker compose up --build api`
- Swagger: http://localhost:8096/docs

Environment
- `APP_PORT` (default 8096)
- `DB_URL` (default postgresql on localhost:5436)
- `JWT_SECRET` or `JWT_JWKS_URL` (HS256 dev or JWKS for shared auth)
- `PAYMENTS_BASE_URL` and `PAYMENTS_INTERNAL_SECRET` (optional for settlement integration)

Notes
- On first run, seeds a demo zone in Damascus with a sample tariff.
- Users are auto‑provisioned on first authenticated request based on token `sub`/`phone`.

