from fastapi.testclient import TestClient


def _auth(client: TestClient, phone: str, name: str = "X") -> dict:
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_over_refund_is_rejected():
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
    a = "+963900077771"  # merchant
    b = "+963900077772"  # payer
    ha = _auth(client, a, "M")
    hb = _auth(client, b, "P")
    # KYC and merchant
    assert client.post("/kyc/dev/approve", headers=ha).status_code == 200
    assert client.post("/kyc/dev/approve", headers=hb).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=ha).status_code == 200
    # Topup payer and pay QR
    assert client.post("/wallet/topup", headers=hb, json={"amount_cents": 5000, "idempotency_key": "topb"}).status_code == 200
    qr = client.post("/payments/merchant/qr", headers=ha, json={"amount_cents": 3000})
    code = qr.json()["code"]
    pay = client.post("/payments/merchant/pay", headers=hb, json={"code": code, "idempotency_key": "qp1"})
    assert pay.status_code == 200
    # Over-refund (more than 3000)
    tid = pay.json()["transfer_id"]
    r = client.post("/refunds", headers=ha, json={"original_transfer_id": tid, "amount_cents": 4000})
    assert r.status_code == 400
