Utilities Flutter Client (MVP)

Simple Flutter client for the Utilities API (`apps/utilities`).

Features
- Login via dev OTP (123456)
- Browse billers and link accounts (meter/phone)
- Refresh and view bills, pay bill (opens Payments app via deep link when available)
- Create mobile top-ups and view history (open in Payments via deep link)

Run
1) Ensure Utilities API runs at http://localhost:8084 (see `apps/utilities/README.md`).
2) If `android/` and `ios/` are missing, run: `flutter create .`
3) In this folder: `flutter pub get`
4) Run: `flutter run`
5) In the app, set Base URL to your API (e.g. `http://localhost:8084`).

Deep link handoff
- This client launches `payments://request/<id>` for bill payments and top-ups. Run the Payments app (`clients/payments_flutter`) to handle the link.
- iOS whitelist: add to `ios/Runner/Info.plist`:
  <key>LSApplicationQueriesSchemes</key>
  <array>
    <string>payments</string>
  </array>
- Or run: `bash scripts/apply_deeplinks.sh` after `flutter create .` to patch automatically.
 - Global shortcut: app bar wallet icon opens the Payments app anytime.

E2E Demo Flow
- Bills
  1) Login (Phone `+963…`, OTP `123456`).
  2) Tab Billers: Link an Electricity account (e.g., `METER-123`).
  3) Tab Bills: Select the linked account (auto-selected) and press refresh (top-right) if needed.
  4) Pay a bill → Bottom sheet offers “Open in Payments” to approve.
- Top-ups
  1) Tab Top-up: Choose operator (MTN/Syriatel), enter target phone and amount (e.g., 5000).
  2) Create Top-up → Bottom sheet offers “Open in Payments”.
  3) Tab Top-ups: View history and open payment again if needed.

Widget Tests
- Run: `flutter test`
- Included: `test/login_smoke_test.dart` to verify Login screen renders.
