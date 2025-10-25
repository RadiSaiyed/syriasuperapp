# Chat Flutter Client

Minimal Flutter client for the Chat API (Threema-like, server stores only ciphertext).

Setup
1) Ensure Chat API runs at http://localhost:8091 (see `apps/chat/README.md`).
2) If platforms are missing, run: `flutter create .`
3) Install deps: `flutter pub get`
4) Run: `flutter run`

Notes
- Change Base URL via the Ethernet icon in the app bar.
- Login uses dev OTP: phone `+963…`, OTP `123456`.
- For MVP, message content is treated as "ciphertext" (no E2E in client).
