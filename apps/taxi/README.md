Taxi Service (MVP)

FastAPI service for ride‑hailing MVP: riders request rides, drivers accept and complete.

New features
- Quote endpoint: `POST /rides/quote` returns `{quoted_fare_cents, distance_km, surge_multiplier}` without creating a ride.
- Simple surge pricing: fares increase when few drivers are available nearby (configurable).
- ETA to pickup: when a driver is assigned, `eta_to_pickup_minutes` is included.
- Rider ratings: `POST /rides/{ride_id}/rate` (1..5 stars) after completion.
- Driver ratings/profile: `GET /driver/ratings`, `GET /driver/profile`.
- Driver earnings: `GET /driver/earnings?days=7` returns total completed fares in period.
 - Multi‑Stops: add `stops` array to quote/request payload to include intermediate points.
 - Promo‑Codes: include `promo_code` in quote/request; dev endpoints to manage: `GET/POST /promos`.
 - Favorites: `GET/POST /favorites`, `DELETE /favorites/{id}`.
- Scheduled rides:
  - `POST /rides/schedule` — create a scheduled ride
  - `GET  /rides/scheduled` — list your scheduled rides
  - `DELETE /rides/scheduled/{id}` — cancel a scheduled ride
  - `POST /rides/dispatch_scheduled` (DEV) — materialize due rides in the next window
- Fraud/Risk Controls:
  - Rider velocity: at most `FRAUD_RIDER_MAX_REQUESTS` requests within `FRAUD_RIDER_WINDOW_SECS` (defaults 6/60s) → 429
  - Driver location checks: location must be fresh (`FRAUD_DRIVER_LOC_MAX_AGE_SECS`, default 300s) and near pickup/dropoff:
    - Accept: distance ≤ `FRAUD_MAX_ACCEPT_DIST_KM` (default 3.0 km)
    - Start: distance ≤ `FRAUD_MAX_START_DIST_KM` (default 0.3 km)
    - Complete: distance ≤ `FRAUD_MAX_COMPLETE_DIST_KM` (default 0.5 km)
  - Events: `fraud_events` logs violations (type + data)

Run locally
1) Copy `.env.example` to `.env` and adjust.
2) Start Postgres: `docker compose up -d db`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8081/docs

Staging stack (Payments + Taxi)
- Copy `ops/staging/payments.env.example` and `ops/staging/taxi.env.example`, populate secrets, then `docker compose -f ops/staging/docker-compose.yml up -d --build`.
- Run wallet/escrow smoke: `tools/e2e/taxi_wallet_escrow_e2e.sh` with `BASE_TAXI`, `BASE_PAYMENTS`, and `ADMIN_TOKEN`.

Security/Rate‑Limit (Prod)
- Set `ENV=prod`, enforce Redis rate‑limiter: `RATE_LIMIT_BACKEND=redis` and `REDIS_URL=redis://...`.
- JWT secrets hardened:
  - Either use HS256 secrets with rotation (`JWT_SECRET`, optional `JWT_SECRET_PREV` or `JWT_SECRETS` CSV; most‑recent first), or use `JWT_JWKS_URL` for RS256.
- Internal Payments HMAC:
  - Use a strong `PAYMENTS_INTERNAL_SECRET` (≥32 chars). Rotate via `PAYMENTS_INTERNAL_SECRET_PREV` or `PAYMENTS_INTERNAL_SECRETS` CSV (most‑recent first). The first secret is used for signing.
- When `ENV!=dev`, the service enforces:
  - Redis rate‑limit; a valid `REDIS_URL`
  - Secure JWT secrets (if no `JWT_JWKS_URL` is set)
  - A secure internal secret

Matching & Reassign (Robustness)
- Timeouts: `ASSIGNMENT_ACCEPT_TIMEOUT_SECS` (default 120s) — rides not accepted in time are cleaned via `/rides/reap_timeouts` (admin, header `X-Admin-Token`) and reassigned.
- Start timeouts: `ACCEPTED_START_TIMEOUT_SECS` (default 300s) — accepted rides without start are cleaned via `/rides/reap_start_timeouts` and reassigned.
- Reassign strategies:
  - Manual: `/rides/{id}/reassign` (rider/driver)
  - Stale scan (DEV): `/rides/reassign_stale?minutes=2`
  - Timeout reaper (cron/job): `/rides/reap_timeouts?accept_timeout_secs=120&limit=200&relax_wallet=false` and `/rides/reap_start_timeouts?start_timeout_secs=300`
- Cron helper: `ops/cron/taxi_maintenance.sh` triggers reapers + scheduled dispatch with `ADMIN_TOKEN`. Run via systemd timer or cron every 1–5 minutes.
- Degradation paths:
  - Increase radius via `REASSIGN_RADIUS_FACTOR` (default 1.0) for reassign/timeout‑reaper
  - Optional wallet relaxation during reassign via `REASSIGN_RELAX_WALLET=true` (only if appropriate)
- Metriken (Prometheus):
  - `taxi_matching_attempts_total{result="assigned|none"}`
  - `taxi_reassign_events_total{reason="driver_cancel|rider_request|stale_scan",result}`
  - `taxi_timeouts_reassigned_total{stage="accept_timeout|start_timeout",result}`
  - `taxi_ride_status_transitions_total{from,to}`

Admin Hardening
- Admin token: `ADMIN_TOKEN` (required for reaper endpoints). In production, prefer `ADMIN_TOKEN_SHA256` with SHA‑256 digests.
- Optional IP allowlist: `ADMIN_IP_ALLOWLIST` (comma‑separated IPs); requests from other hosts receive `403 admin_ip_blocked`.

Admin Endpoints (Fraud/Suspensions)
- `GET  /admin/fraud/events?limit=100` — latest fraud events (admin token required)
- `POST /admin/suspensions { user_phone?|driver_phone?, reason?, minutes? }` — create suspension (optionally time‑bound)
- `GET  /admin/suspensions` — list recent suspensions
- `GET  /admin/suspensions/active[?phone=..|&driver_phone=..]` — active suspensions
- `POST /admin/suspensions/{id}/toggle { active: true|false }` — toggle a suspension
- `POST /admin/suspensions/unsuspend { user_phone?|driver_phone? }` — deactivate all active suspensions for a target
- `GET  /admin/user?phone=+963...` — user/driver profile + suspensions
- `GET  /admin/ui` — minimal HTML overview (live)
  - Includes a “CB Reset” button for the Payments circuit breaker and shows current CB states.

All admin calls require header `X-Admin-Token: <ADMIN_TOKEN>` and optional IP allowlist.

Push‑Benachrichtigungen (optional)
- Registrierung: `POST /push/register { token, platform: android|ios|web, app_mode?: rider|driver }`
- Abmeldung: `POST /push/unregister { token }`
- Server: setzt `FCM_SERVER_KEY` um Push an registrierte Tokens zu senden (FCM legacy HTTP API). Bei nicht gesetztem Key wird still ignoriert.
- Events: Fahrer‑Zuweisung (Driver), Ride akzeptiert/gestartet/abgeschlossen (Rider)

Auth (DEV)
- OTP is stubbed as 123456
- Use phone `+963xxxxxxxxx`

Quick test (cURL)
- Rider A, Driver B (example flow):
  - A: `curl -s -X POST http://localhost:8081/auth/request_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000001"}'`
  - A: `TOKEN_A=$(curl -s -X POST http://localhost:8081/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000001","otp":"123456","name":"Ali"}' | jq -r .access_token)`
  - B: `curl -s -X POST http://localhost:8081/auth/request_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000002"}'`
  - B: `TOKEN_B=$(curl -s -X POST http://localhost:8081/auth/verify_otp -H 'Content-Type: application/json' -d '{"phone":"+963900000002","otp":"123456","name":"Driver"}' | jq -r .access_token)`
  - B apply as driver: `curl -s -X POST http://localhost:8081/driver/apply -H "Authorization: Bearer $TOKEN_B" -H 'Content-Type: application/json' -d '{"vehicle_make":"Toyota","vehicle_plate":"ABC-123"}'`
  - B set available: `curl -s -X PUT http://localhost:8081/driver/status -H "Authorization: Bearer $TOKEN_B" -H 'Content-Type: application/json' -d '{"status":"available"}'`
  - B set location near pickup (Damascus coords example):
    `curl -s -X PUT http://localhost:8081/driver/location -H "Authorization: Bearer $TOKEN_B" -H 'Content-Type: application/json' -d '{"lat":33.5138, "lon":36.2765}'`
  - A requests ride (to a nearby dropoff):
    `RID=$(curl -s -X POST http://localhost:8081/rides/request -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' -d '{"pickup_lat":33.5138,"pickup_lon":36.2765,"dropoff_lat":33.52,"dropoff_lon":36.28}' | jq -r .id)`
  - B accepts: `curl -s -X POST http://localhost:8081/rides/$RID/accept -H "Authorization: Bearer $TOKEN_B"`
  - B starts: `curl -s -X POST http://localhost:8081/rides/$RID/start -H "Authorization: Bearer $TOKEN_B"`
  - B completes: `curl -s -X POST http://localhost:8081/rides/$RID/complete -H "Authorization: Bearer $TOKEN_B"`
  - A ride history: `curl -s http://localhost:8081/rides -H "Authorization: Bearer $TOKEN_A"`

Payments Integration & Driver Taxi Wallet (DEV)
- Separate Taxi Wallet per driver: each driver has an in‑app taxi wallet balance used to cover platform fees for cash rides.
- Linking to main wallet: drivers can top up or withdraw between their main Payments wallet and the taxi wallet via:
  - `GET  /driver/taxi_wallet` — check balance + recent history
  - `POST /driver/taxi_wallet/topup { amount_cents }` — move funds from main wallet → taxi wallet
  - `POST /driver/taxi_wallet/withdraw { amount_cents }` — move funds from taxi wallet → main wallet
- Low‑balance prompt: accepting/assignment requires the taxi wallet to cover the expected platform fee for the quoted fare; otherwise the API returns `insufficient_taxi_wallet_balance` and the client should prompt to top up.
- Ride history entries: at acceptance, the taxi wallet records the ride’s original quoted fare, the 10% fee (configurable), and the driver’s remaining amount (fare minus fee). The fee debits the taxi wallet immediately.
- Settlement model (DEV): when `TAXI_POOL_WALLET_PHONE` is set, top‑ups transfer from the driver’s main wallet to a pool wallet in Payments; ride fees are settled from the pool to the platform fee wallet. In prod, this maps taxi wallet balances to held funds in Payments.
- Client UX (dev convenience): the Flutter Driver screen now parses `insufficient_taxi_wallet_balance` and offers to top up the exact shortfall via `POST /driver/taxi_wallet/topup`, or open the Payments app. In production, prefer the Payments app for funding.
- Configure in `.env`:
  - `PAYMENTS_BASE_URL=http://host.docker.internal:8080` (or your host IP:8080)
  - `PAYMENTS_INTERNAL_SECRET=dev_secret`
  - `PLATFORM_FEE_BPS=1000` (10%) and `FEE_WALLET_PHONE=+963...`
  - `TAXI_WALLET_ENABLED=true` and optionally `TAXI_POOL_WALLET_PHONE=+963...` (pool wallet)
- Ensure Payments API `.env` sets `INTERNAL_API_SECRET=dev_secret` and is running.
- Note: docker-compose maps `host.docker.internal` via `extra_hosts`. On Linux, adjust `PAYMENTS_BASE_URL` to your host gateway if needed.

Production config
- Set `PAYMENTS_BASE_URL` to the Payments API base, `PAYMENTS_INTERNAL_SECRET` to the shared HMAC secret, `FEE_WALLET_PHONE` to the platform fee wallet phone, and (optional) `TAXI_POOL_WALLET_PHONE` for the taxi wallet pool.
- Circuit Breaker (optional): `PAYMENTS_CB_ENABLED=true`, with `PAYMENTS_CB_THRESHOLD` (default 3) and `PAYMENTS_CB_COOLDOWN_SECS` (default 60). When open, internal calls are skipped and counted as `skipped_cb_open`.
- Idempotency: All internal transfers use `X-Idempotency-Key` to avoid double‑charges.
- Secrets & rotation: see `docs/TAXI_SECRET_MANAGEMENT.md` for OTP/SMS, admin token hashes, and Payments HMAC rotation.

Escrow (optional)
- To try prepay from the rider, set `TAXI_ESCROW_WALLET_PHONE` and enable the "Prepay" toggle in the Rider screen; Taxi will attempt an internal transfer from rider → escrow at request time and release to driver on completion. On insufficient rider balance, the API returns `insufficient_rider_balance`.

Third‑Party Partners (APIs)
- Register partner (DEV):
  - `POST /partners/dev/register` with body `{ "name": "Fleet A", "key_id": "fleet_a", "secret": "<hmac_secret>" }`
  - Used only in dev to seed partners. In prod, manage via admin tooling/DB.
- Dispatch to partner:
  - `POST /partners/dispatch` with `{ "ride_id": "<ride_id>", "partner_key_id": "fleet_a", "external_trip_id": "<optional_ext_id>" }`
  - Records dispatch mapping for webhooks.
- Partner webhooks (HMAC headers `X-Internal-Ts`, `X-Internal-Sign`, body JSON):
  - `POST /partners/{partner_key_id}/webhooks/ride_status` with `{ "external_trip_id": "ext-123", "status": "accepted|enroute|completed|canceled", "final_fare_cents": 12345 }`
  - `POST /partners/{partner_key_id}/webhooks/driver_location` with `{ "external_driver_id": "drv-9", "lat": 33.5, "lon": 36.3 }`
  - To sign: use `libs/superapp_shared/superapp_shared/internal_hmac.py::sign_internal_request_headers`.

Maps & Geocoding
- Provider: Google Maps (Directions/ETA, Geocoding). Ohne API‑Key fällt die App in Dev/Test auf einfache Haversine‑Stubs zurück.
- Frontend‑Tiles (TomTom/OSM/MapLibre) sind unabhängig vom Backend‑Provider.
- Endpoints:
  - `GET /maps/reverse?lat=..&lon=..` → `{ display_name, lat, lon, address{} }`
  - `GET /maps/autocomplete?q=...&limit=5` → `{ items: [{ display_name, lat, lon, type, address{} }] }`
  - `GET /maps/traffic/flow_segment` → nicht unterstützt (501) mit Google Maps
- `GET /maps/traffic/incidents` → nicht unterstützt (501) mit Google Maps
- Quote/Request responses optionally include `route_polyline` (only when the provider returns a polyline; Haversine returns `null`). Enable via `MAPS_INCLUDE_POLYLINE=true`.
- Konfiguration:
  - `GOOGLE_MAPS_API_KEY=<required in staging/prod>`
  - `GOOGLE_USE_TRAFFIC=true|false`
  - Timeouts/Backoffs: `MAPS_TIMEOUT_SECS`, `MAPS_MAX_RETRIES`, `MAPS_BACKOFF_SECS`
  - Caches: `MAPS_ROUTE_CACHE_SECS` (Routing), `MAPS_GEOCODER_CACHE_SECS`

Tiles (Flutter)
- Die App kann weiterhin TomTom/OSM/MapLibre Tiles nutzen; das Backend‑Routing läuft über Google Maps.

Config
- Pricing/ETA
  - `AVG_SPEED_KMPH` (default 30)
  - `SURGE_AVAILABLE_THRESHOLD` (default 3)
  - `SURGE_STEP_PER_MISSING` (default 0.25)
 - `SURGE_MAX_MULTIPLIER` (default 2.0)
 - Fraud
  - `FRAUD_RIDER_WINDOW_SECS` (default 60)
  - `FRAUD_RIDER_MAX_REQUESTS` (default 6)
  - `FRAUD_DRIVER_LOC_MAX_AGE_SECS` (default 300)
  - `FRAUD_MAX_ACCEPT_DIST_KM` (default 3.0)
  - `FRAUD_MAX_START_DIST_KM` (default 0.3)
  - `FRAUD_MAX_COMPLETE_DIST_KM` (default 0.5)
- Maps
  - `GOOGLE_MAPS_API_KEY`, `GOOGLE_USE_TRAFFIC`, `MAPS_TIMEOUT_SECS`, `MAPS_MAX_RETRIES`, `MAPS_BACKOFF_SECS`, `MAPS_GEOCODER_CACHE_SECS`
- Auth / OTP
  - `OTP_MODE=redis`, `REDIS_URL=redis://taxi-redis:6379/0`
  - `OTP_SMS_PROVIDER=log|http`, `OTP_SMS_TEMPLATE="Your Taxi verification code is {code}"`
  - HTTP provider: `OTP_SMS_HTTP_URL=https://sms-gateway.internal/...`, optional `OTP_SMS_HTTP_AUTH_TOKEN`

PostGIS/Storage/Analytics
- Database uses the `postgis/postgis` Docker image. The app enables the `postgis` extension automatically.
- Optional MinIO (S3‑compatible) via compose profile `storage`.
- Sentry: enable via `SENTRY_DSN` and optional `SENTRY_TRACES_SAMPLE_RATE`.
- Analytics: simple server‑side logging only; integrate external tooling (e.g., custom dashboards) nach Bedarf.
  - Events: `ride_requested`, `ride_accepted`, `ride_started`, `ride_completed` (with `ride_id`).

Realtime via MQTT (optional)
- Broker: Mosquitto via Compose Profil `realtime` (tcp://localhost:1883)
- Taxi API Vars: `MQTT_BROKER_HOST`, optional `MQTT_BROKER_PORT`, `MQTT_TOPIC_PREFIX` (default `taxi`)
- Topics:
  - `${PREFIX}/driver/{driver_id}/location` → `{driver_id, lat, lon, ts}`
  - `${PREFIX}/ride/{ride_id}/driver_location` → `{ride_id, driver_id, lat, lon, ts}`
