# Taxi Webhook Simulation — Quick Runbook

Purpose: simulate Partner → Taxi webhooks (HMAC signed) from the Taxi Partners operator `/ui`.

Prereqs
- Start Taxi API: `./sup up taxi` (port defaults to 8081)
- Start Taxi Partners operator: `./sup op up taxi_partners`
- Obtain a JWT (dev phone OTP) for Taxi Partners.

Steps
1) Open Taxi Partners `/ui` (check docker-compose for mapped port) and paste the JWT.
2) Register a partner (dev): fill name/key_id/secret → “Register Partner”.
3) Map driver (dev): partner_key_id + external_driver_id + driver_phone → “Map Driver”.
4) Create dispatch: ride_id + partner_key_id (+ optional external_trip_id) → “Create Dispatch”.
5) Simulate webhooks → Taxi:
   - Base URL: default `http://localhost:8081` (override in UI or set env `TAXI_BASE`).
   - Ride Status: partner_key_id, external_trip_id, status (accepted|enroute|completed|canceled), optional final_fare_cents → “Send”.
   - Driver Location: partner_key_id, external_driver_id, lat, lon → “Send”.

Notes
- Requests are HMAC-signed server-side using the Partner secret.
- Taxi API validates HMAC via `verify_internal_hmac_with_replay` (replay-safe if Redis is configured).
- If you see 403 `bad_signature`, verify partner_key_id/secret and clocks; for 404 `dispatch_not_found`, ensure a dispatch exists for the external_trip_id.

