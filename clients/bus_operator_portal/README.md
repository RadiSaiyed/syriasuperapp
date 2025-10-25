Bus Operator Portal (Flutter Web/Desktop)

Minimal portal for bus operators to manage trips, view bookings, see a simple summary, and validate tickets.

Prerequisites
- Flutter SDK 3.x installed
- Bus API running locally (`apps/bus`) with operator endpoints (DEV)
- Optional: Payments service with `PAYMENTS_BASE_URL` and `PAYMENTS_INTERNAL_SECRET` configured in Bus `.env`

Setup
1) `cd clients/bus_operator_portal`
2) If platform folders are missing, generate them:
   - `flutter create .`
3) Install dependencies:
   - `flutter pub get`
4) Run (web or desktop):
   - Web: `flutter run -d chrome`
   - macOS: `flutter run -d macos`

Config
- Default API base URL: `http://localhost:8082`
- You can change it from the settings icon in the app header.

Features (MVP)
- OTP login (DEV: 123456)
- Operator selection (from `/operators/me`)
- Trips: list/create/update/delete, set optional arrive time, bus model/year
- Trips: seat map viewer (reserved seats highlighted)
- Bookings: list and confirm/cancel; shows assigned seat numbers
- Summary: simple KPIs (bookings, revenue, occupancy)
- Tickets: paste QR or scan via camera to validate, see seats, and mark boarded
- Members: admin can list/add/remove members and set roles (admin/agent)

Notes
- This is a minimal reference portal; extend auth, roles, and UI as needed.
 - Camera usage requires granting permission; on iOS/Android ensure proper Info.plist/AndroidManifest camera permissions for production.
