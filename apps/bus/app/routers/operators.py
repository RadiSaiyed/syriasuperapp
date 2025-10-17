from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import (
    User,
    Operator,
    OperatorMember,
    Trip,
    Booking,
    TripSeat,
)
from ..schemas import (
    OperatorOut,
    OperatorMemberOut,
    TripCreateIn,
    TripUpdateIn,
    TripsListOut,
    TripOut,
    TripSeatsOut,
    BookingsAdminListOut,
    BookingOut,
    ReportSummaryOut,
    TicketValidationOut,
)
from superapp_shared.internal_hmac import sign_internal_request_headers
from sqlalchemy import select


router = APIRouter(prefix="/operators", tags=["operators"])


def _ensure_member(db: Session, user_id, operator_id, min_role: str = "agent") -> OperatorMember:
    mem = (
        db.query(OperatorMember)
        .filter(OperatorMember.operator_id == operator_id, OperatorMember.user_id == user_id)
        .one_or_none()
    )
    if mem is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of operator")
    if min_role == "admin" and mem.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return mem


@router.post("/register", response_model=OperatorOut)
def register_operator(
    name: str,
    merchant_phone: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # DEV only helper
    if settings.ENV != "dev":
        raise HTTPException(status_code=403, detail="Disabled outside dev")
    if not name or len(name) < 3:
        raise HTTPException(status_code=400, detail="Name too short")
    existing = db.query(Operator).filter(Operator.name.ilike(name)).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Operator already exists")
    op = Operator(name=name, merchant_phone=merchant_phone)
    db.add(op)
    db.flush()
    db.add(OperatorMember(operator_id=op.id, user_id=user.id, role="admin"))
    db.flush()
    return OperatorOut(id=str(op.id), name=op.name, merchant_phone=op.merchant_phone)


@router.get("/me", response_model=list[OperatorMemberOut])
def my_operators(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(OperatorMember, Operator)
        .join(Operator, Operator.id == OperatorMember.operator_id)
        .filter(OperatorMember.user_id == user.id)
        .all()
    )
    return [
        OperatorMemberOut(operator_id=str(op.id), operator_name=op.name, role=mem.role)
        for (mem, op) in rows
    ]


@router.get("/{operator_id}/trips", response_model=TripsListOut)
def list_trips(operator_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    rows = (
        db.query(Trip)
        .filter(Trip.operator_id == operator_id)
        .order_by(Trip.depart_at.asc())
        .limit(500)
        .all()
    )
    # get operator name
    op = db.get(Operator, operator_id)
    trips = [
        TripOut(
            id=str(t.id),
            operator_name=op.name if op else "",
            origin=t.origin,
            destination=t.destination,
            depart_at=t.depart_at,
            arrive_at=t.arrive_at,
            price_cents=t.price_cents,
            seats_available=t.seats_available,
            bus_model=t.bus_model,
            bus_year=t.bus_year,
        )
        for t in rows
    ]
    return TripsListOut(trips=trips)


@router.post("/{operator_id}/trips", response_model=TripOut)
def create_trip(
    operator_id: str,
    payload: TripCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    op = db.get(Operator, operator_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")
    t = Trip(
        operator_id=op.id,
        origin=payload.origin,
        destination=payload.destination,
        depart_at=payload.depart_at,
        arrive_at=payload.arrive_at,
        price_cents=payload.price_cents,
        seats_total=payload.seats_total,
        seats_available=payload.seats_total,
        bus_model=payload.bus_model,
        bus_year=payload.bus_year,
    )
    db.add(t)
    db.flush()
    return TripOut(
        id=str(t.id),
        operator_name=op.name,
        origin=t.origin,
        destination=t.destination,
        depart_at=t.depart_at,
        arrive_at=t.arrive_at,
        price_cents=t.price_cents,
        seats_available=t.seats_available,
        bus_model=t.bus_model,
        bus_year=t.bus_year,
    )


@router.patch("/{operator_id}/trips/{trip_id}", response_model=TripOut)
def update_trip(
    operator_id: str,
    trip_id: str,
    payload: TripUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    t = db.get(Trip, trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    # Update editable fields
    for field in ["origin", "destination", "depart_at", "arrive_at", "price_cents", "bus_model", "bus_year"]:
        v = getattr(payload, field)
        if v is not None:
            setattr(t, field, v)
    if payload.seats_total is not None:
        # Adjust available to not exceed total and not go negative
        delta = payload.seats_total - t.seats_total
        t.seats_total = payload.seats_total
        t.seats_available = max(0, min(t.seats_total, t.seats_available + delta))
    db.flush()
    op = db.get(Operator, operator_id)
    return TripOut(
        id=str(t.id),
        operator_name=op.name if op else "",
        origin=t.origin,
        destination=t.destination,
        depart_at=t.depart_at,
        arrive_at=t.arrive_at,
        price_cents=t.price_cents,
        seats_available=t.seats_available,
        bus_model=t.bus_model,
        bus_year=t.bus_year,
    )


@router.delete("/{operator_id}/trips/{trip_id}")
def delete_trip(operator_id: str, trip_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    t = db.get(Trip, trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    # Ensure no confirmed bookings before deletion
    any_conf = db.query(Booking).filter(Booking.trip_id == t.id, Booking.status == "confirmed").count()
    if any_conf:
        raise HTTPException(status_code=400, detail="Cannot delete trip with confirmed bookings")
    db.delete(t)
    db.flush()
    return {"detail": "deleted"}


@router.get("/{operator_id}/trips/{trip_id}/seats", response_model=TripSeatsOut)
def trip_seats_admin(operator_id: str, trip_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    t = db.get(Trip, trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    rows = db.query(TripSeat).filter(TripSeat.trip_id == t.id).all()
    reserved = sorted([int(r.seat_number) for r in rows if r.booking_id is not None])
    return TripSeatsOut(trip_id=str(t.id), seats_total=t.seats_total, reserved=reserved)


@router.get("/{operator_id}/bookings", response_model=BookingsAdminListOut)
def list_bookings_admin(
    operator_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    q = (
        db.query(Booking)
        .join(Trip, Trip.id == Booking.trip_id)
        .filter(Trip.operator_id == operator_id)
        .order_by(Booking.created_at.desc())
    )
    if status_filter:
        q = q.filter(Booking.status == status_filter)
    rows = q.limit(500).all()
    out: list[BookingOut] = []
    op = db.get(Operator, operator_id)
    for b in rows:
        t = db.get(Trip, b.trip_id)
        u = db.get(User, b.user_id)
        item = BookingOut(
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
            seat_numbers=None,
            merchant_phone=op.merchant_phone if op and op.merchant_phone else settings.FEE_WALLET_PHONE,
            user_phone=u.phone if u else None,
            boarded_at=b.boarded_at,
        )
        out.append(item)
    return BookingsAdminListOut(bookings=out)


def _fetch_payment_request_status(request_id: str) -> str | None:
    try:
        url = f"{settings.PAYMENTS_BASE_URL}/internal/requests/{request_id}"
        headers = sign_internal_request_headers({"id": str(request_id)}, settings.PAYMENTS_INTERNAL_SECRET)
        with httpx.Client(timeout=3.0) as client:
            r = client.get(url, headers=headers)
            if r.status_code == 200:
                js = r.json()
                return js.get("status")
    except Exception:
        return None
    return None


@router.post("/{operator_id}/bookings/{booking_id}/confirm")
def confirm_booking_admin(operator_id: str, booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    b = db.execute(select(Booking).where(Booking.id == booking_id).with_for_update()).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    t = db.get(Trip, b.trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found for operator")
    if b.status == "confirmed":
        return {"detail": "confirmed"}
    # If payment request exists, require accepted
    if b.payment_request_id:
        status_now = _fetch_payment_request_status(b.payment_request_id)
        if status_now != "accepted":
            raise HTTPException(status_code=400, detail=f"Payment not accepted (status={status_now})")
    b.status = "confirmed"
    db.flush()
    return {"detail": "confirmed"}


@router.post("/{operator_id}/bookings/{booking_id}/cancel")
def cancel_booking_admin(operator_id: str, booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    b = db.execute(select(Booking).where(Booking.id == booking_id).with_for_update()).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    t = db.get(Trip, b.trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found for operator")
    if b.status == "canceled":
        return {"detail": "canceled"}
    # restore seats
    t.seats_available += b.seats_count
    # free seat rows
    db.query(TripSeat).filter(TripSeat.booking_id == b.id).update({TripSeat.booking_id: None})
    b.status = "canceled"
    db.flush()
    return {"detail": "canceled"}


@router.get("/{operator_id}/reports/summary", response_model=ReportSummaryOut)
def report_summary(operator_id: str, since_days: int = 7, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    to = datetime.utcnow()
    fr = to - timedelta(days=max(1, min(since_days, 90)))
    rows = (
        db.query(Booking)
        .join(Trip, Trip.id == Booking.trip_id)
        .filter(Trip.operator_id == operator_id, Booking.created_at >= fr, Booking.created_at <= to)
        .all()
    )
    total = len(rows)
    confirmed = len([b for b in rows if b.status == "confirmed"])
    canceled = len([b for b in rows if b.status == "canceled"])
    revenue = sum(int(b.total_price_cents) for b in rows if b.status == "confirmed")
    # crude occupancy: average of (seats_count / seats_total) over confirmed bookings
    occ_vals = []
    for b in rows:
        if b.status == "confirmed":
            t = db.get(Trip, b.trip_id)
            if t and t.seats_total > 0:
                occ_vals.append(100.0 * float(b.seats_count) / float(t.seats_total))
    avg_occ = round(sum(occ_vals) / len(occ_vals), 2) if occ_vals else 0.0
    return ReportSummaryOut(
        from_utc=fr,
        to_utc=to,
        total_bookings=total,
        confirmed_bookings=confirmed,
        canceled_bookings=canceled,
        gross_revenue_cents=revenue,
        avg_occupancy_percent=avg_occ,
    )


@router.get("/{operator_id}/tickets/validate", response_model=TicketValidationOut)
def validate_ticket(operator_id: str, qr: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    if not qr or not qr.startswith("BUS|"):
        return TicketValidationOut(valid=False, reason="Invalid QR format")
    booking_id = qr.split("|", 1)[1]
    b = db.get(Booking, booking_id)
    if not b:
        return TicketValidationOut(valid=False, reason="Booking not found")
    t = db.get(Trip, b.trip_id)
    if not t or str(t.operator_id) != operator_id:
        return TicketValidationOut(valid=False, reason="Wrong operator")
    op = db.get(Operator, operator_id)
    u = db.get(User, b.user_id)
    out = BookingOut(
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
        merchant_phone=op.merchant_phone if op and op.merchant_phone else settings.FEE_WALLET_PHONE,
        user_phone=u.phone if u else None,
        boarded_at=b.boarded_at,
    )
    if b.status != "confirmed":
        return TicketValidationOut(valid=False, reason=f"Status: {b.status}", booking=out)
    return TicketValidationOut(valid=True, booking=out)


@router.post("/{operator_id}/tickets/board")
def mark_boarded(operator_id: str, booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    b = db.execute(select(Booking).where(Booking.id == booking_id).with_for_update()).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    t = db.get(Trip, b.trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found for operator")
    if b.status != "confirmed":
        raise HTTPException(status_code=400, detail=f"Not confirmed (status={b.status})")
    b.boarded_at = datetime.utcnow()
    db.flush()
    return {"detail": "boarded", "boarded_at": b.boarded_at.isoformat() + "Z"}
