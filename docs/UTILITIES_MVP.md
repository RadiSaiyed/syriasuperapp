Utilities — MVP Scope

Goals
- Provide basic bill payments and mobile top-ups.
- Integrate with Payments API via internal dev endpoint to create payment requests.

Endpoints (Utilities API)
- POST `/auth/request_otp`, `/auth/verify_otp`
- GET `/billers` — list billers
- POST `/accounts/link` — link a biller account (meter/phone)
- GET `/accounts` — list my biller accounts
- POST `/bills/refresh?account_id=...` — seed/fetch dummy bills for an account
- GET `/bills` — list my bills
- POST `/bills/{id}/pay` — create a payment request for a bill
- POST `/topups` — create a mobile top-up payment request
- GET `/topups` — list my top-ups

Data Model (simplified)
- User(id, phone, name)
- Biller(id, name, category)
- BillerAccount(id, user_id, biller_id, account_ref, alias?)
- Bill(id, user_id, biller_id, account_id, amount_cents, status, due_date?, payment_request_id?)
- Topup(id, user_id, operator_biller_id, target_phone, amount_cents, status, payment_request_id?)

Dev Notes
- Bills are seeded on first refresh for a linked account.
- Payments handoff uses fee wallet as placeholder receiver.

