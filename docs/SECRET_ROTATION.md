Secret Rotation Runbook — Taxi

Scope
- JWT secrets (HS256) used by Taxi API to sign/verify access tokens
- Payments Internal HMAC secret(s) used to sign internal requests to Payments

Principles
- Backward compatible verification during rotation (accept old + new), sign only with new
- Orderly rollout across services to avoid auth breakage

Config knobs
- JWT (HS256):
  - Current: `JWT_SECRET`
  - Previous: `JWT_SECRET_PREV` (optional)
  - Or CSV list with current first: `JWT_SECRETS="new,old"`
  - Alternative: `JWT_JWKS_URL` (use RS256 + JWKS; rotation handled by JWKS server)
- Payments HMAC:
  - Current: `PAYMENTS_INTERNAL_SECRET`
  - Previous: `PAYMENTS_INTERNAL_SECRET_PREV` (optional)
  - Or CSV list with current first: `PAYMENTS_INTERNAL_SECRETS="new,old"`

Rotation steps (HS256 scenario)
1) Prepare new secrets
   - Generate cryptographically strong tokens (>= 32 chars for Payments secret; >= 16 chars for JWT)
2) Update verification on both sides
   - Payments: add new secret to allow list; keep old for verification
   - Taxi: set `PAYMENTS_INTERNAL_SECRETS="new,old"` (current first)
   - Taxi: set `JWT_SECRETS="new,old"` (if Taxi also verifies inbound JWTs from another issuer)
3) Switch signing to new
   - Taxi automatically signs JWTs with the first item in `JWT_SECRETS`
   - Taxi signs internal requests with the first item in `PAYMENTS_INTERNAL_SECRETS`
4) Monitor
   - Check 401/403 spikes, Payments HMAC errors, and token decode errors
5) Remove old secrets
   - After a safe period (e.g., JWT exp window + buffer), remove old from lists

JWT with JWKS (recommended)
- Set `JWT_JWKS_URL` and optional `JWT_VALIDATE_AUD/ISS` env; Taxi will verify RS256 via JWKS
- Rotation is handled by JWKS provider (e.g., OIDC), no HS secrets needed

Verification checklist
- Endpoints behave normally; no increase in 401
- Payments accepts internal calls signed by new secret
- Logs do not show `Invalid token` or `bad_signature` spikes

