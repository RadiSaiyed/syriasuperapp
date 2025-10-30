import os
import time
import json
import hmac
import hashlib
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402


client = TestClient(app)


def test_webhook_signature_validation():
    settings.PAYMENTS_WEBHOOK_SECRET = "demo_secret"
    ts = str(int(time.time()))
    body = json.dumps({"type": "requests.accept", "data": {"id": "PR_X", "transfer_id": "TR_Y"}}, separators=(",", ":"))
    # invalid signature
    r = client.post(
        "/payments/webhooks",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Ts": ts,
            "X-Webhook-Event": "requests.accept",
            "X-Webhook-Sign": "deadbeef",
        },
    )
    assert r.status_code == 403

    # valid signature
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

