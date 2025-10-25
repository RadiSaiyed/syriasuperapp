Car Market Flutter Client (MVP)

Flutter client for the Car Market API (`apps/carmarket`).

Features
- Login via dev OTP (123456)
- Browse listings and create offers (buyer)
- My offers (buyer): open payment in Payments app if present
- My listings (seller): view offers, accept/reject; on accept show payment deep-link CTA
 - Global shortcut: wallet icon in the app bar opens the Payments app (`payments://`).

Run
1) Ensure Car Market API runs at http://localhost:8086 (see `apps/carmarket/README.md`).
2) If `android/` and `ios/` are missing, run: `flutter create .`
3) `flutter pub get`
4) `bash scripts/apply_deeplinks.sh`
5) `flutter run` and set Base URL in app (e.g., `http://localhost:8086`).

Deep links
- Launches `payments://request/<id>` for accepted offers. Run the Payments app to handle the link.
