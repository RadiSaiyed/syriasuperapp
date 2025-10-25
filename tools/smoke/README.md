Smoke Tests
===========

Quick health + OTP tests hitting running services via HTTP.

Run
- Payments: `bash tools/smoke/payments_otp_check.sh` (defaults to http://localhost:8080)
- Food: `bash tools/smoke/food_otp_check.sh` (defaults to http://localhost:8090)

Options
- Override base URLs with `BASE` env var, e.g. `BASE=http://payments.local bash tools/smoke/payments_otp_check.sh`

