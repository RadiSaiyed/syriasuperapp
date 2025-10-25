import os
from fastapi.testclient import TestClient

# Configure Redis rate limiter before importing the app
os.environ.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/taxi")
os.environ.setdefault("RATE_LIMIT_BACKEND", "redis")
redis_url = os.getenv("REDIS_TEST_URL", "redis://localhost:6381/0")
os.environ.setdefault("REDIS_URL", redis_url)
os.environ.setdefault("RATE_LIMIT_REDIS_PREFIX", "rl_taxi_test")
# Keep OTP exempt, test uses /health
os.environ["RL_LIMIT_PER_MINUTE_OVERRIDE"] = "2"
os.environ["RL_AUTH_BOOST_OVERRIDE"] = "1"

from app.main import app  # noqa: E402


client = TestClient(app)


import pytest


@pytest.fixture(scope="module", autouse=True)
def _enable_real_rate_limit():
    prev = os.environ.get("RL_TEST_DISABLE")
    os.environ["RL_TEST_DISABLE"] = "false"
    yield
    if prev is None:
        os.environ.pop("RL_TEST_DISABLE", None)
    else:
        os.environ["RL_TEST_DISABLE"] = prev


def test_redis_rate_limit_health_endpoint():
    # within the same minute window, the 3rd request should be rate limited (limit=2)
    r1 = client.get("/health")
    assert r1.status_code == 200
    r2 = client.get("/health")
    assert r2.status_code == 200
    r3 = client.get("/health")
    assert r3.status_code == 429, r3.text
    js = r3.json()
    assert (js.get("error", {}) or {}).get("code") == "rate_limited"
