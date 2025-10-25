# Patient Flutter App

Minimal patient app focusing on doctor appointment booking.

Setup
1) Ensure Doctors API runs at http://localhost:8089 (see `apps/doctors/README.md`).
2) If platforms are missing, run in this folder: `flutter create .`
3) Install deps: `flutter pub get`
4) Run: `flutter run`

Notes
- Change Base URL via the Ethernet icon in the app bar.
- Login uses dev OTP: phone `+963…`, OTP `123456`.
- Current scope: search slots, book, and view my appointments.
- Payments shortcut: app bar wallet icon opens the Payments app.
