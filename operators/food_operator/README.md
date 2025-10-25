# Food Operator API

Operator-facing API for platform-wide restaurant management, orders oversight, and reporting. This service imports the Food domain (models, auth, DB) and exposes only operator routes.

How to run

- Docker Compose: `cd operators/food_operator && docker compose up -d db redis api`
- Local (env vars from `apps/food/.env` apply):
  - `PYTHONPATH=apps/food uvicorn operators.food_operator.main:app --reload --port 8090`

Key endpoints

- Auth: `/auth/request_otp`, `/auth/verify_otp`
- Dashboard: `GET /me` — operator summary (orders, metrics)
- Restaurants:
  - `GET  /operator/restaurants` — list restaurants
  - `POST /operator/restaurants` — create restaurant (admin)
  - `PATCH /operator/restaurants/{restaurant_id}` — update restaurant (admin)
- Menu management (new):
  - `GET    /operator/restaurants/{restaurant_id}/menu`
  - `POST   /operator/restaurants/{restaurant_id}/menu` (admin)
  - `PATCH  /operator/menu/{menu_item_id}` (admin)
  - `DELETE /operator/menu/{menu_item_id}` (admin)
- Images (new):
  - `GET    /operator/restaurants/{restaurant_id}/images`
  - `POST   /operator/restaurants/{restaurant_id}/images` (admin)
  - `DELETE /operator/images/{image_id}` (admin)
- Orders:
  - `GET  /operator/orders` — list recent orders (filter by `status_filter`)
  - `GET  /operator/orders/{order_id}` (new)
  - `POST /operator/orders/{order_id}/status` (admin, new)
- Members (new):
  - `GET    /operator/members`
  - `POST   /operator/members` (admin) — add by phone, set role `admin|agent`
  - `PATCH  /operator/members/{member_id}` (admin)
  - `DELETE /operator/members/{member_id}` (admin)
- Reports:
  - `GET /operator/reports/summary?days=7`
  - `GET /operator/reports/summary.csv?days=7` (new)
  - `GET /operator/reports/summary.pdf?days=7` (new)
  - `GET /operator/reports/top_items?days=30&limit=10` (new)
  - `GET /operator/reports/by_restaurant?days=30` (new)
  - `GET /operator/reports/by_restaurant.csv?days=30` (new)
  - `GET /operator/reports/by_city?days=30` (new)
  - `GET /operator/reports/by_city.csv?days=30` (new)
  - `GET /operator/reports/cancellation_rate?days=30` (new)
  - `GET /operator/reports/sla?days=30` (new)
  - `GET /operator/reports/peaks?days=30` (new)

- Opening hours (new):
  - `GET /operator/restaurants/{restaurant_id}/hours`
  - `POST /operator/restaurants/{restaurant_id}/hours` (admin)
  - Restaurant objects now include `hours` and `is_open` fields

- UI (preview):
  - `GET /ui` — minimal HTML page to explore endpoints with a pasted JWT

Notes

- Security: All routes require JWT. Platform access is granted via `food_operator_members` with roles `admin|agent`.
- Side-effects: Order status changes emit `food.order.status_changed` events and webhooks if enabled. Cancellations after acceptance will request refunds via webhook.
- Schema: Uses the Food domain schema. AUTO_CREATE_SCHEMA extends schema with `hours_json` and `is_open_override` when needed.
