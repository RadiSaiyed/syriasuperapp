Food Delivery API — FastAPI service

Overview
- Minimal food delivery backend: restaurants, menus, cart, and orders with optional Payments integration.
- Mirrors other services (OTP auth, models, routers, Docker, env, metrics, rate limiting).
- Rollen/Trennung:
  - Endkunde (Customer): Browse, Cart, Checkout, Orders, Reviews, Favorites
  - Lieferant (Vendor/Owner): Eigene Restaurants, Menu, Bilder, Bestellungen – Prefix `/admin`
  - Betreiber (Operator): Plattformweite Verwaltung & Reporting – Prefix `/operator`

Quick start
1) Copy env and set variables: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`

Defaults
- Port: 8090
- DB (in Docker): `postgresql+psycopg2://postgres:postgres@db:5432/food`
- DB (local default in config): `postgresql+psycopg2://postgres:postgres@localhost:5443/food`

API (MVP)
- Auth
  - `POST /auth/request_otp` — request OTP (dev: 123456)
  - `POST /auth/verify_otp` — create user, return JWT
- Restaurants
  - `GET  /restaurants` — list restaurants (filters: `city`, `q`; includes `rating_avg`, `rating_count`)
  - `GET  /restaurants/{id}/menu` — list menu items
- Favorites
  - `POST /restaurants/{id}/favorite`, `DELETE /restaurants/{id}/favorite`, `GET /restaurants/favorites`
- Reviews
  - `POST /restaurants/{id}/reviews` (rating 1–5, comment), `GET /restaurants/{id}/reviews`
- Cart
  - `GET  /cart` — get my cart
  - `POST /cart/items` — add item `{menu_item_id, qty}`
  - `PUT  /cart/items/{item_id}` — update qty
  - `DELETE /cart/items/{item_id}` — remove item
- Orders
  - `POST /orders/checkout` — create order (optional Payment request)
  - `GET  /orders` — list my orders
  - `GET  /orders/{id}/tracking` — latest courier position (lat/lon)

Admin
- `POST /admin/dev/become_owner?restaurant_id=...` — link current user as owner (dev convenience)
- `PATCH /admin/restaurants/{id}` — update restaurant (`name`, `city`, `description`, `address`)
- Menu: `POST /admin/restaurants/{id}/menu`, `PATCH /admin/menu/{menu_item_id}`, `DELETE /admin/menu/{menu_item_id}`
- Images: `POST /admin/restaurants/{id}/images` (Array `{url, sort_order}`), `GET /admin/restaurants/{id}/images`, `DELETE /admin/images/{image_id}`
- `GET  /admin/orders` — list orders for owned restaurants
- `POST /admin/orders/{id}/status?status_value=...` — update status (`created→accepted→preparing→out_for_delivery→delivered`)

Courier
- `GET  /courier/available` — list orders ready for pickup (`preparing`, unassigned)
- `POST /courier/orders/{id}/accept` — accept order (assign to me)
- `GET  /courier/orders` — list my assigned orders
- `POST /courier/orders/{id}/picked_up` — set status to `out_for_delivery`
- `POST /courier/orders/{id}/delivered` — set status to `delivered`
- `POST /courier/orders/{id}/location` — update my current location `{lat,lon}`

Notes
- Dev seed ensures there are demo restaurants/menu items on first access.

Demo data (seed)
- `make food-seed` (uses DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5443/food by default)
- Or: `DB_URL=... python apps/food/seed_demo.py`

Webhooks & Notifications
- Service‑level Webhooks (signed): `GET/POST/DELETE /webhooks/endpoints`, `POST /webhooks/test`
- Events: `food.order.created`, `food.order.status_changed`, `food.order.out_for_delivery`, `food.order.delivered`, `food.review.created`
- Configure via env: `WEBHOOK_ENABLED`, `WEBHOOK_TIMEOUT_SECS`, `NOTIFY_MODE`, `NOTIFY_REDIS_CHANNEL`

Payments Integration
- On checkout, a Payment Request is created (user→restaurant owner phone if set, else fee wallet), metadata includes `{order_id}`.
- Inbound payments webhook: `POST /payments/webhooks` verifies `X-Webhook-*` headers and on `requests.accept(ed)` sets order status to `accepted` for matching `payment_request_id`.

E2E Flow (Food ↔ Payments)
- Setup
  - Set in food `.env`: `PAYMENTS_BASE_URL`, `PAYMENTS_INTERNAL_SECRET`, `PAYMENTS_WEBHOOK_SECRET`
  - In Payments, add a webhook endpoint to food: `POST /webhooks/endpoints?url=http://host.docker.internal:8090/payments/webhooks&secret=$PAYMENTS_WEBHOOK_SECRET`
- Checkout
  - User checks out: Food creates a Payment Request and stores `payment_request_id`.
- Confirm (simulate)
  - Accept in Payments to emit `requests.accept` (with `transfer_id`), or simulate by posting to Food `/payments/webhooks` with signed headers and body `{"type":"requests.accept","data":{"id":"PR_ID","transfer_id":"TR_ID"}}`.
  - Food marks order `accepted` and stores `payment_transfer_id`.
  - Cancel → Refund
  - Owner cancels after acceptance: Food emits `refund.requested` webhook `{order_id, transfer_id, amount_cents}`; upon `refunds.create` event, sets `refund_status=completed`.

Make targets (Dev)
- `make up` — startet Payments + Food (DB/Redis/API)
- `make food-webhook` — registriert den Food‑Webhook in Payments (`http://host.docker.internal:8090/payments/webhooks`, Secret `demo_secret`)
- `make e2e` — erstellt bei Bedarf Demo‑Restaurant und Menü, Checkout → Payment Request → Annahme in Payments → Bestellungen auflisten
- `make down` — stoppt beide Stacks inkl. Volumes

Admin cURL (Owner)
- Update restaurant: `PATCH /admin/restaurants/{id}?name=New&city=Damascus&address=Main`
- Menu: `POST /admin/restaurants/{id}/menu?name=Kebab&price_cents=20000`, `PATCH /admin/menu/{menu_item_id}?price_cents=22000`, `DELETE /admin/menu/{menu_item_id}`
- Images: `POST /admin/restaurants/{id}/images` body `[ {"url":"https://.../1.jpg","sort_order":0} ]`; `GET /admin/restaurants/{id}/images`; `DELETE /admin/images/{image_id}`

Sample cURL (Dev)
1) Login (OTP dev):
   curl -s http://localhost:8090/auth/request_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000001"}'
   TOK=$(curl -s http://localhost:8090/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000001","otp":"123456"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
2) Restaurants:
   curl -s http://localhost:8090/restaurants -H "Authorization: Bearer $TOK" | jq .
3) Add to cart and checkout:
   RID=$(curl -s http://localhost:8090/restaurants -H "Authorization: Bearer $TOK" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
   MI=$(curl -s http://localhost:8090/restaurants/$RID/menu -H "Authorization: Bearer $TOK" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
   curl -s -X POST http://localhost:8090/cart/items -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"menu_item_id":"'"$MI"'","qty":1}' | jq .
   curl -s -X POST http://localhost:8090/orders/checkout -H "Authorization: Bearer $TOK" | jq .
4) Admin (link as owner):
   curl -s -X POST "http://localhost:8090/admin/dev/become_owner?restaurant_id=$RID" -H "Authorization: Bearer $TOK"
5) Courier (location update):
   curl -s -X POST http://localhost:8090/courier/orders/ORDER_ID/location -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"lat":33.5138,"lon":36.2765}'
Operator
- DEV grant: `POST /operator/dev/become_admin`
- Restaurants: `GET /operator/restaurants`, `POST /operator/restaurants` (name, city, address, owner_phone?), `PATCH /operator/restaurants/{id}`
- Orders: `GET /operator/orders?status=...`
- Summary: `GET /operator/reports/summary?days=7`
