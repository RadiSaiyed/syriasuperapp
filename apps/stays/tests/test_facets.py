from datetime import date, timedelta
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


def test_search_facets_and_policy_filters():
    # Host setup
    h = _auth("+963900000111", role="host", name="Host")
    r = client.post("/host/properties", headers=h, json={"name": "Facet Hotel", "type": "hotel", "city": "Damascus"})
    assert r.status_code == 200
    prop = r.json()
    pid = prop["id"]
    # Unit with policies/amenities
    r = client.post(f"/host/properties/{pid}/units", headers=h, json={
        "name": "Std Room",
        "capacity": 2,
        "total_units": 3,
        "price_cents_per_night": 40000,
        "amenities": ["free_cancellation", "breakfast", "pay_at_property"],
    })
    assert r.status_code == 200, r.text
    unit = r.json()

    # Add a review to generate rating facets
    g = _auth("+963900000112", role="guest", name="Guest")
    r = client.post(f"/properties/{pid}/reviews", headers=g, json={"rating": 5, "comment": "Great"})
    assert r.status_code == 200

    today = date.today() + timedelta(days=1)
    body = {
        "city": "Damascus",
        "check_in": today.isoformat(),
        "check_out": (today + timedelta(days=2)).isoformat(),
        "guests": 2,
        "group_by_property": True,
    }
    r = client.post("/search_availability", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "facets" in data
    facets = data["facets"] or {}
    # Expect rating bands and price histogram present
    assert isinstance(facets.get("rating_bands", {}), dict)
    assert isinstance(facets.get("price_histogram", {}), dict)

    # Policy filters should include the unit when flags are set
    body.update({
        "free_cancellation": True,
        "breakfast_included": True,
        "pay_at_property": True,
    })
    r = client.post("/search_availability", json=body)
    assert r.status_code == 200, r.text
    res = r.json().get("results", [])
    assert any(x["property_id"] == pid for x in res)

    # Listing: rating band filter 4+ and available_only
    r = client.get(f"/properties?city=Damascus&rating_band=4+&check_in={today.isoformat()}&check_out={(today + timedelta(days=2)).isoformat()}&available_only=true")
    assert r.status_code == 200
    items = r.json()
    assert any(x["id"] == pid for x in items)

