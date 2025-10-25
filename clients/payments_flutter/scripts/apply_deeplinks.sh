#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

ANDROID_MANIFEST="$ROOT_DIR/android/app/src/main/AndroidManifest.xml"
IOS_PLIST="$ROOT_DIR/ios/Runner/Info.plist"

echo "Applying deep-link config for Payments app..."

# Android: add intent-filter for payments://request/<id>
if [[ -f "$ANDROID_MANIFEST" ]]; then
  if ! grep -q 'android:scheme="payments"' "$ANDROID_MANIFEST"; then
    echo "- Patching AndroidManifest.xml"
    cp "$ANDROID_MANIFEST" "$ANDROID_MANIFEST.bak"
    # Insert intent-filter before closing </activity> (assumes single main activity)
    awk '{print} /<activity[^>]*>/ && seen==0 {seen=1} /<\/activity>/ && injected==0 && seen==1 {print "    <intent-filter android:autoVerify=\"false\">\n      <action android:name=\"android.intent.action.VIEW\" />\n      <category android:name=\"android.intent.category.DEFAULT\" />\n      <category android:name=\"android.intent.category.BROWSABLE\" />\n      <data android:scheme=\"payments\" android:host=\"request\" />\n    </intent-filter>"; injected=1; print; next}' "$ANDROID_MANIFEST" > "$ANDROID_MANIFEST.tmp" && mv "$ANDROID_MANIFEST.tmp" "$ANDROID_MANIFEST"
  else
    echo "- AndroidManifest already contains payments scheme. Skipping."
  fi
else
  echo "! AndroidManifest.xml not found. Run: flutter create . inside payments_flutter first."
fi

# iOS: add CFBundleURLTypes scheme payments (use Python plistlib for robustness)
if [[ -f "$IOS_PLIST" ]]; then
  echo "- Patching Info.plist CFBundleURLTypes via Python"
  /usr/bin/python3 - "$IOS_PLIST" <<'PY'
import plistlib, sys
p = sys.argv[1]
with open(p, 'rb') as f:
    pl = plistlib.load(f)
url_types = pl.get('CFBundleURLTypes') or []
found = False
for d in url_types:
    if isinstance(d, dict):
        schemes = d.get('CFBundleURLSchemes') or []
        if 'payments' in schemes:
            found = True
            break
if not found:
    url_types.append({'CFBundleURLName': 'app.payments', 'CFBundleURLSchemes': ['payments']})
pl['CFBundleURLTypes'] = url_types
with open(p, 'wb') as f:
    plistlib.dump(pl, f)
print('  * payments scheme ensured in CFBundleURLTypes')
PY
else
  echo "! Info.plist not found. Run: flutter create . inside payments_flutter first."
fi

echo "Done."
