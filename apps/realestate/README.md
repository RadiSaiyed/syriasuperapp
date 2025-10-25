Real Estate Service

Minimal FastAPI service for property listings (buy/rent), favorites, and inquiries.

Features
- Listings: search/filter (`q`, `city`, `type`, `min_price`, `max_price`)
- Details: listing with images
- Favorites: add/remove/list (auth)
- Inquiries: create and list inquiries for a listing (auth)
- DEV auth via OTP (123456)
 - Reservation (Payments integration): creates a payment request for a reservation fee; recipient is the listing `owner_phone` (fallback Fee‑Wallet)

Start (DEV)
1) `cp -n .env.example .env`
2) `docker compose up -d db`
3) `docker compose up --build api`
4) Swagger: http://localhost:8092/docs

Auth (DEV)
- `POST /auth/request_otp` with `{ phone: "+963..." }`
- `POST /auth/verify_otp` with `{ phone: "+963...", otp: "123456", name:"Ali" }` → `access_token`
- Header `Authorization: Bearer <token>` for protected endpoints

API (excerpt)
- `GET  /listings`                    — list with filters
- `GET  /listings/{id}`               — details
- `POST /reservations?listing_id=...` — reservation fee as payment request (auth)
- `GET  /favorites`                   — favorites (auth)
- `POST /favorites/{listing_id}`      — mark as favorite (auth)
- `DELETE /favorites/{listing_id}`    — remove favorite (auth)
- `GET  /inquiries`                   — my inquiries (auth)
- `POST /inquiries`                   — create inquiry `{listing_id, message}` (auth)
- DEV Admin:
  - `POST /admin/seed`                — seed demo data
  - `POST /admin/listings`            — create listing (simple), optional `owner_phone` parameter
