import os
from fastapi.testclient import TestClient
from .utils import unique_phone


os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")

from app.main import app


client = TestClient(app)


def auth(phone: str, name: str = "Test"):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_invoice_manual_pay():
    merchant_phone = unique_phone("9002")
    payer_phone = unique_phone("9003")

    Hm = auth(merchant_phone, "Merchant")
    Hp = auth(payer_phone, "Payer")

    # Approve KYC and become merchant
    assert client.post("/kyc/dev/approve", headers=Hm).status_code == 200
    assert client.post("/kyc/dev/approve", headers=Hp).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=Hm).status_code == 200

    # Top up payer
    assert (
        client.post("/wallet/topup", headers=Hp, json={"amount_cents": 20000, "idempotency_key": f"inv-topup-{merchant_phone}"}).status_code
        == 200
    )

    # Create invoice from merchant to payer
    r = client.post(
        "/invoices",
        headers=Hm,
        json={"payer_phone": payer_phone, "amount_cents": 5000, "due_in_days": 0, "reference": "INV1"},
    )
    assert r.status_code == 200, r.text
    inv_id = r.json()["id"]

    # Payer pays
    rp = client.post(f"/invoices/{inv_id}/pay", headers={**Hp, "Idempotency-Key": f"inv-pay-{merchant_phone}"})
    assert rp.status_code == 200, rp.text

    # Verify status via list
    li = client.get("/invoices", headers=Hp)
    assert li.status_code == 200
    incoming = li.json()["incoming"]
    assert any(x["id"] == inv_id and x["status"] == "paid" for x in incoming)


def test_invoice_autopay_process_due():
    merchant_phone = unique_phone("9004")
    payer_phone = unique_phone("9005")

    Hm = auth(merchant_phone, "Merchant")
    Hp = auth(payer_phone, "Payer")

    # Approve KYC and become merchant
    assert client.post("/kyc/dev/approve", headers=Hm).status_code == 200
    assert client.post("/kyc/dev/approve", headers=Hp).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=Hm).status_code == 200

    # Top up payer
    assert (
        client.post("/wallet/topup", headers=Hp, json={"amount_cents": 30000, "idempotency_key": f"inv2-topup-{merchant_phone}"}).status_code
        == 200
    )

    # Payer sets mandate for merchant (autopay up to 10,000)
    rm = client.post(
        "/invoices/mandates",
        headers=Hp,
        json={"issuer_phone": merchant_phone, "autopay": True, "max_amount_cents": 10000},
    )
    assert rm.status_code == 200, rm.text

    # Create invoice due today
    r = client.post(
        "/invoices",
        headers=Hm,
        json={"payer_phone": payer_phone, "amount_cents": 7000, "due_in_days": 0, "reference": "INV2"},
    )
    assert r.status_code == 200, r.text
    inv_id = r.json()["id"]

    # Force due to past and process
    client.post(f"/invoices/{inv_id}/dev_force_due", headers=Hp)
    pr = client.post("/invoices/process_due", headers=Hp)
    assert pr.status_code == 200, pr.text
    assert inv_id in pr.json().get("processed", [])
