# Food Flutter Client

Minimal Flutter client for the Food Delivery API.

Setup
1) Ensure Food API runs at http://localhost:8090 (see `apps/food/README.md`). For richer demo content (mehr Seed‑Daten), führe aus:
   - `make food-seed` (Default‑DB: `postgresql+psycopg2://postgres:postgres@localhost:5443/food`)
2) If platforms are missing, run: `flutter create .`
3) Install deps: `flutter pub get`
4) Run: `flutter run`

Notes
- Home‑Screen im Lieferando‑Stil: Suche, Kategorien (Chips), Banner, Restaurant‑Cards (Bild, Bewertung, ETA/Delivery‑Badge — demo‑basiert).
- Use the app bar Ethernet icon to change the base URL.
- Login uses dev OTP (phone `+963…`, OTP `123456`).
- Payments shortcut: tap the wallet icon in the app bar to open the Payments app (`payments://`).
