from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fastapi import Query
from ..auth import get_current_user, get_db
from ..models import User, CarrierProfile, Load, CarrierLocation
from ..schemas import CarrierApplyIn, LoadOut, LoadsListOut, CarrierLocationIn


router = APIRouter(prefix="/carrier", tags=["carrier"])


@router.post("/apply")
def apply_carrier(payload: CarrierApplyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(CarrierProfile).filter(CarrierProfile.user_id == user.id).one_or_none()
    if prof is None:
        prof = CarrierProfile(user_id=user.id, company_name=payload.company_name or None, status="approved")
        db.add(prof)
        user.role = "carrier"
        db.flush()
    return {"detail": "approved"}


@router.get("/loads/available", response_model=LoadsListOut)
def available_loads(
    origin: str | None = Query(None),
    destination: str | None = Query(None),
    min_weight: int | None = Query(None),
    max_weight: int | None = Query(None),
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    # list loads not assigned with basic filters
    q = db.query(Load).filter(Load.status == "posted")
    if origin:
        q = q.filter(Load.origin.ilike(f"%{origin}%"))
    if destination:
        q = q.filter(Load.destination.ilike(f"%{destination}%"))
    if min_weight is not None:
        q = q.filter(Load.weight_kg >= min_weight)
    if max_weight is not None:
        q = q.filter(Load.weight_kg <= max_weight)
    rows = q.order_by(Load.created_at.desc()).limit(100).all()
    return LoadsListOut(loads=[LoadOut(id=str(l.id), status=l.status, shipper_user_id=str(l.shipper_user_id), carrier_id=str(l.carrier_id) if l.carrier_id else None, origin=l.origin, destination=l.destination, weight_kg=l.weight_kg, price_cents=l.price_cents, payment_request_id=l.payment_request_id) for l in rows])


@router.put("/location")
def update_location(payload: CarrierLocationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(CarrierProfile).filter(CarrierProfile.user_id == user.id).one_or_none()
    if prof is None:
        raise HTTPException(status_code=403, detail="Carrier not found")
    loc = db.query(CarrierLocation).filter(CarrierLocation.carrier_id == prof.id).one_or_none()
    if loc is None:
        loc = CarrierLocation(carrier_id=prof.id, lat=payload.lat, lon=payload.lon)
        db.add(loc)
    else:
        from datetime import datetime
        loc.lat = payload.lat
        loc.lon = payload.lon
        loc.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "ok"}
