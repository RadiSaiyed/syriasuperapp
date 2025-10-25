Merchant Links & QR — Client Integration

Overview
- These endpoints require a user/merchant bearer token (JWT) obtained via the app’s auth flow.
- For test/dev: OTP is `123456` (if `OTP_MODE=dev`).

Create Link (dynamic / static)
Python
```python
import requests

BASE = 'http://localhost:8080'
TOKEN = '<merchant bearer token>'

def create_dynamic_link(amount_cents: int):
    r = requests.post(
        f'{BASE}/payments/links',
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
        json={'amount_cents': amount_cents, 'expires_in_minutes': 60}
    )
    r.raise_for_status()
    return r.json()['code']  # e.g. LINK:v1;code=...

def create_static_link():
    r = requests.post(
        f'{BASE}/payments/links',
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
        json={'expires_in_minutes': 1440}
    )
    r.raise_for_status(); return r.json()['code']
```

Pay Link (payer)
```python
def pay_link(code: str, idempotency_key: str, amount_cents: int | None = None, payer_token: str = ''):
    payload = {'code': code, 'idempotency_key': idempotency_key}
    if amount_cents:
        payload['amount_cents'] = amount_cents
    r = requests.post(
        f'{BASE}/payments/links/pay',
        headers={'Authorization': f'Bearer {payer_token}', 'Content-Type': 'application/json'},
        json=payload
    )
    r.raise_for_status(); return r.json()
```

Create QR (dynamic / static)
```python
def create_qr(amount_cents: int, mode: str = 'dynamic'):
    r = requests.post(
        f'{BASE}/payments/merchant/qr',
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
        json={'amount_cents': amount_cents, 'mode': mode}
    )
    r.raise_for_status(); return r.json()['code']  # PAY:v1;code=...
```

Pay QR (payer)
```python
def pay_qr(code: str, idempotency_key: str, payer_token: str, amount_cents: int | None = None):
    payload = {'code': code, 'idempotency_key': idempotency_key}
    if amount_cents:
        payload['amount_cents'] = amount_cents
    r = requests.post(
        f'{BASE}/payments/merchant/pay',
        headers={'Authorization': f'Bearer {payer_token}', 'Content-Type': 'application/json'},
        json=payload
    )
    r.raise_for_status(); return r.json()
```

JavaScript (Node.js)
```js
const fetch = require('node-fetch');
const BASE = 'http://localhost:8080';
const TOKEN = '<merchant bearer token>';

async function createDynamicLink(amount) {
  const res = await fetch(`${BASE}/payments/links`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_cents: amount, expires_in_minutes: 60 })
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()).code;
}
```

Notes
- Static modes (links/QR) require `amount_cents` at payment time; dynamic fixes the amount at creation.
- Always set an `idempotency_key` for payments.
- KYC/limits and risk guards can reject payments (429/403).
