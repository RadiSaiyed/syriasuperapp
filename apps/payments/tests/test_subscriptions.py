from fastapi.testclient import TestClient

from app.main import app
from .utils import unique_phone


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_subscription_charge_flow():
    payer = unique_phone("9012")
    merch = unique_phone("9013")
    Hp = auth(payer, "Payer")
    Hm = auth(merch, "Merchant")

    # Approve KYC both and make merchant
    client.post("/kyc/dev/approve", headers=Hp)
    client.post("/kyc/dev/approve", headers=Hm)
    client.post("/payments/dev/become_merchant", headers=Hm)

    # Payer topup
    client.post(
        "/wallet/topup",
        headers=Hp,
        json={"amount_cents": 20000, "idempotency_key": f"top-{payer}"},
    )

    # Create subscription 3000 cents monthly
    r = client.post(
        "/subscriptions",
        headers=Hp,
        json={"merchant_phone": merch, "amount_cents": 3000, "interval_days": 30},
    )
    assert r.status_code == 200, r.text
    sub_id = r.json()["id"]

    # Force due and process
    client.post(f"/subscriptions/{sub_id}/dev_force_due", headers=Hp)
    r2 = client.post("/subscriptions/process_due", headers=Hp)
    assert r2.status_code == 200, r2.text
    assert r2.json()["processed"] >= 1

    # Check merchant has +3000 and payer has -3000 in recent entries
    tx_m = client.get("/wallet/transactions", headers=Hm).json()["entries"]
    tx_p = client.get("/wallet/transactions", headers=Hp).json()["entries"]
    assert any(e["amount_cents_signed"] == 3000 for e in tx_m)
    assert any(e["amount_cents_signed"] == -3000 for e in tx_p)
