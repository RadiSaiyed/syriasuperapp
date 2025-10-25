import os

# Set admin token before importing app
os.environ.setdefault("ADMIN_TOKEN", "admintest")
os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")

from fastapi.testclient import TestClient
from app.main import app  # noqa: E402


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_suspend_user_prevents_request():
    rider = "+963905600001"
    ha = auth(rider, "Rider")
    # Admin create suspension
    hdr = {"X-Admin-Token": os.environ["ADMIN_TOKEN"]}
    r = client.post("/admin/suspensions", headers=hdr, json={"user_phone": rider, "reason": "abuse", "minutes": 30})
    assert r.status_code == 200
    # Rider cannot request now
    r = client.post("/rides/request", headers=ha, json={"pickup_lat":33.51, "pickup_lon":36.27, "dropoff_lat":33.52, "dropoff_lon":36.28})
    assert r.status_code == 403
    assert r.json().get("detail") == "user_suspended"


def test_admin_unsuspend_user_allows_request():
    rider = "+963905600011"
    ha = auth(rider, "Rider")
    hdr = {"X-Admin-Token": os.environ["ADMIN_TOKEN"]}
    # suspend
    r = client.post("/admin/suspensions", headers=hdr, json={"user_phone": rider, "reason": "abuse", "minutes": 30})
    assert r.status_code == 200
    # unsuspend
    r = client.post("/admin/suspensions/unsuspend", headers=hdr, json={"user_phone": rider})
    assert r.status_code == 200
    assert r.json().get("unsuspended", 0) >= 1
    # should be able to request now
    r = client.post("/rides/request", headers=ha, json={"pickup_lat":33.51, "pickup_lon":36.27, "dropoff_lat":33.52, "dropoff_lon":36.28})
    # may be requested or assigned
    assert r.status_code == 200
