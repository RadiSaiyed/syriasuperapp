import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "MVP"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_voucher_create_and_redeem():
    a = _auth("+963902000001")
    b = _auth("+963902000002")

    # A creates voucher 50 SYP
    r = client.post("/vouchers", headers=a, json={"amount_syp": 50})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    assert code
    assert r.json().get("amount_syp") == 50

    # Snapshot balance before
    r = client.get("/wallet", headers=b)
    assert r.status_code == 200
    before = r.json()["wallet"]["balance_cents"]

    # B redeem voucher
    r = client.post(f"/vouchers/{code}/redeem", headers=b)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "redeemed"

    # Balance should reflect 1% fee (50 SYP -> 4950 cents credited)
    r = client.get("/wallet", headers=b)
    assert r.status_code == 200, r.text
    after = r.json()["wallet"]["balance_cents"]
    assert after - before == 4950

    # Redeeming again should fail
    r = client.post(f"/vouchers/{code}/redeem", headers=b)
    assert r.status_code == 400
