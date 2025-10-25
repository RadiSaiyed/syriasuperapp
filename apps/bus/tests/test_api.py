import os
import time
from fastapi.testclient import TestClient


os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@pg:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "Test"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_search_and_booking_flow():
    suffix = int(time.time()) % 100000
    phone = f"+9639010{suffix:05d}"
    h = _auth(phone)

    # Search trips Damascus -> Aleppo today
    from datetime import date
    r = client.post(
        "/trips/search",
        headers=h,
        json={"origin": "Damascus", "destination": "Aleppo", "date": date.today().isoformat()},
    )
    assert r.status_code == 200, r.text
    trips = r.json().get("trips", [])
    assert isinstance(trips, list)
    assert len(trips) >= 1
    trip_id = trips[0]["id"]

    # Book 1 seat
    r = client.post("/bookings", headers=h, json={"trip_id": trip_id, "seats_count": 1})
    assert r.status_code == 200, r.text
    booking_id = r.json()["id"]
    assert booking_id

    # List my bookings
    r = client.get("/bookings", headers=h)
    assert r.status_code == 200
    items = r.json().get("bookings", [])
    assert any(b.get("id") == booking_id for b in items)

    # Cancel booking
    r = client.post(f"/bookings/{booking_id}/cancel", headers=h)
    assert r.status_code == 200

