import jwt
from fastapi.testclient import TestClient


def _client_with_jwt_flags(validate_iss: bool = True, validate_aud: bool = True) -> tuple[TestClient, str]:
    from app import config
    from app.main import create_app
    # Reset Prometheus registry (avoid duplicate metrics)
    try:
        from prometheus_client import REGISTRY
        for c in list(REGISTRY._collector_to_names.keys()):  # type: ignore[attr-defined]
            try:
                REGISTRY.unregister(c)
            except Exception:
                pass
    except Exception:
        pass

    config.settings.JWT_VALIDATE_ISS = validate_iss
    config.settings.JWT_VALIDATE_AUD = validate_aud
    # Ensure known issuer/audience
    config.settings.JWT_ISSUER = "payments"
    config.settings.JWT_AUDIENCE = "users"
    secret = config.settings.JWT_SECRET
    return TestClient(create_app()), secret


def test_jwt_rejects_wrong_issuer_and_audience():
    client, secret = _client_with_jwt_flags(validate_iss=True, validate_aud=True)
    # Craft token with wrong iss and aud
    payload = {"sub": "00000000-0000-0000-0000-000000000000", "iss": "other", "aud": "notusers"}
    token = jwt.encode(payload, secret, algorithm="HS256")
    r = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    # Health is public; use a protected endpoint instead
    r = client.get("/wallet", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_jwt_expired_token_is_rejected():
    client, secret = _client_with_jwt_flags(validate_iss=False, validate_aud=False)
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": "00000000-0000-0000-0000-000000000000", "exp": int((now - dt.timedelta(seconds=1)).timestamp())}
    token = jwt.encode(payload, secret, algorithm="HS256")
    r = client.get("/wallet", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
