Jobs (Job Board) API — FastAPI service

Overview
- Minimal job board API for seekers and employers.
- Mirrors the structure of other services in this repo (auth, models, routers, Docker, env).

Quick start
1) Copy env and set variables: `cp .env.example .env`
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`

Defaults
- Port: 8087
- DB (in Docker): `postgresql+psycopg2://postgres:postgres@db:5432/jobs`
- DB (local default in config): `postgresql+psycopg2://postgres:postgres@localhost:5440/jobs`

API
- `POST /auth/request_otp` — request OTP (dev: always returns success, OTP=123456)
- `POST /auth/verify_otp` — verify, creates user if needed, returns JWT
- `GET  /health` — health check
- Employer
  - `POST /employer/company` — create company for current user (becomes employer)
  - `GET  /employer/company` — get my company
  - `POST /employer/jobs` — create job
  - `GET  /employer/jobs` — list my jobs
  - `GET  /employer/jobs/{job_id}/applications` — list applications for a job I own
  - `PATCH /employer/jobs/{job_id}` — update job (title, description, location, salary_cents, status)
  - `PATCH /employer/applications/{application_id}` — update application status (applied|reviewed|accepted|rejected)
- Jobs
  - `GET  /jobs` — list open jobs (filters: `q`, `location`, `min_salary`, `max_salary`, `company_id`, `category`, `employment_type`, `remote`, `tags`, `tags_mode=any|all`, `limit`, `offset`; response includes `total`, `next_offset`)
  - `GET  /jobs/{job_id}` — job details
  - `POST /jobs/{job_id}/apply` — apply as seeker
  - `POST /jobs/{job_id}/favorite` — add to favorites
  - `DELETE /jobs/{job_id}/favorite` — remove from favorites
  - `GET  /jobs/favorites` — list my favorited jobs
- Applications
  - `GET  /applications` — list my applications (seeker)
  - `POST /applications/{application_id}/withdraw` — withdraw my application (if not finalized)

Fields
- Job
  - `category` (string, optional)
  - `employment_type` (enum: `full_time|part_time|contract|internship|temporary`, optional)
  - `is_remote` (boolean, default `false`)
  - `tags` (string[])

Notifications
- Configure via env:
  - `NOTIFY_MODE=log|redis` (default `log`)
  - `NOTIFY_REDIS_CHANNEL` (default `jobs.events`)
- Emitted events (payloads include IDs):
  - `job.created`, `job.updated`
  - `application.created`, `application.status_changed`, `application.withdrawn`

Webhooks
- Enable via env:
  - `WEBHOOK_ENABLED=true|false` (default `false`)
  - `WEBHOOK_TIMEOUT_SECS` (default `3`)
- Manage endpoints:
  - `GET  /webhooks/endpoints` — list endpoints
  - `POST /webhooks/endpoints` — body `{ url, secret }`
  - `DELETE /webhooks/endpoints/{id}` — remove endpoint
  - `POST /webhooks/test` — emit `webhook.test` to all endpoints
- Delivery details:
  - Method: `POST` JSON body of event payload
  - Headers: `X-Webhook-Event`, `X-Webhook-Ts`, `X-Webhook-Sign`
  - Signature: `hex(hmac_sha256(secret, ts + event + body))`

Notes
- Rate limiting supported (memory or Redis) via `RATE_LIMIT_BACKEND`.
- Schema is created automatically on startup (SQLAlchemy `create_all`).

Payments Integration (optional)
- Configure in `.env` or docker compose override:
  - `PAYMENTS_BASE_URL` (e.g., `http://host.docker.internal:8080`)
  - `PAYMENTS_INTERNAL_SECRET`
  - `PAYMENTS_WEBHOOK_SECRET`
- Register a webhook in Payments pointing to Jobs:
  - `POST /webhooks/endpoints` with `url=http://host.docker.internal:8087/payments/webhooks` and your chosen `secret`.
- Webhook details:
  - Endpoint: `POST /payments/webhooks`
  - Headers: `X-Webhook-Event`, `X-Webhook-Ts`, `X-Webhook-Sign`
  - Signature: `hex(hmac_sha256(secret, ts + event + body))`
- Jobs currently only acknowledges events (no state changes tied to payments).

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
curl -s -X POST http://localhost:8087/payments/webhooks \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Event: requests.accept" \
  -H "X-Webhook-Ts: $ts" \
  -H "X-Webhook-Sign: $sig" \
  -d "$body" | jq .
```
