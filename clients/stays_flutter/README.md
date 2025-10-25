# Stays Flutter Client

Minimal Flutter client for the Stays API (Hotels & Vacation Rentals).

Setup
1) Ensure Stays API runs at http://localhost:8088 (see `apps/stays/README.md`).
2) In this folder, if platforms are missing, run: `flutter create .`
3) Install deps: `flutter pub get`
4) Run: `flutter run`

Notes
- Use the Ethernet icon in the app bar to change the base URL.
- Login uses dev OTP flow: phone `+963…`, OTP `123456`.
- Roles: guest (search/book, see reservations) or host (create property, add units, list host reservations).
- Payments shortcut: the app bar includes a wallet icon to open the Payments app.
