import os
import time
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

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


def test_doctor_profile_slots_and_booking_flow():
    suf = int(time.time()) % 100000
    # Doctor creates profile and slot
    h_doc = _auth(f"+9639040{suf:05d}", role="doctor", name="Dr. Noor")
    r = client.post("/doctor/profile", headers=h_doc, json={"specialty": "dentist", "city": "Damascus", "clinic_name": "Smile Clinic"})
    assert r.status_code == 200, r.text
    now = datetime.utcnow().replace(microsecond=0)
    start = (now + timedelta(days=1, hours=1)).isoformat()
    end = (now + timedelta(days=1, hours=1, minutes=30)).isoformat()
    r = client.post("/doctor/slots", headers=h_doc, json={"start_time": start, "end_time": end})
    assert r.status_code == 200, r.text
    slot = r.json()

    # Public search slots
    r = client.post("/search_slots", json={"city": "Damascus", "specialty": "dentist", "start_time": (now).isoformat(), "end_time": (now + timedelta(days=2)).isoformat()})
    assert r.status_code == 200
    slots = r.json().get("slots", [])
    assert any(s["slot_id"] == slot["id"] for s in slots)

    # Patient books the slot
    h_pat = _auth(f"+9639041{suf:05d}", role="patient", name="Patient")
    r = client.post("/appointments", headers=h_pat, json={"slot_id": slot["id"]})
    assert r.status_code == 200, r.text
    ap = r.json()
    assert ap["status"] in ("created", "confirmed")

    # Patient lists appointments
    r = client.get("/appointments", headers=h_pat)
    assert r.status_code == 200
    assert len(r.json().get("appointments", [])) >= 1

