Payments Web (React + Vite)

Quick start
- Prereq: Node 20+, npm, Payments API running at http://localhost:8080 (see apps/payments)
- Install deps: `npm install`
- Dev: `npm run dev` (opens http://localhost:5173)
- Build: `npm run build` then `npm run preview`

Config
- API base: set `VITE_API_BASE` env (default http://localhost:8080)

Features
- Dev OTP Login (request + verify)
- Wallet view (balance), Topup (dev), P2P transfer
- Merchant dev setup (approve KYC, become merchant), QR create with inline QR code
- Payment Links: create dynamic/static, pay links
- Subscriptions: create/list/cancel, dev charge
- Merchant Statement: JSON totals, CSV download

Tests
- Unit (Vitest): `npm run test:unit`
- E2E (Playwright): requires running Payments API; `npm run test:e2e`
