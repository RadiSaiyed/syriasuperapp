import os
import time
from fastapi.testclient import TestClient


def _client_with_redis_otp(monkeypatch, ttl: int = 2, max_attempts: int = 3):
    from app import config
    from app.main import create_app

    # Reset Prometheus registry to avoid duplicate metrics across app instances
    try:
        from prometheus_client import REGISTRY
        for c in list(REGISTRY._collector_to_names.keys()):  # type: ignore[attr-defined]
            try:
                REGISTRY.unregister(c)
            except Exception:
                pass
    except Exception:
        pass

    code = "654321"
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OTP_STORAGE_SECRET", "test-secret")
    monkeypatch.setenv("OTP_MODE", "redis")
    monkeypatch.setenv("OTP_TTL_SECS", str(ttl))
    monkeypatch.setenv("OTP_MAX_ATTEMPTS", str(max_attempts))
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setattr("superapp_shared.otp.generate_otp_code", lambda: code, raising=False)
    return TestClient(create_app()), code


def test_otp_redis_ttl_and_consume(monkeypatch):
    client, code = _client_with_redis_otp(monkeypatch, ttl=2, max_attempts=5)
    phone = "+963900099999"
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200

    # Read OTP from Redis directly
    import redis
    rr = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    session = rr.get(f"otp_phone:{phone}")
    assert session is not None
    session_id = session.decode() if hasattr(session, "decode") else str(session)
    assert rr.get(f"otp:{session_id}") is not None

    # Verify with correct code succeeds and consumes keys
    r2 = client.post("/auth/verify_otp", json={"phone": phone, "otp": code, "name": "T"})
    assert r2.status_code == 200, r2.text
    assert rr.get(f"otp:{session_id}") is None
    assert rr.get(f"otp_phone:{phone}") is None


def test_otp_redis_lockout_after_attempts(monkeypatch):
    client, code = _client_with_redis_otp(monkeypatch, ttl=10, max_attempts=2)
    phone = "+963900088888"
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200

    # Two wrong attempts
    for _ in range(2):
        r2 = client.post("/auth/verify_otp", json={"phone": phone, "otp": "000000", "name": "T"})
        assert r2.status_code == 400
    # Even with correct code now, should still be blocked
    import redis
    rr = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    session = rr.get(f"otp_phone:{phone}")
    assert session is not None
    r3 = client.post("/auth/verify_otp", json={"phone": phone, "otp": code, "name": "T"})
    assert r3.status_code == 400
