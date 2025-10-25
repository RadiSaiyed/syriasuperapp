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


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_keys_contacts_and_send_inbox():
    s = int(time.time()) % 100000
    # user A
    hA = _auth(f"+9639080{s:05d}")
    r = client.post("/keys/publish", headers=hA, json={"device_id": "devA", "public_key": "pubA"})
    assert r.status_code == 200
    # user B
    hB = _auth(f"+9639081{s:05d}")
    r = client.post("/keys/publish", headers=hB, json={"device_id": "devB", "public_key": "pubB"})
    assert r.status_code == 200

    # add contact (A adds B)
    r = client.post("/contacts/add", headers=hA, json={"phone": f"+9639081{s:05d}"})
    assert r.status_code == 200

    # resolve B id
    # simple: get keys for B by asking A for B's user id through prior publish retrieval is not implemented;
    # workaround: call get_user_keys with own creds and user_id fetched via publishing is not exposed; so instead we send and expect 400 then fetch via device publish response not available.
    # For test, fetch B's devices via keys endpoint using A token by trying both user ids (not available). Instead, skip and use inbox by sending via B side will fail.
    # Simpler: patch: get B id from auth payload not available; so we call keys endpoint using B asking own id via get keys is invalid. We'll query DB bypass is not allowed.
    # Workaround: use contacts listing to get B id
    r = client.get("/contacts", headers=hA)
    assert r.status_code == 200
    cid = r.json()[0]['user_id']

    # A sends to B (ciphertext opaque)
    r = client.post("/messages/send", headers=hA, json={"recipient_user_id": cid, "sender_device_id": "devA", "ciphertext": "hello_cipher"})
    assert r.status_code == 200, r.text

    # B inbox should have it
    r = client.get("/messages/inbox", headers=hB)
    assert r.status_code == 200
    msgs = r.json().get('messages', [])
    assert any(m['ciphertext'] == 'hello_cipher' for m in msgs)

