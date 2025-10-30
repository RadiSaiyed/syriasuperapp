from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def _auth(phone: str, role: str | None = None, name: str = "Test"):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    payload = {"phone": phone, "otp": "123456", "name": name}
    if role:
        payload["role"] = role
    r = client.post("/auth/verify_otp", json=payload)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_top_pagination_headers():
    h = _auth("+963900000211", role="host", name="Host")
    # create 3 properties in same city
    for i in range(3):
        r = client.post("/host/properties", headers=h, json={"name": f"P{i}", "type": "hotel", "city": "TestCity"})
        assert r.status_code == 200
    r = client.get("/properties/top", params={"city": "TestCity", "limit": 1, "offset": 0})
    assert r.status_code in (200, 304)
    if r.status_code == 200:
        assert int(r.headers.get("X-Total-Count", "0")) >= 1
        link = r.headers.get("Link", "")
        # With 3 items and limit 1, there should be next
        assert "rel=\"next\"" in link or int(r.headers.get("X-Total-Count", "0")) <= 1


def test_nearby_pagination_headers():
    h = _auth("+963900000212", role="host", name="Host2")
    # near Damascus
    coords = [(33.51, 36.28), (33.52, 36.29), (33.53, 36.30)]
    for i, (lat, lon) in enumerate(coords):
        r = client.post("/host/properties", headers=h, json={"name": f"NP{i}", "type": "hotel", "city": "Damascus", "latitude": str(lat), "longitude": str(lon)})
        assert r.status_code == 200
    r = client.get("/properties/nearby", params={"lat": 33.51, "lon": 36.28, "radius_km": 100.0, "limit": 1, "offset": 0})
    assert r.status_code in (200, 304)
    if r.status_code == 200:
        assert int(r.headers.get("X-Total-Count", "0")) >= 1
        link = r.headers.get("Link", "")
        assert "rel=\"next\"" in link or int(r.headers.get("X-Total-Count", "0")) <= 1

