#!/usr/bin/env bash
set -euo pipefail

# Load Hetzner credentials from repo .env, export HCLOUD_TOKEN alias,
# and materialize the SSH key for use with ssh/scp.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "[hetzner-env] Missing env file: $ENV_FILE" >&2
  exit 1
fi

# Load .env in a shell-compatible way
set -a
# shellcheck source=/dev/null
. "$ENV_FILE"
set +a

# Alias used by hcloud CLI / Terraform
export HCLOUD_TOKEN="${HCLOUD_TOKEN:-${HETZNER_API_TOKEN:-}}"

# Prepare SSH key files from env
SSH_DIR="$SCRIPT_DIR/.ssh"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [ -n "${HETZNER_SSH_PRIVATE_KEY_B64:-}" ]; then
  PRIV_FILE="$SSH_DIR/id_hetzner_ed25519"
  umask 077
  # Cross-platform base64 decode (GNU, BSD/macOS)
  if printf '%s' "$HETZNER_SSH_PRIVATE_KEY_B64" | base64 -d >/dev/null 2>&1; then
    printf '%s' "$HETZNER_SSH_PRIVATE_KEY_B64" | base64 -d >"$PRIV_FILE"
  elif printf '%s' "$HETZNER_SSH_PRIVATE_KEY_B64" | base64 --decode >/dev/null 2>&1; then
    printf '%s' "$HETZNER_SSH_PRIVATE_KEY_B64" | base64 --decode >"$PRIV_FILE"
  elif printf '%s' "$HETZNER_SSH_PRIVATE_KEY_B64" | base64 -D >/dev/null 2>&1; then
    printf '%s' "$HETZNER_SSH_PRIVATE_KEY_B64" | base64 -D >"$PRIV_FILE"
  else
    python3 - <<'PY' >"$PRIV_FILE"
import base64, os
data = os.environ['HETZNER_SSH_PRIVATE_KEY_B64']
print(base64.b64decode(data).decode('utf-8'), end='')
PY
  fi
  chmod 600 "$PRIV_FILE"
  export HETZNER_SSH_PRIVATE_KEY_FILE="$PRIV_FILE"
fi

if [ -n "${HETZNER_SSH_PUBLIC_KEY:-}" ]; then
  PUB_FILE="$SSH_DIR/id_hetzner_ed25519.pub"
  printf '%s\n' "$HETZNER_SSH_PUBLIC_KEY" > "$PUB_FILE"
  chmod 644 "$PUB_FILE"
fi

# Convenience SSH options
if [ -n "${HETZNER_SSH_PRIVATE_KEY_FILE:-}" ]; then
  export HETZNER_SSH_OPTS="-o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -i \"$HETZNER_SSH_PRIVATE_KEY_FILE\""
fi

# Expose Terraform variable (optional): allows use of ${var.ssh_public_key}
if [ -n "${HETZNER_SSH_PUBLIC_KEY:-}" ]; then
  export TF_VAR_ssh_public_key="$HETZNER_SSH_PUBLIC_KEY"
fi

echo "[hetzner-env] Loaded $(basename "$ENV_FILE")"
[ -n "${HCLOUD_TOKEN:-}" ] && echo "[hetzner-env] HCLOUD_TOKEN exported" || echo "[hetzner-env] HCLOUD_TOKEN not set"
[ -n "${HETZNER_SSH_PRIVATE_KEY_FILE:-}" ] && echo "[hetzner-env] SSH key: $HETZNER_SSH_PRIVATE_KEY_FILE" || true
[ -n "${HETZNER_IPV4:-}" ] && echo "[hetzner-env] IPv4: $HETZNER_IPV4" || true

# Map env -> TF vars for DNS convenience
if [ -n "${BASE_DOMAIN:-}" ]; then
  export TF_VAR_base_domain="$BASE_DOMAIN"
fi
if [ -n "${HETZNER_IPV4:-}" ]; then
  export TF_VAR_a_ipv4="$HETZNER_IPV4"
fi
if [ -n "${HETZNER_IPV6:-}" ]; then
  export TF_VAR_aaaa_ipv6="$HETZNER_IPV6"
fi
