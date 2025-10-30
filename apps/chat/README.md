Chat API — FastAPI service (Threema‑like, server stores only ciphertext)

Overview
- Minimal secure messaging backend: users/devices with public keys, contacts, conversations, and messages.
- End‑to‑end encryption is client‑side; server stores only opaque `ciphertext` payloads and metadata.
- Real‑time delivery via WebSocket; polling inbox also available.

Quick start
1) Copy env and set variables: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`

Defaults
- Port: 8091
- DB (in Docker): `postgresql+psycopg2://postgres:postgres@db:5432/chat`
- DB (local default in config): `postgresql+psycopg2://postgres:postgres@localhost:5444/chat`

API (MVP)
- Auth
  - `POST /auth/request_otp` — request OTP (dev: 123456)
  - `POST /auth/verify_otp` — create user, return JWT
- Devices & Keys
  - `POST /keys/publish` — register device + public key
  - `GET  /keys/{user_id}` — get user devices public keys
  - `GET  /keys/me` — list my devices
  - `PUT  /keys/devices/{device_id}` — update device (`device_name`, `push_token`)
  - `DELETE /keys/devices/{device_id}` — remove device (logout)
- Contacts
  - `POST /contacts/add` — add contact by phone
  - `GET  /contacts` — list contacts
- Conversations & Messages
  - `POST /messages/send` — send ciphertext to recipient (creates conversation if needed)
  - `GET  /messages/inbox` — fetch pending messages for me (optionally ack delivered)
  - `POST /messages/{id}/ack_delivered` — mark delivered
  - `POST /messages/{id}/ack_read` — mark read
  - `GET  /messages/history?conversation_id=...&before=...&limit=...` — paged history
  - `GET  /messages/conversations` — recent conversations
  - `GET  /messages/conversations_summary` — conversations with `unread_count`
  - `GET  /messages/search?conversation_id=...&sender_device_id=...&has_attachments=...&since=...&until=...` — metadata filters
  - `POST /messages/typing` — typing indicator (WS broadcast to peer)
  - Reactions: `POST /messages/{id}/reactions`, `GET /messages/{id}/reactions`, `DELETE /messages/{id}/reactions?emoji=...`
  - Attachments: `POST /messages/{id}/attachments` (fields include `content_type`, `filename`, encrypted `ciphertext_b64`), `GET /messages/{id}/attachments`
- WebSocket
  - `GET  /ws` — upgrade; server delivers messages in real‑time to connected recipients
- Presence
  - `GET  /presence/{user_id}` — `{ online, last_seen }`
  - `POST /presence/ping` — update own `last_seen`
- Blocks
  - `POST /blocks?blocked_user_id=...`, `DELETE /blocks?blocked_user_id=...`, `GET /blocks`
 - Delivery Receipts per Device
   - `POST /messages/{id}/ack_delivered_device?device_id=...`, `POST /messages/{id}/ack_read_device?device_id=...`
   - `GET  /messages/{id}/receipts` — list per‑device receipts

Notes
- Server never handles plaintext; clients should encrypt message content to recipient device keys.
- For MVP tests, ciphertext can be any opaque string.
- Events & Webhooks: internal events (no ciphertext) for push/orchestration: `chat.message.created`, `chat.message.delivered`, `chat.message.read`, `chat.attachment.added`.
 - Configure via env: `NOTIFY_MODE=log|redis`, `NOTIFY_REDIS_CHANNEL=chat.events`, `WEBHOOK_ENABLED`, `WEBHOOK_TIMEOUT_SECS`, `PUSH_PROVIDER=none|fcm`, `FCM_SERVER_KEY`, `CHAT_USER_MSGS_PER_MINUTE`, `CHAT_GROUP_MSGS_PER_MINUTE`. Optional: `CHAT_WEBHOOK_ENDPOINTS_JSON`.
 - Quotas: `CHAT_USER_MSGS_PER_MINUTE` (default 60), `CHAT_GROUP_MSGS_PER_MINUTE` (default 120)
   - `POST /messages/export?conversation_id=...` — JSON Backup (ciphertext + metadata)
   - `POST /messages/import?conversation_id=...` — Import as local history (no delivery)
 - Groups
  - `POST /groups` — create, optional `member_user_ids`
  - `PATCH /groups/{id}` — rename (owner)
  - `POST /groups/{id}/members` — add (owner/admin)
  - `DELETE /groups/{id}/members/{user_id}` — remove (owner/admin)
  - `POST /groups/{id}/leave` — leave group
  - `POST /messages/send_group` — send group message
  - Avatars: `POST /groups/{id}/avatar/url`, `POST /groups/{id}/avatar/upload`, `GET /groups/{id}/avatar`
  - Roles: `POST /groups/{id}/members/{user_id}/role` (owner), `POST /groups/{id}/transfer_ownership`
  - Archive: `POST /groups/{id}/archive?archived=true|false`
  - Moderation: `DELETE /messages/{message_id}` — delete a group message (owner/admin)
  - Invites: `POST /groups/{id}/invites` (create), `GET /groups/invites/{code}` (preview), `POST /groups/invites/{code}/accept` (join)
 
E2E Media Keys
- Clients encrypt attachments (e.g., AES‑GCM/XChaCha20‑Poly1305) on the client; the server stores only ciphertext or blobs.
- Keys/nonce/metadata stay client‑side or as an encrypted “envelope” in the payload; the server does not interpret this data.

Payments Integration (optional)
- Configure in `.env` or docker compose override:
  - `PAYMENTS_BASE_URL` (e.g., `http://host.docker.internal:8080`)
  - `PAYMENTS_INTERNAL_SECRET`
  - `PAYMENTS_WEBHOOK_SECRET`
- Register a webhook in Payments pointing to Chat:
  - `POST /webhooks/endpoints` with `url=http://host.docker.internal:8091/payments/webhooks` and your chosen `secret`.
- Webhook details:
  - Endpoint: `POST /payments/webhooks`
  - Headers: `X-Webhook-Event`, `X-Webhook-Ts`, `X-Webhook-Sign`
  - Signature: `hex(hmac_sha256(secret, ts + event + body))`
- Chat currently acknowledges events only (no state changes).

Simulate a signed webhook (dev)
```
ts=$(date +%s)
body='{"type":"requests.accept","data":{"id":"PR_ID","transfer_id":"TR_ID"}}'
sig=$(python3 - <<'PY'
import hmac,hashlib,os
secret=os.environ.get('PAYMENTS_WEBHOOK_SECRET','demo_secret')
ts=os.environ.get('TS','%s')
event='requests.accept'
body=os.environ.get('BODY','%s')
print(hmac.new(secret.encode(),(ts+event).encode()+body.encode(),hashlib.sha256).hexdigest())
PY
)
curl -s -X POST http://localhost:8091/payments/webhooks \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Event: requests.accept" \
  -H "X-Webhook-Ts: $ts" \
  -H "X-Webhook-Sign: $sig" \
  -d "$body" | jq .
```
