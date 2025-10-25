import os
from fastapi.testclient import TestClient
from .utils import unique_phone


os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "Test"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_e2e_basic():
    a = unique_phone("9000")
    b = unique_phone("9001")
    suffix_a = a[-5:]
    suffix_b = b[-5:]

    ha = _auth(a)
    hb = _auth(b)

    # Wallets
    ra = client.get("/wallet", headers=ha)
    rb = client.get("/wallet", headers=hb)
    assert ra.status_code == 200 and rb.status_code == 200

    # Topup A and B
    r = client.post("/wallet/topup", headers=ha, json={"amount_cents": 100000, "idempotency_key": f"tpa-{suffix_a}"})
    assert r.status_code == 200, r.text
    r = client.post("/wallet/topup", headers=hb, json={"amount_cents": 100000, "idempotency_key": f"tpb-{suffix_b}"})
    assert r.status_code == 200, r.text

    # P2P: A -> B
    r = client.post(
        "/wallet/transfer",
        headers=ha,
        json={"to_phone": b, "amount_cents": 1000, "idempotency_key": f"p2p-{suffix_a}"},
    )
    assert r.status_code == 200, r.text

    # KYC approve for both (required for merchant features)
    r = client.post("/kyc/dev/approve", headers=ha)
    assert r.status_code == 200, r.text
    r = client.post("/kyc/dev/approve", headers=hb)
    assert r.status_code == 200, r.text

    # Merchant flow: A becomes merchant (dev), generate QR, B pays
    r = client.post("/payments/dev/become_merchant", headers=ha)
    assert r.status_code == 200, r.text
    r = client.post("/payments/merchant/qr", headers=ha, json={"amount_cents": 5000})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    r = client.post("/payments/merchant/pay", headers=hb, json={"code": code, "idempotency_key": f"qr-{suffix_b}"})
    assert r.status_code == 200, r.text

    # Payment request: A requests from B, B accepts
    r = client.post("/requests", headers=ha, json={"to_phone": b, "amount_cents": 2345})
    assert r.status_code == 200, r.text
    req_id = r.json()["id"]
    r = client.post(f"/requests/{req_id}/accept", headers=hb)
    assert r.status_code == 200, r.text
