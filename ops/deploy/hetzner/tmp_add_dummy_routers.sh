#!/usr/bin/env bash
set -euo pipefail

# Ensure web network exists
if ! docker network inspect web >/dev/null 2>&1; then
  docker network create web >/dev/null
fi

# Clean previous
(docker rm -f whoami-payments >/dev/null 2>&1) || true
(docker rm -f whoami-taxi >/dev/null 2>&1) || true

# Run whoami services with Traefik labels

docker run -d --name whoami-payments --restart unless-stopped \
  --network web \
  --label 'traefik.enable=true' \
  --label 'traefik.http.routers.payments.rule=Host(`payments.syriasuperapp.com`)' \
  --label 'traefik.http.routers.payments.entrypoints=websecure' \
  --label 'traefik.http.routers.payments.tls.certresolver=letsencrypt' \
  --label 'traefik.http.services.payments.loadbalancer.server.port=80' \
  traefik/whoami:latest


docker run -d --name whoami-taxi --restart unless-stopped \
  --network web \
  --label 'traefik.enable=true' \
  --label 'traefik.http.routers.taxi.rule=Host(`taxi.syriasuperapp.com`)' \
  --label 'traefik.http.routers.taxi.entrypoints=websecure' \
  --label 'traefik.http.routers.taxi.tls.certresolver=letsencrypt' \
  --label 'traefik.http.services.taxi.loadbalancer.server.port=80' \
  traefik/whoami:latest


docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Networks}}\t{{.Status}}'
