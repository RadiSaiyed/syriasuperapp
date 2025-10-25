import os
import time
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

# Create a temporary test database and point the app to it BEFORE importing app.
DEFAULT_DB = "postgresql+psycopg2://postgres:postgres@localhost:5438/freight"
BASE_URL = os.getenv("DB_URL", DEFAULT_DB)
_base = make_url(BASE_URL)
_test_db_name = f"freight_test_{uuid.uuid4().hex[:8]}"
_admin_url = _base.set(database="postgres")
_test_url = _base.set(database=_test_db_name)

_admin_engine = create_engine(
    _admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT"
)
with _admin_engine.connect() as conn:
    try:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_test_db_name} WITH (FORCE)"))
    except Exception:
        try:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d AND pid <> pg_backend_pid()"
                ),
                {"d": _test_db_name},
            )
            conn.execute(text(f"DROP DATABASE IF EXISTS {_test_db_name}"))
        except Exception:
            pass
    conn.execute(text(f"CREATE DATABASE {_test_db_name}"))

os.environ["DB_URL"] = _test_url.render_as_string(hide_password=False)

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str, name: str = "Test"):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post(
        "/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name}
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_shipper_carrier_flow_with_filters_and_chat():
    # Unique-ish suffix to avoid phone collisions
    suffix = int(time.time()) % 100000

    # 1) Shipper logs in and posts a load
    shipper_h = _auth(f"+963910{suffix:05d}", name="Shipper")
    payload = {
        "origin": "Damascus",
        "destination": "Aleppo",
        "weight_kg": 1000,
        "price_cents": 50000,
    }
    r = client.post("/shipper/loads", headers=shipper_h, json=payload)
    assert r.status_code == 200, r.text
    load = r.json()
    load_id = load["id"]
    assert load["status"] == "posted"

    # 2) Carrier logs in and gets approved (dev)
    carrier_h = _auth(f"+963920{suffix:05d}", name="Carrier")
    r = client.post(
        "/carrier/apply", headers=carrier_h, json={"company_name": "ACME"}
    )
    assert r.status_code == 200, r.text

    # 3) Carrier lists available loads with filters (should include our load)
    r = client.get(
        "/carrier/loads/available",
        headers=carrier_h,
        params={
            "origin": "Dam",
            "destination": "Ale",
            "min_weight": 500,
            "max_weight": 2000,
        },
    )
    assert r.status_code == 200, r.text
    rows = r.json().get("loads", [])
    assert any(l["id"] == load_id for l in rows)

    # 4) Accept the load
    r = client.post(f"/loads/{load_id}/accept", headers=carrier_h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "assigned"

    # 5) Pickup → In transit → Deliver
    r = client.post(f"/loads/{load_id}/pickup", headers=carrier_h)
    assert r.status_code == 200
    assert r.json()["status"] == "picked_up"

    r = client.post(f"/loads/{load_id}/in_transit", headers=carrier_h)
    assert r.status_code == 200
    assert r.json()["status"] == "in_transit"

    r = client.post(f"/loads/{load_id}/deliver", headers=carrier_h)
    assert r.status_code == 200
    assert r.json()["status"] == "delivered"
    # payment_request_id may be present or None depending on Payments availability

    # 6) POD URL
    r = client.post(
        f"/loads/{load_id}/pod",
        headers=carrier_h,
        params={"url": "http://example.com/pod.jpg"},
    )
    assert r.status_code == 200

    # 7) Chat both ways
    r = client.post(
        f"/chats/load/{load_id}", headers=shipper_h, json={"content": "Hello"}
    )
    assert r.status_code == 200
    r = client.post(
        f"/chats/load/{load_id}", headers=carrier_h, json={"content": "On my way"}
    )
    assert r.status_code == 200
    r = client.get(f"/chats/load/{load_id}", headers=shipper_h)
    assert r.status_code == 200
    msgs = r.json().get("messages", [])
    assert len(msgs) >= 2


def teardown_module(_module=None):
    # Drop the ephemeral test database
    try:
        from app.database import engine as app_engine  # noqa: WPS433,E402

        app_engine.dispose()
    except Exception:
        pass
    admin_engine = create_engine(
        _admin_url.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as conn:
        try:
            conn.execute(text(f"DROP DATABASE IF EXISTS {_test_db_name} WITH (FORCE)"))
        except Exception:
            try:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d AND pid <> pg_backend_pid()"
                    ),
                    {"d": _test_db_name},
                )
                conn.execute(text(f"DROP DATABASE IF EXISTS {_test_db_name}"))
            except Exception:
                pass
