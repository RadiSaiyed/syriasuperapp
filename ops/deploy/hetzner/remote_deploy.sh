#!/usr/bin/env bash
set -euo pipefail

# Remote deploy helper for ops/deploy/compose-traefik via SSH.
# - Uses env from repo .env through ops/deploy/hetzner/env.sh
# - Rsyncs the compose bundle to the remote host and runs docker compose up -d
#
# Usage:
#   ops/deploy/hetzner/remote_deploy.sh [-e PATH_TO_ENV] [-h HOST] [-u USER] [-d REMOTE_DIR] [--install-docker] [--no-pull]
#
# Defaults:
#   ENV_FILE: repo .env
#   HOST: $HETZNER_IPV4 from env
#   USER: $HETZNER_SSH_USER from env or "root"
#   REMOTE_DIR: /opt/superapp-deploy

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
HOST=""
USER_NAME="${HETZNER_SSH_USER:-root}"
REMOTE_DIR="/opt/superapp-deploy"
INSTALL_DOCKER=false
NO_PULL=false
SERVICES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--env)
      ENV_FILE="$2"; shift 2 ;;
    -h|--host)
      HOST="$2"; shift 2 ;;
    -u|--user)
      USER_NAME="$2"; shift 2 ;;
    -d|--dir)
      REMOTE_DIR="$2"; shift 2 ;;
    --install-docker)
      INSTALL_DOCKER=true; shift ;;
    --no-pull)
      NO_PULL=true; shift ;;
    --services)
      SERVICES="$2"; shift 2 ;;
    -h?|--help)
      echo "Usage: $0 [-e ENV] [-h HOST] [-u USER] [-d REMOTE_DIR] [--install-docker] [--no-pull]"; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Load Hetzner env, prepare SSH key, expose $HETZNER_SSH_OPTS and $HETZNER_IPV4
source "$SCRIPT_DIR/env.sh" "$ENV_FILE"

HOST="${HOST:-${HETZNER_IPV4:-}}"
if [[ -z "$HOST" ]]; then
  echo "[deploy] No host provided and HETZNER_IPV4 not set in env" >&2
  exit 1
fi

SSH_OPTS=( -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new )
if [[ -n "${HETZNER_SSH_PRIVATE_KEY_FILE:-}" ]]; then
  SSH_OPTS+=( -i "$HETZNER_SSH_PRIVATE_KEY_FILE" )
fi

REMOTE="$USER_NAME@$HOST"

echo "[deploy] Target: $REMOTE"
echo "[deploy] Remote dir: $REMOTE_DIR"

ssh "${SSH_OPTS[@]}" "$REMOTE" 'echo "[remote] Connected: $(hostname)"'

# Ensure remote directory exists
ssh "${SSH_OPTS[@]}" "$REMOTE" "sudo mkdir -p '$REMOTE_DIR' && sudo chown -R \"$USER_NAME\" '$REMOTE_DIR'"

# Rsync compose bundle
echo "[deploy] Syncing compose bundle → $REMOTE:$REMOTE_DIR"
# Build rsync SSH transport with same options/identity as our ssh calls
RSYNC_SSH="ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
if [[ -n "${HETZNER_SSH_PRIVATE_KEY_FILE:-}" ]]; then
  RSYNC_SSH+=" -i \"$HETZNER_SSH_PRIVATE_KEY_FILE\""
fi
if rsync -az --delete -e "$RSYNC_SSH" \
  --exclude '*.example' \
  --exclude '.DS_Store' \
  "$ROOT_DIR/ops/deploy/compose-traefik/" \
  "$REMOTE:$REMOTE_DIR/"; then
  :
else
  echo "[deploy] rsync failed or unavailable. Falling back to tar over SSH…"
  # Package the contents of compose-traefik (not the parent dir) so files land directly in REMOTE_DIR
  tar -C "$ROOT_DIR/ops/deploy/compose-traefik" -czf - . | \
    ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p '$REMOTE_DIR' && tar -xzf - -C '$REMOTE_DIR'"
fi

# Verify required files present remotely
ssh "${SSH_OPTS[@]}" "$REMOTE" "test -f '$REMOTE_DIR/docker-compose.yml' && test -f '$REMOTE_DIR/.env.prod' || { echo '[remote] Missing docker-compose.yml or .env.prod in remote dir' >&2; exit 1; }"

# Optionally install Docker if missing
if $INSTALL_DOCKER; then
  echo "[deploy] Ensuring Docker is installed (remote)"
  ssh "${SSH_OPTS[@]}" "$REMOTE" 'if ! command -v docker >/dev/null 2>&1; then 
    set -e; 
    if [ -f /etc/debian_version ]; then 
      sudo apt-get update -y; 
      sudo apt-get install -y ca-certificates curl gnupg; 
      sudo install -m 0755 -d /etc/apt/keyrings; 
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg; 
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null; 
      sudo apt-get update -y; 
      sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; 
      sudo usermod -aG docker $USER || true; 
    else 
      echo "[remote] Unknown distro; please install Docker manually" >&2; 
      exit 1; 
    fi; 
  fi'
fi

# Run deploy
RUN_PULL_CMD=''
if ! $NO_PULL; then
  if [[ -n "$SERVICES" ]]; then
    RUN_PULL_CMD="docker compose --env-file .env.prod -f docker-compose.yml pull $SERVICES || true &&"
  else
    RUN_PULL_CMD="docker compose --env-file .env.prod -f docker-compose.yml pull || true &&"
  fi
fi

echo "[deploy] Bringing up services via docker compose"
if [[ -n "$SERVICES" ]]; then
  ssh "${SSH_OPTS[@]}" "$REMOTE" "cd '$REMOTE_DIR' && $RUN_PULL_CMD docker compose --env-file .env.prod -f docker-compose.yml up -d $SERVICES"
else
  ssh "${SSH_OPTS[@]}" "$REMOTE" "cd '$REMOTE_DIR' && $RUN_PULL_CMD docker compose --env-file .env.prod -f docker-compose.yml up -d"
fi

echo "[deploy] Status:"
ssh "${SSH_OPTS[@]}" "$REMOTE" "cd '$REMOTE_DIR' && docker compose --env-file .env.prod -f docker-compose.yml ps"

echo "[deploy] Done. Check endpoints like: https://payments.">${ROOT_DIR}/.last_deploy_hint 2>/dev/null || true
echo "[deploy]   - payments.
[deploy]   - taxi.
[deploy] Update BASE_DOMAIN in .env.prod for full URLs." | sed "s/^/$(printf '%s' "${BASE_DOMAIN:-<your-domain>}")/" >/dev/null 2>&1 || true
