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


def test_shop_browse_cart_checkout():
    suffix = int(time.time()) % 100000
    phone = f"+9639011{suffix:05d}"
    h = _auth(phone)

    # List shops and products
    r = client.get("/shops", headers=h)
    assert r.status_code == 200
    shops = r.json()
    assert len(shops) >= 1
    shop_id = shops[0]["id"]
    r = client.get(f"/shops/{shop_id}/products", headers=h)
    assert r.status_code == 200
    products = r.json()
    assert len(products) >= 1
    prod = products[0]

    # Add to cart
    r = client.post("/cart/items", headers=h, json={"product_id": prod["id"], "qty": 2})
    assert r.status_code == 200
    cart = r.json()
    assert cart["total_cents"] >= 1

    # Checkout -> order
    r = client.post("/orders/checkout", headers=h)
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["total_cents"] >= 1
    assert order["status"] in ("created", "paid")

