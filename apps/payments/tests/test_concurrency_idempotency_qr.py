from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from .utils import unique_phone


def _auth(client: TestClient, phone: str, name: str = "X") -> dict:
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_concurrent_qr_pay_idempotency_single_transfer(monkeypatch):
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
    # Disable risk/velocity guards for concurrency test
    import app.utils.fraud as fraud
    import app.utils.risk as risk
    monkeypatch.setattr(fraud, "check_qr_velocity", lambda db, user, n: None)
    monkeypatch.setattr(risk, "evaluate_risk_and_maybe_block", lambda db, user, amt, **kw: None)

    a = unique_phone("004444")
    b = unique_phone("004445")
    ha = _auth(client, a, "M")
    hb = _auth(client, b, "P")
    assert client.post("/kyc/dev/approve", headers=ha).status_code == 200
    assert client.post("/kyc/dev/approve", headers=hb).status_code == 200
    assert client.post("/payments/dev/become_merchant", headers=ha).status_code == 200
    # Prefund payer
    assert client.post("/wallet/topup", headers=hb, json={"amount_cents": 50000, "idempotency_key": f"prefund-{b}"}).status_code == 200
    # Create QR
    qr = client.post("/payments/merchant/qr", headers=ha, json={"amount_cents": 3000})
    assert qr.status_code == 200, qr.text
    code = qr.json()["code"]

    idem = f"qr-concurrent-{b}"

    def pay_once():
        return client.post("/payments/merchant/pay", headers=hb, json={"code": code, "idempotency_key": idem})

    # Fire 10 concurrent payments with same idempotency key
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(pay_once) for _ in range(10)]
        results = [f.result() for f in as_completed(futs)]

    # All succeed and share the same transfer_id
    assert all(r.status_code == 200 for r in results)
    ids = {r.json()["transfer_id"] for r in results}
    assert len(ids) == 1

    # Check payer balance reduced exactly once amount
    wb = client.get("/wallet", headers=hb)
    assert wb.status_code == 200
    # remaining balance should be 50000 - 3000 +/- fees; minimum 47000
    assert wb.json()["wallet"]["balance_cents"] >= 47000
