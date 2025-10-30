#!/usr/bin/env bash
set -euo pipefail

# Launch two iOS Simulators and run two Flutter apps to test Payments deep-links.
# - Payments Flutter on "Demo iPhone"
# - Commerce Flutter on "Demo iPad"
#
# Prereqs:
# - macOS with Xcode CLI tools (xcrun/simctl) and CocoaPods for iOS builds
# - Docker running (to start backend APIs)
# - Flutter SDK bundled in repo: tools/flutter/bin/flutter

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
FLUTTER_BIN="$ROOT_DIR/tools/flutter/bin/flutter"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "[error] Missing dependency: $1" >&2; exit 2; }
}

require xcrun
require "$FLUTTER_BIN"

echo "[step] Starting backends (Payments + Commerce)"
(
  set -e
  cd "$ROOT_DIR/apps/payments" && docker compose up -d db redis api
  cd "$ROOT_DIR/apps/commerce" && docker compose up -d db redis api
) || echo "[warn] Could not start one or more backends. Ensure Docker is running."

echo "[step] Opening iOS Simulator app"
open -a Simulator || true

echo "[step] Ensuring demo devices exist (Demo iPhone / Demo iPad)"
make -C "$ROOT_DIR" ios-create-iphone >/dev/null 2>&1 || true
make -C "$ROOT_DIR" ios-create-ipad >/dev/null 2>&1 || true

get_udid() { # $1=name
  xcrun simctl list devices available | awk -v N="$1" -F'[()]' '$0 ~ N {print $2; exit}'
}

boot_device() { # $1=name
  local name="$1"; local udid
  udid=$(get_udid "$name")
  if [[ -z "$udid" ]]; then echo "[error] Could not find device: $name" >&2; return 1; fi
  xcrun simctl boot "$udid" 2>/dev/null || true
  echo "$udid"
}

IPHONE_UDID=$(boot_device "Demo iPhone")
IPAD_UDID=$(boot_device "Demo iPad")
echo "[info] Demo iPhone UDID: $IPHONE_UDID"
echo "[info] Demo iPad UDID:   $IPAD_UDID"

build_and_install() { # $1=app_dir, $2=device_udid
  local app_dir="$1"; local udid="$2"
  echo "[step] Building iOS (simulator) for $app_dir"
  (
    cd "$app_dir"
    bash scripts/apply_deeplinks.sh >/dev/null 2>&1 || true
    # iOS deps (best effort)
    (cd ios && pod install) || true
    "$FLUTTER_BIN" pub get
    "$FLUTTER_BIN" build ios --simulator --no-codesign
  )
  local app_path="$app_dir/build/ios/iphonesimulator/Runner.app"
  if [[ ! -d "$app_path" ]]; then
    echo "[error] .app not found at $app_path" >&2
    return 2
  fi
  echo "[step] Installing app to device $udid"
  xcrun simctl install "$udid" "$app_path"
  # Read bundle identifier from built Info.plist
  local bid
  bid=$(python3 - <<'PY'
import plistlib, sys
from pathlib import Path
p = Path(sys.argv[1])/'Info.plist'
with p.open('rb') as f:
    d=plistlib.load(f)
print(d.get('CFBundleIdentifier',''))
PY
"$app_path")
  if [[ -z "$bid" ]]; then
    echo "[error] Could not read CFBundleIdentifier" >&2
    return 3
  fi
  echo "[step] Launching $bid"
  xcrun simctl launch "$udid" "$bid" || true
}

echo "[step] Launch Payments app on Demo iPhone"
build_and_install "$ROOT_DIR/clients/payments_flutter" "$IPHONE_UDID" || echo "[warn] Payments app launch failed. Try running: (cd clients/payments_flutter && ../../tools/flutter/bin/flutter run -d \"Demo iPhone\")"

echo "[step] Launch Commerce app on Demo iPad"
build_and_install "$ROOT_DIR/clients/commerce_flutter" "$IPAD_UDID" || echo "[warn] Commerce app launch failed. Try running: (cd clients/commerce_flutter && ../../tools/flutter/bin/flutter run -d \"Demo iPad\")"

echo "[done] Simulators are up. Configure Base URLs in apps if needed:"
echo "       Payments: http://localhost:8080 | Commerce: http://localhost:8083"

