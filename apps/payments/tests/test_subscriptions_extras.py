from fastapi.testclient import TestClient


def _auth(client: TestClient, phone: str, name: str = "X") -> dict:
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_subscription_cancel_and_insufficient_funds():
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
    client = TestClient(create_app())
    payer = "+963900066661"
    merch = "+963900066662"
    hp = _auth(client, payer, "P")
    hm = _auth(client, merch, "M")
    # Approve KYC and become merchant
    assert client.post("/kyc/dev/approve", headers=hp).status_code == 200
    assert client.post("/kyc/dev/approve", headers=hm).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=hm).status_code == 200
    # Topup payer small amount
    assert client.post("/wallet/topup", headers=hp, json={"amount_cents": 1000, "idempotency_key": "t1"}).status_code == 200
    # Create subscription for amount above balance
    r = client.post("/subscriptions", headers=hp, json={"merchant_phone": merch, "amount_cents": 2000, "interval_days": 1})
    assert r.status_code == 200, r.text
    sid = r.json().get("id")
    # Force due and process; should not charge due to insufficient balance
    assert client.post(f"/subscriptions/{sid}/dev_force_due", headers=hp).status_code == 200
    rr = client.post("/subscriptions/process_due", headers=hp)
    assert rr.status_code == 200
    assert rr.json().get("processed") == 0
    # Cancel subscription
    rc = client.post(f"/subscriptions/{sid}/cancel", headers=hp)
    assert rc.status_code == 200
    # Cancel again is idempotent
    rc2 = client.post(f"/subscriptions/{sid}/cancel", headers=hp)
    assert rc2.status_code == 200
