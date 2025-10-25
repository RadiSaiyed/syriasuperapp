Taxi Driver (Standalone)

Standalone Driver UI for the Taxi service, reusing the shared code from `clients/taxi_flutter`.

What’s included
- Driver-only shell app (no rider UI) with login, base URL selector, push registration, and the existing Driver screen.
- Localizations (en, ar).

Run (Web)
- Ensure Taxi API is running (default base URL `http://localhost:8081`).
- From this folder:
  - `flutter pub get`
  - `flutter run -d chrome`

Run (Mobile)
- If platform folders are not present, create them once: `flutter create .`
- Then build normally: `flutter run -d ios` or `flutter run -d android`.

Notes
- This app depends on `clients/taxi_flutter` via a path dependency and reuses:
  - `api.dart`, `screens/driver_screen.dart`, `screens/login_screen.dart`, `push.dart`.
- Configure map tiles with `--dart-define` flags used by the driver screen if needed:
  - `--dart-define=USE_MAPLIBRE=true --dart-define=STYLE_URL=...`

