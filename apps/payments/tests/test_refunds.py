import os
from fastapi.testclient import TestClient
from .utils import unique_phone

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _wallet(headers):
    r = client.get("/wallet", headers=headers)
    assert r.status_code == 200
    return r.json()["wallet"]["id"], r.json()["user"]["phone"]


def test_refund_create_and_idempotency():
    # Setup users
    payer_phone = unique_phone("055555")
    merchant_phone = unique_phone("055556")
    H_payer = _auth(payer_phone, "Payer")
    H_merchant = _auth(merchant_phone, "Merchant")

    # Topup payer with sufficient balance
    r = client.post(
        "/wallet/topup",
        headers={**H_payer, "Content-Type": "application/json"},
        json={"amount_cents": 50000, "idempotency_key": f"topup-{payer_phone}"},
    )
    assert r.status_code == 200, r.text

    # Get merchant phone
    _, merchant_phone = _wallet(H_merchant)

    # Payer transfers to merchant
    r = client.post(
        "/wallet/transfer",
        headers={**H_payer, "Content-Type": "application/json"},
        json={"to_phone": merchant_phone, "amount_cents": 20000, "idempotency_key": f"p2p-{payer_phone}"},
    )
    assert r.status_code == 200, r.text
    transfer_id = r.json()["transfer_id"]

    # Merchant lists transactions to confirm incoming
    r = client.get("/wallet/transactions", headers=H_merchant)
    assert r.status_code == 200
    incoming = [e for e in r.json()["entries"] if e["amount_cents_signed"] > 0]
    assert any(e["transfer_id"] == transfer_id for e in incoming)

    # Merchant refunds partially 5000 cents
    r = client.post(
        "/refunds",
        headers={**H_merchant, "Content-Type": "application/json", "Idempotency-Key": "refund-1"},
        json={"original_transfer_id": transfer_id, "amount_cents": 5000},
    )
    assert r.status_code == 200, r.text
    refund_transfer_id = r.json()["transfer_id"]
    assert refund_transfer_id

    # Idempotency: retry same refund
    r2 = client.post(
        "/refunds",
        headers={**H_merchant, "Content-Type": "application/json", "Idempotency-Key": "refund-1"},
        json={"original_transfer_id": transfer_id, "amount_cents": 5000},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["transfer_id"] == refund_transfer_id
