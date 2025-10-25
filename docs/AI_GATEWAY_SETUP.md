AI Gateway & SDK — Setup Guide

Components
- Service: `apps/ai_gateway` (FastAPI). Endpoints under `/v1/*`.
- SDK: `libs/superapp_ai` providing `AIGatewayClient` for other services.

Local Run
- `make -C apps/ai_gateway run` to start on `http://localhost:8099`.

Environment
- Service env:
  - `AI_PROVIDER` (default: `local`).
  - `AI_PROVIDER_BASE_URL`, `AI_PROVIDER_API_KEY` if proxying to external.
  - CORS via `ALLOWED_ORIGINS`.
- Client env (consumers):
  - `AI_GATEWAY_BASE_URL` (default: `http://localhost:8099`).
  - `AI_GATEWAY_API_KEY` (optional).

Docker Images
- For each consumer service image, copy the SDK into the image (see CarMarket Dockerfile):
  - `COPY libs/superapp_ai/superapp_ai /app/superapp_ai`
- The AI Gateway image already includes `superapp_shared`.

CarMarket Example
- New endpoint: `GET /listings/{listing_id}/recommendations` using AI ranking over title/make/model/city.
- Falls back gracefully if the gateway is unavailable.

Docs Ingestion (SuperSearch)
- Run: `AI_GATEWAY_BASE_URL=http://localhost:8099 python tools/ai_ingest_docs.py`
- Query via Utilities: `GET /help/search?q=your+query` (Utilities API)

Utilities OCR (MVP)
- Endpoint: `POST /ocr/invoice` with `{ "text_hint": "..." }` or `image_url` (image OCR not enabled in MVP).
- Returns normalized fields: `amount`, `invoice_number`, `date`, `due_date` when detected.

Assistant Tool-Calls (MVP)
- `/v1/chat` now returns optional `tool_calls` suggestions for intents like `pay_bill`, `start_parking_session`, `create_car_listing` (no side effects yet).
- Clients should request user confirmation and then call the appropriate service endpoints.

Tool Execution (Secure)
- Execute tool: `POST /v1/tools/execute` with body `{ "tool": "pay_bill", "args": {"bill_id": "..."}, "user_id": "..." }`.
- Include the user's `Authorization: Bearer ...` header; the gateway forwards it to Utilities and signs the request with HMAC.
- Configure secrets:
  - On AI Gateway: `INTERNAL_API_SECRET` and `UTILITIES_BASE_URL`.
  - On Utilities: `INTERNAL_API_SECRET` (same value), validates HMAC and user token, and performs the action.

Additional tools
- Start parking: `{ "tool": "start_parking_session", "args": {"zone_id": "...", "plate": "...", "minutes": 30}, "user_id": "..." }`
  - Gateway env: `PARKING_ONSTREET_BASE_URL`
  - Parking service exposes `/internal/tools/start_parking` (HMAC + user token)
- Create car listing: `{ "tool": "create_car_listing", "args": {"title": "...", "make": "...", "model": "...", "year": 2010, "price_cents": 3000000}, "user_id": "..." }`
  - Gateway env: `CARMARKET_BASE_URL`
  - CarMarket exposes `/internal/tools/create_listing` (HMAC + user token)

Risk, Membership, Missions, Digest
- Risk scoring: `POST /v1/risk` with features `{ signals, flags, kyc_level, recency_days }` → `{ score, reasons, recommended }` (MVP heuristic)
- Membership: `GET /v1/membership/status?user_id=...&phone=...` → `{ tier, benefits }` (env allowlist via `SUPERPASS_PHONES`)
- Missions: `GET /v1/missions?user_id=...` → static list of missions for MVP
- Digest: `POST /v1/digest` with `{ user_id, items: [{title, detail?, link?}, ...] }` → delivers a Chat system message

Chat Confirmation Execution
- Instead of calling `/v1/tools/execute` directly, clients may call `/v1/chat` with:
  - `confirm: true`, and
  - `selected_tool`: `{ "tool": "pay_bill", "args": {"bill_id": "..."}, "user_id": "..." }`
- Include `Authorization: Bearer <user_jwt>`; the gateway executes and returns `executed_tool` + `execution_result`.

Extending
- Add OCR at `/v1/ocr` and wire a Utilities router for OCR autofill.
- Add tools to `/v1/chat` and a secured internal Tool Registry.
