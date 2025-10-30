from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_properties_etag_304():
    # no data assumptions; list may be empty
    r1 = client.get("/properties", params={"limit": 1, "offset": 0})
    assert r1.status_code in (200, 304)
    if r1.status_code == 200:
        etag = r1.headers.get("ETag")
        assert etag is not None
        r2 = client.get("/properties", params={"limit": 1, "offset": 0}, headers={"If-None-Match": etag})
        assert r2.status_code == 304

