Payments MVP — Scope and Architecture

Goals (Phase 1)
- Phone‑number identity with dev OTP
- User wallet in SYP with balance
- P2P transfer by phone number (idempotent, safe)
- Merchant QR: create dynamic QR for amount; pay by scanning
- Basic transaction history

Non‑Goals (Phase 1)
- Real KYC/AML, sanctions screening, risk engine
- Settlement with banks/telcos, card rails
- Multi‑currency, FX, cross‑border
- Production‑grade OTP/SMS, HSM, PCI DSS

Architecture
- API: FastAPI + SQLAlchemy + Postgres
- Auth: JWT (dev only), phone + OTP stub (123456)
- Data: double‑entry ledger with wallet balance
- Idempotency: Idempotency‑Key header for monetary ops
- Concurrency: row‑level locks (FOR UPDATE)
- Metrics: Prometheus `/metrics`; simple in‑memory rate limiting (dev)
 - Policies: KYC min‑level for merchant features (default: 1)

Key Data Model
- users(id, phone, name, is_merchant, merchant_status, kyc_level, kyc_status, created_at)
- wallets(id, user_id, balance_cents, currency_code, created_at)
- transfers(id, from_wallet_id?, to_wallet_id, amount_cents, currency_code, status, idempotency_key, created_at)
- ledger_entries(id, transfer_id, wallet_id, amount_cents_signed, created_at)
- merchants(id, user_id, wallet_id, created_at)
- qr_codes(id, merchant_id, code, amount_cents, currency_code, expires_at, status, created_at)
- payment_requests(id, requester_user_id, target_user_id, amount_cents, currency_code, status, created_at, updated_at)

API Surface (MVP)
- POST /auth/request_otp
- POST /auth/verify_otp -> JWT, creates user+wallet if new
- GET  /wallet -> balance
- POST /wallet/topup (dev only)
- POST /wallet/transfer (Idempotency‑Key)
- POST /payments/merchant/qr (merchant only)
- POST /payments/merchant/pay (Idempotency‑Key)
- GET  /transactions
- GET  /kyc, POST /kyc/submit (dev: /kyc/dev/approve)
- POST /payments/merchant/apply, GET /payments/merchant/status (dev: /payments/dev/become_merchant)
- POST /requests — create a payment request (requester → target by phone)
- GET  /requests — list incoming/outgoing
- POST /requests/{id}/accept — payer accepts and pays
- POST /requests/{id}/reject — payer rejects
- POST /requests/{id}/cancel — requester cancels
- POST /cash/cashin/request — user requests cash‑in
- POST /cash/cashout/request — user requests cash‑out
- GET  /cash/requests — user: own; agent: incoming pending
- POST /cash/requests/{id}/accept — agent settles and transfers funds
- POST /cash/requests/{id}/reject — agent rejects
- POST /cash/requests/{id}/cancel — user cancels

QR Format (MVP)
- String: `PAY:v1;code=<opaque>`; `code` maps to server QR record.

Security Notes
- Use HTTPS and JWT in production
- Validate amounts, prevent negative and overflow
- Enforce idempotency for all money‑moving ops
- KYC enforcement: per‑transaction and daily limits by level; min KYC for merchant features

Fees
- Merchant fee (bps) debited from merchant after settlement → fee wallet
- Cash‑in fee (bps) debited from agent; Cash‑out fee (bps) debited from user
- Env vars: `MERCHANT_FEE_BPS`, `CASHIN_FEE_BPS`, `CASHOUT_FEE_BPS`, `FEE_WALLET_PHONE`
