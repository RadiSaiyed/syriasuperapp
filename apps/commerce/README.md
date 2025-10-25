Commerce Service

FastAPI service for shops, products, carts, and orders with promo codes, wishlist, reviews, and shipping.

Run locally
1) Copy `.env.example` to `.env` and adjust.
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8083/docs

Auth (DEV)
- OTP is stubbed as 123456
- Use phone `+963xxxxxxxxx`

Features
- Shops & products (seeded sample data in dev), search and category filter
- Cart management (add/update/remove/clear)
- Checkout with shipping fields and promo codes (percent/fixed; limits + reporting DEV)
- Orders: list, cancel, mark paid/shipped (DEV helpers)
- Wishlist (favourite products)
- Reviews & ratings (only after purchase)
- Payments integration (dev/internal)

API (selection)
- Auth: `POST /auth/request_otp`, `POST /auth/verify_otp`
- Shops: `GET /shops`, `GET /shops/{shop_id}/products?q=&category=`
- Cart: `GET /cart`, `POST /cart/items`, `PUT /cart/items/{id}?qty=`, `POST /cart/clear`
- Orders: `POST /orders/checkout` (body: `{promo_code, shipping_*}`), `GET /orders`, `POST /orders/{id}/cancel` (and DEV: `/mark_paid`, `/mark_shipped`)
- Promos (DEV): `GET/POST /promos`, `GET /promos/stats`
- Wishlist: `GET/POST /wishlist`, `DELETE /wishlist/{id}`
- Reviews: `POST /reviews/{product_id}`, `GET /reviews/{product_id}`
