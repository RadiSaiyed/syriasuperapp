Car Rental — MVP Scope

Goals
- Simple rental marketplace: sellers manage vehicles, renters browse and book.

Data Model (MVP)
- User(id, phone, name, role: renter|seller)
- Company(id, owner_user_id, name, location, description)
- Vehicle(id, company_id, make, model, year, transmission, seats, location, price_per_day_cents, status)
- Booking(id, user_id, vehicle_id, start_date, end_date, days, total_cents, status, payment_request_id?, payment_transfer_id?)

API Surface
- Auth: OTP (dev: 123456)
- Company/Seller: create/get company; add/list/update vehicles; list orders (bookings)
- Market: list/get vehicles (filters: q, location, make, transmission, seats_min, price range, availability window); favorites add/list/remove; book; list my bookings
- Payments (optional): create Payment Request for booking and confirm via `/payments/webhooks` using HMAC secret

Observability
- `/metrics` Prometheus endpoint (`service="carrental"` label on request counter)

Non-Goals (MVP)
- Insurance handling, deposits, damage claims, driver KYC beyond OTP, delivery logistics.
