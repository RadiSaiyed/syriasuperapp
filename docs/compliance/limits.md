Limits & Velocity Checks

Beispiel-Policy (abhängig von KYC-Level)
- Level 0 (unverifiziert): max 50k SYP pro Transaktion, 100k SYP / Tag outgoing, 200k SYP / Monat outgoing.
- Level 1 (Basis-KYC): 500k SYP / Tx, 2M SYP / Tag, 10M SYP / Monat.
- Level 2 (voll KYC): höhere/individuelle Limits nach Risiko.

Velocity & AML
- Heuristiken: Häufung kleiner Beträge, neue Empfänger, Geo/Device-Änderungen.
- Maßnahmen: Soft-Block, zusätzliche Verifikation, manuelles Review.

Implementierung (Server)
- Durchsetzen in der API (authz layer) mit Idempotenz, atomaren Zählern (pro Tag/Monat) und Audit‑Trail.
- Client zeigt Limits an (read‑only) und erklärt Ablehnungsgründe.

