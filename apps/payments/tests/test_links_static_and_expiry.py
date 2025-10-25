from fastapi.testclient import TestClient


def _auth(client: TestClient, phone: str, name: str = "X") -> dict:
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_static_link_requires_amount_and_dynamic_expires():
    from app.main import create_app
    # Reset Prometheus registry for fresh app instance
    try:
        from prometheus_client import REGISTRY
        for c in list(REGISTRY._collector_to_names.keys()):  # type: ignore[attr-defined]
            try:
                REGISTRY.unregister(c)
            except Exception:
                pass
    except Exception:
        pass
    app = create_app()
    client = TestClient(app)

    a = "+963900055551"  # merchant
    b = "+963900055552"  # payer
    ha = _auth(client, a, "M")
    hb = _auth(client, b, "P")
    # KYC approve both
    assert client.post("/kyc/dev/approve", headers=ha).status_code == 200
    assert client.post("/kyc/dev/approve", headers=hb).status_code == 200
    # Become merchant
    assert client.post("/payments/dev/become_merchant", headers=ha).status_code == 200
    # Prefund payer
    assert client.post("/wallet/topup", headers=hb, json={"amount_cents": 5000, "idempotency_key": "lk-topup"}).status_code == 200

    # Create static link (no amount provided)
    r = client.post("/payments/links", headers=ha, json={"expires_in_minutes": 5})
    assert r.status_code == 200, r.text
    code = r.json()["code"]

    # Paying without amount should fail
    r2 = client.post("/payments/links/pay", headers=hb, json={"code": code, "idempotency_key": "lk1"})
    assert r2.status_code == 400
    # Pay with explicit amount works
    r3 = client.post("/payments/links/pay", headers=hb, json={"code": code, "idempotency_key": "lk2", "amount_cents": 1234})
    assert r3.status_code == 200, r3.text
