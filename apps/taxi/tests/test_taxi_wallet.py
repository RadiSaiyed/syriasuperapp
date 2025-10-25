import os

# Ensure predictable config for this test BEFORE importing app
os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")
os.environ.setdefault("PLATFORM_FEE_BPS", "1000")  # 10%
os.environ.setdefault("TAXI_WALLET_ENABLED", "true")
# Disable pool/escrow to avoid external Payments dependency in unit tests
os.environ.setdefault("TAXI_POOL_WALLET_PHONE", "")
os.environ.setdefault("TAXI_ESCROW_WALLET_PHONE", "")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post(
        "/auth/verify_otp",
        json={"phone": phone, "otp": "123456", "name": name},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_driver(phone: str):
    hb = auth(phone, "Driver")
    client.post(
        "/driver/apply",
        headers=hb,
        json={"vehicle_make": "Toyota", "vehicle_plate": "WAL"},
    )
    client.put("/driver/status", headers=hb, json={"status": "available"})
    client.put(
        "/driver/location", headers=hb, json={"lat": 33.5138, "lon": 36.2765}
    )
    return hb


def test_fee_requires_taxi_wallet_topup_then_accept_succeeds():
    rider = "+963905400001"
    drv = "+963905400002"
    ha = auth(rider, "Rider")
    hb = _setup_driver(drv)

    # Request ride near driver (quoted fare > 0)
    r = client.post(
        "/rides/request",
        headers=ha,
        json={
            "pickup_lat": 33.5138,
            "pickup_lon": 36.2765,
            "dropoff_lat": 33.5200,
            "dropoff_lon": 36.2800,
        },
    )
    assert r.status_code == 200
    ride = r.json()
    ride_id = ride["id"]
    quoted = int(ride.get("quoted_fare_cents") or 0)
    assert quoted > 0

    # Initial accept should fail due to insufficient taxi wallet balance
    r = client.post(f"/rides/{ride_id}/accept", headers=hb)
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("code") == "insufficient_taxi_wallet_balance"
    required = int(detail.get("required_fee_cents") or 0)
    shortfall = int(detail.get("shortfall_cents") or 0)
    assert required > 0 and shortfall > 0

    # Top up exactly the shortfall
    r = client.post(
        "/driver/taxi_wallet/topup",
        headers=hb,
        json={"amount_cents": shortfall},
    )
    assert r.status_code == 200
    bal = int(r.json().get("balance_cents") or 0)
    assert bal >= shortfall

    # Accept should now succeed
    r = client.post(f"/rides/{ride_id}/accept", headers=hb)
    assert r.status_code == 200

    # Completing ride returns platform_fee_cents (for info)
    client.post(f"/rides/{ride_id}/start", headers=hb)
    r = client.post(f"/rides/{ride_id}/complete", headers=hb)
    assert r.status_code == 200
    fee = int(r.json().get("platform_fee_cents") or 0)
    assert fee == required
