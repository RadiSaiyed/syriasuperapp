import os
import time
from fastapi.testclient import TestClient


def _new_app_with_limits(backend: str, per_minute: int, auth_boost: int = 1, redis_url: str | None = None, monkeypatch=None):
    # Lazy import to avoid polluting global app
    from app import config
    from app.main import create_app
    # Reset default Prometheus registry to avoid duplicate metric registration across app instances in tests
    try:
        from prometheus_client import REGISTRY
        for c in list(REGISTRY._collector_to_names.keys()):  # type: ignore[attr-defined]
            try:
                REGISTRY.unregister(c)
            except Exception:
                pass
    except Exception:
        pass

    # Patch settings for this app instance
    if monkeypatch:
        monkeypatch.setattr(config.settings, "RATE_LIMIT_BACKEND", backend, raising=False)
        monkeypatch.setattr(config.settings, "RATE_LIMIT_PER_MINUTE", per_minute, raising=False)
        monkeypatch.setattr(config.settings, "RATE_LIMIT_AUTH_BOOST", auth_boost, raising=False)
        if redis_url:
            monkeypatch.setattr(config.settings, "REDIS_URL", redis_url, raising=False)
    else:
        config.settings.RATE_LIMIT_BACKEND = backend
        config.settings.RATE_LIMIT_PER_MINUTE = per_minute
        config.settings.RATE_LIMIT_AUTH_BOOST = auth_boost
        if redis_url:
            config.settings.REDIS_URL = redis_url
    # Ensure OTP exempt does not affect /health
    os.environ["RL_EXEMPT_OTP"] = "true"
    return create_app()


def test_rate_limit_memory_returns_429(monkeypatch):
    app = _new_app_with_limits("memory", per_minute=3, auth_boost=1, monkeypatch=monkeypatch)
    client = TestClient(app)
    codes = [client.get("/health").status_code for _ in range(5)]
    # Expect at least one 429 once limit exceeded
    assert codes.count(429) >= 1, codes


def test_rate_limit_redis_returns_429(monkeypatch):
    # Requires local redis (docker compose exposes :6379 in dev)
    app = _new_app_with_limits("redis", per_minute=3, auth_boost=1, redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"), monkeypatch=monkeypatch)
    client = TestClient(app)
    codes = [client.get("/health").status_code for _ in range(5)]
    assert codes.count(429) >= 1, codes
