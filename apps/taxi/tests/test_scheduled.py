import os
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")

from app.main import app  # noqa: E402


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_driver(phone: str):
    hb = auth(phone, "Driver")
    client.post("/driver/apply", headers=hb, json={"vehicle_make": "Toyota", "vehicle_plate": "SCH"})
    client.put("/driver/status", headers=hb, json={"status": "available"})
    client.put("/driver/location", headers=hb, json={"lat": 33.5138, "lon": 36.2765})
    return hb


def test_scheduled_dispatch_creates_ride():
    rider = "+963905400001"
    drv = "+963905400002"
    ha = auth(rider, "Rider")
    _setup_driver(drv)

    # Count current rides
    r = client.get("/rides", headers=ha)
    assert r.status_code == 200
    before = len(r.json().get("rides", []))

    # Optional: create promo code (dev only)
    code = "SCH10"
    r = client.post("/promos", headers=ha, json={"code": code, "percent_off_bps": 1000, "active": True})
    # tolerate 403 if promos disabled outside dev
    assert r.status_code in (200, 403)

    # Schedule a ride 2 minutes in the future (still within dispatch window)
    when = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    r = client.post(
        "/rides/schedule",
        headers=ha,
        json={
            "pickup_lat": 33.5138,
            "pickup_lon": 36.2765,
            "dropoff_lat": 33.52,
            "dropoff_lon": 36.28,
            "scheduled_for": when,
            "promo_code": code,
        },
    )
    assert r.status_code == 200
    body = r.json()
    if "final_quote_cents" in body:
        assert body["final_quote_cents"] <= body["quoted_fare_cents"]

    # Dispatch due scheduled rides (dev helper)
    r = client.post("/rides/dispatch_scheduled", headers=ha)
    assert r.status_code == 200
    dispatched = r.json().get("dispatched", 0)
    assert dispatched >= 1

    # Verify new live ride shows up in rider list
    r = client.get("/rides", headers=ha)
    assert r.status_code == 200
    after = len(r.json().get("rides", []))
    assert after >= before + 1
