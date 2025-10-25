#!/usr/bin/env bash
set -euo pipefail

# Build and push all app images to a Docker registry.
# Usage examples:
#   REGISTRY=docker.io ORG=myorg TAG=latest bash tools/docker_push_all.sh
#   ORG=myorg TAG=$(git rev-parse --short HEAD) bash tools/docker_push_all.sh
#
# Required env:
#   ORG  - your Docker Hub org/user (e.g., myorg)
# Optional env:
#   REGISTRY - registry hostname (default: docker.io)
#   TAG      - image tag (default: latest)
#   APPS     - space-separated app names to build (default: detect from apps/*)

REGISTRY=${REGISTRY:-docker.io}
TAG=${TAG:-latest}
APPS=${APPS:-}

if [[ -z "${ORG:-}" ]]; then
  echo "ORG env var is required (Docker Hub org/username)." >&2
  exit 1
fi

if [[ -z "$APPS" ]]; then
  APPS=$(ls -1 apps | tr '\n' ' ')
fi

echo "Registry: $REGISTRY"
echo "Org:      $ORG"
echo "Tag:      $TAG"
echo "Apps:     $APPS"

for app in $APPS; do
  dir="apps/$app"
  if [[ ! -f "$dir/Dockerfile" ]]; then
    echo "[skip] $app has no Dockerfile"; continue
  fi
  image="$REGISTRY/$ORG/syria-$app:$TAG"
  echo "[build] $image with -f $dir/Dockerfile (context repo root)"
  docker build -t "$image" -f "$dir/Dockerfile" .
  echo "[push]  $image"
  docker push "$image"
done

echo "Done."
