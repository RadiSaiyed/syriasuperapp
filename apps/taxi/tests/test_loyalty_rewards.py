import os
import uuid

# Configure test environment before importing app
os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")
os.environ.setdefault("PLATFORM_FEE_BPS", "1000")
os.environ.setdefault("TAXI_WALLET_ENABLED", "true")
os.environ.setdefault("TAXI_POOL_WALLET_PHONE", "")
os.environ.setdefault("TAXI_ESCROW_WALLET_PHONE", "")
os.environ.setdefault("LOYALTY_RIDER_FREE_CAP_CENTS", "50000")

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


def setup_driver(phone: str):
    hb = auth(phone, "Driver")
    client.post(
        "/driver/apply",
        headers=hb,
        json={"vehicle_make": "Hyundai", "vehicle_plate": "LOY"},
    )
    client.put("/driver/status", headers=hb, json={"status": "available"})
    client.put(
        "/driver/location",
        headers=hb,
        json={"lat": 33.5138, "lon": 36.2765},
    )
    # Ensure taxi wallet has sufficient balance for expected fees
    client.post(
        "/driver/taxi_wallet/topup",
        headers=hb,
        json={"amount_cents": 500000},
    )
    return hb


def run_ride(ha, hb):
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
    ride_id = r.json()["id"]

    r = client.post(f"/rides/{ride_id}/accept", headers=hb)
    assert r.status_code == 200
    r = client.post(f"/rides/{ride_id}/start", headers=hb)
    assert r.status_code == 200
    r = client.post(f"/rides/{ride_id}/complete", headers=hb)
    assert r.status_code == 200
    return r.json()


def get_wallet_balance(hb):
    r = client.get("/driver/taxi_wallet", headers=hb)
    assert r.status_code == 200
    return int(r.json().get("balance_cents") or 0)


def test_loyalty_rewards_for_rider_and_driver():
    rider_phone = "+9639" + str(uuid.uuid4().int % 10**7).zfill(7)
    driver_phone = "+9639" + str(uuid.uuid4().int % 10**7).zfill(7)
    ha = auth(rider_phone, "Rider")
    hb = setup_driver(driver_phone)

    ride_count = 10
    balances = []
    for idx in range(ride_count):
        res = run_ride(ha, hb)
        if idx < ride_count - 1:
            assert int(res.get("final_fare_cents") or 0) > 0
            assert not res.get("rider_reward_applied")
            assert not res.get("driver_reward_fee_waived")
        else:
            assert int(res.get("final_fare_cents") or 0) == 0
            assert res.get("rider_reward_applied")
            assert res.get("driver_reward_fee_waived")
            assert int(res.get("platform_fee_cents") or 0) == 0
        balances.append(get_wallet_balance(hb))

    # After the loyalty ride, the driver's wallet should be restored to the pre-ride balance
    assert balances[-1] == balances[-2]
