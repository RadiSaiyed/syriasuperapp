import os
import time
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "U"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_billers_accounts_bills_and_topup_flow():
    suffix = int(time.time()) % 100000
    phone = f"+9639012{suffix:05d}"
    h = _auth(phone)

    # Billers
    r = client.get("/billers", headers=h)
    assert r.status_code == 200
    billers = r.json()
    assert any(b["category"] == "electricity" for b in billers)
    elec = next(b for b in billers if b["category"] == "electricity")

    # Link account
    r = client.post("/accounts/link", headers=h, json={"biller_id": elec["id"], "account_ref": "METER-123"})
    assert r.status_code == 200
    acc_id = r.json()["id"]

    # Refresh and list bills
    r = client.post(f"/bills/refresh?account_id={acc_id}", headers=h)
    assert r.status_code == 200
    assert len(r.json().get("bills", [])) >= 1
    bill_id = r.json()["bills"][0]["id"]

    # Pay bill (creates payment request id optionally)
    r = client.post(f"/bills/{bill_id}/pay", headers=h)
    assert r.status_code == 200

    # Topup
    mtn = next(b for b in billers if b["category"] == "mobile")
    r = client.post("/topups", headers=h, json={"operator_biller_id": mtn["id"], "target_phone": "+963900000000", "amount_cents": 5000})
    assert r.status_code == 200

