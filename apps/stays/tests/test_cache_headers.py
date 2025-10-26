from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_suggest_etag_304():
    r1 = client.get("/suggest", params={"q": "Damascus"})
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag is not None
    r2 = client.get("/suggest", params={"q": "Damascus"}, headers={"If-None-Match": etag})
    assert r2.status_code == 304

