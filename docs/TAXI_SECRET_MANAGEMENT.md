# Taxi Service – Secret & Credential Management

| Secret | Purpose | Notes |
| ------ | ------- | ----- |
| `JWT_SECRET` / `JWT_SECRETS` | API token signing | Use at least 32 random bytes. Prefer rotating list (`JWT_SECRETS=cur,prev`). For asymmetric setups set `JWT_JWKS_URL`. |
| `PAYMENTS_INTERNAL_SECRET(S)` | HMAC between Taxi and Payments | Length ≥32 chars. Provide active + standby secrets via `PAYMENTS_INTERNAL_SECRETS`. |
| `ADMIN_TOKEN` / `ADMIN_TOKEN_SHA256` | Protect maintenance endpoints | In production set `ADMIN_TOKEN_SHA256` to one or more SHA-256 digests. Plain tokens are only allowed for dev. |
| `OTP_SMS_PROVIDER` | Choose SMS backend (`log` or `http`) | When `http`, configure `OTP_SMS_HTTP_URL` (and optional `OTP_SMS_HTTP_AUTH_TOKEN`). |
| `OTP_MODE` | OTP persistence | `redis` in staging/prod. Requires `REDIS_URL`. |
| `OTP_SMS_TEMPLATE` | Custom text for SMS | Supports `{code}` placeholder. |
| `TAXI_POOL_WALLET_PHONE`/`TAXI_ESCROW_WALLET_PHONE` | Wallet routing | Should be dedicated corporate wallets inside Payments. |
| `ADMIN_IP_ALLOWLIST` | Optional IP restriction | Comma-separated public IPs allowed to call admin endpoints. |

## Rotation Checklist

1. Generate new secret (e.g. `openssl rand -hex 32`).
2. Update Kubernetes/Compose secret (`PAYMENTS_INTERNAL_SECRETS=new,old`).
3. Reload services (Payments first, then Taxi).
4. Remove retired secret after confirming logs/metrics show no validation errors.

## OTP SMS

Configure environment:

```
OTP_MODE=redis
OTP_SMS_PROVIDER=http
OTP_SMS_HTTP_URL=https://sms-gateway.internal/api/send
OTP_SMS_HTTP_AUTH_TOKEN=replace-with-bearer-token
OTP_SMS_TEMPLATE=Your Taxi code is {code}
```

For staging, switch back to `OTP_SMS_PROVIDER=log` to avoid sending real SMS.

## Admin token hashing

Generate SHA-256 digest of the admin token to avoid storing plaintext values:

```bash
echo -n 'very-secret-admin-token' | sha256sum
# => 4f4c... digest
```

Set `ADMIN_TOKEN_SHA256=4f4c...` and leave `ADMIN_TOKEN` empty. Multiple digests can be supplied separated by commas for gradual rotation.
