Syria Super‑App BFF (Backend for Frontend)

Purpose
- Provide a single, mobile‑optimized API surface for the Super‑App client.
- Aggregate user/profile data, expose a feature manifest, and fan‑out to backend verticals.

Endpoints
- GET `/health` — liveness + env info
- GET `/v1/features` — feature manifest for the client grid (ETag + Cache‑Control)
- GET `/v1/me` — aggregated profile snapshot (Payments wallet + recent tx, KYC, Merchant; Chat conversation summary)
- Auth convenience (proxied to Payments):
  - POST `/auth/register` — create account (username/password/phone)
  - POST `/auth/login` — login with username/password
  - POST `/auth/dev_login` — dev-only shortcut
  - POST `/auth/request_otp` — request OTP for phone
  - POST `/auth/verify_otp` — verify OTP (returns RS256 JWT)
- Path proxy `/<service>/*` — HTTP proxy to upstreams (payments, taxi, bus, commerce, utilities, ...)
- WebSocket proxy `/{service}/ws` — WS tunnel to upstream `/ws` (e.g. Chat). Use `wss://api.<domain>/<service>/ws?token=...`.
- Convenience endpoints with ETag/304:
  - GET `/v1/commerce/shops`
  - GET `/v1/commerce/shops/{shop_id}/products`
  - GET `/v1/commerce/orders`
  - GET `/v1/commerce/orders/{order_id}`
  - GET `/v1/stays/properties`
  - GET `/v1/stays/properties/{property_id}`
  - GET `/v1/stays/reservations`
  - GET `/v1/stays/favorites`
  - Dev (proxied): `POST /stays/dev/seed`, `POST /chat/dev/seed` (available when upstream services run in `ENV=dev`)
- Push & Topics (dev‑friendly, optional Redis):
  - POST `/v1/push/register` — register device push token `{token, platform, device_id}`
  - GET  `/v1/push/dev/list` — list my registered devices (dev)
  - POST `/v1/push/dev/send` — send a dev notification to myself `{title, body, deeplink?, data?}`
  - POST `/v1/push/topic/subscribe` — subscribe to a topic `{topic}`
  - POST `/v1/push/topic/unsubscribe` — unsubscribe `{topic}`
  - GET  `/v1/push/topic/list` — my topics
  - POST `/v1/push/dev/broadcast_topic` — broadcast to a topic `{topic, title, body, deeplink?}`

Security (dev push endpoints)
- Dev endpoints under `/v1/push/dev/*` require admin when `APP_ENV=prod` or when `PUSH_DEV_ALLOW_ALL=false`.
- Admin detection checks token claims: `role` in {admin, owner, operator, ops}, `is_admin=true`, or permissions/scopes include `admin`/`push:admin`/`push:send`.
- Allowlists are supported via env:
  - `PUSH_DEV_ALLOWED_PHONES` — comma‑separated phone list
  - `PUSH_DEV_ALLOWED_SUBS` — comma‑separated user ids
  - `PUSH_DEV_ALLOW_ALL` — default true for non‑prod; set to false to always require admin

Config
- APP_ENV — string in health response (default dev)
- Upstreams (defaults assume local ports):
  - PAYMENTS_BASE_URL (default http://host.docker.internal:8080)
  - TAXI_BASE_URL (http://host.docker.internal:8081), BUS_BASE_URL (…:8082), COMMERCE_BASE_URL (…:8083), … up to AI_GATEWAY_BASE_URL (…:8099)
 - REDIS_URL — optional; enables Redis‑backed storage for push registrations and topic sets
 - FCM_SERVER_KEY — optional; when provided, dev sends/broadcasts go through FCM

Run (local)
- Python: `ENV=dev APP_PORT=8070 python -m apps.bff.app.main`
- Docker Compose: `docker compose -f apps/bff/docker-compose.yml up --build`

Notes
- For now, /v1/me reads wallet data from Payments only. Expand gradually to include other verticals.
- The Super‑App client can be pointed to the BFF by setting `SUPERAPP_API_BASE` (e.g., http://localhost:8070). In that mode, all services use path‑based routing via the BFF proxy (`http://localhost:8070/taxi/...`).
- WebSockets: a lightweight WS proxy exists at `/{service}/ws`. For very high‑throughput chat, direct connections are still an option.
- ETag/304: Commerce/Stays endpoints include ETag and sane Cache‑Control; the client caches and sends `If-None-Match` to reduce bandwidth and latency.

Repository cleanup
- Per‑service demo Flutter clients were removed in favor of the unified `superapp_flutter` client. A copy is archived under `archive/<timestamp>/clients/` for reference.
