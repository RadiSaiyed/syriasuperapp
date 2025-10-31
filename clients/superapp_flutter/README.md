Super‑App Flutter (Container)

A unified container client bundling the verticals (Payments, Taxi, …). Each vertical currently exposes a minimal view (OTP login, simple queries) and can add deep‑links/launch options.

Start
1) `cd clients/superapp_flutter`
2) `flutter pub get`
3) Variante A — Single‑Base (empfohlen, BFF):
   `flutter run --dart-define=SUPERAPP_API_BASE=http://<your_dev_mac_ip>:8070`
   - BFF lokal: `make bff-up` (Port 8070)
   - Alle Services laufen dann über `http://<host>:8070/<service>/...`
   
   Variante B — Per‑Service (Legacy):
   `flutter run \
       --dart-define=USE_GOOGLE_MAPS=true \
       --dart-define=SUPERAPP_BASE_HOST=http://<your_dev_mac_ip> \
       --dart-define=TAXI_BASE_URL=http://<your_dev_mac_ip>:8081 \
       --dart-define=PAYMENTS_BASE_URL=http://<your_dev_mac_ip>:8080 \
       --dart-define=CHAT_BASE_URL=https://chat.<your_domain>`
   - Google Maps SDK wird auf iOS/Android verwendet (Key erforderlich; siehe unten). Ohne Key fällt die Map auf OSM‑Tiles zurück.
   - For physical devices (iOS/Android) use the Dev machine IP (not `localhost`)
   - Optional: `--dart-define=MAPS_SHOW_TRAFFIC=true` to enable Google traffic overlay where supported
 - For testing Chat in production, set `CHAT_BASE_URL=https://chat.<your_domain>`; Inbox/WebSocket will use it.
 - Optional (AI Gateway): `--dart-define=AI_GATEWAY_BASE_URL=http://<your_dev_mac_ip>:8099` (UI erlaubt manuelles Setzen).

Prod defines
- Create `dart_defines/prod.json` (a template is included) with your production endpoints:

```
{
  "TAXI_BASE_URL": "https://taxi.example.com",
  "PAYMENTS_BASE_URL": "https://payments.example.com",
  "CHAT_BASE_URL": "https://chat.example.com",
  "USE_GOOGLE_MAPS": "true"
}
```

- Run locally against prod:

```
cd clients/superapp_flutter
flutter run --dart-define-from-file=dart_defines/prod.json
```

- Build iOS release with prod defines:

```
flutter build ios --release --dart-define-from-file=dart_defines/prod.json
```

- Makefile shortcuts (from `clients/superapp_flutter`):

```
make run-prod DEVICE="iPhone 17 Pro"
make build-ios-prod
```

Xcode scheme (optional)
- In Xcode, edit Scheme → Run → Arguments → Environment Variables, add `DART_DEFINES` with Base64-encoded key=value pairs joined by commas.
- You can generate the value from `dart_defines/prod.json` with `jq`:

```
cd clients/superapp_flutter
export DART_DEFINES=$(jq -r 'to_entries|map("\(.key)=\(.value)")|map(@base64)|join(",")' dart_defines/prod.json)
```

- Paste `$DART_DEFINES` into the scheme’s `DART_DEFINES` environment variable.

Notes
- Prefer service-specific URLs (`*_BASE_URL`) for production. `SUPERAPP_BASE_HOST` is mainly for local dev.
- With BFF single‑base, prefer `SUPERAPP_API_BASE` instead.
- Legacy module cleanup: external module embeddings (`chat_flutter`, `taxi_flutter`) were removed. The Super‑App now uses built‑in screens
  (Inbox/WS for Chat, TaxiScreen for Taxi) and talks to services directly via the shared HTTP client and the BFF.
- iOS requires HTTPS unless ATS exceptions are configured in `ios/Runner/Info.plist`.
- Localization/RTL: The app ships with English + Arabic locales (RTL). Set from device or Settings; Material widgets flip layout automatically.
- Deep‑links: The app registers `superapp://` (iOS+Android). Beispiele:
  - `superapp://feature/payments` öffnet die Wallet
  - `superapp://feature/taxi` öffnet Taxi
  - `superapp://search?q=invoice` öffnet die globale Suche
  - Mit Parametern:
    - `superapp://payments?view=p2p&to=+963900000002&amount=2500` (P2P vorbefüllen)
    - `superapp://taxi?pickup=33.5138,36.2765&drop=33.5000,36.3000&action=request` (Fahrt anlegen und Taxi öffnen)
    - `superapp://commerce?shop_id=SHOP1&product_id=PROD1&action=checkout` (Shop+Produkt, Warenkorb anzeigen)
    - `superapp://commerce?action=order&order_id=ORDER123` (Bestellung öffnen)
    - `superapp://stays?city=Damascus&check_in=2025-12-01&check_out=2025-12-03&guests=2` (Suche)
    - `superapp://stays?view=listing&property_id=PROP123` (Listing‑Detail)
- Google Maps Key:
  - iOS: add the key to `ios/Runner/Info.plist` as `<key>GMSApiKey</key><string>YOUR_KEY</string>` and run `pod install` in `ios/`.
  - Android: add `<meta-data android:name="com.google.android.geo.API_KEY" android:value="YOUR_KEY"/>` to `android/app/src/main/AndroidManifest.xml` inside `<application>`.
  - The app uses Google Maps on mobile by default when `USE_GOOGLE_MAPS=true`.

Services & Auth
- Default base URLs point to localhost and can be adjusted in `lib/services.dart`.
- Unified Login (SSO): use the Login/Registration screen in the Super‑App. It registers/logins against Payments and propagates the RS256 JWT to all services.
  - Backends accept the token via JWKS: set `JWT_JWKS_URL=http://<payments-host>/.well-known/jwks.json` on each service.
  - In this repo, Chat/Commerce/Stays docker‑compose files already set `JWT_JWKS_URL` to the local Payments API for dev.
- Splash/silent login: on startup, an existing Payments token is validated and, if valid, propagated to all services (single‑login UX).

Privacy & Offline
- Privacy: Crash reporting is disabled by default and can be enabled in Settings → Privacy (no PII is sent; see `CrashReporter` config).
- Offline: Frequently viewed lists (e.g., Commerce shops/products, Stays listings, Agriculture listings) use a small HTTP cache with TTL for faster loads and basic offline reads (`RequestOptions.cacheTtl`).

Structure
- `lib/main.dart` — Home (apps grid, tabs), splash/silent login
- `lib/features.dart` — Feature manifest loader (BFF `/v1/features`)
- `lib/services.dart` — service config + multi‑token store + OTP/auth helpers
- `lib/screens/inbox_screen.dart` — realtime inbox (Chat WS + fetch)
- `lib/screens/payments_screen.dart` — wallet (Payments)
- `lib/screens/food_screen.dart` — restaurants → menu → cart → checkout
- `lib/screens/commerce_screen.dart` — shops → products → cart → checkout
- `lib/screens/utilities_screen.dart` — link account, fetch/pay bills
- `lib/screens/taxi_screen.dart` — quote (Taxi)
 - `lib/screens/ai_gateway_screen.dart` — AI Assistant (Vorschläge, Bestätigung & Ausführung, SuperSearch/OCR via Gateway)

Next steps
- Deepen verticals (reviews, tracking, payment histories)
- Shared profile/account area (phone, KYC status from Payments)
- Push (FCM) in addition to WebSocket inbox
- Optional: feature flags per environment

Push & Topics (optional)
- Foreground banners + local inbox are built‑in. For real push delivery, configure Firebase:
  - iOS: add `ios/Runner/GoogleService-Info.plist`; enable Capabilities: Push Notifications + Background Modes (Remote notifications).
  - Android: add `android/app/google-services.json`; apply Google Services Gradle plugins (already referenced by the template).
- The BFF needs `FCM_SERVER_KEY` for real sends; without it, dev sends/broadcast simulate delivery.
- Topics: Profile → Push Topics to subscribe/unsubscribe; Ops‑Admin can broadcast to topics.
- Optional policy:
  - Admin‑only dev push: by default BFF restricts `/v1/push/dev/*` to admin. Set `PUSH_DEV_ALLOW_ALL=true` during local exploration.
  - Topics gating: set `PUSH_TOPICS_ALLOW_ALL=false` on BFF to require admin/allowlist for subscribe/unsubscribe; allowlists: `PUSH_TOPICS_ALLOWED_PHONES`, `PUSH_TOPICS_ALLOWED_SUBS`.

Firebase setup (for real push)
- iOS:
  - Download your `GoogleService-Info.plist` from Firebase console and place it at `ios/Runner/GoogleService-Info.plist` (a template exists at `ios/Runner/GoogleService-Info.plist.example`).
  - In Xcode, enable Capabilities: Push Notifications and Background Modes → Remote notifications.
  - Ensure your Bundle ID matches the Firebase iOS app.
- Android:
  - Download `google-services.json` and place it at `android/app/google-services.json` (a template exists at `android/app/google-services.json.example`).
  - Ensure the applicationId in `android/app/build.gradle` matches the Firebase Android app package name.
- Backend:
  - Set `FCM_SERVER_KEY` in the BFF environment to your Firebase Cloud Messaging server key.
- Notes: Without Firebase configured, the client will still register with an empty token and the BFF simulates delivery (useful for local dev).

Local dev workflow
1) Start core: `make core-up`
2) Reseed data: `make core-reseed`
3) Smoke test: `make smoke-core`
4) Run app (desktop):
   `cd clients/superapp_flutter && ../../tools/flutter/bin/flutter run -d macOS -t lib/main.dart --dart-define=SUPERAPP_API_BASE=http://localhost:8070`

Settings & UX
- Animations: Off/Normal/Smooth (Settings → Appearance) controls `AnimatedSwitcher` durations.
- Chat unread refresh: choose refresh interval (10/20/60s) in Settings; WS increments count only messages addressed to you.
- Haptics/Sounds: toggle action haptics and notification sounds.
- Privacy: crash and analytics toggles in Settings → Privacy.
- What’s New: reset in Settings to show again on next start.

Extra structure
- `lib/push_register.dart` — device registration + topic subscribe/unsubscribe flows
- `lib/push_history.dart` — local notifications inbox + unread badge logic
