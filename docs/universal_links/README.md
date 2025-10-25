Universal/App Links Setup for Payments+

Overview
- iOS Universal Links require hosting `apple-app-site-association` on your domain and enabling Associated Domains in the iOS app (entitlements).
- Android App Links require hosting `/.well-known/assetlinks.json` and declaring an `https` VIEW intent filter with `android:autoVerify="true"`.

Assumptions
- Feature deep link: open payment request detail at `https://<DOMAIN>/request/<id>` and `payments://request/<id>`.
- Replace placeholders below:
  - <DOMAIN>: your public domain (e.g., example.com)
  - <IOS_TEAM_ID>: Apple Team ID (10‑char)
  - <IOS_BUNDLE_ID>: iOS bundle identifier (e.g., com.acme.payments)
  - <ANDROID_PACKAGE>: Android applicationId (e.g., com.acme.payments)
  - <ANDROID_SHA256_CERT>: SHA‑256 signing cert fingerprint of release keystore

iOS: Server file (AASA)
- Path: `https://<DOMAIN>/.well-known/apple-app-site-association` (no extension, JSON, content‑type `application/json`)
- Template: see `apple-app-site-association.json`

iOS: App configuration
- Edit Xcode target (Runner):
  1) Add Capability: Associated Domains
  2) Add domain: `applinks:<DOMAIN>`
  3) Ensure entitlements file included (Runner.entitlements)
- Example entitlements added in repo: `clients/payments_flutter/ios/Runner/Runner.entitlements` (replace `<DOMAIN>`)

Android: Server file (Asset Links)
- Path: `https://<DOMAIN>/.well-known/assetlinks.json`
- Template: see `assetlinks.json`
- `sha256_cert_fingerprints`: compute from your release keystore, e.g.:
  - `keytool -list -v -alias <alias> -keystore <keystore.jks> | grep SHA256` (copy the 64‑hex uppercase without colons)

Android: App configuration
- Manifest intent filter already present with `android:autoVerify="true"` and placeholder host. Update host to `<DOMAIN>`.
  - File: `clients/payments_flutter/android/app/src/main/AndroidManifest.xml`

Client handling
- The app handles both `payments://request/<id>` and `https://<DOMAIN>/request/<id>`
- For builds, pass the domain to the app (optional): `--dart-define=APP_LINK_HOST=<DOMAIN>`

Templates to deploy
- Copy JSONs below to your web server and replace placeholders.

