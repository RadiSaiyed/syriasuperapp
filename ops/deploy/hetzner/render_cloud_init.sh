#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"

# Load env (HETZNER_SSH_PUBLIC_KEY)
source "$SCRIPT_DIR/env.sh" "$ROOT_DIR/.env"

TEMPLATE="$ROOT_DIR/cloud-init.yml"
OUTFILE="$ROOT_DIR/cloud-init.rendered.yml"

if [ -z "${HETZNER_SSH_PUBLIC_KEY:-}" ]; then
  echo "[cloud-init] HETZNER_SSH_PUBLIC_KEY not set in .env" >&2
  exit 1
fi

if ! grep -q '{{HETZNER_SSH_PUBLIC_KEY}}' "$TEMPLATE"; then
  echo "[cloud-init] Placeholder {{HETZNER_SSH_PUBLIC_KEY}} not found in $TEMPLATE" >&2
  exit 1
fi

python3 - "$TEMPLATE" "$OUTFILE" <<'PY'
import sys, os
tpl_path, out_path = sys.argv[1:3]
pub = os.environ.get('HETZNER_SSH_PUBLIC_KEY','').strip()
if not pub:
    sys.exit("HETZNER_SSH_PUBLIC_KEY empty")
with open(tpl_path, 'r', encoding='utf-8') as f:
    data = f.read()
data = data.replace('{{HETZNER_SSH_PUBLIC_KEY}}', pub)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(data)
print(f"[cloud-init] Rendered -> {out_path}")
PY

echo "$OUTFILE"

