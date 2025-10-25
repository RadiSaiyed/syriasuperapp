# Jobs Flutter Client

Minimal Flutter client for the Jobs (Job Board) API.

Setup
1) Ensure Jobs API runs at http://localhost:8087 (see `apps/jobs/README.md`).
2) In this folder, if missing platforms, run: `flutter create .`
3) Install deps: `flutter pub get`
4) Run: `flutter run`

Notes
- Use the top-right Ethernet icon to change the base URL.
- Login uses the dev OTP flow (enter any phone like `+963...`, OTP is `123456`).
- To post jobs, create a company first in the Employer tab.
