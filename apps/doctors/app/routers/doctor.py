from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, DoctorProfile, AvailabilitySlot, Appointment, DoctorImage
from ..schemas import DoctorProfileIn, DoctorOut, SlotCreateIn, SlotOut, AppointmentsListOut, AppointmentOut, DoctorImageCreateIn, DoctorImageOut


router = APIRouter(prefix="/doctor", tags=["doctor"])


@router.post("/profile", response_model=DoctorOut)
def upsert_profile(payload: DoctorProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("doctor", "patient"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
    if user.role != "doctor":
        user.role = "doctor"
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if prof is None:
        prof = DoctorProfile(user_id=user.id, specialty=payload.specialty, city=payload.city, clinic_name=payload.clinic_name, address=payload.address, latitude=payload.latitude, longitude=payload.longitude, bio=payload.bio)
        db.add(prof)
        db.flush()
    else:
        prof.specialty = payload.specialty
        prof.city = payload.city
        prof.clinic_name = payload.clinic_name
        prof.address = payload.address
        prof.latitude = payload.latitude
        prof.longitude = payload.longitude
        prof.bio = payload.bio
    return DoctorOut(id=str(prof.id), user_id=str(user.id), name=user.name, specialty=prof.specialty, city=prof.city, clinic_name=prof.clinic_name, address=prof.address, latitude=prof.latitude, longitude=prof.longitude, bio=prof.bio)


@router.post("/slots", response_model=SlotOut)
def add_slot(payload: SlotCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if prof is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Create profile first")
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid time range")
    s = AvailabilitySlot(doctor_id=prof.id, start_time=payload.start_time, end_time=payload.end_time, is_booked=False, price_cents=payload.price_cents or 0)
    db.add(s)
    db.flush()
    return SlotOut(id=str(s.id), doctor_id=str(s.doctor_id), start_time=s.start_time, end_time=s.end_time, is_booked=s.is_booked, price_cents=s.price_cents)


@router.get("/slots", response_model=list[SlotOut])
def my_slots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if prof is None:
        return []
    slots = db.query(AvailabilitySlot).filter(AvailabilitySlot.doctor_id == prof.id).order_by(AvailabilitySlot.start_time.asc()).all()
    return [SlotOut(id=str(s.id), doctor_id=str(s.doctor_id), start_time=s.start_time, end_time=s.end_time, is_booked=s.is_booked, price_cents=s.price_cents) for s in slots]


@router.get("/appointments", response_model=AppointmentsListOut)
def my_appointments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if prof is None:
        return AppointmentsListOut(appointments=[])
    apps = db.query(Appointment).filter(Appointment.doctor_id == prof.id).order_by(Appointment.created_at.desc()).all()
    return AppointmentsListOut(appointments=[
        AppointmentOut(id=str(a.id), doctor_id=str(a.doctor_id), patient_user_id=str(a.patient_user_id), slot_id=str(a.slot_id), status=a.status, created_at=a.created_at) for a in apps
    ])


@router.post("/appointments/{appointment_id}/status", response_model=AppointmentOut)
def update_appointment_status(appointment_id: str, status_value: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if prof is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a doctor")
    ap = db.get(Appointment, appointment_id)
    if not ap or ap.doctor_id != prof.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    if status_value not in ("confirmed", "canceled", "completed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    ap.status = status_value
    if status_value == "canceled":
        slot = db.get(AvailabilitySlot, ap.slot_id)
        if slot:
            slot.is_booked = False
        try:
            if ap.payment_transfer_id and ap.price_cents > 0:
                from ..utils.webhooks import send_webhooks
                send_webhooks(db, "refund.requested", {"appointment_id": str(ap.id), "transfer_id": ap.payment_transfer_id, "amount_cents": int(ap.price_cents)})
                ap.refund_status = "requested"
                db.flush()
        except Exception:
            pass
    db.flush()
    return AppointmentOut(id=str(ap.id), doctor_id=str(ap.doctor_id), patient_user_id=str(ap.patient_user_id), slot_id=str(ap.slot_id), status=ap.status, created_at=ap.created_at, price_cents=ap.price_cents, payment_request_id=ap.payment_request_id)


@router.post("/images", response_model=list[DoctorImageOut])
def add_images(images: list[DoctorImageCreateIn], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if prof is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Create profile first")
    created = []
    for im in images:
        di = DoctorImage(doctor_id=prof.id, url=im.url, sort_order=im.sort_order)
        db.add(di)
        db.flush()
        created.append(DoctorImageOut(id=str(di.id), url=di.url, sort_order=di.sort_order))
    return created


@router.get("/images", response_model=list[DoctorImageOut])
def list_images(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if prof is None:
        return []
    imgs = db.query(DoctorImage).filter(DoctorImage.doctor_id == prof.id).order_by(DoctorImage.sort_order.asc(), DoctorImage.created_at.asc()).all()
    return [DoctorImageOut(id=str(i.id), url=i.url, sort_order=i.sort_order) for i in imgs]


@router.delete("/images/{image_id}")
def delete_image(image_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    img = db.get(DoctorImage, image_id)
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    prof = db.query(DoctorProfile).filter(DoctorProfile.user_id == user.id).one_or_none()
    if not prof or img.doctor_id != prof.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    db.delete(img)
    return {"detail": "ok"}
