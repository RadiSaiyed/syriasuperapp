AI Gateway (Superapp)

Purpose
- Provide a single, secure interface for AI features across services: chat, embeddings, ranking, moderation, and (future) OCR.
- Centralize provider selection, guardrails, telemetry, and cost controls.

Endpoints (MVP)
- POST `/v1/chat` — basic assistant stub (echo/provider-backed).
- POST `/v1/embed` — text embeddings (provider-backed or local fallback).
- POST `/v1/rank` — scores items vs. a query using cosine similarity.
- POST `/v1/moderate` — simple content moderation (keyword-based stub).
- POST `/v1/store/upsert` — upsert documents into in-memory RAG store.
- POST `/v1/store/search` — semantic search over a collection via embeddings.
- POST `/v1/ocr` — MVP OCR stub (requires `text_hint`; image OCR disabled in MVP).

Notes
- This is a minimal skeleton intended for quick integration and iteration.
- Provider calls are abstracted and optional; without configuration, safe local fallbacks apply.

Secure Tool Execution
- POST `/v1/tools/execute` executes allowed tools after client confirmation.
- Currently supports `pay_bill` by calling Utilities internal endpoint with HMAC + user Authorization passthrough.
- Env:
  - `UTILITIES_BASE_URL` (default `http://localhost:8084`)
  - `INTERNAL_API_SECRET` shared with Utilities for HMAC
  - `PARKING_ONSTREET_BASE_URL` (default `http://localhost:8096`)
  - `CARMARKET_BASE_URL` (default `http://localhost:8086`)

Supported tools
- `pay_bill` → Utilities `/internal/tools/pay_bill`
- `start_parking_session` → Parking On‑Street `/internal/tools/start_parking`
- `create_car_listing` → CarMarket `/internal/tools/create_listing`

Chat Confirmation Flow
- `/v1/chat` accepts `confirm` and `selected_tool`.
- If `confirm: true` and `selected_tool` includes `{ tool, args, user_id }`, the gateway executes the tool and returns `executed_tool` + `execution_result` in the response.

Run
- `make run` to start a dev server on `:8099`.
