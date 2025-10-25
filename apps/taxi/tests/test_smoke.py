import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str, name: str):
    client.post("/auth/request_otp", json={"phone": phone})
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_quote_and_promo_and_favorites_and_maps():
    rider = "+963905000001"
    h = _auth(rider, "Rider")

    # Maps: reverse + autocomplete (dev network)
    r = client.get("/maps/reverse", headers=h, params={"lat": 33.5138, "lon": 36.2765})
    assert r.status_code in (200, 502)  # allow geocoder_unavailable in CI
    r = client.get("/maps/autocomplete", headers=h, params={"q": "Damascus", "limit": 2})
    assert r.status_code in (200, 502)

    # Dev promo create + list
    code = "TEST10PY"
    r = client.post(
        "/promos",
        headers=h,
        json={"code": code, "percent_off_bps": 1000, "active": True},
    )
    assert r.status_code in (200, 403)  # allow disabled in non-dev

    # Quote without/with promo
    payload = {
        "pickup_lat": 33.5138,
        "pickup_lon": 36.2765,
        "dropoff_lat": 33.52,
        "dropoff_lon": 36.28,
    }
    r = client.post("/rides/quote", headers=h, json=payload)
    assert r.status_code == 200
    q0 = r.json()
    r = client.post("/rides/quote", headers=h, json=dict(payload, promo_code=code))
    if r.status_code == 200:
        q1 = r.json()
        assert q1["final_quote_cents"] <= q0["quoted_fare_cents"]

    # Favorites CRUD
    r = client.post(
        "/favorites",
        headers=h,
        json={"label": "Home", "lat": 33.51, "lon": 36.27},
    )
    assert r.status_code == 200
    fav_id = r.json()["id"]
    r = client.get("/favorites", headers=h)
    assert r.status_code == 200 and any(it["id"] == fav_id for it in r.json())
    r = client.delete(f"/favorites/{fav_id}", headers=h)
    assert r.status_code == 200

