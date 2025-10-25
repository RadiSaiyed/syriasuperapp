from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Company, Vehicle, Booking, VehicleImage
from ..schemas import CompanyCreateIn, CompanyOut, VehicleCreateIn, VehicleUpdateIn, VehicleOut, BookingsListOut, BookingOut, VehicleImageCreateIn, VehicleImageOut


router = APIRouter(prefix="", tags=["company"])  # company + seller vehicles


def _require_seller(user: User):
    if user.role not in ("seller",):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller role required")


@router.post("/company", response_model=CompanyOut)
def create_company(payload: CompanyCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    existing = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Company already exists")
    c = Company(owner_user_id=user.id, name=payload.name, location=payload.location, description=payload.description)
    db.add(c)
    db.flush()
    return CompanyOut(id=str(c.id), name=c.name, location=c.location, description=c.description, created_at=c.created_at)


@router.get("/company", response_model=CompanyOut)
def get_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyOut(id=str(c.id), name=c.name, location=c.location, description=c.description, created_at=c.created_at)


@router.post("/vehicles", response_model=VehicleOut)
def add_vehicle(payload: VehicleCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c:
        raise HTTPException(status_code=400, detail="Company required")
    v = Vehicle(company_id=c.id, make=payload.make, model=payload.model, year=payload.year, transmission=payload.transmission, seats=payload.seats, location=payload.location, price_per_day_cents=payload.price_per_day_cents)
    db.add(v)
    db.flush()
    return VehicleOut(id=str(v.id), company_id=str(v.company_id), make=v.make, model=v.model, year=v.year, transmission=v.transmission, seats=v.seats, location=v.location, price_per_day_cents=v.price_per_day_cents, status=v.status, created_at=v.created_at)


@router.get("/vehicles", response_model=list[VehicleOut])
def my_vehicles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c:
        return []
    rows = db.query(Vehicle).filter(Vehicle.company_id == c.id).order_by(Vehicle.created_at.desc()).all()
    return [VehicleOut(id=str(v.id), company_id=str(v.company_id), make=v.make, model=v.model, year=v.year, transmission=v.transmission, seats=v.seats, location=v.location, price_per_day_cents=v.price_per_day_cents, status=v.status, created_at=v.created_at) for v in rows]


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: str, payload: VehicleUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c or v.company_id != c.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.transmission is not None:
        v.transmission = payload.transmission
    if payload.seats is not None:
        v.seats = payload.seats
    if payload.location is not None:
        v.location = payload.location
    if payload.price_per_day_cents is not None:
        v.price_per_day_cents = payload.price_per_day_cents
    if payload.status is not None:
        v.status = payload.status
    db.flush()
    return VehicleOut(id=str(v.id), company_id=str(v.company_id), make=v.make, model=v.model, year=v.year, transmission=v.transmission, seats=v.seats, location=v.location, price_per_day_cents=v.price_per_day_cents, status=v.status, created_at=v.created_at)


@router.get("/orders", response_model=BookingsListOut)
def company_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c:
        return BookingsListOut(bookings=[])
    vids = [v.id for v in db.query(Vehicle).filter(Vehicle.company_id == c.id).all()]
    if not vids:
        return BookingsListOut(bookings=[])
    rows = db.query(Booking).filter(Booking.vehicle_id.in_(vids)).order_by(Booking.created_at.desc()).all()
    return BookingsListOut(bookings=[BookingOut(id=str(b.id), vehicle_id=str(b.vehicle_id), start_date=b.start_date, end_date=b.end_date, days=b.days, total_cents=b.total_cents, status=b.status, created_at=b.created_at) for b in rows])


@router.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c or v.company_id != c.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    # ensure no active bookings overlapping future
    db.delete(v)
    return {"detail": "deleted"}


@router.post("/vehicles/{vehicle_id}/images", response_model=VehicleImageOut)
def add_vehicle_image(vehicle_id: str, payload: VehicleImageCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c or v.company_id != c.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    img = VehicleImage(vehicle_id=v.id, url=payload.url.strip(), sort_order=payload.sort_order or 0)
    db.add(img)
    db.flush()
    return VehicleImageOut(id=str(img.id), vehicle_id=str(img.vehicle_id), url=img.url, sort_order=img.sort_order, created_at=img.created_at)


@router.get("/vehicles/{vehicle_id}/images", response_model=list[VehicleImageOut])
def list_vehicle_images(vehicle_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # seller-only listing for now
    _require_seller(user)
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c or v.company_id != c.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = db.query(VehicleImage).filter(VehicleImage.vehicle_id == v.id).order_by(VehicleImage.sort_order.asc(), VehicleImage.created_at.asc()).all()
    return [VehicleImageOut(id=str(i.id), vehicle_id=str(i.vehicle_id), url=i.url, sort_order=i.sort_order, created_at=i.created_at) for i in rows]


@router.delete("/vehicles/{vehicle_id}/images/{image_id}")
def delete_vehicle_image(vehicle_id: str, image_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c or v.company_id != c.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    img = db.get(VehicleImage, image_id)
    if not img or img.vehicle_id != v.id:
        raise HTTPException(status_code=404, detail="Image not found")
    db.delete(img)
    return {"detail": "deleted"}


@router.post("/orders/{booking_id}/confirm", response_model=BookingOut)
def confirm_booking(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    b = db.get(Booking, booking_id)
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c:
        raise HTTPException(status_code=403, detail="Forbidden")
    v = db.get(Vehicle, b.vehicle_id)
    if not v or v.company_id != c.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if b.status == "canceled":
        raise HTTPException(status_code=400, detail="Booking canceled")
    b.status = "confirmed"
    db.flush()
    return BookingOut(id=str(b.id), vehicle_id=str(b.vehicle_id), start_date=b.start_date, end_date=b.end_date, days=b.days, total_cents=b.total_cents, status=b.status, created_at=b.created_at)


@router.post("/orders/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    b = db.get(Booking, booking_id)
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    c = db.query(Company).filter(Company.owner_user_id == user.id).one_or_none()
    if not c:
        raise HTTPException(status_code=403, detail="Forbidden")
    v = db.get(Vehicle, b.vehicle_id)
    if not v or v.company_id != c.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if b.status == "canceled":
        return BookingOut(id=str(b.id), vehicle_id=str(b.vehicle_id), start_date=b.start_date, end_date=b.end_date, days=b.days, total_cents=b.total_cents, status=b.status, created_at=b.created_at)
    b.status = "canceled"
    db.flush()
    return BookingOut(id=str(b.id), vehicle_id=str(b.vehicle_id), start_date=b.start_date, end_date=b.end_date, days=b.days, total_cents=b.total_cents, status=b.status, created_at=b.created_at)
