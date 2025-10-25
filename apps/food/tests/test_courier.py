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


def test_courier_flow():
    s = int(time.time()) % 100000
    # Create order
    h_user = _auth(f"+9639070{s:05d}")
    r = client.get("/restaurants", headers=h_user)
    rid = r.json()[0]['id']
    r = client.get(f"/restaurants/{rid}/menu", headers=h_user)
    mi = r.json()[0]['id']
    client.post("/cart/items", headers=h_user, json={"menu_item_id": mi, "qty": 1})
    r = client.post("/orders/checkout", headers=h_user)
    oid = r.json()['id']

    # Admin set order to preparing
    h_owner = _auth(f"+9639071{s:05d}")
    client.post("/admin/dev/become_owner", headers=h_owner, params={"restaurant_id": rid})
    client.post(f"/admin/orders/{oid}/status", headers=h_owner, params={"status_value": "accepted"})
    client.post(f"/admin/orders/{oid}/status", headers=h_owner, params={"status_value": "preparing"})

    # Courier accepts and delivers
    h_courier = _auth(f"+9639072{s:05d}")
    r = client.get("/courier/available", headers=h_courier)
    assert any(o['id'] == oid for o in r.json().get('orders', []))
    client.post(f"/courier/orders/{oid}/accept", headers=h_courier)
    client.post(f"/courier/orders/{oid}/picked_up", headers=h_courier)
    client.post(f"/courier/orders/{oid}/delivered", headers=h_courier)

