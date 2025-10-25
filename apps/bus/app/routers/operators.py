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
    Vehicle,
    PromoCode,
    OperatorBranch,
    OperatorWebhook,
)
from ..schemas import (
    OperatorOut,
    OperatorMemberOut,
    OperatorMemberDetailOut,
    OperatorMembersListOut,
    OperatorMemberAddIn,
    OperatorMemberRoleIn,
    OperatorMemberBranchIn,
    ManifestOut,
    ManifestItemOut,
    CloneTripIn,
    VehicleIn,
    VehicleOut,
    PromoCreateIn,
    PromoUpdateIn,
    PromoOut,
    BranchIn,
    BranchOut,
    TripCreateIn,
    TripUpdateIn,
    TripsListOut,
    TripOut,
    TripSeatsOut,
    BookingsAdminListOut,
    BookingOut,
    ReportSummaryOut,
    TicketValidationOut,
    WebhookIn,
    WebhookOut,
)
from superapp_shared.internal_hmac import sign_internal_request_headers
from sqlalchemy import select
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
import hmac, hashlib, json as jsonlib


router = APIRouter(prefix="/operators", tags=["operators"])


def _ensure_member(db: Session, user_id, operator_id, min_role: str = "agent") -> OperatorMember:
    mem = (
        db.query(OperatorMember)
        .filter(OperatorMember.operator_id == operator_id, OperatorMember.user_id == user_id)
        .one_or_none()
    )
    if mem is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of operator")
    # Role precedence: checker < cashier < agent < admin
    ranks = {"checker": 0, "cashier": 1, "agent": 2, "admin": 3}
    need = ranks.get(min_role, 2)
    have = ranks.get(mem.role, -1)
    if have < need:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{min_role} required")
    return mem


def _ensure_admin_left(db: Session, operator_id: str, excluding_member_id: str | None = None) -> None:
    admins_q = db.query(OperatorMember).filter(OperatorMember.operator_id == operator_id, OperatorMember.role == "admin")
    if excluding_member_id is not None:
        admins_q = admins_q.filter(OperatorMember.id != excluding_member_id)
    count = admins_q.count()
    if count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one admin required")


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


@router.get("/{operator_id}/members", response_model=OperatorMembersListOut)
def list_members(operator_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    rows = (
        db.query(OperatorMember, User, OperatorBranch)
        .join(User, User.id == OperatorMember.user_id)
        .outerjoin(OperatorBranch, OperatorBranch.id == OperatorMember.branch_id)
        .filter(OperatorMember.operator_id == operator_id)
        .order_by(OperatorMember.created_at.asc())
        .all()
    )
    members = [
        OperatorMemberDetailOut(
            id=str(mem.id),
            user_id=str(u.id),
            phone=u.phone,
            name=u.name,
            role=mem.role,
            created_at=mem.created_at,
            branch_id=str(b.id) if b else None,
            branch_name=b.name if b else None,
        )
        for (mem, u, b) in rows
    ]
    return OperatorMembersListOut(members=members)


@router.post("/{operator_id}/members", response_model=OperatorMemberDetailOut)
def add_member(operator_id: str, payload: OperatorMemberAddIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    role = (payload.role or "agent").lower()
    if role not in ("admin", "agent"):
        raise HTTPException(status_code=400, detail="Invalid role")
    phone = (payload.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone required")
    u = db.query(User).filter(User.phone == phone).one_or_none()
    if u is None:
        # Dev convenience: create stub user
        if settings.ENV != "dev":
            raise HTTPException(status_code=400, detail="User not found")
        u = User(phone=phone)
        db.add(u)
        db.flush()
    existing = (
        db.query(OperatorMember)
        .filter(OperatorMember.operator_id == operator_id, OperatorMember.user_id == u.id)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    mem = OperatorMember(operator_id=operator_id, user_id=u.id, role=role)
    if payload.branch_id:
        br = db.get(OperatorBranch, payload.branch_id)
        if not br or str(br.operator_id) != operator_id:
            raise HTTPException(status_code=400, detail="Invalid branch")
        mem.branch_id = br.id
    db.add(mem)
    db.flush()
    br = db.get(OperatorBranch, mem.branch_id) if mem.branch_id else None
    return OperatorMemberDetailOut(id=str(mem.id), user_id=str(u.id), phone=u.phone, name=u.name, role=mem.role, created_at=mem.created_at, branch_id=str(mem.branch_id) if mem.branch_id else None, branch_name=br.name if br else None)


@router.post("/{operator_id}/members/{member_id}/role")
def set_member_role(operator_id: str, member_id: str, payload: OperatorMemberRoleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    role = (payload.role or "").lower()
    if role not in ("admin", "agent"):
        raise HTTPException(status_code=400, detail="Invalid role")
    mem = db.get(OperatorMember, member_id)
    if not mem or str(mem.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if mem.role == role:
        return {"detail": "ok", "role": role}
    # Prevent removing last admin
    if mem.role == "admin" and role != "admin":
        _ensure_admin_left(db, operator_id, excluding_member_id=mem.id)
    mem.role = role
    db.flush()
    return {"detail": "ok", "role": role}


@router.post("/{operator_id}/members/{member_id}/branch")
def set_member_branch(operator_id: str, member_id: str, payload: OperatorMemberBranchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    mem = db.get(OperatorMember, member_id)
    if not mem or str(mem.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if payload.branch_id:
        br = db.get(OperatorBranch, payload.branch_id)
        if not br or str(br.operator_id) != operator_id:
            raise HTTPException(status_code=400, detail="Invalid branch")
        mem.branch_id = br.id
    else:
        mem.branch_id = None
    db.flush()
    return {"detail": "ok", "branch_id": str(mem.branch_id) if mem.branch_id else None}


@router.delete("/{operator_id}/members/{member_id}")
def remove_member(operator_id: str, member_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    mem = db.get(OperatorMember, member_id)
    if not mem or str(mem.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if mem.role == "admin":
        _ensure_admin_left(db, operator_id, excluding_member_id=mem.id)
    db.delete(mem)
    db.flush()
    return {"detail": "deleted"}


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
    if payload.vehicle_id:
        v = db.get(Vehicle, payload.vehicle_id)
        if not v or str(v.operator_id) != operator_id:
            raise HTTPException(status_code=400, detail="Invalid vehicle")
        t.vehicle_id = v.id
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
    if payload.vehicle_id is not None:
        if payload.vehicle_id == "":
            t.vehicle_id = None
        else:
            v = db.get(Vehicle, payload.vehicle_id)
            if not v or str(v.operator_id) != operator_id:
                raise HTTPException(status_code=400, detail="Invalid vehicle")
            t.vehicle_id = v.id
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
    q_phone: str | None = Query(default=None, alias="phone"),
    from_utc: datetime | None = Query(default=None, alias="from"),
    to_utc: datetime | None = Query(default=None, alias="to"),
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
    if from_utc:
        q = q.filter(Booking.created_at >= from_utc)
    if to_utc:
        q = q.filter(Booking.created_at <= to_utc)
    if q_phone:
        q = q.join(User, User.id == Booking.user_id).filter(User.phone.ilike(f"%{q_phone}%"))
    rows = q.limit(500).all()
    out: list[BookingOut] = []
    op = db.get(Operator, operator_id)
    # Prefetch seat numbers for all bookings in one query
    b_ids = [b.id for b in rows]
    seats_by_booking: dict = {}
    if b_ids:
        seat_rows = db.query(TripSeat).filter(TripSeat.booking_id.in_(b_ids)).all()
        for s in seat_rows:
            seats_by_booking.setdefault(s.booking_id, []).append(int(s.seat_number))
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
            seat_numbers=sorted([int(n) for n in seats_by_booking.get(b.id, [])]),
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
    mem = _ensure_member(db, user.id, operator_id, min_role="cashier")
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
    # attach branch if cashier has one and not set yet
    if b.operator_branch_id is None and getattr(mem, 'branch_id', None):
        b.operator_branch_id = mem.branch_id
    db.flush()
    try:
        _emit_webhooks(db, operator_id, "booking.confirmed", {"booking_id": str(b.id), "trip_id": str(b.trip_id), "user_id": str(b.user_id)})
    except Exception:
        pass
    return {"detail": "confirmed"}


@router.post("/{operator_id}/bookings/{booking_id}/cancel")
def cancel_booking_admin(operator_id: str, booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="cashier")
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
    try:
        _emit_webhooks(db, operator_id, "booking.canceled", {"booking_id": str(b.id), "trip_id": str(b.trip_id), "user_id": str(b.user_id)})
    except Exception:
        pass
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
    # Prefetch trips once for occupancy calc
    trip_ids = {b.trip_id for b in rows if b.status == "confirmed"}
    if trip_ids:
        trips = {t.id: t for t in db.query(Trip).filter(Trip.id.in_(trip_ids)).all()}
        for b in rows:
            if b.status == "confirmed":
                t = trips.get(b.trip_id)
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


@router.get("/{operator_id}/trips/{trip_id}/manifest", response_model=ManifestOut)
def trip_manifest(operator_id: str, trip_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    t = db.get(Trip, trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    op = db.get(Operator, operator_id)
    rows = db.query(Booking).filter(Booking.trip_id == t.id).order_by(Booking.created_at.asc()).all()
    # Prefetch seats and users
    b_ids = [r.id for r in rows]
    seat_rows = db.query(TripSeat).filter(TripSeat.booking_id.in_(b_ids)).all() if b_ids else []
    seats_by_booking: dict = {}
    for s in seat_rows:
        seats_by_booking.setdefault(s.booking_id, []).append(int(s.seat_number))
    users = {}
    if rows:
        u_ids = {r.user_id for r in rows}
        for u in db.query(User).filter(User.id.in_(u_ids)).all():
            users[u.id] = u
    items = []
    for b in rows:
        u = users.get(b.user_id)
        items.append(
            ManifestItemOut(
                booking_id=str(b.id),
                status=b.status,
                seats_count=b.seats_count,
                seat_numbers=sorted([int(n) for n in seats_by_booking.get(b.id, [])]) or None,
                user_phone=u.phone if u else None,
                user_name=u.name if u else None,
                created_at=b.created_at,
            )
        )
    return ManifestOut(
        trip_id=str(t.id),
        operator_name=op.name if op else "",
        origin=t.origin,
        destination=t.destination,
        depart_at=t.depart_at,
        items=items,
    )


@router.get("/{operator_id}/bookings.csv")
def export_bookings_csv(operator_id: str, status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    q = (
        db.query(Booking)
        .join(Trip, Trip.id == Booking.trip_id)
        .filter(Trip.operator_id == operator_id)
        .order_by(Booking.created_at.desc())
    )
    if status:
        q = q.filter(Booking.status == status)
    rows = q.all()
    op = db.get(Operator, operator_id)
    # Prefetch seats
    b_ids = [r.id for r in rows]
    seat_rows = db.query(TripSeat).filter(TripSeat.booking_id.in_(b_ids)).all() if b_ids else []
    seats_by_booking: dict = {}
    for s in seat_rows:
        seats_by_booking.setdefault(s.booking_id, []).append(int(s.seat_number))
    # Build CSV
    from io import StringIO
    import csv
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["booking_id", "status", "trip_id", "operator", "origin", "destination", "depart_at", "seats_count", "seat_numbers", "total_price_cents", "user_phone", "boarded_at", "created_at"])
    for b in rows:
        t = db.get(Trip, b.trip_id)
        u = db.get(User, b.user_id)
        seats = seats_by_booking.get(b.id, [])
        w.writerow([
            str(b.id), b.status, str(b.trip_id), op.name if op else "",
            t.origin if t else "", t.destination if t else "", (t.depart_at.isoformat() + "Z") if t else "",
            b.seats_count, ";".join(str(n) for n in sorted(seats)), b.total_price_cents,
            u.phone if u else "",
            (b.boarded_at.isoformat() + "Z") if b.boarded_at else "",
            b.created_at.isoformat() + "Z",
        ])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8")


# Branches management

@router.get("/{operator_id}/branches", response_model=list[BranchOut])
def list_branches(operator_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    rows = db.query(OperatorBranch).filter(OperatorBranch.operator_id == operator_id).order_by(OperatorBranch.created_at.asc()).all()
    return [BranchOut(id=str(b.id), name=b.name, commission_bps=b.commission_bps) for b in rows]


@router.post("/{operator_id}/branches", response_model=BranchOut)
def create_branch(operator_id: str, payload: BranchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    b = OperatorBranch(operator_id=operator_id, name=payload.name, commission_bps=payload.commission_bps)
    db.add(b)
    db.flush()
    return BranchOut(id=str(b.id), name=b.name, commission_bps=b.commission_bps)


@router.patch("/{operator_id}/branches/{branch_id}", response_model=BranchOut)
def update_branch(operator_id: str, branch_id: str, payload: BranchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    b = db.get(OperatorBranch, branch_id)
    if not b or str(b.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    b.name = payload.name
    b.commission_bps = payload.commission_bps
    db.flush()
    return BranchOut(id=str(b.id), name=b.name, commission_bps=b.commission_bps)


@router.delete("/{operator_id}/branches/{branch_id}")
def delete_branch(operator_id: str, branch_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    b = db.get(OperatorBranch, branch_id)
    if not b or str(b.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    any_member = db.query(OperatorMember).filter(OperatorMember.branch_id == b.id).count()
    any_bookings = db.query(Booking).filter(Booking.operator_branch_id == b.id).count()
    if any_member or any_bookings:
        raise HTTPException(status_code=400, detail="Branch in use")
    db.delete(b)
    db.flush()
    return {"detail": "deleted"}


# Webhooks CRUD

@router.get("/{operator_id}/webhooks", response_model=list[WebhookOut])
def list_webhooks(operator_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    rows = db.query(OperatorWebhook).filter(OperatorWebhook.operator_id == operator_id).order_by(OperatorWebhook.created_at.asc()).all()
    return [WebhookOut(id=str(w.id), url=w.url, active=w.active, created_at=w.created_at) for w in rows]


@router.post("/{operator_id}/webhooks", response_model=WebhookOut)
def create_webhook(operator_id: str, payload: WebhookIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    w = OperatorWebhook(operator_id=operator_id, url=payload.url, secret=payload.secret, active=payload.active)
    db.add(w); db.flush()
    return WebhookOut(id=str(w.id), url=w.url, active=w.active, created_at=w.created_at)


@router.patch("/{operator_id}/webhooks/{webhook_id}", response_model=WebhookOut)
def update_webhook(operator_id: str, webhook_id: str, payload: WebhookIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    w = db.get(OperatorWebhook, webhook_id)
    if not w or str(w.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    w.url = payload.url
    w.secret = payload.secret
    w.active = payload.active
    db.flush()
    return WebhookOut(id=str(w.id), url=w.url, active=w.active, created_at=w.created_at)


@router.delete("/{operator_id}/webhooks/{webhook_id}")
def delete_webhook(operator_id: str, webhook_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    w = db.get(OperatorWebhook, webhook_id)
    if not w or str(w.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(w); db.flush()
    return {"detail": "deleted"}


@router.post("/{operator_id}/trips/{trip_id}/clone")
def clone_trip(operator_id: str, trip_id: str, payload: CloneTripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    src = db.get(Trip, trip_id)
    if not src or str(src.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="Invalid date range")
    weekdays = payload.weekdays or [src.depart_at.weekday()]
    from datetime import datetime, time, timedelta
    created = 0
    # Keep same departure time-of-day
    tod = time(src.depart_at.hour, src.depart_at.minute, src.depart_at.second)
    d = payload.start_date
    while d <= payload.end_date:
        if d.weekday() in weekdays:
            depart_at = datetime(d.year, d.month, d.day, tod.hour, tod.minute, tod.second)
            # Skip if same as source or duplicate on same datetime for operator
            exists = (
                db.query(Trip)
                .filter(Trip.operator_id == operator_id, Trip.origin == src.origin, Trip.destination == src.destination, Trip.depart_at == depart_at)
                .count()
            )
            if exists == 0:
                t = Trip(
                    operator_id=src.operator_id,
                    origin=src.origin,
                    destination=src.destination,
                    depart_at=depart_at,
                    arrive_at=src.arrive_at,
                    price_cents=src.price_cents,
                    seats_total=src.seats_total,
                    seats_available=src.seats_total,
                    bus_model=src.bus_model,
                    bus_year=src.bus_year,
                )
                db.add(t)
                created += 1
        d = d + timedelta(days=1)
    db.flush()
    return {"detail": "ok", "created": created}


# Settlements (daily) and Analytics

@router.get("/{operator_id}/settlements/daily")
def settlements_daily(operator_id: str, from_utc: datetime | None = None, to_utc: datetime | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    to = to_utc or datetime.utcnow()
    fr = from_utc or (to - timedelta(days=7))
    rows = (
        db.query(Booking)
        .join(Trip, Trip.id == Booking.trip_id)
        .filter(Trip.operator_id == operator_id, Booking.status == "confirmed", Booking.created_at >= fr, Booking.created_at <= to)
        .all()
    )
    # group by date
    from collections import defaultdict
    daily = defaultdict(lambda: {"bookings": 0, "gross_revenue_cents": 0})
    by_branch = defaultdict(lambda: {"gross_revenue_cents": 0, "commission_cents": 0, "commission_bps": 0, "name": ""})
    # Prefetch branches
    branch_ids = {r.operator_branch_id for r in rows if r.operator_branch_id is not None}
    branches = {b.id: b for b in db.query(OperatorBranch).filter(OperatorBranch.id.in_(branch_ids)).all()} if branch_ids else {}
    for b in rows:
        dkey = b.created_at.date().isoformat()
        daily[dkey]["bookings"] += 1
        daily[dkey]["gross_revenue_cents"] += int(b.total_price_cents)
        if b.operator_branch_id is not None:
            br = branches.get(b.operator_branch_id)
            by_branch[str(b.operator_branch_id)]["gross_revenue_cents"] += int(b.total_price_cents)
            if br and br.commission_bps:
                by_branch[str(b.operator_branch_id)]["commission_bps"] = br.commission_bps
                by_branch[str(b.operator_branch_id)]["name"] = br.name
    # compute commissions per branch
    for v in by_branch.values():
        bps = int(v.get("commission_bps") or 0)
        v["commission_cents"] = (v["gross_revenue_cents"] * bps + 5000) // 10000 if bps else 0
    return {"from_utc": fr, "to_utc": to, "daily": daily, "branches": by_branch}


@router.get("/{operator_id}/settlements/daily.csv")
def settlements_daily_csv(operator_id: str, from_utc: datetime | None = None, to_utc: datetime | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = settlements_daily(operator_id, from_utc, to_utc, user, db)
    from io import StringIO
    import csv
    buf = StringIO(); w = csv.writer(buf)
    w.writerow(["date", "bookings", "gross_revenue_cents"])
    for d, rec in sorted(data["daily"].items()):
        w.writerow([d, rec["bookings"], rec["gross_revenue_cents"]])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8")


@router.get("/{operator_id}/settlements/branches.csv")
def settlements_branches_csv(operator_id: str, from_utc: datetime | None = None, to_utc: datetime | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = settlements_daily(operator_id, from_utc, to_utc, user, db)
    branches = data.get("branches", {}) or {}
    from io import StringIO
    import csv
    buf = StringIO(); w = csv.writer(buf)
    w.writerow(["branch_id", "name", "gross_revenue_cents", "commission_bps", "commission_cents"])
    for bid, rec in branches.items():
        w.writerow([bid, rec.get("name", ""), rec.get("gross_revenue_cents", 0), rec.get("commission_bps", 0), rec.get("commission_cents", 0)])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8")


@router.get("/{operator_id}/analytics/routes")
def analytics_routes(operator_id: str, days: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="agent")
    to = datetime.utcnow(); fr = to - timedelta(days=max(1, min(days, 365)))
    rows = (
        db.query(Booking)
        .join(Trip, Trip.id == Booking.trip_id)
        .filter(Trip.operator_id == operator_id, Booking.created_at >= fr, Booking.created_at <= to)
        .all()
    )
    from collections import defaultdict
    agg = defaultdict(lambda: {"total": 0, "confirmed": 0, "revenue_cents": 0})
    trips = {t.id: t for t in db.query(Trip).filter(Trip.id.in_({r.trip_id for r in rows})).all()} if rows else {}
    for b in rows:
        t = trips.get(b.trip_id)
        if not t:
            continue
        key = f"{t.origin}->{t.destination}"
        agg[key]["total"] += 1
        if b.status == "confirmed":
            agg[key]["confirmed"] += 1
            agg[key]["revenue_cents"] += int(b.total_price_cents)
    out = [{"route": k, **v} for k, v in sorted(agg.items(), key=lambda x: x[1]["confirmed"], reverse=True)]
    return {"from_utc": fr, "to_utc": to, "routes": out}


@router.get("/{operator_id}/tickets/validate", response_model=TicketValidationOut)
def validate_ticket(operator_id: str, qr: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="checker")
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
        seat_numbers=sorted([int(r.seat_number) for r in db.query(TripSeat).filter(TripSeat.booking_id == b.id).all()]),
        merchant_phone=op.merchant_phone if op and op.merchant_phone else settings.FEE_WALLET_PHONE,
        user_phone=u.phone if u else None,
        boarded_at=b.boarded_at,
    )
    if b.status != "confirmed":
        return TicketValidationOut(valid=False, reason=f"Status: {b.status}", booking=out)
    return TicketValidationOut(valid=True, booking=out)


@router.post("/{operator_id}/tickets/board")
def mark_boarded(operator_id: str, booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="checker")
    b = db.execute(select(Booking).where(Booking.id == booking_id).with_for_update()).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    t = db.get(Trip, b.trip_id)
    if not t or str(t.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Trip not found for operator")
    if b.status != "confirmed":
        raise HTTPException(status_code=400, detail=f"Not confirmed (status={b.status})")
    if b.boarded_at is not None:
        raise HTTPException(status_code=400, detail=f"Already boarded at {b.boarded_at.isoformat()}Z")
    b.boarded_at = datetime.utcnow()
    db.flush()
    try:
        _emit_webhooks(db, operator_id, "booking.boarded", {"booking_id": str(b.id), "trip_id": str(b.trip_id), "user_id": str(b.user_id), "boarded_at": b.boarded_at.isoformat() + "Z"})
    except Exception:
        pass
    return {"detail": "boarded", "boarded_at": b.boarded_at.isoformat() + "Z"}


# Vehicles endpoints

@router.get("/{operator_id}/vehicles", response_model=list[VehicleOut])
def list_vehicles(operator_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    rows = db.query(Vehicle).filter(Vehicle.operator_id == operator_id).order_by(Vehicle.created_at.desc()).all()
    return [VehicleOut(id=str(v.id), name=v.name, seats_total=v.seats_total, seat_columns=v.seat_columns) for v in rows]


@router.post("/{operator_id}/vehicles", response_model=VehicleOut)
def create_vehicle(operator_id: str, payload: VehicleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    v = Vehicle(operator_id=operator_id, name=payload.name, seats_total=payload.seats_total, seat_columns=payload.seat_columns)
    db.add(v)
    db.flush()
    return VehicleOut(id=str(v.id), name=v.name, seats_total=v.seats_total, seat_columns=v.seat_columns)


@router.patch("/{operator_id}/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(operator_id: str, vehicle_id: str, payload: VehicleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    v = db.get(Vehicle, vehicle_id)
    if not v or str(v.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    v.name = payload.name
    v.seats_total = payload.seats_total
    v.seat_columns = payload.seat_columns
    db.flush()
    return VehicleOut(id=str(v.id), name=v.name, seats_total=v.seats_total, seat_columns=v.seat_columns)


@router.delete("/{operator_id}/vehicles/{vehicle_id}")
def delete_vehicle(operator_id: str, vehicle_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    v = db.get(Vehicle, vehicle_id)
    if not v or str(v.operator_id) != operator_id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    cnt = db.query(Trip).filter(Trip.vehicle_id == v.id).count()
    if cnt:
        raise HTTPException(status_code=400, detail="Vehicle assigned to trips")
    db.delete(v)
    db.flush()
    return {"detail": "deleted"}


# Promos endpoints (scoped to operator or global)

@router.get("/{operator_id}/promos", response_model=list[PromoOut])
def list_promos_operator(operator_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    rows = db.query(PromoCode).filter((PromoCode.operator_id == operator_id) | (PromoCode.operator_id == None)).order_by(PromoCode.created_at.desc()).limit(200).all()  # noqa: E711
    out = []
    for p in rows:
        out.append(PromoOut(
            id=str(p.id), code=p.code, percent_off_bps=p.percent_off_bps, amount_off_cents=p.amount_off_cents,
            valid_from=p.valid_from, valid_until=p.valid_until, max_uses=p.max_uses, per_user_max_uses=p.per_user_max_uses,
            uses_count=p.uses_count or 0, min_total_cents=p.min_total_cents, active=p.active,
        ))
    return out


@router.post("/{operator_id}/promos", response_model=PromoOut)
def create_promo_operator(operator_id: str, payload: PromoCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    if not payload.percent_off_bps and not payload.amount_off_cents:
        raise HTTPException(status_code=400, detail="Provide percent_off_bps or amount_off_cents")
    pc = db.query(PromoCode).filter(PromoCode.code == payload.code).one_or_none()
    if pc is None:
        pc = PromoCode(code=payload.code, operator_id=operator_id)
        db.add(pc)
    pc.operator_id = operator_id
    pc.percent_off_bps = payload.percent_off_bps
    pc.amount_off_cents = payload.amount_off_cents
    pc.valid_from = payload.valid_from
    pc.valid_until = payload.valid_until
    pc.max_uses = payload.max_uses
    pc.per_user_max_uses = payload.per_user_max_uses
    pc.min_total_cents = payload.min_total_cents
    pc.active = payload.active
    db.flush()
    return PromoOut(
        id=str(pc.id), code=pc.code, percent_off_bps=pc.percent_off_bps, amount_off_cents=pc.amount_off_cents,
        valid_from=pc.valid_from, valid_until=pc.valid_until, max_uses=pc.max_uses, per_user_max_uses=pc.per_user_max_uses,
        uses_count=pc.uses_count or 0, min_total_cents=pc.min_total_cents, active=pc.active,
    )


@router.patch("/{operator_id}/promos/{promo_id}", response_model=PromoOut)
def update_promo_operator(operator_id: str, promo_id: str, payload: PromoUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    pc = db.get(PromoCode, promo_id)
    if not pc or (pc.operator_id is not None and str(pc.operator_id) != operator_id):
        raise HTTPException(status_code=404, detail="Promo not found")
    for field in ["percent_off_bps", "amount_off_cents", "valid_from", "valid_until", "max_uses", "per_user_max_uses", "min_total_cents", "active"]:
        v = getattr(payload, field)
        if v is not None:
            setattr(pc, field, v)
    db.flush()
    return PromoOut(
        id=str(pc.id), code=pc.code, percent_off_bps=pc.percent_off_bps, amount_off_cents=pc.amount_off_cents,
        valid_from=pc.valid_from, valid_until=pc.valid_until, max_uses=pc.max_uses, per_user_max_uses=pc.per_user_max_uses,
        uses_count=pc.uses_count or 0, min_total_cents=pc.min_total_cents, active=pc.active,
    )


@router.delete("/{operator_id}/promos/{promo_id}")
def delete_promo_operator(operator_id: str, promo_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_member(db, user.id, operator_id, min_role="admin")
    pc = db.get(PromoCode, promo_id)
    if not pc or (pc.operator_id is not None and str(pc.operator_id) != operator_id):
        raise HTTPException(status_code=404, detail="Promo not found")
    db.delete(pc)
    db.flush()
    return {"detail": "deleted"}
