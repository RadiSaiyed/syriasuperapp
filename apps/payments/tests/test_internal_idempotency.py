import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402
from superapp_shared.internal_hmac import sign_internal_request_headers  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "Test"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_internal_requests_idempotency():
    # HMAC-signed internal request (default requires HMAC)
    secret_val = os.getenv("INTERNAL_API_SECRET", "dev_secret")
    payload = {"from_phone": "+963900777777", "to_phone": "+963900777778", "amount_cents": 1111}
    idem = {"X-Idempotency-Key": "idem-test-1"}
    h = sign_internal_request_headers(payload, secret_val)
    r1 = client.post("/internal/requests", headers={**h, **idem}, json=payload)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/internal/requests", headers={**h, **idem}, json=payload)
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]
