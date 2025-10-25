Agriculture — MVP Scope

Goals
- Offer a light-weight Agriculture vertical combining:
  - Farmers: create farm, publish produce listings
  - Seasonal workers: browse and apply to farm jobs
  - Buyers: browse produce and place simple orders

Non-Goals (MVP)
- No payments capture; orders are created as `created` only. Later integrate via Payments internal API.
- No delivery/fulfillment orchestration beyond status fields.
- No complex inventory or auctions; single-quantity reservation semantics.

Data Model (MVP)
- User(id, phone, name, role: buyer|farmer|worker)
- Farm(id, owner_user_id, name, location, description)
- Listing(id, farm_id, produce_name, category, quantity_kg, price_per_kg_cents, status)
- Order(id, buyer_user_id, listing_id, qty_kg, total_cents, status)
- Job(id, farm_id, title, description, location, wage_per_day_cents, start_date, end_date, status)
- Application(id, job_id, user_id, message, status)

API Surface
- Auth: OTP (dev: 123456)
- Farmer: create/get farm; create/list/update listings; create/list jobs; view applicants; update application status; list orders of my listings
- Market: list/get listings; place order; list my orders
- Jobs: list/get jobs; apply; list my applications; withdraw

Observability
- `/metrics` Prometheus endpoint with basic request counter labeled `service="agriculture"`.

Payments Handoff & Webhook
- Optional: set `PAYMENTS_BASE_URL`, `PAYMENTS_INTERNAL_SECRET`, `FEE_WALLET_PHONE` to create a Payment Request on order.
- To auto-confirm orders on payment acceptance, expose `/payments/webhooks` and set `PAYMENTS_WEBHOOK_SECRET` to match the secret configured in Payments when registering the webhook.

Next Steps
- Payments handoff: create payment requests per order and confirm on webhook
- Attach simple media/photos for listings
- Price units and measurement variants (kg, crate, ton)
- Bulk upload for farmers; location-based discovery improvements
