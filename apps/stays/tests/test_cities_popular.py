from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_cities_popular_headers_present():
    r = client.get("/cities/popular")
    assert r.status_code in (200, 304)
    # Headers
    assert r.headers.get("Cache-Control") is not None
    assert r.headers.get("ETag") is not None
    # X-Total-Count may be present
    xt = r.headers.get("X-Total-Count")
    if xt is not None:
        assert int(xt) >= 0

