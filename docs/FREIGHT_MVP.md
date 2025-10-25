Freight — MVP Scope

Goals
- Shippers post loads, carriers accept and deliver.
- Simple lifecycle: posted → assigned → picked_up → in_transit → delivered.
- Payments handoff to internal Payments API on delivery (shipper → carrier) with optional platform fee.

Endpoints (Freight API)
- POST `/auth/request_otp`, `/auth/verify_otp`
- POST `/shipper/loads` — create a load
- GET `/shipper/loads` — list my loads (as shipper)
- GET `/carrier/loads/available` — list posted loads
- POST `/carrier/apply` — become a carrier (dev-approved)
- POST `/loads/{id}/accept` — carrier accepts a load
- POST `/loads/{id}/pickup`, `/loads/{id}/in_transit`, `/loads/{id}/deliver` — status updates
- GET `/loads` — list my loads (as shipper or carrier)

Data Model (simplified)
- User(id, phone, name, role: shipper|carrier)
- CarrierProfile(id, user_id, company_name, status)
- Load(id, shipper_user_id, carrier_id?, status, origin, destination, weight_kg, price_cents, payment_request_id?)

Dev Notes
- Carrier apply auto-approves in dev.
- Payments handoff uses internal endpoint; failures are ignored in dev.

