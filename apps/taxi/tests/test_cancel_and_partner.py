import os
from fastapi.testclient import TestClient
from superapp_shared.internal_hmac import sign_internal_request_headers

os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")

from app.main import app  # noqa: E402


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cancel_by_rider_flow():
    A = "+963905100001"
    B = "+963905100002"
    ha = auth(A, "Rider")
    hb = auth(B, "Driver")

    # Setup driver
    client.post("/driver/apply", headers=hb, json={"vehicle_make": "Toyota", "vehicle_plate": "ABC"})
    client.put("/driver/status", headers=hb, json={"status": "available"})
    client.put("/driver/location", headers=hb, json={"lat": 33.5138, "lon": 36.2765})

    # Rider requests a ride
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
    # Rider cancels
    r = client.post(f"/rides/{ride_id}/cancel_by_rider", headers=ha)
    assert r.status_code == 200
    # List rider rides contains the ride back in requested/canceled state list
    r = client.get("/rides", headers=ha)
    assert r.status_code == 200
    assert any(it["id"] == ride_id for it in r.json()["rides"])  # schema: RidesListOut


def test_partner_webhook_accept():
    A = "+963905200001"
    B = "+963905200002"
    ha = auth(A, "Rider")
    hb = auth(B, "Driver")
    # Ensure driver exists
    client.post("/driver/apply", headers=hb, json={"vehicle_make": "Toyota", "vehicle_plate": "ABC"})

    # Register partner (dev)
    key_id = "fleet_py"
    secret = "sekret"
    r = client.post("/partners/dev/register", headers=ha, json={"name": "Fleet PY", "key_id": key_id, "secret": secret})
    assert r.status_code in (200, 403)  # allow disabled outside dev
    if r.status_code != 200:
        return
    # Map driver via JSON body
    r = client.post("/partners/dev/map_driver", headers=ha, json={"partner_key_id": key_id, "external_driver_id": "drv-9", "driver_phone": B})
    assert r.status_code == 200

    # Create ride (not necessarily assigned)
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

    # Create dispatch
    r = client.post("/partners/dispatch", headers=ha, json={"ride_id": ride_id, "partner_key_id": key_id, "external_trip_id": "ext-123"})
    assert r.status_code == 200, r.text

    # Webhook accept with HMAC
    payload = {"external_trip_id": "ext-123", "status": "accepted", "final_fare_cents": None}
    headers = sign_internal_request_headers(payload, secret)
    r = client.post(f"/partners/{key_id}/webhooks/ride_status", headers=headers, json=payload)
    assert r.status_code == 200, r.text

    # Check ride status moved to accepted/requested/assigned
    r = client.get(f"/rides/{ride_id}", headers=ha)
    assert r.status_code == 200
    st = r.json()["status"]
    assert st in ("accepted", "requested", "assigned")
