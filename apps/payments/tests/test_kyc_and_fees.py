from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from .utils import unique_phone


client = TestClient(app)


def auth(phone: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "T"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_merchant_qr_requires_kyc_level():
    p = unique_phone("9002")
    h = auth(p)
    # Without KYC, creating QR should fail with 403
    r = client.post("/payments/merchant/qr", headers=h, json={"amount_cents": 1000})
    assert r.status_code == 403
    assert "KYC" in r.text or "level" in r.text
    # Approve KYC and enable merchant (dev), then succeed
    r = client.post("/kyc/dev/approve", headers=h)
    assert r.status_code == 200
    r = client.post("/payments/dev/become_merchant", headers=h)
    assert r.status_code == 200
    r = client.post("/payments/merchant/qr", headers=h, json={"amount_cents": 1000})
    assert r.status_code == 200


def test_p2p_tx_limit_enforced():
    # Limit level 0 tx to 1000 cents for the duration of this test
    old_tx = settings.KYC_L0_TX_MAX_CENTS
    settings.KYC_L0_TX_MAX_CENTS = 1000
    try:
        a = unique_phone("9003")
        b = unique_phone("9004")
        ha = auth(a)
        hb = auth(b)
        # Topup sender
        r = client.post("/wallet/topup", headers=ha, json={"amount_cents": 50000, "idempotency_key": f"t-{a}"})
        assert r.status_code == 200
        # Attempt transfer above limit
        r = client.post(
            "/wallet/transfer",
            headers=ha,
            json={"to_phone": b, "amount_cents": 5000, "idempotency_key": f"p2p-{a}"},
        )
        assert r.status_code == 400
        assert "limit" in r.text
    finally:
        settings.KYC_L0_TX_MAX_CENTS = old_tx


def test_merchant_fee_deducted_on_pay():
    old_fee = settings.MERCHANT_FEE_BPS
    settings.MERCHANT_FEE_BPS = 1000  # 10%
    try:
        a = unique_phone("9005")
        b = unique_phone("9006")
        ha = auth(a)
        hb = auth(b)
        # Approve KYC both
        client.post("/kyc/dev/approve", headers=ha)
        client.post("/kyc/dev/approve", headers=hb)
        # A merchant
        client.post("/payments/dev/become_merchant", headers=ha)
        # B topup
        client.post("/wallet/topup", headers=hb, json={"amount_cents": 20000, "idempotency_key": f"btop-{b}"})
        # Create QR 10,000 cents
        qr = client.post("/payments/merchant/qr", headers=ha, json={"amount_cents": 10000}).json()["code"]
        # B pays
        client.post("/payments/merchant/pay", headers=hb, json={"code": qr, "idempotency_key": f"qr-{qr}"})
        # Merchant transactions should show +10000 and a -1000 fee entry
        tx = client.get("/wallet/transactions", headers=ha).json()["entries"]
        amounts = [e["amount_cents_signed"] for e in tx]
        assert any(v == 10000 for v in amounts)
        assert any(v == -1000 for v in amounts)
    finally:
        settings.MERCHANT_FEE_BPS = old_fee
