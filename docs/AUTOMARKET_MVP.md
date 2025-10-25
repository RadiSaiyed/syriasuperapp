Car Market — MVP Scope

Goals
- Allow sellers to post car listings and buyers to make offers.
- On seller acceptance, create a payment request (buyer → seller) via Payments internal API.

Endpoints (Car Market API)
- POST `/auth/request_otp`, `/auth/verify_otp`
- POST `/listings` — create a listing
- GET `/listings` — browse listings
- GET `/listings/mine` — my listings (seller)
- POST `/offers/listing/{id}` — create offer
- GET `/offers` — my offers (buyer)
- POST `/offers/{id}/accept`, `/offers/{id}/reject` — seller decision

Data Model (simplified)
- User(id, phone, name)
- Listing(id, seller_user_id, title, make?, model?, year?, price_cents, description?)
- Offer(id, listing_id, buyer_user_id, amount_cents, status, payment_request_id?)

Dev Notes
- Payments handoff is best-effort and ignored on failure in dev.
