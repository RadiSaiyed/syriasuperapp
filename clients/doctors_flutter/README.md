# Doctors Flutter Client

Minimal Flutter client for the Doctors API (appointments).

Setup
1) Ensure Doctors API runs at http://localhost:8089 (see `apps/doctors/README.md`).
2) In this folder, if platforms are missing, run: `flutter create .`
3) Install deps: `flutter pub get`
4) Run: `flutter run`

Notes
- Change Base URL via the Ethernet icon.
- Login uses dev OTP: phone `+963…`, OTP `123456`.
- Roles: patient (search/book, see appointments) or doctor (profile, add slots, view appointments).
- Payments shortcut: wallet icon in app bar opens the Payments app (`payments://`).
