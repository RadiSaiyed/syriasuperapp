Bus Operators – Onboarding (DEV)

Goal
- Einen Bus‑Betreiber anlegen, eine Fahrt erstellen, Ticket buchen und QR am Operator‑UI scannen/boarden.

Voraussetzungen
- Payments API optional (für echte payment_request Verifikation), sonst bestätigt Bus auch ohne Request.
- Läuft lokal: `apps/bus` und `operators/bus_operators` via Docker Compose.

Starten
1) Bus API
   - `cd apps/bus && docker compose up -d db redis`
   - `docker compose up --build api`
2) Bus Operators API (UI)
   - `cd operators/bus_operators && docker compose up -d db redis api`
   - UI: http://localhost:8085/ui

Auth (DEV)
- Bus API: `POST /auth/dev_login` → {username,password} z.B. {"username":"admin","password":"admin"}
- Operators UI: `POST /auth/dev_login_operator` (auf :8085) → Token einfügen im UI‑Feld.

Operator anlegen (DEV)
- Bus API: `POST /operators/register` (Form‑Felder) z.B.:
  - name=Demo Operator
  - merchant_phone=+963999999999 (Wallet fürs Ticketgeld)

Fahrt erstellen
- `POST /operators/{operator_id}/trips` (Bearer vom Dev Login):
  {
    "origin":"Damascus",
    "destination":"Aleppo",
    "depart_at":"2025-11-01T08:00:00",
    "price_cents":200000,
    "seats_total":40
  }

Ticket kaufen (als Nutzer)
1) Dev‑Login (Bus API): `POST /auth/dev_login` → Nutzer‑Token
2) Suche: `POST /trips/search` {origin,destination,date}
3) Buchen: `POST /bookings` {trip_id,seats_count[,seat_numbers][,promo_code]}
   - Response enthält ggf. `payment_request_id` und `merchant_phone`
4) (Optional) Payment verifizieren: Bei akzeptiertem Request →
   `POST /bookings/{id}/confirm`
5) QR abrufen: `GET /bookings/{id}/ticket` → `qr_text = "BUS|<booking_id>"`

QR prüfen und Boarden (Operators UI)
1) Token ins Feld „Bearer Token“ einfügen (von /auth/dev_login_operator)
2) Operator‑ID eintragen
3) QR prüfen: „Tickets & Clone“ → Validate (z.B. BUS|<booking_id>)
4) Boarding: Booking ID eintragen → „Board“

CSV/Manifest/Reports
- Manifest: `GET /operators/{op}/trips/{trip}/manifest`
- Bookings CSV: Link im UI, oder `GET /operators/{op}/bookings.csv?status=confirmed`
- Zusammenfassung: `GET /operators/{op}/reports/summary?since_days=7`

Troubleshooting
- Migrationen: `cd apps/bus && make migrate`
- Payments nicht erreichbar: Buchung/Bestätigung weiter testbar; `payment_request_id` bleibt ggf. leer.

