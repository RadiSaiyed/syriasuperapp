import os
import time
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DB_URL",
    os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"),
)

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402


client = TestClient(app)


def _auth(phone: str, name: str = "Test"):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class _FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _FakeHttpxClient:
    def __init__(self, timeout=5.0):
        self.posts = []  # (url, headers, json)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: dict | None = None, json: dict | None = None, content: bytes | None = None):  # type: ignore[override]
        self.posts.append((url, headers or {}, json or {}))
        if url.endswith("/internal/requests"):
            return _FakeResponse(200, {"id": "PR_TEST"})
        return _FakeResponse(200, {})


def test_checkout_creates_internal_payment_request_user_to_fee_wallet(monkeypatch):
    settings.PAYMENTS_BASE_URL = "http://payments.test"
    settings.PAYMENTS_INTERNAL_SECRET = "sek"
    settings.FEE_WALLET_PHONE = "+963999999999"

    # Patch httpx.Client used in orders module
    from app.routers import orders as orders_mod
    fake = _FakeHttpxClient()
    monkeypatch.setattr(orders_mod.httpx, "Client", lambda timeout=5.0: fake)

    suf = int(time.time()) % 100000
    h = _auth(f"+9639020{suf:05d}")

    # Fetch shops (triggers dev seed) and products
    shops = client.get("/shops", headers=h).json()
    assert isinstance(shops, list) and shops, shops
    shop_id = shops[0]["id"]
    prods = client.get(f"/shops/{shop_id}/products", headers=h).json()
    assert isinstance(prods, list) and prods, prods
    p1 = prods[0]["id"]
    client.post("/cart/items", headers=h, json={"product_id": p1, "qty": 1})

    # Checkout
    order = client.post(
        "/orders/checkout",
        headers=h,
        json={"shipping_name": "John", "shipping_phone": "+963900000001", "shipping_address": "Damascus"},
    ).json()
    assert order.get("payment_request_id") == "PR_TEST"
    # Verify payload from user to fee wallet
    internal_posts = [p for p in fake.posts if p[0].endswith("/internal/requests")]
    assert internal_posts, fake.posts
    sent = internal_posts[-1][2]
    assert sent.get("to_phone") == settings.FEE_WALLET_PHONE

