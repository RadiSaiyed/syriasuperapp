from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth import get_current_user
from ..models import Listing, Reservation, User


router = APIRouter(prefix="/owner", tags=["owner"])


@router.get("/listings")
def my_listings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Listing).filter(Listing.owner_phone == user.phone).order_by(Listing.created_at.desc()).limit(100).all()
    return {"items": [{
        "id": str(l.id),
        "title": l.title,
        "city": l.city,
        "type": l.type,
        "price_cents": l.price_cents,
    } for l in rows]}


@router.post("/listings")
def create_my_listing(title: str, city: str, type: str = "rent", property_type: str = "apartment", price_cents: int = 0, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = Listing(title=title, city=city, type=type, property_type=property_type, price_cents=price_cents, owner_phone=user.phone)
    db.add(l)
    db.flush()
    return {"id": str(l.id)}


@router.patch("/listings/{listing_id}")
def update_my_listing(listing_id: str, title: str | None = None, city: str | None = None, price_cents: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="not_found")
    if l.owner_phone != user.phone:
        raise HTTPException(status_code=403, detail="forbidden")
    if title is not None:
        l.title = title
    if city is not None:
        l.city = city
    if price_cents is not None:
        l.price_cents = int(price_cents)
    db.flush()
    return {"detail": "updated"}


@router.get("/reservations")
def owner_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Reservation).filter(Reservation.owner_phone == user.phone).order_by(Reservation.created_at.desc()).limit(100).all()
    out = []
    for r in rows:
        l = db.get(Listing, r.listing_id)
        out.append({
            "id": str(r.id),
            "listing_id": str(r.listing_id),
            "title": l.title if l else None,
            "amount_cents": r.amount_cents,
            "status": r.status,
            "owner_decision": r.owner_decision,
            "payment_request_id": r.payment_request_id,
        })
    return {"items": out}


@router.post("/reservations/{reservation_id}/decision")
def decide_reservation(reservation_id: str, decision: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if decision not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="invalid_decision")
    r = db.get(Reservation, reservation_id)
    if r is None:
        raise HTTPException(status_code=404, detail="not_found")
    if r.owner_phone != user.phone:
        raise HTTPException(status_code=403, detail="forbidden")
    r.owner_decision = decision
    db.flush()
    return {"detail": decision}
