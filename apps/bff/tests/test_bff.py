import base64
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Dict

from fastapi.testclient import TestClient

# Ensure repository root on sys.path for `import apps.*`
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _bearer(sub: str = "00000000-0000-0000-0000-000000000001", phone: str = "+963900000001", extra: Dict[str, object] | None = None) -> str:
    payload = {"sub": sub, "phone": phone}
    if extra:
        payload.update(extra)
    # Minimal unsigned JWT shape header.payload.sig
    header_b64 = base64.urlsafe_b64encode(b"{}\n").decode("utf-8").rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    return f"Bearer {header_b64}.{payload_b64}.sig"


_APP = None


def _fresh_app():
    global _APP
    if _APP is not None:
        return _APP
    # Ensure non-prod gating is permissive (default) for dev endpoints
    os.environ.setdefault("APP_ENV", "dev")
    # Avoid redis in tests
    os.environ.setdefault("REDIS_URL", "")
    mod = importlib.import_module("apps.bff.app.main")
    _APP = mod.app
    return _APP


def test_health_and_features_etag():
    app = _fresh_app()
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    js = r.json()
    assert js.get("service") == "bff"

    r1 = client.get("/v1/features")
    assert r1.status_code == 200
    etag = r1.headers.get("etag")
    assert etag and len(etag) >= 8
    r2 = client.get("/v1/features", headers={"If-None-Match": etag})
    assert r2.status_code == 304


def test_push_topics_and_dev_send_and_broadcast():
    app = _fresh_app()
    client = TestClient(app)
    auth = _bearer(sub="user1", phone="+963900000001")

    # Topic subscribe/list/unsubscribe
    r = client.post("/v1/push/topic/subscribe", headers={"Authorization": auth}, json={"topic": "offers"})
    assert r.status_code == 200
    r = client.get("/v1/push/topic/list", headers={"Authorization": auth})
    assert r.status_code == 200 and "offers" in r.json().get("topics", [])
    r = client.post("/v1/push/topic/unsubscribe", headers={"Authorization": auth}, json={"topic": "offers"})
    assert r.status_code == 200

    # Register a device token to receive dev sends/broadcasts
    r = client.post(
        "/v1/push/register",
        headers={"Authorization": auth},
        json={"device_id": "dev1", "token": "tok1", "platform": "ios"},
    )
    assert r.status_code == 200

    # Dev list should show one registration
    r = client.get("/v1/push/dev/list", headers={"Authorization": auth})
    assert r.status_code == 200
    regs = r.json().get("registrations", [])
    assert isinstance(regs, list) and len(regs) == 1

    # Dev send to self should simulate one send (FCM key not set)
    r = client.post(
        "/v1/push/dev/send",
        headers={"Authorization": auth},
        json={"title": "Hello", "body": "World", "deeplink": "superapp://payments"},
    )
    assert r.status_code == 200 and r.json().get("sent") == 1

    # Subscribe to topic and broadcast to that topic
    r = client.post("/v1/push/topic/subscribe", headers={"Authorization": auth}, json={"topic": "news"})
    assert r.status_code == 200
    r = client.post(
        "/v1/push/dev/broadcast_topic",
        headers={"Authorization": auth},
        json={"topic": "news", "title": "News", "body": "Update"},
    )
    assert r.status_code == 200 and r.json().get("sent", 0) >= 1
