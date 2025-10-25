import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")

from app.main import app  # noqa: E402


client = TestClient(app)


def test_verify_otp_wrong_code_returns_400():
    phone = "+963900999999"
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "000000", "name": "X"})
    assert r.status_code == 400
