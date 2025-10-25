Audit‑Trail (Unveränderliche Logs)

Ziel
- Nachvollziehbarkeit sicherstellen (Wer/Was/Wann/Wo), fälschungssicher (WORM/Append‑Only).

Ereignisse (Beispiele)
- login_success|failure, kyc_submit|approve|reject, payment_p2p, payment_qr, wallet_topup, voucher_redeem, request_accept|reject|cancel.

Technik
- Server: Append‑Only Store (z. B. WORM‑Bucket/Tamper‑evident Log), signierte Batches.
- Client: Best‑Effort Fire‑and‑Forget; keine Blockade der UX bei Audit‑Fehlern.
- Felder: event.type, ts, actor (user_id/phone maskiert), device, ip (serverseitig), details (ohne sensible PII).

Rechtliches
- Aufbewahrung nach lokalen Vorgaben; Zugriff nur für berechtigte Rollen; Datenschutz beachten.

