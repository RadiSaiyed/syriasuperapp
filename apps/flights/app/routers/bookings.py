from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from sqlalchemy import func, select
from ..models import User, Flight, Booking, Airline, FlightSeat, PromoCode, PromoRedemption
from ..schemas import CreateBookingIn, BookingOut, BookingsListOut, CancelIn, TicketOut


router = APIRouter(prefix="/bookings", tags=["bookings"])


def _to_booking_out(db: Session, b: Booking) -> BookingOut:
    f = db.get(Flight, b.flight_id)
    al = db.get(Airline, f.airline_id) if f else None
    return BookingOut(
        id=str(b.id),
        status=b.status,
        flight_id=str(b.flight_id),
        airline_name=al.name if al else "",
        origin=f.origin if f else "",
        destination=f.destination if f else "",
        depart_at=f.depart_at if f else datetime.utcnow(),
        seats_count=b.seats_count,
        total_price_cents=b.total_price_cents,
        payment_request_id=b.payment_request_id,
    )


@router.post("", response_model=BookingOut)
def create_booking(payload: CreateBookingIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    flight = db.get(Flight, payload.flight_id)
    if flight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")
    if flight.seats_available < payload.seats_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough seats")

    # Seat selection/assignment
    seats_req = payload.seat_numbers or []
    if seats_req:
        if len(seats_req) != payload.seats_count:
            raise HTTPException(status_code=400, detail="seat_numbers count must equal seats_count")
        if any(s <= 0 or s > flight.seats_total for s in seats_req):
            raise HTTPException(status_code=400, detail="Invalid seat numbers")
        taken = set(
            s.seat_number for s in db.query(FlightSeat).filter(FlightSeat.flight_id == flight.id, FlightSeat.seat_number.in_(seats_req), FlightSeat.booking_id != None).all()  # noqa: E711
        )
        if taken:
            raise HTTPException(status_code=400, detail=f"Seats taken: {sorted(list(taken))}")
    else:
        existing = set(r.seat_number for r in db.query(FlightSeat).filter(FlightSeat.flight_id == flight.id, FlightSeat.booking_id != None).all())  # noqa: E711
        auto = []
        for n in range(1, flight.seats_total + 1):
            if n not in existing:
                auto.append(n)
                if len(auto) == payload.seats_count:
                    break
        seats_req = auto
        if len(seats_req) != payload.seats_count:
            raise HTTPException(status_code=400, detail="Not enough free seats to auto-assign")

    total = flight.price_cents * payload.seats_count
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

    booking = Booking(user_id=user.id, flight_id=flight.id, status="reserved", seats_count=payload.seats_count, total_price_cents=total)
    flight.seats_available -= payload.seats_count
    db.add(booking)
    db.flush()
    for n in seats_req:
        row = db.query(FlightSeat).filter(FlightSeat.flight_id == flight.id, FlightSeat.seat_number == n).one_or_none()
        if row is None:
            row = FlightSeat(flight_id=flight.id, seat_number=n, booking_id=booking.id)
            db.add(row)
        else:
            row.booking_id = booking.id
    if payload.promo_code:
        pc = db.query(PromoCode).filter(PromoCode.code == payload.promo_code).one_or_none()
        if pc and pc.active:
            pc.uses_count = (pc.uses_count or 0) + 1
            db.add(PromoRedemption(promo_code_id=pc.id, booking_id=booking.id, user_id=user.id))

    payment_request_id = None
    # Optional: create a payment request in Payments service
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and total > 0:
            to_phone = settings.FEE_WALLET_PHONE
            payload_json = {"from_phone": user.phone, "to_phone": to_phone, "amount_cents": total}
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.PAYMENTS_BASE_URL}/internal/requests",
                    headers=headers,
                    json=payload_json,
                )
                if r.status_code < 400:
                    payment_request_id = r.json().get("id")
    except Exception:
        pass

    if payment_request_id:
        booking.payment_request_id = payment_request_id
        booking.status = "confirmed"
    db.flush()

    out = _to_booking_out(db, booking)
    seats = db.query(FlightSeat).filter(FlightSeat.booking_id == booking.id).order_by(FlightSeat.seat_number.asc()).all()
    out.seat_numbers = [int(r.seat_number) for r in seats]
    return out


@router.get("", response_model=BookingsListOut)
def list_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Booking)
        .filter(Booking.user_id == user.id)
        .order_by(Booking.created_at.desc())
        .limit(100)
        .all()
    )
    if not rows:
        return BookingsListOut(bookings=[])
    # Avoid N+1: prefetch flights and airlines
    flight_ids = {b.flight_id for b in rows}
    flights = {f.id: f for f in db.query(Flight).filter(Flight.id.in_(flight_ids)).all()}
    airline_ids = {f.airline_id for f in flights.values() if f}
    airlines = {a.id: a for a in db.query(Airline).filter(Airline.id.in_(airline_ids)).all()} if airline_ids else {}
    out = []
    for b in rows:
        f = flights.get(b.flight_id)
        al = airlines.get(f.airline_id) if f else None
        out.append(
            BookingOut(
                id=str(b.id),
                status=b.status,
                flight_id=str(b.flight_id),
                airline_name=al.name if al else "",
                origin=f.origin if f else "",
                destination=f.destination if f else "",
                depart_at=f.depart_at if f else datetime.utcnow(),
                seats_count=b.seats_count,
                total_price_cents=b.total_price_cents,
                payment_request_id=b.payment_request_id,
            )
        )
    return BookingsListOut(bookings=out)


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
    f = db.get(Flight, b.flight_id)
    if f:
        f.seats_available += b.seats_count
    # free seats
    rows = db.query(FlightSeat).filter(FlightSeat.booking_id == b.id).all()
    for r in rows:
        r.booking_id = None
    b.status = "canceled"
    db.flush()
    return {"detail": "canceled"}


@router.get("/{booking_id}/ticket", response_model=TicketOut)
def booking_ticket(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    qr = f"FLIGHT|{b.id}"
    return TicketOut(booking_id=str(b.id), qr_text=qr)


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return _to_booking_out(db, b)
