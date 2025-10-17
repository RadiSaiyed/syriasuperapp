from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, CarrierProfile, Load, Bid
from sqlalchemy import select
from ..schemas import BidCreateIn, BidOut, BidsListOut


router = APIRouter(prefix="/bids", tags=["bids"]) 


def _get_carrier(db: Session, user: User) -> CarrierProfile:
    prof = db.query(CarrierProfile).filter(CarrierProfile.user_id == user.id).one_or_none()
    if prof is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Carrier not found")
    return prof


def _to_out(b: Bid) -> BidOut:
    return BidOut(id=str(b.id), load_id=str(b.load_id), carrier_id=str(b.carrier_id), amount_cents=b.amount_cents, status=b.status, created_at=b.created_at)


@router.post("/load/{load_id}", response_model=BidOut)
def create_bid(load_id: str, payload: BidCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    carrier = _get_carrier(db, user)
    l = db.get(Load, load_id)
    if l is None or l.status != "posted":
        raise HTTPException(status_code=404, detail="Load not available")
    b = Bid(load_id=l.id, carrier_id=carrier.id, amount_cents=payload.amount_cents, status="pending")
    db.add(b)
    db.flush()
    return _to_out(b)


@router.get("", response_model=BidsListOut)
def my_bids(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    carrier = _get_carrier(db, user)
    rows = db.query(Bid).filter(Bid.carrier_id == carrier.id).order_by(Bid.created_at.desc()).limit(100).all()
    return BidsListOut(bids=[_to_out(b) for b in rows])


@router.get("/load/{load_id}", response_model=BidsListOut)
def bids_for_load(load_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Load, load_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Load not found")
    if l.shipper_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your load")
    rows = db.query(Bid).filter(Bid.load_id == l.id).order_by(Bid.created_at.desc()).limit(100).all()
    return BidsListOut(bids=[_to_out(b) for b in rows])


@router.post("/{bid_id}/accept", response_model=BidOut)
def accept_bid(bid_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.execute(select(Bid).where(Bid.id == bid_id).with_for_update()).scalars().first()
    if b is None:
        raise HTTPException(status_code=404, detail="Bid not found")
    l = db.get(Load, b.load_id)
    if l is None or l.shipper_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if l.status != "posted":
        raise HTTPException(status_code=400, detail="Load not available")
    b.status = "accepted"
    # assign
    l.carrier_id = b.carrier_id
    l.price_cents = b.amount_cents
    l.status = "assigned"
    # reject other bids
    others = db.query(Bid).filter(Bid.load_id == l.id, Bid.id != b.id, Bid.status == "pending").all()
    for ob in others:
        ob.status = "rejected"
    db.flush()
    return _to_out(b)


@router.post("/{bid_id}/reject", response_model=BidOut)
def reject_bid(bid_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.execute(select(Bid).where(Bid.id == bid_id).with_for_update()).scalars().first()
    if b is None:
        raise HTTPException(status_code=404, detail="Bid not found")
    l = db.get(Load, b.load_id)
    if l is None or l.shipper_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    b.status = "rejected"
    db.flush()
    return _to_out(b)
