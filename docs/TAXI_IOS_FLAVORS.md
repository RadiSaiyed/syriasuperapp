Taxi iOS: Rider/Driver Targets & Schemes

Goal: build two separate iOS apps (Rider/Driver) from the Flutter project.

Preparation
- Flutter iOS already generated (folder `clients/taxi_flutter/ios` exists)
- Open the workspace: `open clients/taxi_flutter/ios/Runner.xcworkspace`

Steps in Xcode
1) Duplicate targets
   - Select target "Runner" → Right‑click → Duplicate.
   - Name the new target e.g. "Driver". (The existing target serves as "Rider").
   - Xcode also creates a new scheme. Rename schemes accordingly (Product → Scheme → Manage Schemes…).

2) Bundle IDs / Names
   - Rider target:
     - General → Display Name: "Taxi Rider"
     - Signing & Capabilities → Bundle Identifier: e.g. `com.yourorg.taxi.rider`
   - Driver target:
     - General → Display Name: "Taxi Driver"
     - Signing & Capabilities → Bundle Identifier: e.g. `com.yourorg.taxi.driver`

3) Info.plist per target
   - Rider: keep default `Info.plist`
   - Driver: set Build Settings → Packaging → Info.plist File to `Runner/Info-Driver.plist`
     (file at `clients/taxi_flutter/ios/Runner/Info-Driver.plist`)

4) Background Modes (Driver only)
   - Driver target → Signing & Capabilities → "+ Capability" → Background Modes → enable "Location updates"
     (alternatively, `UIBackgroundModes = location` is already set in `Info-Driver.plist`)

5) Set `APP_MODE` via scheme
   - Edit Scheme… → Run → Arguments → Environment Variables (or Build → Pre‑Actions) is tedious.
   - Better: when launching with Flutter, pass:
     - Rider: `flutter run --flavor rider --dart-define=APP_MODE=rider -t lib/main.dart`
     - Driver: `flutter run --flavor driver --dart-define=APP_MODE=driver -t lib/main.dart`
   - Optional: create two schemes that set `--dart-define=APP_MODE=driver` under "Arguments Passed On Launch" (if invoking `flutter` from Xcode).

6) Icons (optional, recommended)
   - Create a separate AppIcon set per target in `Assets.xcassets` (e.g. `AppIconRider`, `AppIconDriver`).
   - Set the proper icon set under General → App Icons for each target.

7) Build & Test
   - Rider: choose scheme/target "Rider", press Run (simulator/device)
   - Driver: choose scheme/target "Driver", press Run

Notes
- The app also sets title/content at runtime via `APP_MODE` (see `lib/main.dart`).
- For App Store submission, use two separate bundle IDs, different display names, and — if needed — distinct permissions (e.g., Background Location only for Driver).
