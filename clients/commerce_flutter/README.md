Commerce Flutter Client (MVP)

Simple Flutter client for the Commerce API (`apps/commerce`).

Features
- Login via dev OTP (123456)
- Browse shops and products
- Add to cart, update quantities, clear cart
- Checkout to create order
- View orders and open payment in Payments app via deep link when available

Run
1) Ensure Commerce API runs at http://localhost:8083 (see `apps/commerce/README.md`).
2) If `android/` and `ios/` are missing, run: `flutter create .`
3) In this folder: `flutter pub get`
4) Run: `flutter run`
5) In the app, set Base URL to your API (e.g. `http://localhost:8083`).

Notes
- On Android emulator, use `http://10.0.2.2:8083` as Base URL.
- To open payment requests directly in the Payments app, also run the Payments Flutter app from `clients/payments_flutter`.
- Payments shortcut: the app bar has a wallet icon to open the Payments app (`payments://`).

iOS scheme whitelist (for launching deep links)
- If you want `canLaunchUrl(payments://…)` to return true on iOS, add this to `ios/Runner/Info.plist`:
  ```xml
  <key>LSApplicationQueriesSchemes</key>
  <array>
    <string>payments</string>
  </array>
  ```

Automate patching after `flutter create .`
- Run: `bash scripts/apply_deeplinks.sh`

E2E Demo Flow
- Login: Phone `+963…`, OTP `123456`.
- Shops: Browse shops, open a shop and add a product to cart.
- Cart: Adjust quantities, then Checkout.
- Payment: After checkout a bottom sheet offers “Open in Payments”.
- Orders: View order history and open payment again if needed.

Widget Tests
- You can run `flutter test` (add your own tests as needed).
