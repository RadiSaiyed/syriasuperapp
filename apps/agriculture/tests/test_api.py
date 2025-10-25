import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "Buyer"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_and_seed_and_flows():
    # health
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

    # seed demo data
    r = client.post("/admin/seed")
    assert r.status_code == 200

    # login buyer
    h = _auth("+963901000001")

    # browse listings
    r = client.get("/market/listings")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    listing = data["listings"][0]

    # place order
    r = client.post(f"/market/listings/{listing['id']}/order", headers=h, json={"qty_kg": 1})
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["total_cents"] >= 1
    assert order["status"] in ("created", "confirmed")

    # browse jobs & apply
    r = client.get("/jobs")
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert len(jobs) >= 1
    job_id = jobs[0]["id"]
    r = client.post(f"/jobs/{job_id}/apply", headers=h, json={"message": "Ready to work"})
    assert r.status_code == 200, r.text

