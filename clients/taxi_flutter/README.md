Taxi Flutter Client (MVP)

Minimal Flutter client for the Taxi API: dev login via username/password, request a ride (rider), simple driver controls (apply, go available, set location, accept/start/complete ride), and ride list.

Prereqs
- Flutter SDK (3.x)
- Taxi API running at http://localhost:8081 (or reachable from device/emulator)

Scaffold platform files
1) `cd syria-superapp/clients/taxi_flutter`
2) `flutter create .`
3) `flutter pub get`
4) `flutter run`

Flavors & getrennte Apps
- UI trennt Fahrer/Fahrgast über `APP_MODE`:
  - Rider‑App: `flutter run --flavor rider --dart-define=APP_MODE=rider -t lib/main.dart`
  - Driver‑App: `flutter run --flavor driver --dart-define=APP_MODE=driver -t lib/main.dart`
- Android: Flavors `rider`/`driver` eingerichtet (andere App‑Namen/Bundlesuffixe)
- iOS: vorerst nur `--dart-define=APP_MODE=...` nutzen. Für Store‑Trennung: in Xcode zwei Schemes/Targets (Bundle‑IDs) anlegen und mit `APP_MODE` bauen.

Base URL
- Defaults to http://localhost:8081; change via top-right menu in app.
- Android emulator: http://10.0.2.2:8081; iOS simulator: http://localhost:8081.

Cash rides & Driver fee
- Fare is quoted; passenger pays cash to the driver. On ride completion, the platform charges the driver a 10% fee from their Payments wallet. Use the "Guthaben aufladen" button in the Driver screen to top up via the Payments app.
 - New: Driver can view Taxi Wallet balance (dev) and trigger an in‑app top‑up of the exact shortfall when Accept fails with `insufficient_taxi_wallet_balance`. This calls `POST /driver/taxi_wallet/topup` directly for faster local testing. In production, use the Payments app.

Map & Live Status
- Standardmäßig wird TomTom verwendet. Starte die App z. B. mit `--dart-define=TOMTOM_MAP_KEY=dein_key` (optional `--dart-define=TOMTOM_TILE_STYLE=basic/main`).
- Alternativ lässt sich ein eigener Tile-Endpunkt über `--dart-define=TILE_URL=<template>` setzen, falls TomTom nicht verfügbar ist.
- Rider: tap the map to set pickup/dropoff (toggle which pin to set), request ride, and see live status via polling + WebSocket.
- Driver: tap map to set location (updates lat/lon fields), periodic polling to refresh ride status.
- Background location (Driver): toggle "Auto-Update Location" to stream GPS updates and push `/driver/location` periodically.
  - iOS: requires location permissions and Background Modes → Location Updates (Info-Driver.plist already set).
  - Android: requires location permissions and foreground service permission; manifest updated with ACCESS_*_LOCATION and FOREGROUND_SERVICE.

Notifications
- Local notifications pop on assignment/status events while the app runs (via `flutter_local_notifications`).
- Server push setup (optional):
  - Backend exposes `/push/register` and supports FCM with `FCM_SERVER_KEY`.
  - To enable real push on devices, integrate `firebase_messaging` in this app and POST the FCM token to `/push/register` (not included here to avoid project‑wide Firebase setup).

Localization (en now, ar later)
- App is prepared for i18n. Currently English only (Material/Widgets/Cupertino delegates enabled). Arabic can be added later by extending supportedLocales and string resources.
Driver fee
- Configured by Taxi API env `PLATFORM_FEE_BPS` (default 1000 = 10%).

iOS Simulator (Dummy Test)
- Prereqs: Xcode + Simulator, CocoaPods, Flutter installed (`flutter doctor` green)
- Steps:
  1) Start a simulator:
     - List devices: `xcrun simctl list devices`
     - Boot: `xcrun simctl boot "iPhone 15"` (or any available)
     - Open UI: `open -a Simulator`
  2) Fetch deps: `flutter pub get`
  3) Run integration test on simulator:
     - `flutter test integration_test -d "iPhone 15"`
     - Alternative: `flutter drive --driver integration_test/driver.dart --target integration_test/app_test.dart` (if a driver is added)
  4) Expected: test "launches and shows title" passes; app shows title "Taxi MVP".
- Notes:
  - If a device isn’t found, run `flutter devices` and use the exact simulator name after `-d`.
  - For first iOS run, CocoaPods may run automatically; if not, `cd ios && pod install`.
  - To test escrow prepay from rider, enable the toggle in the Rider screen and ensure Taxi API has `TAXI_ESCROW_WALLET_PHONE` set and Payments is running.
