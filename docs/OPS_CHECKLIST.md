Super‑App Operations — Daily/Weekly Checklist (MVP)

Daily
- Review status: `bash tools/superapp_status.sh` (all services UP?)
- Prometheus/Grafana: Errors (5xx), p95 latency, request volume per service
- Payments: gross/fees/net, webhook retries (if any), fee wallet balance trend
- Support inbox: refund requests, failed payments, KYC escalations
- Queues/backlogs: webhook deliveries pending/retrying

Weekly
- SLO review: payments success rate, error budget burn, top endpoints p95
- Fees/Revenue: compare MDR/Cash‑in/out fees vs. targets
- Capacity: DB size, slow queries, CPU/mem for busiest apps
- Security: rotate tokens for internal HMAC (if policy requires), review admin access

Monthly
- Incident post‑mortems summary, backlog of tech‑debt
- Cost review (DB/storage/compute), plan scaling or archiving

Runbooks (short)
- Payments errors/5xx spike: check `/metrics` for `http_requests_total{status="500"}` and logs; validate DB/Redis connectivity; fallback disable non‑critical features via env flags if needed.
- Webhook retries high: inspect endpoints, re‑sign secrets, increase backoff; temporarily disable failing endpoint via DB flag if needed.
- Merchant payout/fee mismatch: reconcile via `/payments/merchant/statement` and fee wallet ledger; check `MERCHANT_FEE_BPS` changes.

Tips
- Keep `.env` under version control (safe values) and promote via CI.
- Use request id `X-Request-ID` to correlate logs across services.
- Automate smoke tests before/after deploy (`tools/health_check.sh`, `make e2e`).

