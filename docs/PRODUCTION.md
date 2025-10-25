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
