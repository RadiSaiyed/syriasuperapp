Livestock — MVP Scope

Goals
- Enable a simple marketplace for livestock (animals) and animal-derived farm products.

Data Model (MVP)
- User(id, phone, name, role: buyer|seller)
- Ranch(id, owner_user_id, name, location, description)
- AnimalListing(id, ranch_id, species, breed, sex, age_months, weight_kg, price_cents, status)
- ProductListing(id, ranch_id, product_type, unit, quantity, price_per_unit_cents, status)
- Order(id, buyer_user_id, type: product|animal, product_id?, animal_id?, qty, total_cents, status, payment_request_id?, payment_transfer_id?)

API Surface
- Auth: OTP (dev: 123456)
- Seller: create/get ranch; create/list/update animals & products; list orders for my ranch; create/list/close auctions
- Market: list/get animals & products (filters: q, species/type, unit, breed/sex, price range, location); favorites add/list/remove; place orders; list my orders
- Auctions: list/get auctions; place bids; seller close to finalize sale and create an order for the highest bidder

Payments Handoff (optional)
- If `PAYMENTS_BASE_URL` and `PAYMENTS_INTERNAL_SECRET` are set, orders create Payment Requests.
- Webhook endpoint `/payments/webhooks` confirms orders on acceptance if `PAYMENTS_WEBHOOK_SECRET` matches the one configured in Payments.

Observability
- `/metrics` Prometheus endpoint with `service="livestock"` label on request counter.

Out of Scope (MVP)
- Auctions/bidding, health certifications, transport logistics, vet records.
- Media uploads; use links/static placeholders in UIs.
