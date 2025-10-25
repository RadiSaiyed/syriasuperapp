POS Demo CLI

Minimal command-line helper to exercise merchant QR flows against the Payments API.

Setup
- Export a merchant bearer token as `PAYMENTS_MERCHANT_TOKEN` (login and promote merchant in dev).
- Optionally set `PAYMENTS_BASE_URL` (default `http://localhost:8080`).

Commands
- Create dynamic QR: `python3 pos_cli.py create_qr 1500`
  - Prints `{ "code": "PAY:v1;code=...", "expires_at": "..." }`
- Poll QR status: `python3 pos_cli.py qr_status 'PAY:v1;code=...'`
- Wait until paid/expired: `python3 pos_cli.py wait_paid 'PAY:v1;code=...' [timeout_secs]`
- CPM request after scanning customer QR: `python3 pos_cli.py cpm_request 'CPM:v1;phone=+963...' 2500`

Notes
- For production, prefer webhooks over polling.
- This CLI is for reference/testing; vendors can implement the same calls in their POS stack.
