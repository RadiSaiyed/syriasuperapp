Superapp Shared Library (Python)

Location
- libs/superapp_shared/

Modules
- superapp_shared.otp
  - OTPConfig(mode, ttl_secs, max_attempts, redis_url, dev_code, storage_secret, dev_mode)
  - OTPSendResult(code, session_id, is_dev)
  - send_and_store_otp(phone, cfg, session_id=None, device_key=None, client_id=None)
  - verify_otp_code(phone, code, cfg, session_id=None, device_key=None, client_id=None)
  - consume_otp(phone, cfg, session_id=None, client_id=None)
- superapp_shared.rate_limit
  - SlidingWindowLimiter (in-memory)
  - RedisRateLimiter (fixed window/min)
- superapp_shared.internal_hmac
  - sign_internal_request_headers(payload, secret, ts=None, request_id=None)
  - verify_internal_hmac_with_replay(ts, payload, sign, secret, redis_url=None, ttl_secs=60)

Adoption
- Apps import wrappers that delegate to this shared lib. No public API change inside apps (routers keep current imports).
- Tests: tools/health_check.sh adds PYTHONPATH to libs/superapp_shared.
- Docker builds: follow-up step — either set build context to repo root and COPY libs/superapp_shared, or package and publish the lib.

HMAC Standard
- Signature covers `ts + compact_json(payload)` with SHA256 and hex encoding.
- Headers: `X-Internal-Ts`, `X-Internal-Sign` (+ optional `X-Request-ID`).
- Payments service verifies via the same logic with optional Redis replay protection.

Metrics & Dashboards
- Added `commerce_orders_total{status}` and `doctors_appointments_total{status}` counters.
- Grafana dashboards: ops/observability/grafana/dashboards/{commerce.json, doctors.json}.

E2E Orchestrator
- tools/e2e_orchestrator.py triggers core flows.
  - env: COMMERCE_BASE_URL, DOCTORS_BASE_URL, PHONE_A, NAME_A, FLOWS
