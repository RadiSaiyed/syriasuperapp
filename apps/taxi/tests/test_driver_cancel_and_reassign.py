import os
os.environ.setdefault("PLATFORM_FEE_BPS", "0")
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
    client.post("/driver/apply", headers=hb, json={"vehicle_make": "Toyota", "vehicle_plate": "TST"})
    client.put("/driver/status", headers=hb, json={"status": "available"})
    client.put("/driver/location", headers=hb, json={"lat": 33.5138, "lon": 36.2765})
    return hb


def test_cancel_by_driver_flow():
    rider = "+963905300001"
    drv = "+963905300002"
    ha = auth(rider, "Rider")
    hb = _setup_driver(drv)

    # Rider requests ride (likely assigned to driver)
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
    ride_id = r.json()["id"]

    # Driver cancels; system frees driver and may reassign
    r = client.post(f"/rides/{ride_id}/cancel_by_driver", headers=hb)
    # If the ride is not assigned to this driver (e.g., another test driver closer), API should return 403
    if r.status_code == 403:
        assert r.json().get("detail") in ("Not your ride",)
    else:
        assert r.status_code == 200
        detail = r.json().get("detail")
        assert detail in ("reassigned", "canceled")


def test_reassign_endpoint():
    rider = "+963905300011"
    drv = "+963905300012"
    ha = auth(rider, "Rider")
    hb = _setup_driver(drv)

    # Create ride (assigned to driver)
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
    ride_id = r.json()["id"]

    # Reassign by rider
    r = client.post(f"/rides/{ride_id}/reassign", headers=ha)
    assert r.status_code == 200
    assert r.json().get("detail") in ("reassigned", "no_driver")
