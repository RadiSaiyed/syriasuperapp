Flights Flutter Client (MVP)

Simple Flutter client for the Flights API (`apps/flights`).

Features
- Login via dev OTP (123456)
- Search flights (origin, destination, date)
- Book seats and view/cancel my bookings
- Open payment in Payments app via deep link when a payment request is created

Run
1) Ensure Flights API runs at http://localhost:8092 (see `apps/flights/README.md`).
2) If `android/` and `ios/` are missing, run: `flutter create .`
3) In this folder: `flutter pub get`
4) Run: `flutter run`
5) In the app, set Base URL to your API (e.g. `http://localhost:8092`).

Desktop Builds (optional)
- macOS: `flutter config --enable-macos-desktop && flutter create . && flutter build macos --no-codesign`
- Windows: `flutter config --enable-windows-desktop && flutter create . && flutter build windows`

Optional Payments handoff
- To open payment requests directly in the Payments app, also run the Payments Flutter app from `clients/payments_flutter`.
- When a booking returns a `payment_request_id`, the client offers an "Open in Payments" action that launches `payments://request/<id>`.
- The app bar also has a wallet icon to open the Payments app anytime.

iOS scheme whitelist (for launching deep links)
- If you want `canLaunchUrl(payments://…)` to return true on iOS, add this to `ios/Runner/Info.plist`:
  <key>LSApplicationQueriesSchemes</key>
  <array>
    <string>payments</string>
  </array>

Notes
- On Android emulator, use `http://10.0.2.2:8092` as Base URL.
 
Automate patching after `flutter create .`
- Run: `bash scripts/apply_deeplinks.sh`

E2E Demo Flow
- Login: Phone `+963…`, OTP `123456`.
- Search: Set Origin/Destination/Date, tap “Search”.
- Book: Tap “Book” on a result.
- Payment: If a `payment_request_id` was created, a bottom sheet offers “Open in Payments”.
- Bookings: Check “Bookings” tab to view/cancel, or open the payment again.

Widget Tests
- You can run `flutter test` (add your own tests as needed).
