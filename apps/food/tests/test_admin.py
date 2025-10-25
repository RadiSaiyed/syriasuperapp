import os
import time
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "User"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_flow():
    s = int(time.time()) % 100000
    # Owner attach to a restaurant
    h_owner = _auth(f"+9639060{s:05d}")
    # ensure we have at least one restaurant
    r = client.get("/restaurants", headers=h_owner)
    assert r.status_code == 200
    rid = r.json()[0]["id"]
    r = client.post("/admin/dev/become_owner", headers=h_owner, params={"restaurant_id": rid})
    assert r.status_code == 200

    # Another user creates an order for that restaurant
    h_user = _auth(f"+9639061{s:05d}")
    r = client.get(f"/restaurants/{rid}/menu", headers=h_user)
    assert r.status_code == 200
    mi = r.json()[0]["id"]
    r = client.post("/cart/items", headers=h_user, json={"menu_item_id": mi, "qty": 1})
    assert r.status_code == 200
    r = client.post("/orders/checkout", headers=h_user)
    assert r.status_code == 200
    oid = r.json()["id"]

    # Owner sees order, updates status
    r = client.get("/admin/orders", headers=h_owner)
    assert r.status_code == 200
    orders = r.json().get("orders", [])
    assert any(o["id"] == oid for o in orders)

    r = client.post(f"/admin/orders/{oid}/status", headers=h_owner, params={"status_value": "accepted"})
    assert r.status_code == 200

