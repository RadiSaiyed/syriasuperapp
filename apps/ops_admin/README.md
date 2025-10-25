Ops Admin (Read-only)

Kleine FastAPI-App, die Kernzahlen der Super‑App aggregiert und aus Prometheus zusammenzieht.

Run (dev)
1) Optional: Start Prometheus+Grafana: `docker compose -f ops/observability/docker-compose.yml up -d`
2) `cd apps/ops_admin && uvicorn app.main:app --reload --port 8099`
3) Open: http://localhost:8099 (JSON summary unter `/summary`)

Env
- `PROMETHEUS_BASE_URL` (default `http://localhost:9090`)
- Basic Auth (optional): set `OPS_ADMIN_BASIC_USER` and `OPS_ADMIN_BASIC_PASS`

Slack ChatOps (optional)
- Slash Command endpoint: `POST /slack/command`
- Env:
  - `SLACK_SIGNING_SECRET` — from your Slack app
  - `CHATOPS_GH_REPO` — `owner/repo` for this repository
  - `CHATOPS_GH_TOKEN` — GitHub PAT with `repo` scope to send repository_dispatch
  - `CHATOPS_ALLOWED_USERS` — optional comma-separated list of allowed Slack `user_id` or `user_name`
  - `CHATOPS_ALLOWED_CHANNELS` — optional comma-separated list of allowed Slack channel IDs
- Commands:
  - `status` — error rate and RPS by service (Prometheus)
  - `alerts` — recent alerts (via `/alert` webhook intake)
  - `restart <app>` — triggers GitHub ChatOps workflow (requires self‑hosted runner)
  - `restart stack <name>` — restarts a preset group; supported names: `core`, `food`, `commerce`, `taxi`, `doctors`, `bus`, `freight`, `utilities`, `automarket`, `chat`, `stays`, `jobs`
- Setup
  1) Create Slack app → Slash Commands → `/superapp` to `https://<ops-admin-host>/slack/command`.
  2) Put signing secret and GH env vars into Ops Admin env.
  3) Add a self‑hosted runner on the server and enable Docker.
  4) Use the included `.github/workflows/chatops-exec.yml` for restarts.
