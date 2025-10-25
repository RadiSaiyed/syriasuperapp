import os
import hmac, hashlib, json
from fastapi.testclient import TestClient


class _StubResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore


class _StubClient:
    def __init__(self, timeout=5.0):
        self.calls = []
        self._count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, content=None):
        self._count += 1
        self.calls.append((url, headers or {}, content or b""))
        # First attempt fail, second succeed
        return _StubResponse(500 if self._count == 1 else 200)


def test_webhook_retry_and_hmac_headers(monkeypatch):
    # Ensure backoff allows immediate retry
    os.environ["WEBHOOK_BASE_DELAY_SECS"] = "0"
    os.environ["WEBHOOK_BACKOFF_FACTOR"] = "1"
    os.environ["WEBHOOK_MAX_ATTEMPTS"] = "3"

    from app.main import create_app
    # Reset Prometheus registry for fresh app instance
    try:
        from prometheus_client import REGISTRY
        for c in list(REGISTRY._collector_to_names.keys()):  # type: ignore[attr-defined]
            try:
                REGISTRY.unregister(c)
            except Exception:
                pass
    except Exception:
        pass
    client = TestClient(create_app())
    # Auth and merchant
    r = client.post("/auth/request_otp", json={"phone": "+963900033331"}); assert r.status_code == 200
    tok = client.post("/auth/verify_otp", json={"phone": "+963900033331", "otp": "123456", "name": "M"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/kyc/dev/approve", headers=h).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=h).status_code == 200

    # Replace httpx.Client with stub
    import httpx as _httpx
    stub = _StubClient()
    monkeypatch.setattr(_httpx, "Client", lambda timeout=5.0: stub)

    # Create endpoint and enqueue test event
    ep = client.post("/webhooks/endpoints", headers=h, params={"url": "https://merchant.test/h", "secret": "sek"})
    assert ep.status_code == 200
    make = client.post("/webhooks/test", headers=h)
    assert make.status_code == 200

    # Process pending twice; first attempt fails, second succeeds
    p1 = client.post("/webhooks/process_once", headers=h); assert p1.status_code == 200
    p2 = client.post("/webhooks/process_once", headers=h); assert p2.status_code == 200

    # Verify we made at least two calls and headers contain valid HMAC
    assert len(stub.calls) >= 2
    url, headers, content = stub.calls[-1]
    assert headers.get("X-Webhook-Ts") and headers.get("X-Webhook-Event") and headers.get("X-Webhook-Sign")
    ts = headers["X-Webhook-Ts"]; ev = headers["X-Webhook-Event"]; sig = headers["X-Webhook-Sign"]
    expected = hmac.new(b"sek", (ts + ev).encode() + content, hashlib.sha256).hexdigest()
    assert sig == expected
