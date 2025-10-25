import os
import time
from datetime import date, timedelta
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DB_URL",
    os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"),
)

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str, role: str | None = None, name: str = "Test"):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    payload = {"phone": phone, "otp": "123456", "name": name}
    if role:
        payload["role"] = role
    r = client.post("/auth/verify_otp", json=payload)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_host_create_property_and_unit_and_search_and_book():
    suf = int(time.time()) % 100000
    # Host creates property and unit
    h_host = _auth(f"+9639030{suf:05d}", role="host", name="Host")
    r = client.post("/host/properties", headers=h_host, json={"name": "Sunrise Hotel", "type": "hotel", "city": "Damascus", "description": "Center"})
    assert r.status_code == 200, r.text
    prop = r.json()
    pid = prop["id"]
    r = client.post(f"/host/properties/{pid}/units", headers=h_host, json={"name": "Deluxe", "capacity": 2, "total_units": 2, "price_cents_per_night": 50000})
    assert r.status_code == 200, r.text
    unit = r.json()

    # Public list and availability
    r = client.get("/properties?city=Damascus")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    today = date.today() + timedelta(days=1)
    r = client.post("/search_availability", json={"city": "Damascus", "check_in": today.isoformat(), "check_out": (today + timedelta(days=2)).isoformat(), "guests": 2})
    assert r.status_code == 200, r.text
    res = r.json().get("results", [])
    assert any(x["unit_id"] == unit["id"] for x in res)

    # Guest books reservation
    h_guest = _auth(f"+9639031{suf:05d}", role="guest", name="Guest")
    r = client.post("/reservations", headers=h_guest, json={"unit_id": unit["id"], "check_in": today.isoformat(), "check_out": (today + timedelta(days=2)).isoformat(), "guests": 2})
    assert r.status_code == 200, r.text
    reservation = r.json()
    assert reservation["total_cents"] >= 1
    assert reservation["status"] in ("created", "confirmed")

    # Guest lists reservations
    r = client.get("/reservations", headers=h_guest)
    assert r.status_code == 200
    assert len(r.json().get("reservations", [])) >= 1

