#!/usr/bin/env bash
set -euo pipefail

# Stop and remove all app stacks.
# Usage:
#   bash tools/docker_down_all.sh
#   APPS="payments taxi" bash tools/docker_down_all.sh

APPS=${APPS:-}
if [[ -z "$APPS" ]]; then
  APPS=$(ls -1 apps | tr '\n' ' ')
fi

echo "Stopping apps: $APPS"
for app in $APPS; do
  compose="apps/$app/docker-compose.yml"
  if [[ ! -f "$compose" ]]; then
    echo "[skip] $app has no docker-compose.yml"; continue
  fi
  echo "[down] $app"
  (cd "apps/$app" && docker compose down -v || true)
done

echo "All requested apps stopped."

