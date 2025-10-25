Bus (Intercity) — MVP Scope

Goals
- Enable users to search intercity bus trips and make simple bookings.
- MVP pricing, seat handling, and optional payment link via internal Payments API.

Endpoints (Bus API)
- POST `/auth/request_otp` — dev OTP delivery
- POST `/auth/verify_otp` — returns bearer token
- POST `/trips/search` — search trips by origin, destination, date
- POST `/bookings` — create booking (reserves seats and optionally creates a payment request)
- GET `/bookings` — list my bookings
- POST `/bookings/{id}/cancel` — cancel booking (frees seats)

Data Model (simplified)
- User(id, phone, name)
- Operator(id, name)
- Trip(id, operator_id, origin, destination, depart_at, arrive_at?, price_cents, seats_total, seats_available)
- Booking(id, user_id, trip_id, status: reserved|confirmed|canceled, seats_count, total_price_cents, payment_request_id?)

Dev Notes
- Trips are seeded on first search (Damascus→Aleppo/Homs) for today and tomorrow.
- Payments integration uses internal dev endpoint if configured.
- Client can deep-link to Payments app using scheme `payments://request/<id>` when booking creates a payment request.
