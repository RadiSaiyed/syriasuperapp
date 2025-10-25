from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, Load
from ..schemas import LoadCreateIn, LoadOut, LoadsListOut


router = APIRouter(prefix="/shipper", tags=["shipper"])


@router.post("/loads", response_model=LoadOut)
def post_load(payload: LoadCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("shipper", "carrier"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    load = Load(shipper_user_id=user.id, origin=payload.origin, destination=payload.destination, weight_kg=payload.weight_kg, price_cents=payload.price_cents)
    db.add(load)
    db.flush()
    return LoadOut(id=str(load.id), status=load.status, shipper_user_id=str(load.shipper_user_id), carrier_id=None, origin=load.origin, destination=load.destination, weight_kg=load.weight_kg, price_cents=load.price_cents)


@router.get("/loads", response_model=LoadsListOut)
def my_loads(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Load).filter(Load.shipper_user_id == user.id).order_by(Load.created_at.desc()).limit(100).all()
    return LoadsListOut(loads=[LoadOut(id=str(l.id), status=l.status, shipper_user_id=str(l.shipper_user_id), carrier_id=str(l.carrier_id) if l.carrier_id else None, origin=l.origin, destination=l.destination, weight_kg=l.weight_kg, price_cents=l.price_cents, payment_request_id=l.payment_request_id) for l in rows])

