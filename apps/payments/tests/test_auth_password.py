from fastapi.testclient import TestClient
import os
import secrets

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import create_app  # noqa: E402


client = TestClient(create_app())


def _unique_user() -> tuple[str, str, str]:
    suffix = secrets.token_hex(4)
    username = f"testuser_{suffix}"
    phone = "+9639" + str(secrets.randbits(28)).zfill(8)[:8]
    password = "SecretPass123"
    return username, phone, password


def test_register_and_login_password_flow():
    u, ph, pw = _unique_user()
    # Register
    r = client.post("/auth/register", json={"username": u, "password": pw, "phone": ph, "name": "Test"})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    assert isinstance(tok, str) and len(tok) > 10
    # Wallet should be accessible
    w = client.get("/wallet", headers={"Authorization": f"Bearer {tok}"})
    assert w.status_code == 200, w.text
    # Duplicate username
    r2 = client.post("/auth/register", json={"username": u, "password": pw, "phone": "+9639300" + ph[-4:], "name": "Dup"})
    assert r2.status_code == 400
    assert r2.json().get("error", {}).get("message") == "username_taken"
    # Duplicate phone
    r3 = client.post("/auth/register", json={"username": u + "x", "password": pw, "phone": ph, "name": "Dup"})
    assert r3.status_code == 400
    assert r3.json().get("error", {}).get("message") == "phone_taken"
    # Login
    r4 = client.post("/auth/login", json={"username": u, "password": pw})
    assert r4.status_code == 200, r4.text
    tok2 = r4.json().get("access_token")
    assert isinstance(tok2, str) and len(tok2) > 10
    # Wrong password
    r5 = client.post("/auth/login", json={"username": u, "password": pw + "x"})
    assert r5.status_code == 401
    assert r5.json().get("error", {}).get("message") == "invalid_credentials"

