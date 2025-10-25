One‑Person Ops — Super‑App

Purpose
- Operate the monorepo efficiently as a single owner by standardizing common actions, automation, and a clear daily/weekly rhythm.

Key Tools
- CLI: `sup` (wrapper for docker, deploy, secrets, health)
- Health: `tools/health_check.sh`
- Secrets: `ops/secrets/superapp.secrets.env`, `tools/sync_secrets.py`
- Deploy: `ops/deploy/compose-traefik/` (Traefik + services)
- Observability: `ops/observability/` (Prometheus, Grafana, Alertmanager)
- Runbooks: `ops/runbooks/`

Quick Start
- Bootstrap core stack (secrets → envs, observability, Payments):
  - `./sup bootstrap`
- Open URLs:
  - Payments API: `http://localhost:8080/docs`
  - Grafana: `http://localhost:3000`
  - Prometheus: `http://localhost:9090`

Common Commands
- Apps lifecycle
  - `./sup apps` — list compose‑enabled apps
  - `./sup up payments` — start db/redis/api for an app
  - `./sup logs taxi` — follow logs
  - `./sup down food` — stop the app
  - Presets: `./sup stack list`, `./sup stack up core` (obs+payments), `./sup stack down core`, `./sup stack up all`
  - Operators: `./sup op up food_operator`, `./sup op logs food_operator`, `./sup op down food_operator`
  - Combined preset: `./sup stack up food-operator` (starts apps/food + operators/food_operator)
- Observability
  - `./sup obs up` — start Prometheus + Grafana + Alertmanager
  - `./sup obs logs`
- Health
  - `./sup doctor` — run backend tests per app on ephemeral Postgres/Redis
  - Make targets: `make health` (repo tests), `make deploy-health APP=payments` or `make deploy-health STACK=core`
- Deploy (Traefik compose)
  - Prepare `ops/deploy/compose-traefik/.env.prod` (copy from `.env.prod.example`)
  - `./sup deploy up` — start/refresh the production stack on the target host
  - `./sup deploy restart` — quick restart (no data loss)
- Backups
  - `./sup backup payments --out ./backups` — on‑demand dump
  - Seeding (Food): `./sup seed food` oder kombiniertes Stack‑Seeding: `./sup seed food-operator`
  - Seeding (Commerce): `./sup seed commerce` | Payments Webhooks Pipeline (merchant test): `./sup seed commerce-webhooks`
  - Seeding (Doctors): `./sup seed doctors` | Webhooks‑Flow (Payments→Doctors): `./sup seed doctors-webhooks` | Voller Payments‑Flow (PR annehmen): `./sup seed doctors-payments`
  - Seeding (Taxi): `./sup seed taxi` (benötigt Payments)
  - Seeding (Bus): `./sup seed bus`
  - Seeding (Utilities): `./sup seed utilities`
  - Seeding (Freight): `./sup seed freight`
  - Seeding (Car Market): `./sup seed carmarket`
  - Seeding (Chat): `./sup seed chat` (zwei Nutzer + Nachrichten)
  - Seeding (Stays): `./sup seed stays` (optional `--db postgresql+psycopg2://...`)

Daily Flow (10–15 minutes)
- Check alerts (Slack/Email via Alertmanager)
- Scan Grafana overview dashboard (error rate, latency, RPS)
- `./sup doctor` on the repo (verifies tests across services)
- Review GitHub Actions (CI, smoke, nightly)

Weekly Flow
- Run `tools/prod_audit.py` — ensure hardening stays intact
- Rotate a subset of secrets (see `ops/secrets/ROTATION.md`)
- Review logs for outliers; update dashboards/alerts as needed
 - CI: Weekly prod audit job runs automatically (see `.github/workflows/weekly-prod-audit.yml`)

Incident Quick Actions
- Open runbook: `./sup runbook payments`
- Raise limits temporarily via Admin API (document and revert)
- Requeue failed webhooks (Payments scripts)
- Communicate via Alertmanager routing, keep a brief timeline

Notes
- Keep real secrets out of Git; use `.env.example` + secret managers for prod.
- The repo already ships with smoke and security checks under `.github/workflows/`.
- The Ops Admin service at `apps/ops_admin` provides a lightweight RPS/error/alerts view.
- Optional ChatOps: see `apps/ops_admin/README.md` to enable Slack slash commands and GitHub runner based restarts.
  - Commands: `/superapp status`, `/superapp alerts`, `/superapp restart payments`, `/superapp restart stack core|food|commerce|taxi|doctors|bus|freight|utilities|automarket|chat|stays|jobs`
  - Access control: `CHATOPS_ALLOWED_USERS`, `CHATOPS_ALLOWED_CHANNELS`
