from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from .utils import unique_phone


def _auth(client: TestClient, phone: str, name: str = "X") -> dict:
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_concurrent_p2p_idempotency_single_transfer(monkeypatch):
    import os
    # Use local Postgres if not provided
    os.environ.setdefault(
        "DB_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres",
    )
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
    # Disable velocity/risk guards to focus on idempotency
    import app.utils.fraud as fraud
    import app.utils.risk as risk
    monkeypatch.setattr(fraud, "check_p2p_velocity", lambda db, user, amt: None)
    monkeypatch.setattr(risk, "evaluate_risk_and_maybe_block", lambda db, user, amt, **kw: None)

    a = unique_phone("005555")
    b = unique_phone("005556")
    ha = _auth(client, a, "A")
    hb = _auth(client, b, "B")
    # Prefund A
    assert client.post("/wallet/topup", headers=ha, json={"amount_cents": 20000, "idempotency_key": f"prefund-{a}"}).status_code == 200

    idem = f"p2p-concurrent-{a}"

    def send_once():
        return client.post("/wallet/transfer", headers=ha, json={"to_phone": b, "amount_cents": 2000, "idempotency_key": idem})

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(send_once) for _ in range(10)]
        results = [f.result() for f in as_completed(futs)]

    assert all(r.status_code == 200 for r in results)
    ids = {r.json()["transfer_id"] for r in results}
    assert len(ids) == 1

    # Sender should be debited once (allowing for rounding none). 20000 - 2000 = 18000 minimum
    wa = client.get("/wallet", headers=ha)
    assert wa.status_code == 200
    assert wa.json()["wallet"]["balance_cents"] >= 18000
