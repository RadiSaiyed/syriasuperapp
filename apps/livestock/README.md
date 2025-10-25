Livestock API — Viehmarkt & Tierische Produkte

Overview
- FastAPI service for:
  - Sellers (farmers/ranches) to publish animal listings and animal products (milk, eggs, cheese, meat)
  - Buyers to browse and place simple orders

Quick start
1) Copy env: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8094/docs

Defaults
- Port: 8094
- DB (in Docker): `postgresql+psycopg2://postgres:postgres@db:5432/livestock`
- DB (local default in config): `postgresql+psycopg2://postgres:postgres@localhost:5446/livestock`

API (selection)
- Auth: `POST /auth/request_otp`, `POST /auth/verify_otp` (dev OTP 123456)
- Health: `GET /health`
- Seller
  - `POST /seller/ranch`, `GET /seller/ranch`
  - Animals: `POST /seller/animals`, `GET /seller/animals`, `PATCH /seller/animals/{id}`
  - Products: `POST /seller/products`, `GET /seller/products`, `PATCH /seller/products/{id}`
  - Orders: `GET /seller/orders`
- Market
  - Animals: `GET /market/animals` (filters: `q`, `species`, `location`), `GET /market/animals/{id}`, `POST /market/animals/{id}/order`
  - Products: `GET /market/products` (filters: `q`, `type`, `location`), `GET /market/products/{id}`, `POST /market/products/{id}/order`
  - My Orders: `GET /market/orders`

Notes
- Orders are created with status `created`; optional Payments handoff can create a Payment Request and confirm via webhook.
- OTP in `dev` mode uses code `123456`.

