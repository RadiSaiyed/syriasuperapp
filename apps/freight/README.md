Freight Service

FastAPI service for freight matching (shippers post loads, carriers bid/accept and deliver), with chat, tracking and payments.

Run locally
1) Copy `.env.example` to `.env` and adjust.
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8085/docs

Tests
- Start DB first: `docker compose up -d db redis`
- From repo root: `make freight-tests`
- Or directly: `PYTHONPATH=apps/freight DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5438/freight pytest -q apps/freight/tests`

Auth (DEV)
- OTP is stubbed as 123456
- Use phone `+963xxxxxxxxx`

Features
- Shipper posts loads (origin, destination, weight, price)
- Carrier applies (dev approval), browse/search available loads with filters
- Bids: carriers submit price bids; shipper accepts a bid to assign load
- Status: accept → pickup → in_transit → deliver (+ POD URL)
- Tracking: carrier updates current lat/lon; load details expose POD and payment id
- Chat: shipper ↔ assigned carrier per load
- Payments (DEV): on deliver, create internal payment request (shipper → carrier); optional platform fee

API (selection)
- Auth: `POST /auth/request_otp`, `POST /auth/verify_otp`
- Shipper: `POST /shipper/loads`, `GET /shipper/loads`
- Carrier: `POST /carrier/apply`, `GET /carrier/loads/available?origin=&destination=&min_weight=&max_weight=`, `PUT /carrier/location`
- Loads: `POST /loads/{id}/accept|pickup|in_transit|deliver`, `GET /loads/{id}`, `POST /loads/{id}/pod?url=`
- Bids: `POST /bids/load/{load_id}`, `GET /bids` (carrier), `GET /bids/load/{load_id}` (shipper), `POST /bids/{bid_id}/accept|reject`
- Chats: `GET/POST /chats/load/{load_id}`
