import os
import time
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

# Ensure DB_URL is set (tests in this repo rely on a running Postgres)
os.environ.setdefault(
    "DB_URL",
    os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"),
)

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402


client = TestClient(app)


def _auth(phone: str, role: str | None = None, name: str = "Test"):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    payload = {"phone": phone, "otp": "123456", "name": name}
    if role:
        payload["role"] = role
    r = client.post("/auth/verify_otp", json=payload)
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
    """Context-manager compatible fake httpx.Client capturing POSTs."""

    def __init__(self, timeout: float | int | None = None):
        self.timeout = timeout
        self.posts: list[tuple[str, dict, dict]] = []  # (url, headers, json)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: dict | None = None, json: dict | None = None, content: bytes | None = None):  # type: ignore[override]
        self.posts.append((url, headers or {}, json or {}))
        # Return success with an id for internal /requests
        if url.endswith("/internal/requests"):
            return _FakeResponse(200, {"id": "PR_TEST"})
        return _FakeResponse(200, {})


def test_booking_creates_internal_payment_request_doctor_to_patient(monkeypatch):
    # Force Payments integration code path
    settings.PAYMENTS_BASE_URL = "http://payments.test"
    settings.PAYMENTS_INTERNAL_SECRET = "sek"

    # Patch httpx.Client used in appointments module
    from app.routers import appointments as ap_mod

    fake = _FakeHttpxClient()

    def _mk_client(timeout=5.0):
        # Return the same fake client; captures posts
        return fake

    monkeypatch.setattr(ap_mod.httpx, "Client", _mk_client)

    suf = int(time.time()) % 100000
    doc_phone = f"+9639050{suf:05d}"
    pat_phone = f"+9639051{suf:05d}"
    h_doc = _auth(doc_phone, role="doctor", name="Doc")
    # Create profile and slot
    r = client.post("/doctor/profile", headers=h_doc, json={"specialty": "cardiology", "city": "Damascus"})
    assert r.status_code == 200, r.text
    now = datetime.utcnow().replace(microsecond=0)
    start = (now + timedelta(minutes=30)).isoformat()
    end = (now + timedelta(minutes=60)).isoformat()
    r = client.post("/doctor/slots", headers=h_doc, json={"start_time": start, "end_time": end, "price_cents": 4000})
    assert r.status_code == 200, r.text
    slot = r.json()

    h_pat = _auth(pat_phone, role="patient", name="Pat")
    r = client.post("/appointments", headers=h_pat, json={"slot_id": slot["id"]})
    assert r.status_code == 200, r.text
    appt = r.json()
    assert appt.get("payment_request_id") == "PR_TEST"

    # Verify posted payload has from_phone=doctor, to_phone=patient
    posts = list(fake.posts)
    assert any(u.endswith("/internal/requests") for (u, _, _) in posts), posts
    last = [p for p in posts if p[0].endswith("/internal/requests")][-1]
    sent = last[2]
    assert sent.get("from_phone") == doc_phone
    assert sent.get("to_phone") == pat_phone


def test_webhook_accept_confirms_appointment(monkeypatch):
    # Set webhook secret
    settings.PAYMENTS_WEBHOOK_SECRET = "demo_secret"

    suf = int(time.time()) % 100000
    doc_phone = f"+9639052{suf:05d}"
    pat_phone = f"+9639053{suf:05d}"

    # Fake httpx client to return PR id
    from app.routers import appointments as ap_mod
    fake = _FakeHttpxClient()

    def _mk_client(timeout=5.0):
        return fake

    settings.PAYMENTS_BASE_URL = "http://payments.test"
    settings.PAYMENTS_INTERNAL_SECRET = "sek"
    monkeypatch.setattr(ap_mod.httpx, "Client", _mk_client)

    # Create doc+slot and book
    h_doc = _auth(doc_phone, role="doctor", name="Doc")
    client.post("/doctor/profile", headers=h_doc, json={"specialty": "gp"})
    now = datetime.utcnow().replace(microsecond=0)
    start = (now + timedelta(minutes=10)).isoformat()
    end = (now + timedelta(minutes=40)).isoformat()
    slot = client.post("/doctor/slots", headers=h_doc, json={"start_time": start, "end_time": end, "price_cents": 5000}).json()
    h_pat = _auth(pat_phone, role="patient", name="Pat")
    appt = client.post("/appointments", headers=h_pat, json={"slot_id": slot["id"]}).json()
    pr_id = appt.get("payment_request_id") or "PR_TEST"

    # Send signed webhook (requests.accept)
    ts = str(int(time.time()))
    body = json.dumps({"type": "requests.accept", "data": {"id": pr_id, "transfer_id": "TR_WEB"}}, separators=(",", ":"))
    sign = hmac.new(settings.PAYMENTS_WEBHOOK_SECRET.encode(), (ts + "requests.accept").encode() + body.encode(), hashlib.sha256).hexdigest()
    r = client.post(
        "/payments/webhooks",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Ts": ts,
            "X-Webhook-Event": "requests.accept",
            "X-Webhook-Sign": sign,
        },
    )
    assert r.status_code == 200, r.text

    # Appointment should be confirmed
    out = client.get("/appointments", headers=h_pat).json()
    statuses = [a.get("status") for a in out.get("appointments", [])]
    assert any(s == "confirmed" for s in statuses)

