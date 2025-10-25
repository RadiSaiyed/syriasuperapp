Super‑App SSO Plan (Payments as IdP)

Goal
- Single sign‑on (OTP) via the Payments service, trusted tokens for all verticals.

Approach
1) Payments as Identity Provider
   - Issue JWTs with standard claims (`sub`, `phone`, `iat`, `exp`, `iss`, `aud`).
   - Publish public key (JWKS), e.g. `GET /.well-known/jwks.json`.
   - `aud` can be an array, e.g. ["users", "superapp"].

2) Services validate tokens
   - Verticals validate signatures using JWKS; no shared secret required.
   - Verify claims: `iss == payments`, and `aud` contains the expected audience.
   - Optional: a token‑exchange endpoint in Payments to issue short‑lived, service‑specific tokens.

3) Super‑App client
   - Authenticate only against Payments; keep tokens in secure storage (per env).
   - For vertical API calls either:
     a) Pass the Payments token directly (if the vertical accepts Payments as issuer), or
     b) Obtain a service token via token‑exchange before the call.

4) Migration (MVP → Prod)
   - MVP: Each service has its own OTP auth (current state) → gradually switch verticals to JWKS validation.
   - Super‑App: Switch to Payments as the single login once all verticals support JWKS.

5) Security
   - Rotating signing keys in Payments (key IDs, `kid` in JWT).
   - Short‑lived tokens (e.g., 24h) + refresh via encrypted refresh token or OTP re‑login.
   - Optional scope/role claims (e.g., `is_merchant`, `is_driver`).

Roadmap
- [ ] Payments: JWKS endpoint, RS256 signature, key rotation
- [ ] Verticals: JWT middleware with JWKS cache
- [ ] Super‑App: single login screen → Payments, token propagation
