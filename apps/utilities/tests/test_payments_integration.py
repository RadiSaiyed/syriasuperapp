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
    client.post("/auth/request_otp", json={"phone": phone})
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
        if url.endswith("/internal/invoices"):
            return _FakeResponse(200, {"id": "PR_TEST"})
        if url.endswith("/internal/requests"):
            return _FakeResponse(200, {"id": "PR_TEST"})
        return _FakeResponse(200, {})


def test_bills_pay_creates_internal_invoice_issuer_to_user(monkeypatch):
    settings.PAYMENTS_BASE_URL = "http://payments.test"
    settings.PAYMENTS_INTERNAL_SECRET = "sek"
    settings.PAYMENTS_EBILL_ISSUER_PHONE = "+963910000000"

    from app.routers import bills as bills_mod
    fake = _FakeHttpxClient()
    monkeypatch.setattr(bills_mod.httpx, "Client", lambda timeout=5.0: fake)

    suf = int(time.time()) % 100000
    h = _auth(f"+9639030{suf:05d}")

    # List billers (seed), link account, refresh bills
    billers = client.get("/billers", headers=h).json()
    assert isinstance(billers, list) and billers, billers
    biller_id = billers[0]["id"]
    acc = client.post("/accounts/link", headers=h, json={"biller_id": biller_id, "account_ref": "ACC-1", "alias": "Home"}).json()
    client.post(f"/bills/refresh?account_id={acc['id']}", headers=h)
    bills = client.get("/bills", headers=h).json().get("bills", [])
    assert bills, bills
    bid = bills[0]["id"]

    # Pay bill
    out = client.post(f"/bills/{bid}/pay", headers=h).json()
    assert out.get("payment_request_id") == "PR_TEST"
    internal_posts = [p for p in fake.posts if p[0].endswith("/internal/invoices")]
    assert internal_posts, fake.posts
    sent = internal_posts[-1][2]
    assert sent.get("from_phone") == settings.PAYMENTS_EBILL_ISSUER_PHONE


def test_topup_creates_internal_payment_request_user_to_fee_wallet(monkeypatch):
    settings.PAYMENTS_BASE_URL = "http://payments.test"
    settings.PAYMENTS_INTERNAL_SECRET = "sek"
    settings.FEE_WALLET_PHONE = "+963999999999"

    from app.routers import topups as topups_mod
    fake = _FakeHttpxClient()
    monkeypatch.setattr(topups_mod.httpx, "Client", lambda timeout=5.0: fake)

    suf = int(time.time()) % 100000
    h = _auth(f"+9639031{suf:05d}")

    # Pick mobile biller
    billers = client.get("/billers?category=mobile", headers=h).json()
    assert billers, billers
    op_id = billers[0]["id"]

    out = client.post(
        "/topups",
        headers=h,
        json={"operator_biller_id": op_id, "target_phone": "+963900000000", "amount_cents": 5000},
    ).json()
    assert out.get("payment_request_id") == "PR_TEST"

    internal_posts = [p for p in fake.posts if p[0].endswith("/internal/requests")]
    assert internal_posts, fake.posts
    sent = internal_posts[-1][2]
    assert sent.get("to_phone") == settings.FEE_WALLET_PHONE

