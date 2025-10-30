#!/usr/bin/env bash
set -euo pipefail

# Quick deploy for the Super‑App Traefik stack (payments + core apps).
# Builds and pushes all images, then brings up the compose bundle.
#
# Usage:
#   ORG=<dockerhub_user> [TAG=$(git rev-parse --short HEAD)] [REGISTRY=docker.io] \
#     bash tools/deploy_quick.sh

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEPLOY_DIR="$ROOT/ops/deploy/compose-traefik"

ORG=${ORG:-}
TAG=${TAG:-$(git -C "$ROOT" rev-parse --short HEAD)}
REGISTRY=${REGISTRY:-docker.io}

need() { command -v "$1" >/dev/null 2>&1 || { echo "[error] missing: $1" >&2; exit 2; }; }
need docker
need bash

echo "[step] Ensuring deploy env exists"
if [[ ! -f "$DEPLOY_DIR/.env.prod" ]]; then
  echo "[hint] No .env.prod found; generating a template with strong secrets"
  (cd "$ROOT" && make prod-env)
  echo "[info] Edit $DEPLOY_DIR/.env.prod (ORG, BASE_DOMAIN, TRAEFIK_ACME_EMAIL, CORS, secrets) before retrying." >&2
  exit 1
fi

echo "[step] Loading deploy env (.env.prod)"
set -a
source "$DEPLOY_DIR/.env.prod"
set +a

if [[ -z "$ORG" ]]; then ORG=${ORG:-}; fi
if [[ -z "$ORG" ]]; then
  echo "[error] ORG not set. Set ORG=<dockerhub_user> env or in .env.prod" >&2
  exit 2
fi

TAG=${TAG:-latest}
REGISTRY=${REGISTRY:-docker.io}

echo "[step] Docker login check (if needed)"
if ! docker info >/dev/null 2>&1; then
  echo "[error] Docker daemon not available" >&2
  exit 2
fi
echo "[info] Using REGISTRY=$REGISTRY ORG=$ORG TAG=$TAG"

echo "[step] Build & push images"
REGISTRY="$REGISTRY" ORG="$ORG" TAG="$TAG" bash "$ROOT/tools/docker_push_all.sh"

echo "[step] Deploy compose bundle (Traefik + services)"
make -C "$DEPLOY_DIR" up

echo "[step] Health checks"
make -C "$ROOT" deploy-health STACK=core || true

echo "[done] Deployed. Verify endpoints (replace BASE_DOMAIN if needed):"
echo "  - https://payments.${BASE_DOMAIN:-example.com}/health"
echo "  - https://taxi.${BASE_DOMAIN:-example.com}/health"

