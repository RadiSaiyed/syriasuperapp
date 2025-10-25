from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, AvailabilitySlot, Appointment, DoctorProfile
from ..schemas import AppointmentCreateIn, AppointmentOut, AppointmentsListOut
from ..config import settings
import httpx
import time, hmac, hashlib, json
from prometheus_client import Counter


router = APIRouter(prefix="/appointments", tags=["appointments"]) 

# App-specific metrics
APPTS_COUNTER = Counter("doctors_appointments_total", "Doctor appointments", ["status"]) 


@router.post("", response_model=AppointmentOut)
def book(payload: AppointmentCreateIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slot = db.get(AvailabilitySlot, payload.slot_id)
    if not slot or slot.is_booked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not available")
    doc = db.get(DoctorProfile, slot.doctor_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor missing")
    # Mark slot as booked and create appointment
    slot.is_booked = True
    ap = Appointment(patient_user_id=user.id, doctor_id=doc.id, slot_id=slot.id, status="created", price_cents=slot.price_cents or 0)
    db.add(ap)
    db.flush()

    # Optional Payments integration
    try:
        amount = ap.price_cents or 0
        if amount > 0 and settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET:
            # Request money for the doctor (requester=doctor, target=patient)
            # Accepting the request (by patient) will transfer from patient -> doctor
            doc_user = db.get(User, doc.user_id)
            from_phone = doc_user.phone if doc_user and doc_user.phone else settings.FEE_WALLET_PHONE
            to_phone = user.phone
            payload_json = {"from_phone": from_phone, "to_phone": to_phone, "amount_cents": amount}
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.PAYMENTS_BASE_URL}/internal/requests",
                    headers=headers,
                    json=payload_json,
                )
                if r.status_code < 400:
                    ap.payment_request_id = r.json().get("id")
    except Exception:
        pass

    try:
        APPTS_COUNTER.labels(status=ap.status).inc()
    except Exception:
        pass
    return AppointmentOut(id=str(ap.id), doctor_id=str(ap.doctor_id), patient_user_id=str(ap.patient_user_id), slot_id=str(ap.slot_id), status=ap.status, created_at=ap.created_at, price_cents=ap.price_cents, payment_request_id=ap.payment_request_id)


@router.get("", response_model=AppointmentsListOut)
def my_appointments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    apps = db.query(Appointment).filter(Appointment.patient_user_id == user.id).order_by(Appointment.created_at.desc()).all()
    return AppointmentsListOut(appointments=[
        AppointmentOut(id=str(a.id), doctor_id=str(a.doctor_id), patient_user_id=str(a.patient_user_id), slot_id=str(a.slot_id), status=a.status, created_at=a.created_at, price_cents=a.price_cents, payment_request_id=a.payment_request_id) for a in apps
    ])


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_my_appointment(appointment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ap = db.get(Appointment, appointment_id)
    if not ap or ap.patient_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if ap.status in ("canceled", "completed"):
        return AppointmentOut(id=str(ap.id), doctor_id=str(ap.doctor_id), patient_user_id=str(ap.patient_user_id), slot_id=str(ap.slot_id), status=ap.status, created_at=ap.created_at, price_cents=ap.price_cents, payment_request_id=ap.payment_request_id)
    ap.status = "canceled"
    slot = db.get(AvailabilitySlot, ap.slot_id)
    if slot:
        slot.is_booked = False
    db.flush()
    try:
        if ap.payment_transfer_id and ap.price_cents > 0:
            from ..utils.webhooks import send_webhooks
            send_webhooks(db, "refund.requested", {"appointment_id": str(ap.id), "transfer_id": ap.payment_transfer_id, "amount_cents": int(ap.price_cents)})
            ap.refund_status = "requested"
            db.flush()
    except Exception:
        pass
    return AppointmentOut(id=str(ap.id), doctor_id=str(ap.doctor_id), patient_user_id=str(ap.patient_user_id), slot_id=str(ap.slot_id), status=ap.status, created_at=ap.created_at, price_cents=ap.price_cents, payment_request_id=ap.payment_request_id)
