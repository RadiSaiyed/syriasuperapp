from fastapi.testclient import TestClient


from app.main import app
from .utils import unique_phone


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_mpm_qr_status_and_cpm_request_flow():
    merch = unique_phone("902")
    payer = unique_phone("903")

    Hm = auth(merch, "Merchant")
    Hp = auth(payer, "Payer")

    # KYC approve and become merchant
    assert client.post("/kyc/dev/approve", headers=Hm).status_code == 200
    assert client.post("/kyc/dev/approve", headers=Hp).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=Hm).status_code == 200

    # Top up payer
    assert client.post("/wallet/topup", headers=Hp, json={"amount_cents": 20000, "idempotency_key": f"pos-top-{merch}"}).status_code == 200

    # Create dynamic QR and check status
    r = client.post("/payments/merchant/qr", headers=Hm, json={"amount_cents": 1500})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    r2 = client.get(f"/payments/merchant/qr_status", headers=Hm, params={"code": code})
    assert r2.status_code == 200 and r2.json()["status"] == "active"

    # Payer pays
    rp = client.post("/payments/merchant/pay", headers=Hp, json={"code": code, "idempotency_key": f"qr-{code}"})
    assert rp.status_code == 200, rp.text

    # Status becomes used
    r3 = client.get(f"/payments/merchant/qr_status", headers=Hm, params={"code": code})
    assert r3.status_code == 200 and r3.json()["status"] in ("used", "expired")

    # CPM: Merchant scans customer's QR (phone)
    cpm_code = f"CPM:v1;phone={payer}"
    rc = client.post("/payments/merchant/cpm_request", headers=Hm, json={"code": cpm_code, "amount_cents": 1234})
    assert rc.status_code == 200, rc.text
    req_id = rc.json()["id"]

    # Payer accepts
    ra = client.post(f"/requests/{req_id}/accept", headers=Hp)
    assert ra.status_code == 200, ra.text
