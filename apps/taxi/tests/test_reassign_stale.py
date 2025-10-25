import os
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
    client.post("/driver/apply", headers=hb, json={"vehicle_make": "Toyota", "vehicle_plate": "RST"})
    client.put("/driver/status", headers=hb, json={"status": "available"})
    client.put("/driver/location", headers=hb, json={"lat": 33.5138, "lon": 36.2765})
    return hb


def test_reassign_stale_dev():
    rider = "+963905500001"
    drv = "+963905500002"
    ha = auth(rider, "Rider")
    _setup_driver(drv)

    # Create a requested/assigned ride
    r = client.post(
        "/rides/request",
        headers=ha,
        json={
            "pickup_lat": 33.5138,
            "pickup_lon": 36.2765,
            "dropoff_lat": 33.52,
            "dropoff_lon": 36.28,
        },
    )
    assert r.status_code == 200

    # Run reassign_stale with minutes=0 so newly created rides match cutoff
    r = client.post("/rides/reassign_stale", headers=ha, params={"minutes": 0})
    assert r.status_code in (200, 403)  # 403 if ENV != dev
    if r.status_code == 200:
        body = r.json()
        assert "reassigned" in body and "scanned" in body

