import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("PAYMENTS_BASE_URL", "http://payments.test")
os.environ.setdefault("PAYMENTS_INTERNAL_SECRET", "test-secret")

from app.main import app  # noqa: E402


client = TestClient(app)


def auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_request_and_cancel_flow():
    # Rider & Driver
    A = "+963900200001"
    B = "+963900200002"
    ha = auth(A, "Ali")
    hb = auth(B, "Driver")

    # Driver apply, set available and location
    r = client.post("/driver/apply", headers=hb, json={"vehicle_make": "Toyota", "vehicle_plate": "ABC"})
    assert r.status_code == 200
    r = client.put("/driver/status", headers=hb, json={"status": "available"})
    assert r.status_code == 200
    r = client.put("/driver/location", headers=hb, json={"lat": 33.5138, "lon": 36.2765})
    assert r.status_code == 200

    # Rider requests a ride
    r = client.post(
        "/rides/request",
        headers=ha,
        json={
            "pickup_lat": 33.5138,
            "pickup_lon": 36.2765,
            "dropoff_lat": 33.52,
            "dropoff_lon": 36.28,
        },
    )
    assert r.status_code == 200
    ride_id = r.json()["id"]
    assert ride_id

    # Rider cancels (MVP behavior returns to requested; here we just expect a valid response)
    r = client.post(f"/rides/{ride_id}/cancel_by_rider", headers=ha)
    assert r.status_code == 200


def test_wallet_balance_proxy(monkeypatch):
    phone = "+963900200010"
    headers = auth(phone, "WalletUser")

    class DummyResponse:
        def __init__(self, data):
            self.status_code = 200
            self._data = data
            self.text = ""

        def json(self):
            return self._data

    def fake_client(*args, **kwargs):
        class _Client:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc_val, exc_tb):
                return False

            def get(self_inner, url, params=None, headers=None):
                assert params and params.get("phone") == phone
                return DummyResponse(
                    {
                        "phone": phone,
                        "wallet_id": "wallet-123",
                        "balance_cents": 43210,
                        "currency_code": "SYP",
                    }
                )

        return _Client()

    monkeypatch.setattr("app.routers.wallet.httpx.Client", fake_client)

    res = client.get("/wallet/balance", headers=headers)
    assert res.status_code == 200
    js = res.json()
    assert js["phone"] == phone
    assert js["balance_cents"] == 43210
    assert js["currency_code"] == "SYP"
