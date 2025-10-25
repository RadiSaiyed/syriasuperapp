Device Integrity (Play Integrity / App Attest)

Android (Play Integrity)
- Serverseitig prüfen (nonce ↔ request binding):
  1) Client fordert Nonce vom Backend (gebundene Session/Request‑Daten, z. B. user_id, device_id, ts)
  2) Client ruft Play Integrity API (Native/SDK) und sendet token + nonce ans Backend
  3) Backend validiert Token bei Google API und erzwingt Policy

iOS (DeviceCheck / App Attest)
- Empfehlung: App Attest (starke Bindung an Device + Key) oder DeviceCheck (leichter, dafür schwächer)
  1) Client erstellt Attestation/Assertion mit App Attest
  2) Backend prüft über Apple API und erzwingt Policy

Client‑Integration (geplant)
- Flutter Plugins/Native Bridges einbinden; API‑Endpunkte im Backend bereitstellen: /integrity/nonce, /integrity/verify
- Token an kritische Transaktionen koppeln (Top‑Up, Payments, Voucher)

