#!/usr/bin/env bash
set -euo pipefail

# Run flutter tests for all *_flutter clients.
# Usage: bash tools/run_flutter_tests.sh [--pattern <glob>] [--continue]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

# If Flutter is not available, skip gracefully with a helpful message
if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter SDK not found. Skipping UI tests."
  echo "Install via: brew install --cask flutter  (then run: flutter doctor)"
  exit 0
fi

PATTERN="*_flutter"
CONTINUE_ON_FAIL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pattern)
      PATTERN="$2"; shift 2;;
    --continue)
      CONTINUE_ON_FAIL=true; shift;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

clients=( $(ls -d clients/${PATTERN} 2>/dev/null || true) )
if [[ ${#clients[@]} -eq 0 ]]; then
  echo "No clients match pattern: ${PATTERN}"
  exit 1
fi

echo "Found ${#clients[@]} clients: ${clients[*]}"

FAILS=()
for dir in "${clients[@]}"; do
  echo "===== Testing ${dir} ====="
  pushd "$dir" >/dev/null
  flutter pub get
  if ! flutter test; then
    echo "FAILED: ${dir}"
    FAILS+=("${dir}")
    if [[ "$CONTINUE_ON_FAIL" != true ]]; then
      exit 1
    fi
  else
    echo "OK: ${dir}"
  fi
  popd >/dev/null
done

if [[ ${#FAILS[@]} -gt 0 ]]; then
  echo "Some client tests failed: ${FAILS[*]}"
  exit 1
fi

echo "All client tests passed."
