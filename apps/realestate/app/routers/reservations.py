from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Listing, User, Reservation
from ..auth import get_current_user
from ..config import settings
import httpx


router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("")
def create_reservation(listing_id: str, amount_cents: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.PAYMENTS_BASE_URL or not settings.PAYMENTS_INTERNAL_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="payments_not_configured")
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing_not_found")
    # Target: owner phone, otherwise fee wallet
    to_phone = l.owner_phone or settings.FEE_WALLET_PHONE
    amt = int(amount_cents) if amount_cents and amount_cents > 0 else settings.RESERVATION_FEE_CENTS
    payload = {
        "from_phone": user.phone,
        "to_phone": to_phone,
        "amount_cents": amt,
        "metadata": {"listing_id": str(l.id), "title": l.title},
    }
    headers = {"X-Internal-Secret": settings.PAYMENTS_INTERNAL_SECRET}
    idem = {"X-Idempotency-Key": f"re:{user.id}:{l.id}:reserve"}
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", headers={**headers, **idem}, json=payload)
            if r.status_code >= 400:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="payments_request_failed")
            req_id = (r.json() or {}).get("id")
            resv = Reservation(listing_id=l.id, renter_user_id=user.id, owner_phone=to_phone, payment_request_id=req_id, amount_cents=amt, status="pending", owner_decision="pending")
            db.add(resv)
            db.flush()
            return {"id": str(resv.id), "payment_request_id": req_id, "amount_cents": amt}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="payments_unreachable")


@router.post("/{reservation_id}/sync")
def sync_reservation(reservation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Reservation, reservation_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    # Visibility: renter or owner can sync
    if r.renter_user_id != user.id and r.owner_phone != user.phone:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    req_id = r.payment_request_id
    if not req_id:
        return {"detail": "no_request", "status": r.status}
    headers = {"X-Internal-Secret": settings.PAYMENTS_INTERNAL_SECRET}
    try:
        with httpx.Client(timeout=5.0) as client:
            res = client.get(f"{settings.PAYMENTS_BASE_URL}/internal/requests/{req_id}", headers=headers)
            if res.status_code >= 400:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="payments_failed")
            js = res.json() or {}
            st = js.get("status")
            if st == "accepted":
                r.status = "completed"
            elif st in ("rejected", "canceled", "expired"):
                r.status = "canceled"
            db.flush()
            return {"detail": "synced", "status": r.status}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="payments_unreachable")


@router.get("")
def my_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Reservation)
        .filter(Reservation.renter_user_id == user.id)
        .order_by(Reservation.created_at.desc())
        .limit(100)
        .all()
    )
    if not rows:
        return {"items": []}
    ids = {r.listing_id for r in rows}
    from sqlalchemy import select
    lst = db.execute(select(Listing).where(Listing.id.in_(ids))).scalars().all()
    lmap = {l.id: l for l in lst}
    out = []
    for r in rows:
        l = lmap.get(r.listing_id)
        out.append({
            "id": str(r.id),
            "listing_id": str(r.listing_id),
            "payment_request_id": r.payment_request_id,
            "amount_cents": r.amount_cents,
            "status": r.status,
            "owner_decision": r.owner_decision,
            "title": l.title if l else None,
            "city": l.city if l else None,
        })
    return {"items": out}
