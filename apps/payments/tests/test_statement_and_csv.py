from fastapi.testclient import TestClient


def _auth(client: TestClient, phone: str, name: str = "X") -> dict:
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_merchant_statement_json_and_csv():
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
    a = "+963900022221"
    b = "+963900022222"
    ha = _auth(client, a, "M")
    hb = _auth(client, b, "P")
    # Become merchant and fund payer
    assert client.post("/kyc/dev/approve", headers=ha).status_code == 200
    assert client.post("/kyc/dev/approve", headers=hb).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=ha).status_code == 200
    assert client.post("/wallet/topup", headers=hb, json={"amount_cents": 3000, "idempotency_key": "stm-topup"}).status_code == 200
    # Make one QR payment
    code = client.post("/payments/merchant/qr", headers=ha, json={"amount_cents": 1000}).json()["code"]
    pay = client.post("/payments/merchant/pay", headers=hb, json={"code": code, "idempotency_key": "stm-pay"})
    assert pay.status_code == 200
    # JSON statement
    js = client.get("/payments/merchant/statement", headers=ha)
    assert js.status_code == 200
    data = js.json()
    assert data["gross_cents"] >= 1000 and data["net_cents"] <= data["gross_cents"]
    # CSV statement
    cs = client.get("/payments/merchant/statement", headers=ha, params={"format": "csv"})
    assert cs.status_code == 200
    txt = cs.text.replace("\r\n", "\n")
    assert txt.startswith("created_at,direction,amount_cents,currency_code,transfer_id\n")
