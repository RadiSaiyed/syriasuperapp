import os
import time
from fastapi.testclient import TestClient

# Use a local default Postgres DB for tests if not provided
os.environ.setdefault(
    "DB_URL",
    os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"),
)

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str, role: str | None = None, name: str = "Test"):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    payload = {"phone": phone, "otp": "123456", "name": name}
    if role:
        payload["role"] = role
    r = client.post("/auth/verify_otp", json=payload)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_employer_can_create_company_and_job_and_list_open_jobs():
    suffix = int(time.time()) % 100000
    phone = f"+9639020{suffix:05d}"
    h = _auth(phone, role="employer", name="Employer")

    # Create company
    r = client.post("/employer/company", headers=h, json={"name": "ACME", "description": "Test Co"})
    assert r.status_code in (200, 400), r.text  # 400 if already exists (re-run)

    # Create job
    r = client.post(
        "/employer/jobs",
        headers=h,
        json={"title": "Backend Dev", "description": "FastAPI", "location": "Damascus", "salary_cents": 1000000},
    )
    assert r.status_code == 200, r.text
    job = r.json()
    job_id = job["id"]

    # My jobs contains it
    r = client.get("/employer/jobs", headers=h)
    assert r.status_code == 200
    my_jobs = r.json()
    assert any(j["id"] == job_id for j in my_jobs)

    # Open jobs contains it
    r = client.get("/jobs")
    assert r.status_code == 200
    open_jobs = r.json().get("jobs", [])
    assert any(j["id"] == job_id for j in open_jobs)


def test_seeker_can_apply_and_list_applications():
    # Ensure there is at least one open job; if not, create one quickly via a temp employer
    r = client.get("/jobs")
    assert r.status_code == 200
    jobs = r.json().get("jobs", [])
    if not jobs:
        h_emp = _auth(f"+9639021{int(time.time())%100000:05d}", role="employer", name="Emp")
        client.post("/employer/company", headers=h_emp, json={"name": "TEMP", "description": ""})
        r2 = client.post("/employer/jobs", headers=h_emp, json={"title": "Temp Job"})
        assert r2.status_code == 200
        jobs = [r2.json()]

    job_id = jobs[0]["id"]

    # Login as seeker and apply
    h = _auth(f"+9639022{int(time.time())%100000:05d}", role="seeker", name="Seeker")
    r = client.post(f"/jobs/{job_id}/apply", headers=h, json={"cover_letter": "Hallo"})
    assert r.status_code == 200, r.text

    # Applying twice should fail
    r2 = client.post(f"/jobs/{job_id}/apply", headers=h, json={"cover_letter": "Again"})
    assert r2.status_code == 400

    # My applications show the application
    r = client.get("/applications", headers=h)
    assert r.status_code == 200
    apps = r.json().get("applications", [])
    assert len(apps) >= 1

