# Operator UIs — Quick Runbook

Purpose: quick, click-through smoke tests for each operator API at `/ui` using a pasted JWT token.

Prereqs
- Start the target operator via Docker Compose or `./sup`:
  - List: `./sup op list`
  - Up:   `./sup op up <name>` (e.g. `bus_operators`, `food_operator`)
- Obtain a JWT via each domain’s `/auth` flow (phone OTP) or seed scripts.

General `/ui` usage
1) Open the service base URL (see docker-compose.yml for the mapped port), then `/ui`.
2) Paste the JWT in the “Bearer Token” field.
3) Use the prewired buttons/inputs to call typical operator endpoints.

Highlights per service

- Bus Operators
  - Trips: list trips, manifests; export bookings CSV; reports summary.
  - Tickets: validate QR (`BUS|<booking_id>`), mark boarded.
  - Admin: branches (list/create/update/delete), vehicles (list/create/update/delete), promos (list/create/update/delete).
  - Clone Trip: clone by date range + weekdays.

- Food Operator
  - Categories/Modifiers/Items/Stations management; KDS bump; Orders bulk status.
  - Bulk stock via CSV/XLSX; Reports summary + payout XLSX/PDF.
  - Admin extras: Create Restaurant; Hours get/set (JSON + override); Menu Item create; Restaurant Images add/list.

- Doctors (Doctor)
  - Profile upsert, slots list/create, appointments list/status.
  - Images add/list/delete.

- Stays Host
  - Properties/Units create/list; Reservations confirm/cancel.
  - Property Images add/list/delete; Unit Blocks add/list/delete; Unit Prices set/get.

- Freight Carrier
  - Filter available loads; set location; create bid; list my bids.

- Freight Shipper
  - Post and list loads; list bids for load; accept/reject bid.

- Jobs Employer
  - Company create/get; Jobs create/list; Applications list/status.
  - Update job tags via PATCH (comma-separated in UI helper).

Troubleshooting
- 401/403 → verify you pasted a valid JWT with the expected role/membership.
- 404 → check IDs (operator_id/restaurant_id/trip_id) and service ports.
- CORS/localhost redirects → prefer calling from the same host + mapped port.

