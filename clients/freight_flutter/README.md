Freight Flutter Client (MVP)

Simple Flutter client for the Freight API (`apps/freight`).

Features
- Login via dev OTP (123456)
- Shipper: Post a load and view my loads
- Carrier: Apply (dev), browse available loads, accept and update status (pickup → in transit → deliver)
- On delivery, open payment in Payments app via deep link when a request is created

Run
1) Ensure Freight API runs at http://localhost:8085 (see `apps/freight/README.md`).
2) If `android/` and `ios/` are missing, run: `flutter create .`
3) In this folder: `flutter pub get`
4) Run: `flutter run`
5) In the app, set Base URL to your API (e.g. `http://localhost:8085`).

Deep link handoff
- This client launches `payments://request/<id>` after delivery. Run the Payments app (`clients/payments_flutter`) to handle the link.
- iOS whitelist: add to `ios/Runner/Info.plist`:
  <key>LSApplicationQueriesSchemes</key>
  <array>
    <string>payments</string>
  </array>
- Or run: `bash scripts/apply_deeplinks.sh` after `flutter create .` to patch automatically.
 - Global shortcut: wallet icon in app bar opens the Payments app.

E2E Demo Flow
- Login: Phone `+963…`, OTP `123456`.
- Shipper: Post a load (Damascus → Aleppo, weight, price).
- Carrier: Apply, view available loads, Accept, then Pickup → In transit → Deliver.
- Payment: On deliver a bottom sheet offers “Open in Payments”.
