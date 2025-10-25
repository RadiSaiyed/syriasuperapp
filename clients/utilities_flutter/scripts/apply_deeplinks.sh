#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
IOS_PLIST="$ROOT_DIR/ios/Runner/Info.plist"
ANDROID_MANIFEST="$ROOT_DIR/android/app/src/main/AndroidManifest.xml"

echo "Applying deep-link launch whitelist for Utilities app (iOS)..."

if [[ -f "$IOS_PLIST" ]]; then
  echo "- Patching Info.plist LSApplicationQueriesSchemes via Python"
  /usr/bin/python3 - "$IOS_PLIST" <<'PY'
import plistlib, sys
p = sys.argv[1]
with open(p, 'rb') as f:
    pl = plistlib.load(f)
schemes = pl.get('LSApplicationQueriesSchemes') or []
if 'payments' not in schemes:
    schemes.append('payments')
pl['LSApplicationQueriesSchemes'] = schemes
with open(p, 'wb') as f:
    plistlib.dump(pl, f)
print('  * payments scheme ensured in LSApplicationQueriesSchemes')
PY
else
  echo "! Info.plist not found. Run: flutter create . inside utilities_flutter first."
fi

echo "Applying Android queries visibility for Utilities app (Android)..."

if [[ -f "$ANDROID_MANIFEST" ]]; then
  if ! grep -q '<queries>' "$ANDROID_MANIFEST"; then
    echo "- Adding <queries> with payments scheme"
    cp "$ANDROID_MANIFEST" "$ANDROID_MANIFEST.bak"
    awk '{print} /<manifest[^>]*>/ && done==0 {print "  <queries>\n    <intent>\n      <action android:name=\"android.intent.action.VIEW\" />\n      <data android:scheme=\"payments\" />\n    </intent>\n  </queries>"; done=1}' "$ANDROID_MANIFEST" > "$ANDROID_MANIFEST.tmp" && mv "$ANDROID_MANIFEST.tmp" "$ANDROID_MANIFEST"
  else
    if ! grep -q 'android:scheme="payments"' "$ANDROID_MANIFEST"; then
      echo "- Appending payments scheme into existing <queries>"
      cp "$ANDROID_MANIFEST" "$ANDROID_MANIFEST.bak"
      awk '{print} /<queries>/ {flag=1} flag==1 && /<\/queries>/ && done==0 {print "  <intent>\n    <action android:name=\"android.intent.action.VIEW\" />\n    <data android:scheme=\"payments\" />\n  </intent>"; done=1}' "$ANDROID_MANIFEST" > "$ANDROID_MANIFEST.tmp" && mv "$ANDROID_MANIFEST.tmp" "$ANDROID_MANIFEST"
    else
      echo "- AndroidManifest already declares payments scheme in <queries>. Skipping."
    fi
  fi
else
  echo "! AndroidManifest.xml not found. Run: flutter create . inside utilities_flutter first."
fi

echo "Done."

