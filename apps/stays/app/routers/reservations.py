from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Unit, Reservation, Property, UnitBlock, UnitPrice
from ..schemas import ReservationCreateIn, ReservationOut, ReservationsListOut
from ..utils.notify import notify
from ..config import settings
import httpx
from superapp_shared.internal_hmac import sign_internal_request_headers
from ..utils.webhooks import send_webhooks
from ..utils.ids import as_uuid


router = APIRouter(prefix="/reservations", tags=["reservations"])


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


@router.post("", response_model=ReservationOut)
def create_reservation(payload: ReservationCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    unit = db.get(Unit, as_uuid(payload.unit_id))
    if not unit or not unit.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not available")
    if payload.check_in >= payload.check_out:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date range")
    if payload.guests > unit.capacity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many guests for unit")

    # Day-by-day availability with blocks and dynamic prices
    nights = int((payload.check_out - payload.check_in) // timedelta(days=1))
    if nights <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Zero nights")
    if nights < unit.min_nights:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Below minimum nights")
    rs = db.query(Reservation).filter(Reservation.unit_id == unit.id, Reservation.status.in_(["created", "confirmed"]))
    res_days = [(r.check_in, r.check_out) for r in rs]
    blocks = db.query(UnitBlock).filter(UnitBlock.unit_id == unit.id).all()
    prices = db.query(UnitPrice).filter(UnitPrice.unit_id == unit.id, UnitPrice.date >= payload.check_in, UnitPrice.date < payload.check_out).all()
    price_map = {p.date: p.price_cents for p in prices}
    min_avail = unit.total_units
    total = int(unit.cleaning_fee_cents)
    d = payload.check_in
    while d < payload.check_out:
        occ = sum(1 for (ci, co) in res_days if ci <= d and d < co)
        blk = sum(b.blocked_units for b in blocks if b.start_date <= d and d < b.end_date)
        avail_today = max(0, unit.total_units - occ - blk)
        if avail_today < min_avail:
            min_avail = avail_today
        total += int(price_map.get(d, unit.price_cents_per_night))
        d = d + timedelta(days=1)
    if min_avail <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No availability")
    prop = db.get(Property, unit.property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Property missing")

    r = Reservation(user_id=user.id, property_id=prop.id, unit_id=unit.id, check_in=payload.check_in, check_out=payload.check_out, guests=payload.guests, total_cents=total, status="created")
    db.add(r)
    db.flush()
    # Create payment request via Payments internal API (host -> guest)
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET:
            host_user = db.get(User, prop.owner_user_id)
            payload_body = {
                "from_phone": host_user.phone if host_user else "",
                "to_phone": user.phone,
                "amount_cents": int(total),
                "metadata": {"reservation_id": str(r.id), "service": "stays"},
            }
            headers = sign_internal_request_headers(payload_body, settings.PAYMENTS_INTERNAL_SECRET)
            headers["X-Idempotency-Key"] = f"stays:{r.id}"
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", json=payload_body, headers=headers)
                if resp.status_code == 200:
                    pr_id = resp.json().get("id")
                    if pr_id:
                        r.payment_request_id = pr_id
                        db.flush()
    except Exception:
        pass
    try:
        send_webhooks(db, "reservation.created", {"reservation_id": str(r.id), "user_id": str(user.id), "property_id": str(prop.id), "unit_id": str(unit.id)})
    except Exception:
        pass
    try:
        notify("reservation.created", {"reservation_id": str(r.id), "user_id": str(user.id), "property_id": str(prop.id), "unit_id": str(unit.id)})
    except Exception:
        pass
    return ReservationOut(id=str(r.id), property_id=str(r.property_id), unit_id=str(r.unit_id), status=r.status, check_in=r.check_in, check_out=r.check_out, guests=r.guests, total_cents=r.total_cents, created_at=r.created_at, payment_request_id=r.payment_request_id)


@router.get("", response_model=ReservationsListOut)
def my_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rs = db.query(Reservation).filter(Reservation.user_id == user.id).order_by(Reservation.created_at.desc()).all()
    return ReservationsListOut(reservations=[
        ReservationOut(id=str(r.id), property_id=str(r.property_id), unit_id=str(r.unit_id), status=r.status, check_in=r.check_in, check_out=r.check_out, guests=r.guests, total_cents=r.total_cents, created_at=r.created_at, payment_request_id=r.payment_request_id) for r in rs
    ])


@router.post("/{reservation_id}/cancel", response_model=ReservationOut)
def cancel_my_reservation(reservation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Reservation, as_uuid(reservation_id))
    if not r or r.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    if r.status == "canceled":
        return ReservationOut(id=str(r.id), property_id=str(r.property_id), unit_id=str(r.unit_id), status=r.status, check_in=r.check_in, check_out=r.check_out, guests=r.guests, total_cents=r.total_cents, created_at=r.created_at, payment_request_id=r.payment_request_id)
    # Optional: prevent cancel on/after check-in date
    if r.check_in <= __import__("datetime").date.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot cancel on/after check-in")
    r.status = "canceled"
    db.flush()
    try:
        notify("reservation.canceled", {"reservation_id": str(r.id), "by": "guest"})
    except Exception:
        pass
    try:
        if r.payment_transfer_id:
            send_webhooks(db, "refund.requested", {"reservation_id": str(r.id), "transfer_id": r.payment_transfer_id, "amount_cents": int(r.total_cents)})
            r.refund_status = "requested"
            db.flush()
    except Exception:
        pass
    try:
        send_webhooks(db, "reservation.canceled", {"reservation_id": str(r.id), "by": "guest"})
    except Exception:
        pass
    return ReservationOut(id=str(r.id), property_id=str(r.property_id), unit_id=str(r.unit_id), status=r.status, check_in=r.check_in, check_out=r.check_out, guests=r.guests, total_cents=r.total_cents, created_at=r.created_at, payment_request_id=r.payment_request_id)
