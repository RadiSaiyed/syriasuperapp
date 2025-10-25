from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import httpx
from uuid import UUID

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Company, Vehicle, Booking, FavoriteVehicle
from ..schemas import VehiclesListOut, VehicleOut, BookingCreateIn, BookingOut, BookingsListOut
from ..utils import notify
from ..config import settings
from superapp_shared.internal_hmac import sign_internal_request_headers


router = APIRouter(prefix="/market", tags=["market"]) 


@router.get("/vehicles", response_model=VehiclesListOut)
def browse_vehicles(
    q: str | None = None,
    location: str | None = None,
    make: str | None = None,
    transmission: str | None = None,
    seats_min: int | None = Query(None, ge=1),
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str | None = Query(None, description="price|created"),
    sort_dir: str | None = Query(None, description="asc|desc"),
    db: Session = Depends(get_db),
):
    query = db.query(Vehicle).filter(Vehicle.status == "available")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Vehicle.make.ilike(like), Vehicle.model.ilike(like), Vehicle.location.ilike(like)))
    if location:
        query = query.filter(Vehicle.location.ilike(f"%{location}%"))
    if make:
        query = query.filter(Vehicle.make.ilike(f"%{make}%"))
    if transmission:
        query = query.filter(Vehicle.transmission == transmission)
    if seats_min is not None:
        query = query.filter(Vehicle.seats.is_(None) | (Vehicle.seats >= seats_min))
    if min_price is not None:
        query = query.filter(Vehicle.price_per_day_cents >= min_price)
    if max_price is not None:
        query = query.filter(Vehicle.price_per_day_cents <= max_price)
    # date availability: ensure no overlapping booking exists
    if start_date and end_date:
        sub = db.query(Booking.vehicle_id).filter(
            Booking.status != "canceled",
            # overlap if (start <= end2) and (end >= start2)
            and_(Booking.start_date <= end_date, Booking.end_date >= start_date),
        ).subquery()
        query = query.filter(~Vehicle.id.in_(sub))
    total = query.count()
    # Sorting
    order = Vehicle.created_at.desc()
    if sort_by == "price":
        order = Vehicle.price_per_day_cents.asc() if sort_dir == "asc" else Vehicle.price_per_day_cents.desc()
    elif sort_by == "created":
        order = Vehicle.created_at.asc() if sort_dir == "asc" else Vehicle.created_at.desc()
    rows = query.order_by(order).limit(limit).offset(offset).all()
    return VehiclesListOut(vehicles=[
        VehicleOut(id=str(v.id), company_id=str(v.company_id), make=v.make, model=v.model, year=v.year, transmission=v.transmission, seats=v.seats, location=v.location, price_per_day_cents=v.price_per_day_cents, status=v.status, created_at=v.created_at)
        for v in rows
    ], total=total)


@router.get("/vehicles/favorites", response_model=VehiclesListOut)
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(FavoriteVehicle).filter(FavoriteVehicle.user_id == user.id).all()
    ids = [r.vehicle_id for r in rows]
    if not ids:
        return VehiclesListOut(vehicles=[], total=0)
    vs = db.query(Vehicle).filter(Vehicle.id.in_(ids), Vehicle.status == "available").all()
    return VehiclesListOut(vehicles=[
        VehicleOut(id=str(v.id), company_id=str(v.company_id), make=v.make, model=v.model, year=v.year, transmission=v.transmission, seats=v.seats, location=v.location, price_per_day_cents=v.price_per_day_cents, status=v.status, created_at=v.created_at)
        for v in vs
    ], total=len(vs))


@router.get("/vehicles/{vehicle_id}", response_model=VehicleOut)
def vehicle_details(vehicle_id: UUID, db: Session = Depends(get_db)):
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return VehicleOut(id=str(v.id), company_id=str(v.company_id), make=v.make, model=v.model, year=v.year, transmission=v.transmission, seats=v.seats, location=v.location, price_per_day_cents=v.price_per_day_cents, status=v.status, created_at=v.created_at)


@router.post("/vehicles/{vehicle_id}/book", response_model=BookingOut)
def create_booking(vehicle_id: UUID, payload: BookingCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(Vehicle, vehicle_id)
    if not v or v.status != "available":
        raise HTTPException(status_code=404, detail="Vehicle not available")
    # compute days
    import datetime as dt
    try:
        sd = dt.date.fromisoformat(payload.start_date)
        ed = dt.date.fromisoformat(payload.end_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid dates")
    if ed <= sd:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    days = (ed - sd).days
    # availability check
    overlap = (
        db.query(Booking)
        .filter(
            Booking.vehicle_id == v.id,
            Booking.status != "canceled",
            and_(Booking.start_date <= payload.end_date, Booking.end_date >= payload.start_date),
        )
        .count()
    )
    if overlap:
        raise HTTPException(status_code=400, detail="Vehicle not available for given dates")
    total = days * int(v.price_per_day_cents)
    b = Booking(user_id=user.id, vehicle_id=v.id, start_date=payload.start_date, end_date=payload.end_date, days=days, total_cents=total, status="requested")
    db.add(b)
    db.flush()
    # Optional payments handoff
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and total > 0:
            payload_json = {"from_phone": user.phone, "to_phone": settings.FEE_WALLET_PHONE, "amount_cents": total}
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, "")
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", headers=headers, json=payload_json)
                if r.status_code < 400:
                    b.payment_request_id = r.json().get("id")
                    db.flush()
    except Exception:
        pass
    notify("booking.created", {"booking_id": str(b.id)})
    return BookingOut(id=str(b.id), vehicle_id=str(b.vehicle_id), start_date=b.start_date, end_date=b.end_date, days=b.days, total_cents=b.total_cents, status=b.status, created_at=b.created_at)


@router.get("/bookings", response_model=BookingsListOut)
def my_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).all()
    return BookingsListOut(bookings=[
        BookingOut(id=str(b.id), vehicle_id=str(b.vehicle_id), start_date=b.start_date, end_date=b.end_date, days=b.days, total_cents=b.total_cents, status=b.status, created_at=b.created_at)
        for b in rows
    ])


@router.get("/vehicles/{vehicle_id}/availability")
def vehicle_availability(vehicle_id: UUID, from_date: str | None = None, to_date: str | None = None, db: Session = Depends(get_db)):
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    q = db.query(Booking).filter(Booking.vehicle_id == v.id, Booking.status != "canceled")
    if from_date:
        q = q.filter(Booking.end_date >= from_date)
    if to_date:
        q = q.filter(Booking.start_date <= to_date)
    rows = q.order_by(Booking.start_date.asc()).all()
    return {"booked": [{"start_date": b.start_date, "end_date": b.end_date} for b in rows]}


@router.post("/vehicles/{vehicle_id}/favorite")
def add_favorite(vehicle_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    exists = db.query(FavoriteVehicle).filter(FavoriteVehicle.user_id == user.id, FavoriteVehicle.vehicle_id == v.id).one_or_none()
    if exists:
        return {"detail": "ok"}
    db.add(FavoriteVehicle(user_id=user.id, vehicle_id=v.id))
    return {"detail": "ok"}


@router.delete("/vehicles/{vehicle_id}/favorite")
def remove_favorite(vehicle_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(FavoriteVehicle).filter(FavoriteVehicle.user_id == user.id, FavoriteVehicle.vehicle_id == vehicle_id).one_or_none()
    if row:
        db.delete(row)
    return {"detail": "ok"}
