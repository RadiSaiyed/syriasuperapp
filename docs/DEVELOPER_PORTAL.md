Developer Portal (MVP)

Purpose
- Define safe, auditable actions ("tools") that the AI Assistant and partner mini‑apps can call.
- Provide schemas, auth model, and example requests.

Auth
- All internal tool calls are signed with HMAC headers and require a valid user JWT.
- Headers:
  - `X-Internal-Ts`: Unix timestamp (seconds)
  - `X-Internal-Sign`: `sha256(secret, ts + compact_json(payload))`
  - Optional: `X-Idempotency-Key` for safe retries
- Shared secret: `INTERNAL_API_SECRET` across AI Gateway and target service (per‑env).

Available Tools (as of now)
- Utilities: `POST /internal/tools/pay_bill`
  - Payload: `{ user_id: string, bill_id: string }`
  - Effect: Creates invoice/payment request if configured; returns bill state
- Parking On‑Street: `POST /internal/tools/start_parking`
  - Payload: `{ user_id: string, zone_id: string, plate: string, minutes?: number }`
  - Effect: Starts a session; returns session id and meta
- CarMarket: `POST /internal/tools/create_listing`
  - Payload: `{ user_id, title, make, model, year, price_cents, ... }`
  - Effect: Creates a listing; returns listing
- Chat: `POST /internal/tools/system_notify`
  - Payload: `{ user_id: string, text: string }`
  - Effect: Delivers a system message to user’s inbox

AI Gateway Endpoints
- `/v1/chat` — Assistant; can return `tool_calls`; with `confirm` + `selected_tool` executes
- `/v1/tools/execute` — Direct tool execution (after user confirmation)
- `/v1/embed|rank|moderate` — AI primitives
- `/v1/store/upsert|search` — RAG store
- `/v1/ocr` — OCR stub
- `/v1/risk` — Compute a risk score from features
- `/v1/membership/status` — Membership tier + benefits (MVP)
- `/v1/missions` — Static missions (MVP)
- `/v1/digest` — Send a weekly digest message via Chat

Client Examples
- See demos/ai_gateway_ui/index.html for Assistant + tool confirmation via browser.
- Super‑App Flutter has an “AI Assistant” screen with the same flow.

Guidelines
- Keep tools idempotent; require `X-Idempotency-Key` for write‑paths.
- Tools must enforce user matching: the JWT subject must equal `user_id`.
- All tool executions must be auditable (consider appending to a shared audit in future).

