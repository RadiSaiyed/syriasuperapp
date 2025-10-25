#!/usr/bin/env bash
set -euo pipefail

# Start all app stacks on Docker Desktop (or any local Docker).
# Usage:
#   bash tools/docker_up_all.sh              # all apps
#   APPS="payments taxi food" bash tools/docker_up_all.sh  # subset

APPS=${APPS:-}
if [[ -z "$APPS" ]]; then
  APPS=$(ls -1 apps | tr '\n' ' ')
fi

echo "Starting apps: $APPS"

for app in $APPS; do
  compose="apps/$app/docker-compose.yml"
  if [[ ! -f "$compose" ]]; then
    echo "[skip] $app has no docker-compose.yml"; continue
  fi
  # ensure .env exists if .env.example provided
  if [[ -f "apps/$app/.env.example" && ! -f "apps/$app/.env" ]]; then
    cp "apps/$app/.env.example" "apps/$app/.env"
    echo "[env] created apps/$app/.env from .env.example"
  fi
  echo "[up] $app"
  (cd "apps/$app" && docker compose up -d db redis >/dev/null 2>&1 || true)
  (cd "apps/$app" && docker compose up -d api)
done

echo "All requested apps started. Open Docker Desktop to view containers."
