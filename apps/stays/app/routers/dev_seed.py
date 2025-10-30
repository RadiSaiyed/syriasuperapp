from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, Property, Unit, PropertyImage, UnitPrice

router = APIRouter(prefix="/dev", tags=["dev"])


def _ensure_user(db: Session, phone: str, name: str, role: str) -> User:
    u = db.query(User).filter(User.phone == phone).one_or_none()
    if u:
        if u.role != role:
            u.role = role
        if not u.name:
            u.name = name
        db.flush()
        return u
    u = User(phone=phone, name=name, role=role)
    db.add(u)
    db.flush()
    return u


@router.post("/seed")
def seed_demo(db: Session = Depends(get_db)):
    """
    Seed a few demo properties in dev to stabilize list endpoints.
    Safe to call multiple times (idempotent-ish by name/city).
    """
    if settings.ENV.lower() != "dev":
        return {"detail": "noop (not dev)"}

    # Create a host
    host = _ensure_user(db, "+963900000100", "Demo Host", "host")

    # Helper to ensure property exists
    def ensure_property(name: str, city: str, ptype: str, description: str, lat: str|None=None, lon: str|None=None) -> Property:
        p = (
            db.query(Property)
            .filter(Property.owner_user_id == host.id, Property.name == name, Property.city == city)
            .one_or_none()
        )
        if p:
            return p
        p = Property(owner_user_id=host.id, name=name, type=ptype, city=city, description=description, latitude=lat, longitude=lon)
        db.add(p)
        db.flush()
        return p

    def add_unit(prop: Property, name: str, capacity: int, total: int, price: int) -> Unit:
        u = db.query(Unit).filter(Unit.property_id == prop.id, Unit.name == name).one_or_none()
        if not u:
            u = Unit(property_id=prop.id, name=name, capacity=capacity, total_units=total, price_cents_per_night=price, active=True)
            db.add(u)
            db.flush()
        return u

    def add_image(prop: Property, url: str, sort: int = 0):
        exists = db.query(PropertyImage).filter(PropertyImage.property_id == prop.id, PropertyImage.url == url).one_or_none()
        if not exists:
            db.add(PropertyImage(property_id=prop.id, url=url, sort_order=sort))

    def add_prices(unit: Unit, base_price: int, days: int = 7):
        from datetime import date, timedelta
        start = date.today()
        for i in range(days):
            d = start + timedelta(days=i)
            if db.query(UnitPrice).filter(UnitPrice.unit_id == unit.id, UnitPrice.date == d).one_or_none() is None:
                db.add(UnitPrice(unit_id=unit.id, date=d, price_cents=base_price))

    # Damascus — Hotel
    p1 = ensure_property("Sunrise Hotel", "Damascus", "hotel", "Central location, modern rooms", "33.5138", "36.2765")
    u11 = add_unit(p1, "Deluxe Room", 2, 5, 60000)
    add_image(p1, "https://images.unsplash.com/photo-1551776235-dde6d4829808?w=1200", 0)
    add_prices(u11, 60000)

    # Aleppo — Apartment
    p2 = ensure_property("Old City Apartment", "Aleppo", "apartment", "Cozy 2BR near the Citadel", "36.2154", "37.1593")
    u21 = add_unit(p2, "2BR Apartment", 4, 3, 80000)
    add_image(p2, "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1200", 0)
    add_prices(u21, 80000)

    # Latakia — Apartments
    p3 = ensure_property("Seaside Apartments", "Latakia", "apartment", "Sea view studio & 1BR", "35.5167", "35.7833")
    u31 = add_unit(p3, "Studio", 2, 4, 50000)
    add_image(p3, "https://images.unsplash.com/photo-1521783988139-893ce3a61929?w=1200", 0)
    add_prices(u31, 50000)

    db.commit()
    return {"detail": "ok", "properties": db.query(Property).count()}

