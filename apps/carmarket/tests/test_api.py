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


def test_listing_offer_accept_flow():
    suffix = int(time.time()) % 100000
    seller = f"+9639015{suffix:05d}"
    buyer = f"+9639016{suffix:05d}"
    Hs = _auth(seller)
    Hb = _auth(buyer)

    # Seller posts listing
    r = client.post("/listings", headers=Hs, json={"title": "Toyota Corolla", "make": "Toyota", "model": "Corolla", "year": 2010, "price_cents": 3000000})
    assert r.status_code == 200
    listing_id = r.json()["id"]

    # Buyer browses and offers
    r = client.get("/listings", headers=Hb)
    assert any(l["id"] == listing_id for l in r.json().get("listings", []))
    r = client.post(f"/offers/listing/{listing_id}", headers=Hb, json={"amount_cents": 2800000})
    assert r.status_code == 200
    offer_id = r.json()["id"]

    # Seller accepts
    r = client.post(f"/offers/{offer_id}/accept", headers=Hs)
    assert r.status_code == 200
    assert r.json().get("status") == "accepted"
