GDPR / Datenschutz – Architektur & Prozesse (Payments+)

Ziele
- Datenminimierung, Zweckbindung, Transparenz, Lösch- und Auskunftsrechte.

Technik & Prozesse
- Datenklassifizierung: PII, Finanz-/Transaktionsdaten, Telemetrie.
- Speicherorte: App (flüchtig), Backend DB, Objektspeicher (Belege), Logs (minimiert, PII-scrubbed).
- Aufbewahrung: Transaktionen gem. rechtl. Anforderungen (z. B. 10 Jahre), KYC-Dokumente gem. lokalen Vorgaben. Telemetrie max. 14–90 Tage.
- Löschkonzept: Konto-Schließung → Pseudonymisierung/Reduktion (Transaktionsreferenzen erhalten zur Buchhaltung), harte Löschung für optionale Daten (Kontakte, Notizen).
- Rechte: Export personenbezogener Daten (JSON/CSV), Berichtigung, Einschränkung, Widerspruch.
- Sicherheit: Verschlüsselung in Transit (TLS), Encryption‑at‑Rest im Backend, Secrets Rotation, Zugriffskontrollen (RBAC), Audit Logs.
- DPA: AV‑Vertrag mit Auftragsverarbeitern, Drittland-Übermittlungen prüfen.

Kundenkommunikation
- Privacy Policy (öffentlich), In‑App Datenschutzhinweis, Opt‑In für Telemetrie/Analytics.

