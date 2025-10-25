Utilities Service

FastAPI service for bill payments and mobile top-ups with promo codes and account management.

Run locally
1) Copy `.env.example` to `.env` and adjust.
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8084/docs

Auth (DEV)
- OTP is stubbed as 123456
- Use phone `+963xxxxxxxxx`

Features
- List supported billers (electricity, water, mobile) with category filter
- Link/rename/delete biller accounts (e.g., meter / phone)
- Fetch dummy bills (seeded in dev) and pay (creates payment request)
- Mobile top-ups with promo codes (discount %/fixed, limits + reporting DEV)
- Payments integration via internal endpoint (DEV)

API
- Auth: `POST /auth/request_otp`, `POST /auth/verify_otp`
- Billers: `GET /billers?category=`
- Accounts: `POST /accounts/link`, `GET /accounts`, `PUT /accounts/{id}?alias=`, `DELETE /accounts/{id}`
- Bills: `POST /bills/refresh?account_id=`, `GET /bills`, `POST /bills/{id}/pay`
- Topups: `POST /topups` (body supports `promo_code`), `GET /topups`
- Promos (DEV): `GET/POST /promos`, `GET /promos/stats`
