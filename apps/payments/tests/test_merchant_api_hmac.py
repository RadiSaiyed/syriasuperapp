import os, time, hmac, hashlib
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "M"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_merchant_api_hmac_transactions():
    h = _auth("+963900555555")
    # Become merchant (dev)
    client.post("/payments/dev/become_merchant", headers=h)
    # Create API key
    r = client.post("/merchant/api/keys", headers=h)
    assert r.status_code == 200
    key_id = r.json()["key_id"]
    secret = r.json()["secret"]

    # Sign request
    ts = str(int(time.time()))
    path = "/merchant/api/transactions"
    body = b""
    sign = hmac.new(secret.encode(), (ts + path).encode() + body, hashlib.sha256).hexdigest()
    r2 = client.post(path, headers={"X-API-Key": key_id, "X-API-Sign": sign, "X-API-Ts": ts})
    assert r2.status_code == 200, r2.text
    assert "entries" in r2.json()

