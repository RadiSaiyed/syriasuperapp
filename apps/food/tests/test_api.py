import os
import time
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "Buyer"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_browse_cart_checkout():
    suffix = int(time.time()) % 100000
    phone = f"+9639050{suffix:05d}"
    h = _auth(phone)

    # List restaurants and menu
    r = client.get("/restaurants", headers=h)
    assert r.status_code == 200
    restaurants = r.json()
    assert len(restaurants) >= 1
    rid = restaurants[0]["id"]
    r = client.get(f"/restaurants/{rid}/menu", headers=h)
    assert r.status_code == 200
    menu = r.json()
    assert len(menu) >= 1
    mi = menu[0]

    # Add to cart
    r = client.post("/cart/items", headers=h, json={"menu_item_id": mi["id"], "qty": 2})
    assert r.status_code == 200
    cart = r.json()
    assert cart["total_cents"] >= 1

    # Checkout -> order
    r = client.post("/orders/checkout", headers=h)
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["total_cents"] >= 1
    assert order["status"] in ("created", "accepted", "preparing", "out_for_delivery", "delivered")

