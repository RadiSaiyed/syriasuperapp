PCI Scope (Kartenintegration – optional)

Strategie
- PCI‑Scope minimieren: Keine Kartendaten im Backend/App verarbeiten; stattdessen PSP mit tokenisierten Zahlungen (PCI Level beim PSP).
- 3DS/Strong Customer Authentication via PSP SDK/WebView.

Empfehlungen
- Client: Nur PSP‑SDK einbinden; PaymentMethod‑Token speichern (nicht PAN/CVV).
- Backend: Nur Tokens/PaymentIntents, Webhooks verifizieren, Idempotenz sicherstellen.
- Logs: Keine PAN/CVV, keine sensiblen Daten.

Compliance
- Falls dennoch Kartendaten → SAQ‑D Anforderungen, Segmentierung, strenge Kontrollen. Empfehlung: vermeiden.

