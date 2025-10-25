AML / Sanktionsscreening & Transaktionsüberwachung

Bausteine
- KYC‑Daten geprüft (Name, Geburtsdatum, Dokumente).
- Screening: Sanktions-/Watchlists (UN/EU/OFAC), PEP/HIO via Provider.
- Transaktionsmonitoring: Regeln + ML‑Heuristiken (Velocity, Muster, Geografie, Gerät).

Prozessfluss
1) Bei KYC/Änderung: Screening → Freigabe oder Review.
2) Bei Transaktionen: Regeln evaluieren → ggf. Soft‑Block + manuelles Review.
3) Audit‑Trail: Alle Prüfungen und Entscheidungen protokollieren (unveränderlich).

Implementierung
- Server‑seitig (empfohlen): Pre‑/Post‑Transaction Hooks, Idempotenz, Audit.
- Client: Hinweise & UI‑Gründe anzeigen (z. B. „Limit überschritten“, „Review erforderlich“).

