from fastapi.testclient import TestClient

from app.main import app
from .utils import unique_phone


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_pay_by_link_dynamic():
    a = unique_phone("9010")
    b = unique_phone("9011")
    ha = auth(a, "Merchant")
    hb = auth(b, "Payer")

    # Approve both for KYC and become merchant
    client.post("/kyc/dev/approve", headers=ha)
    client.post("/kyc/dev/approve", headers=hb)
    client.post("/payments/dev/become_merchant", headers=ha)

    # Top up payer
    client.post(
        "/wallet/topup",
        headers=hb,
        json={"amount_cents": 10000, "idempotency_key": f"top-{b}"},
    )

    # Create dynamic link for 1500
    r = client.post(
        "/payments/links",
        headers=ha,
        json={"amount_cents": 1500, "expires_in_minutes": 30},
    )
    assert r.status_code == 200, r.text
    code = r.json()["code"]

    # Pay link
    r2 = client.post(
        "/payments/links/pay",
        headers=hb,
        json={"code": code, "idempotency_key": f"lpay-{code}"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["amount_cents"] == 1500
