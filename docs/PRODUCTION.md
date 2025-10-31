Production Deployment Guide

Overview
- Reverse proxy: Traefik v3 with automatic HTTPS (Let’s Encrypt)
- Services: Docker images per API (payments, taxi, bus, etc.)
- Config: `.env.prod` in `ops/deploy/compose-traefik/`
- Observability: optional via `ops/observability` (Grafana, Prometheus)

Prerequisites
- Docker installed on the host
- A DNS zone for your `BASE_DOMAIN` pointing to the host’s IPv4/IPv6
- Docker Hub (or compatible registry) account for image pushes

Quick Start
1) Generate production env file
   - `make prod-env`
   - Edits: set `ORG`, `BASE_DOMAIN`, `TRAEFIK_ACME_EMAIL`, `GOOGLE_MAPS_API_KEY_TAXI`, and review the generated secrets.
   - CORS: `COMMON_ALLOWED_ORIGINS`, `PAYMENTS_ALLOWED_ORIGINS`, `TAXI_ALLOWED_ORIGINS` are prefilled (adjust as needed).

2) Build and push images
   - `ORG=myorg TAG=$(git rev-parse --short HEAD) make prod-build`
   - Or use GitHub Actions: “Docker Publish” workflow (matrix across all apps). Set `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` secrets.

3) Deploy
   - `make prod-deploy`
   - Traefik serves HTTPS and routes to each service (payments/taxi/etc.).

4) Verify
   - Payments: `https://payments.${BASE_DOMAIN}/health`
   - Taxi: `https://taxi.${BASE_DOMAIN}/health`
   - (others accordingly). Swagger UIs at `/docs`.

Observability (optional)
- Configure `ops/observability/docker-compose.yml` with `BASE_DOMAIN` and `GRAFANA_BASIC_AUTH_USERS` for basic auth.
- Bring up: `./sup obs up` and route `grafana.${BASE_DOMAIN}` via Traefik.

Security Defaults (enforced)
- `ENV=prod`, rate limiter backend = `redis` across services.
- Explicit `ALLOWED_ORIGINS` required (no wildcard) for non‑dev.
- Payments internal API requires HMAC (`INTERNAL_REQUIRE_HMAC=true`).
- Admin endpoints require tokens (prefer SHA‑256 digests via `*_ADMIN_TOKEN_SHA256`).

Secrets & Rotation
- Regenerate `*_JWT_SECRET` and `PAYMENTS_INTERNAL_SECRET` if leaked.
- For Taxi/Payments admin, rotate by adding a new digest alongside the old, then remove the old.

Rollback
- `./sup deploy down` to stop the stack (volumes preserved).
- Pin `TAG` to a previous image digest in `.env.prod` for quick rollback.

Troubleshooting
- Check logs: `make -C ops/deploy/compose-traefik logs`
- DNS/ACME: Ensure `BASE_DOMAIN` A/AAAA records point to this host; watch Traefik logs for cert issuance.

Unified Auth & BFF (recommended)
- RS256 SSO: Payments issues RS256 JWTs and exposes JWKS at `/.well-known/jwks.json`.
  - Ensure all services that verify JWTs set `JWT_JWKS_URL=https://payments.${BASE_DOMAIN}/.well-known/jwks.json` and, optionally, `JWT_ISSUER`/`JWT_AUDIENCE` validation.
- Single entrypoint: Deploy the BFF (`apps/bff`) behind `api.${BASE_DOMAIN}`.
  - Client uses `SUPERAPP_API_BASE=https://api.${BASE_DOMAIN}` and path‑based routing (`/payments`, `/chat`, `/stays`, ...).
  - WebSocket proxy: `wss://api.${BASE_DOMAIN}/{service}/ws?token=...` for Chat.
 - BFF CORS: set `ALLOWED_ORIGINS=https://app.${BASE_DOMAIN},https://ops.${BASE_DOMAIN}` (no wildcard in prod).
 - BFF rate‑limit: optionally set `REDIS_URL` and `RL_LIMIT_PER_MINUTE` for per‑IP limits.

Push Notifications
- Backend: set `FCM_SERVER_KEY` on BFF for real FCM sends.
- iOS: add `GoogleService-Info.plist` to the Flutter iOS target and enable Push Notifications + Background Modes (Remote notifications).
- Android: add `google-services.json` and ensure the Google Services Gradle plugin is applied.

Push Policy (optional)
- Dev push endpoints (`/v1/push/dev/*`) require admin by default.
  - Relax in non‑prod by setting `PUSH_DEV_ALLOW_ALL=true`.
  - Allowlists: `PUSH_DEV_ALLOWED_PHONES`, `PUSH_DEV_ALLOWED_SUBS`.
- Topics: set `PUSH_TOPICS_ALLOW_ALL=false` to require admin/allowlist for subscribe/unsubscribe.
  - Allowlists: `PUSH_TOPICS_ALLOWED_PHONES`, `PUSH_TOPICS_ALLOWED_SUBS`.
