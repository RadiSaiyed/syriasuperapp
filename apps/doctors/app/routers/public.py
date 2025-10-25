from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, DoctorProfile, AvailabilitySlot, DoctorReview
from ..schemas import DoctorOut, SearchSlotsIn, SearchSlotsOut, SearchSlotOut


router = APIRouter(tags=["public"])  # no auth


@router.get("/doctors", response_model=list[DoctorOut])
def list_doctors(city: str | None = None, specialty: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    q = db.query(DoctorProfile)
    if city:
        q = q.filter(DoctorProfile.city == city)
    if specialty:
        q = q.filter(DoctorProfile.specialty == specialty)
    docs = q.limit(limit).offset(offset).all()
    res: list[DoctorOut] = []
    for d in docs:
        u = db.get(User, d.user_id)
        # Aggregate ratings
        from sqlalchemy import func
        avg, cnt = db.query(func.avg(DoctorReview.rating), func.count(DoctorReview.id)).filter(DoctorReview.doctor_id == d.id).one()
        # Search q over name/clinic
        if q:
            if ((u.name or "") + " " + (d.clinic_name or "")).lower().find(q.lower()) < 0:
                continue
        res.append(DoctorOut(id=str(d.id), user_id=str(d.user_id), name=u.name if u else None, specialty=d.specialty, city=d.city, clinic_name=d.clinic_name, rating_avg=float(avg) if avg is not None else None, rating_count=int(cnt) if cnt is not None else 0))
    return res


@router.get("/doctors/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: str, db: Session = Depends(get_db)):
    d = db.get(DoctorProfile, doctor_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    u = db.get(User, d.user_id)
    from sqlalchemy import func
    avg, cnt = db.query(func.avg(DoctorReview.rating), func.count(DoctorReview.id)).filter(DoctorReview.doctor_id == d.id).one()
    return DoctorOut(id=str(d.id), user_id=str(d.user_id), name=u.name if u else None, specialty=d.specialty, city=d.city, clinic_name=d.clinic_name, rating_avg=float(avg) if avg is not None else None, rating_count=int(cnt) if cnt is not None else 0)


@router.post("/search_slots", response_model=SearchSlotsOut)
def search_slots(payload: SearchSlotsIn, db: Session = Depends(get_db)):
    # Find free slots meeting criteria
    q = db.query(AvailabilitySlot).filter(AvailabilitySlot.is_booked == False)  # noqa: E712
    if payload.doctor_id:
        q = q.filter(AvailabilitySlot.doctor_id == payload.doctor_id)
    if payload.start_time:
        q = q.filter(AvailabilitySlot.start_time >= payload.start_time)
    if payload.end_time:
        q = q.filter(AvailabilitySlot.end_time <= payload.end_time)
    slots = q.order_by(AvailabilitySlot.start_time.asc()).limit(payload.limit).offset(payload.offset).all()
    out: list[SearchSlotOut] = []
    for s in slots:
        d = db.get(DoctorProfile, s.doctor_id)
        if not d:
            continue
        if payload.city and d.city != payload.city:
            continue
        if payload.specialty and d.specialty != payload.specialty:
            continue
        u = db.get(User, d.user_id)
        out.append(SearchSlotOut(
            doctor_id=str(d.id), doctor_name=(u.name if u else None), specialty=d.specialty, city=d.city,
            slot_id=str(s.id), start_time=s.start_time, end_time=s.end_time,
        ))
    return SearchSlotsOut(slots=out)
