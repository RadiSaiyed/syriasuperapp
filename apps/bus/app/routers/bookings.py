from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from sqlalchemy import func, select
from ..models import User, Trip, Booking, Operator, TripSeat, PromoCode, PromoRedemption, TripRating
from ..schemas import CreateBookingIn, BookingOut, BookingsListOut, CancelIn, TicketOut, RateBookingIn
from superapp_shared.internal_hmac import sign_internal_request_headers


router = APIRouter(prefix="/bookings", tags=["bookings"])


def _to_booking_out(db: Session, b: Booking) -> BookingOut:
    t = db.get(Trip, b.trip_id)
    op = db.get(Operator, t.operator_id) if t else None
    rating = db.query(TripRating).filter(TripRating.booking_id == b.id).one_or_none()
    return BookingOut(
        id=str(b.id),
        status=b.status,
        trip_id=str(b.trip_id),
        operator_name=op.name if op else "",
        origin=t.origin if t else "",
        destination=t.destination if t else "",
        depart_at=t.depart_at if t else datetime.utcnow(),
        seats_count=b.seats_count,
        total_price_cents=b.total_price_cents,
        payment_request_id=b.payment_request_id,
        my_rating=rating.rating if rating else None,
        my_rating_comment=rating.comment if rating else None,
        my_rating_created_at=rating.created_at if rating else None,
    )


@router.post("", response_model=BookingOut)
def create_booking(payload: CreateBookingIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = db.get(Trip, payload.trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    if trip.seats_available < payload.seats_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough seats")

    # Seat selection/assignment
    seats_req = payload.seat_numbers or []
    if seats_req:
        if len(seats_req) != payload.seats_count:
            raise HTTPException(status_code=400, detail="seat_numbers count must equal seats_count")
        if any(s <= 0 or s > trip.seats_total for s in seats_req):
            raise HTTPException(status_code=400, detail="Invalid seat numbers")
        taken = set(
            s.seat_number for s in db.query(TripSeat).filter(TripSeat.trip_id == trip.id, TripSeat.seat_number.in_(seats_req), TripSeat.booking_id != None).all()  # noqa: E711
        )
        if taken:
            raise HTTPException(status_code=400, detail=f"Seats taken: {sorted(list(taken))}")
    else:
        existing = set(r.seat_number for r in db.query(TripSeat).filter(TripSeat.trip_id == trip.id, TripSeat.booking_id != None).all())  # noqa: E711
        auto = []
        for n in range(1, trip.seats_total + 1):
            if n not in existing:
                auto.append(n)
                if len(auto) == payload.seats_count:
                    break
        seats_req = auto
        if len(seats_req) != payload.seats_count:
            raise HTTPException(status_code=400, detail="Not enough free seats to auto-assign")

    total = trip.price_cents * payload.seats_count
    # Promo application
    if payload.promo_code:
        pc = db.query(PromoCode).filter(PromoCode.code == payload.promo_code).one_or_none()
        if pc and pc.active:
            now = datetime.utcnow()
            if not ((pc.valid_from and now < pc.valid_from) or (pc.valid_until and now > pc.valid_until)):
                if pc.max_uses is None or pc.uses_count < pc.max_uses:
                    per_user_ok = True
                    if pc.per_user_max_uses:
                        cnt = db.query(func.count(PromoRedemption.id)).filter(PromoRedemption.promo_code_id == pc.id, PromoRedemption.user_id == user.id).scalar() or 0
                        per_user_ok = cnt < pc.per_user_max_uses
                    if per_user_ok and (pc.min_total_cents is None or total >= pc.min_total_cents):
                        disc = 0
                        if pc.percent_off_bps:
                            disc = max(disc, int((total * pc.percent_off_bps + 5000) // 10000))
                        if pc.amount_off_cents:
                            disc = max(disc, int(pc.amount_off_cents))
                        disc = min(disc, total)
                        total -= disc

    booking = Booking(user_id=user.id, trip_id=trip.id, status="reserved", seats_count=payload.seats_count, total_price_cents=total)
    trip.seats_available -= payload.seats_count
    db.add(booking)
    db.flush()
    for n in seats_req:
        row = db.query(TripSeat).filter(TripSeat.trip_id == trip.id, TripSeat.seat_number == n).one_or_none()
        if row is None:
            row = TripSeat(trip_id=trip.id, seat_number=n, booking_id=booking.id)
            db.add(row)
        else:
            row.booking_id = booking.id
    if payload.promo_code:
        pc = db.query(PromoCode).filter(PromoCode.code == payload.promo_code).one_or_none()
        if pc and pc.active:
            pc.uses_count = (pc.uses_count or 0) + 1
            db.add(PromoRedemption(promo_code_id=pc.id, booking_id=booking.id, user_id=user.id))

    # Frontend pays directly via Payments /wallet/transfer using merchant phone; we expose it below.
    db.flush()

    out = _to_booking_out(db, booking)
    seats = db.query(TripSeat).filter(TripSeat.booking_id == booking.id).order_by(TripSeat.seat_number.asc()).all()
    out.seat_numbers = [int(r.seat_number) for r in seats]
    # Determine merchant wallet phone: operator override or platform default
    op = db.get(Operator, trip.operator_id) if trip else None
    merchant_phone = op.merchant_phone if op and op.merchant_phone else settings.FEE_WALLET_PHONE
    out.merchant_phone = merchant_phone

    # Create Payments internal request for this booking (best-effort)
    try:
        payload_req = {
            "from_phone": merchant_phone,
            "to_phone": user.phone,
            "amount_cents": int(total),
            "metadata": {"booking_id": str(booking.id), "service": "bus"},
        }
        url = f"{settings.PAYMENTS_BASE_URL}/internal/requests"
        # Sign HMAC headers, include idempotency key
        headers = sign_internal_request_headers(payload_req, settings.PAYMENTS_INTERNAL_SECRET, None, request.headers.get("X-Request-ID", None))
        headers["X-Idempotency-Key"] = f"bus-booking-{booking.id}"
        with httpx.Client(timeout=3.0) as client:
            r = client.post(url, json=payload_req, headers=headers)
            if r.status_code == 200 and (r.json() or {}).get("id"):
                booking.payment_request_id = r.json()["id"]
                db.flush()
                out.payment_request_id = booking.payment_request_id
    except Exception:
        # Ignore failures; client can still pay via merchant phone directly
        pass
    return out


@router.get("", response_model=BookingsListOut)
def list_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).limit(100).all()
    return BookingsListOut(bookings=[_to_booking_out(db, b) for b in rows])


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, payload: CancelIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.execute(select(Booking).where(Booking.id == booking_id).with_for_update()).scalars().first()
    if b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if b.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")
    if b.status == "canceled":
        return {"detail": "canceled"}
    # restore seats
    t = db.get(Trip, b.trip_id)
    if t:
        t.seats_available += b.seats_count
    # free seats
    rows = db.query(TripSeat).filter(TripSeat.booking_id == b.id).all()
    for r in rows:
        r.booking_id = None
    b.status = "canceled"
    db.flush()
    return {"detail": "canceled"}


@router.post("/{booking_id}/rate")
def rate_booking(booking_id: str, payload: RateBookingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.execute(select(Booking).where(Booking.id == booking_id).with_for_update()).scalars().first()
    if b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if b.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")
    t = db.get(Trip, b.trip_id)
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    if t.depart_at and t.depart_at > datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trip has not departed yet")
    if b.status not in ("reserved", "confirmed", "canceled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking not eligible for rating")

    row = db.query(TripRating).filter(TripRating.booking_id == b.id).one_or_none()
    now = datetime.utcnow()
    if row:
        row.rating = payload.rating
        row.comment = payload.comment
        row.created_at = now
    else:
        row = TripRating(
            booking_id=b.id,
            trip_id=b.trip_id,
            user_id=user.id,
            rating=payload.rating,
            comment=payload.comment,
            created_at=now,
        )
        db.add(row)
    db.flush()

    avg, count = db.query(func.avg(TripRating.rating), func.count(TripRating.id)).filter(TripRating.trip_id == b.trip_id).one()
    avg_rating = float(avg) if avg is not None else None
    ratings_count = int(count or 0)
    return {
        "detail": "ok",
        "rating": row.rating,
        "comment": row.comment,
        "avg_rating": avg_rating,
        "ratings_count": ratings_count,
    }


@router.get("/{booking_id}/ticket", response_model=TicketOut)
def booking_ticket(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    qr = f"BUS|{b.id}"
    return TicketOut(booking_id=str(b.id), qr_text=qr)


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    out = _to_booking_out(db, b)
    # Determine merchant wallet phone
    t = db.get(Trip, b.trip_id)
    op = db.get(Operator, t.operator_id) if t else None
    out.merchant_phone = op.merchant_phone if op and op.merchant_phone else settings.FEE_WALLET_PHONE
    return out


@router.post("/{booking_id}/confirm")
def confirm_booking(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.execute(select(Booking).where(Booking.id == booking_id).with_for_update()).scalars().first()
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if b.status == "confirmed":
        return {"detail": "confirmed"}
    # If a payment_request_id exists, verify status with Payments internal API
    if b.payment_request_id:
        try:
            url = f"{settings.PAYMENTS_BASE_URL}/internal/requests/{b.payment_request_id}"
            # HMAC for GET expects the payload used by Payments internal: {"id": request_id}
            headers = sign_internal_request_headers({"id": str(b.payment_request_id)}, settings.PAYMENTS_INTERNAL_SECRET)
            with httpx.Client(timeout=3.0) as client:
                r = client.get(url, headers=headers)
                if r.status_code == 200:
                    js = r.json() or {}
                    status_now = js.get("status")
                    if status_now != "accepted":
                        raise HTTPException(status_code=400, detail=f"Payment not accepted (status={status_now})")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=502, detail="Payments verification failed")
    # Confirm
    b.status = "confirmed"
    db.flush()
    return {"detail": "confirmed"}
