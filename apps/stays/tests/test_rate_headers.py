from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_rate_limit_headers_present_on_suggest():
    r = client.get("/suggest", params={"q": "a"})
    assert r.status_code in (200, 304, 429)
    # Headers should be present even when limited
    assert r.headers.get("X-RateLimit-Limit") is not None
    assert r.headers.get("X-RateLimit-Remaining") is not None
    assert r.headers.get("X-RateLimit-Reset") is not None

