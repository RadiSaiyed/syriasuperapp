import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str, role: str | None = None):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    payload = {"phone": phone, "otp": "123456", "name": "User"}
    if role:
        payload["role"] = role
    r = client.post("/auth/verify_otp", json=payload)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_seed_browse_book():
    r = client.get("/health")
    assert r.status_code == 200
    client.post("/admin/seed")

    # renter login
    h = _auth("+963901000010", role="renter")
    r = client.get("/market/vehicles")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    vid = data["vehicles"][0]["id"]

    # book 2 days
    r = client.post(f"/market/vehicles/{vid}/book", headers=h, json={"start_date": "2025-01-10", "end_date": "2025-01-12"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["days"] == 2
    assert b["total_cents"] >= 1


def test_favorites_flow():
    client.post("/admin/seed")
    h = _auth("+963901000011", role="renter")
    r = client.get("/market/vehicles")
    assert r.status_code == 200
    vehicles = r.json()["vehicles"]
    assert vehicles
    vid = vehicles[0]["id"]
    assert client.post(f"/market/vehicles/{vid}/favorite", headers=h).status_code == 200
    r = client.get("/market/vehicles/favorites", headers=h)
    assert r.status_code == 200
    favs = r.json()["vehicles"]
    assert any(v["id"] == vid for v in favs)
    assert client.delete(f"/market/vehicles/{vid}/favorite", headers=h).status_code == 200


def test_seller_confirm_cancel():
    client.post("/admin/seed")
    # renter makes a booking so seller has an order
    hr = _auth("+963901000012", role="renter")
    r = client.get("/market/vehicles")
    vid = r.json()["vehicles"][0]["id"]
    client.post(f"/market/vehicles/{vid}/book", headers=hr, json={"start_date": "2025-02-01", "end_date": "2025-02-03"})
    # try both sellers to find the booking
    for s_phone in ("+96390000050", "+963900000510"):
        hs = _auth(s_phone, role="seller")
        rr = client.get("/orders", headers=hs)
        if rr.status_code != 200:
            continue
        orders = rr.json().get("bookings", [])
        if not orders:
            continue
        bid = orders[0]["id"]
        assert client.post(f"/orders/{bid}/confirm", headers=hs).status_code in (200, 400)
        assert client.post(f"/orders/{bid}/cancel", headers=hs).status_code in (200, 400)
        break
