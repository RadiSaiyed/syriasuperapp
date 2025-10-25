import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "W"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_webhook_delivery_process_once():
    h = _auth("+963900444444")
    # Become merchant (dev) to allow webhooks mgmt
    client.post("/payments/dev/become_merchant", headers=h)
    # Add endpoint using app://echo (internal success)
    r = client.post("/webhooks/endpoints", headers=h, params={"url": "app://echo", "secret": "s"})
    assert r.status_code == 200
    # Send test event (creates pending delivery)
    r = client.post("/webhooks/test", headers=h)
    assert r.status_code == 200
    # Process once (dev helper)
    r = client.post("/webhooks/process_once", headers=h)
    assert r.status_code == 200
    # List deliveries and expect delivered
    r = client.get("/webhooks/deliveries", headers=h)
    assert r.status_code == 200
    items = r.json()
    assert any(d.get("status") == "delivered" for d in items)
