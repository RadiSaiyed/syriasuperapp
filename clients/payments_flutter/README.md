Payments Flutter Client (MVP)

This Flutter app targets the Payments API in this repo. It implements dev login (phone + OTP stub), wallet view, dev topup, P2P transfer, merchant QR creation, QR payment (manual code entry), voucher top‑ups (create + redeem), and transactions.

Prereqs
- Flutter SDK installed (3.x)
- Backend running at http://localhost:8080 or reachable from device/emulator

Scaffold platform files
1) Open this folder: `syria-superapp/clients/payments_flutter`
2) Run: `flutter create .` (generates android/ios/web folders)
3) Get deps: `flutter pub get`
4) Run: `flutter run`
  
Patching deep link configs automatically
- After `flutter create .`, run: `bash scripts/apply_deeplinks.sh`

Notes
- Base URL defaults to http://localhost:8080 (change in app top-right menu). For Android emulator use http://10.0.2.2:8080. For iOS simulator use http://localhost:8080. For real device use your machine IP.
- OTP is dev-only: 123456

QR Scanning & Display
- The app uses `mobile_scanner` for camera-based QR scanning.
- The merchant and vouchers screens render QR codes via `qr_flutter` for customers to scan.
- Voucher QR format: `VCHR|<code>` (scan to auto‑redeem on the Vouchers tab).
- You can Copy or Share the QR text via the buttons below the QR.
- The Base URL set via the top-right menu is persisted across restarts.
- P2P Receive QR: In the Wallet, tap "Receive QR" to show a personal P2P QR. Format: `P2P:v1;to=<phone>;amount_cents=<optional>`.
- Contacts: Local contact book for quick P2P. Add contacts and start a Transfer or a Request from the list.
- Requests: Inbox lists incoming/outgoing requests. Accept/Reject incoming, Cancel outgoing.
- Android: add camera permission in `android/app/src/main/AndroidManifest.xml:1` inside `<manifest>`:
  `<uses-permission android:name="android.permission.CAMERA" />`
- iOS: add a camera usage description in `ios/Runner/Info.plist:1`:
  `<key>NSCameraUsageDescription</key><string>Scan QR codes to pay merchants</string>`
- After changing permissions, run `flutter clean` and re-run the app.

Security (PIN & Biometrics)
- Set an App PIN and enable biometrics under Security (Wallet → Security).
- Sensitive actions (Transfer, Pay QR, Accept Request, Cash-Out) require biometric or PIN.
- iOS: add Face ID usage description to `ios/Runner/Info.plist:1`:
  `<key>NSFaceIDUsageDescription</key><string>Authorize payments with Face ID</string>`

Deep links (payments://request/<id>)
- Android (Intent filter): in `android/app/src/main/AndroidManifest.xml`, inside your `MainActivity` add:
  ```xml
  <intent-filter android:autoVerify="false">
      <action android:name="android.intent.action.VIEW" />
      <category android:name="android.intent.category.DEFAULT" />
      <category android:name="android.intent.category.BROWSABLE" />
      <data android:scheme="payments" android:host="request" />
  </intent-filter>
  ```
- iOS (URL Types): in `ios/Runner/Info.plist`, add:
  ```xml
  <key>CFBundleURLTypes</key>
  <array>
    <dict>
      <key>CFBundleURLName</key>
      <string>app.payments</string>
      <key>CFBundleURLSchemes</key>
      <array>
        <string>payments</string>
      </array>
    </dict>
  </array>
  ```
- Test the link:
  - Android: `adb shell am start -a android.intent.action.VIEW -d "payments://request/demo123"`
  - iOS Simulator: `xcrun simctl openurl booted payments://request/demo123`

Integration Tests (Desktop)
- macOS: From this folder run
  - `flutter test integration_test -d macos`
  - Optional Admin flows (Bulk Vouchers): `flutter test integration_test -d macos --dart-define=ADMIN_TOKEN=<your_admin_token>`
  - Ensure backend is running at the Base URL (default http://localhost:8080).
