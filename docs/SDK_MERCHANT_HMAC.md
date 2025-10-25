Merchant API HMAC — Python and JavaScript

Overview
- Header names:
  - `X-API-Key`: Merchant API key id
  - `X-API-Ts`: Unix timestamp (seconds)
  - `X-API-Sign`: HMAC SHA256 hex over: `ts + path + body`
- Body is the raw request payload bytes; for GET with no body use empty bytes.
- Path must match exactly what is requested (e.g., `/merchant/api/transactions`).
- Server accepts ±5 minutes clock skew.

Python
```python
import time, hmac, hashlib, requests

BASE = "http://localhost:8080"
KEY_ID = "<your key id>"
SECRET = "<your key secret>"

def sign(ts: str, path: str, body: bytes) -> str:
    msg = (ts + path).encode() + body
    return hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()

def list_transactions():
    path = "/merchant/api/transactions"
    ts = str(int(time.time()))
    body = b""  # GET has no body
    headers = {
        "X-API-Key": KEY_ID,
        "X-API-Ts": ts,
        "X-API-Sign": sign(ts, path, body),
    }
    r = requests.post(BASE + path, headers=headers)  # endpoint expects POST in this API
    r.raise_for_status()
    return r.json()
```

JavaScript (Node.js)
```js
const crypto = require('crypto');
const fetch = require('node-fetch');

const BASE = 'http://localhost:8080';
const KEY_ID = '<your key id>';
const SECRET = '<your key secret>';

function sign(ts, path, bodyBytes) {
  const msg = Buffer.concat([Buffer.from(ts + path), Buffer.from(bodyBytes || [])]);
  return crypto.createHmac('sha256', SECRET).update(msg).digest('hex');
}

async function listTransactions() {
  const path = '/merchant/api/transactions';
  const ts = String(Math.floor(Date.now() / 1000));
  const body = Buffer.alloc(0);
  const headers = {
    'X-API-Key': KEY_ID,
    'X-API-Ts': ts,
    'X-API-Sign': sign(ts, path, body)
  };
  // API expects POST for transactions listing in this MVP
  const res = await fetch(BASE + path, { method: 'POST', headers });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}
```

Notes
- Ensure the `path` string matches the exact request path.
- For JSON payloads: the body used for signing must be the raw serialized bytes actually sent on the wire.
- Keep clocks in sync to avoid timestamp rejections.

