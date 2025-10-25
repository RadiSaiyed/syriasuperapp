Super‑App Flutter (Container)

A unified container client bundling the verticals (Payments, Taxi, …). Each vertical currently exposes a minimal view (OTP login, simple queries) and can add deep‑links/launch options.

Start
1) `cd clients/superapp_flutter`
2) `flutter pub get`
3) `flutter run \
       --dart-define=TOMTOM_MAP_KEY=<your_dev_key> \
       --dart-define=SUPERAPP_BASE_HOST=http://<your_dev_mac_ip> \
       --dart-define=TAXI_BASE_URL=http://<your_dev_mac_ip>:8081 \
       --dart-define=PAYMENTS_BASE_URL=http://<your_dev_mac_ip>:8080 \
       --dart-define=CHAT_BASE_URL=https://chat.<your_domain>`
   - Without a TomTom key the Taxi map doesn’t start (no fallback)
   - For physical devices (iOS/Android) use the Dev machine IP (not `localhost`)
   - Custom style: `--dart-define=TOMTOM_TILE_STYLE=a8940ba3-b342-45b9-84d7-7fc7d3c538fe` uses the provided TomTom styling (GUID automatically mapped to `style/<id>`)
   - Optional: `--dart-define=TOMTOM_TILE_STYLE=basic/main` for the TomTom default style set
- Optional: `--dart-define=TOMTOM_SHOW_TRAFFIC_FLOW=false` to disable the traffic overlay
 - For testing Chat in production, set `CHAT_BASE_URL=https://chat.<your_domain>`; Inbox/WebSocket will use it.
 - Optional (AI Gateway): `--dart-define=AI_GATEWAY_BASE_URL=http://<your_dev_mac_ip>:8099` (UI erlaubt manuelles Setzen).

Prod defines
- Create `dart_defines/prod.json` (a template is included) with your production endpoints and keys:

```
{
  "TAXI_BASE_URL": "https://taxi.example.com",
  "PAYMENTS_BASE_URL": "https://payments.example.com",
  "CHAT_BASE_URL": "https://chat.example.com",
  "TOMTOM_MAP_KEY": "<replace-with-real-key>",
  "TOMTOM_TILE_STYLE": "basic/main",
  "TOMTOM_SHOW_TRAFFIC_FLOW": "false",
  "TOMTOM_SHOW_TRAFFIC_INCIDENTS": "false"
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
- iOS requires HTTPS unless ATS exceptions are configured in `ios/Runner/Info.plist`.

Services & Auth
- Default base URLs point to localhost and can be adjusted in `lib/services.dart`.
- OTP login is per service; tokens are stored per service in SharedPreferences.
- Splash/silent login: on startup, an existing Payments token is validated and, if valid, propagated to all services (single‑login UX).

Structure
- `lib/main.dart` — Home (apps grid, tabs), splash/silent login
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
