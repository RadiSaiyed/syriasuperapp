"""
Seed demo data for Stays API (dev only).

Creates:
- 1 host user
- 3 properties (Damascus hotel, Aleppo apartment, Latakia apartments)
- Units, amenities, sample images
- Optional unit prices for the next 14 days (simple variation)

Usage (from repo root):
  DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5441/stays \
  python apps/stays/seed_demo.py
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from sqlalchemy import text

try:
    # When PYTHONPATH=apps/stays
    from app.database import SessionLocal
    from app.models import (
        User,
        Property,
        Unit,
        UnitAmenity,
        PropertyImage,
        UnitPrice,
        FavoriteProperty,
        Review,
        Base,
    )
except ModuleNotFoundError:
    # Fallback when importing from repo root
    from apps.stays.app.database import SessionLocal  # type: ignore
    from apps.stays.app.models import (  # type: ignore
        User,
        Property,
        Unit,
        UnitAmenity,
        PropertyImage,
        UnitPrice,
        Base,
        FavoriteProperty,
        Review,
    )
else:
    # Base when imported via app.*
    from app.models import Base  # type: ignore


def ensure_user(session, phone: str, name: str, role: str) -> User:
    u = session.query(User).filter(User.phone == phone).one_or_none()
    if u:
        if u.role != role:
            u.role = role
        if not u.name:
            u.name = name
        session.flush()
        return u
    u = User(phone=phone, name=name, role=role)
    session.add(u)
    session.flush()
    return u


def ensure_property(session, owner: User, name: str, city: str, ptype: str, description: str, lat: str | None = None, lon: str | None = None) -> Property:
    p = (
        session.query(Property)
        .filter(Property.owner_user_id == owner.id, Property.name == name, Property.city == city)
        .one_or_none()
    )
    if p:
        return p
    p = Property(owner_user_id=owner.id, name=name, type=ptype, city=city, description=description, latitude=lat, longitude=lon)
    session.add(p)
    session.flush()
    return p


def add_unit(session, prop: Property, name: str, capacity: int, total: int, price: int, min_nights: int = 1, cleaning_fee: int = 0, amenities: list[str] | None = None) -> Unit:
    u = (
        session.query(Unit)
        .filter(Unit.property_id == prop.id, Unit.name == name)
        .one_or_none()
    )
    if not u:
        u = Unit(
            property_id=prop.id,
            name=name,
            capacity=capacity,
            total_units=total,
            price_cents_per_night=price,
            min_nights=min_nights,
            cleaning_fee_cents=cleaning_fee,
            active=True,
        )
        session.add(u)
        session.flush()
    if amenities:
        for tag in amenities:
            tag = tag.strip()
            if not tag:
                continue
            exists = (
                session.query(UnitAmenity)
                .filter(UnitAmenity.unit_id == u.id, UnitAmenity.tag == tag)
                .one_or_none()
            )
            if not exists:
                session.add(UnitAmenity(unit_id=u.id, tag=tag))
    session.flush()
    return u


def add_image(session, prop: Property, url: str, sort: int):
    exists = (
        session.query(PropertyImage)
        .filter(PropertyImage.property_id == prop.id, PropertyImage.url == url)
        .one_or_none()
    )
    if not exists:
        session.add(PropertyImage(property_id=prop.id, url=url, sort_order=sort))
        session.flush()


def add_prices_for_next_days(session, unit: Unit, base_price: int, days: int = 14):
    start = date.today() + timedelta(days=1)
    for i in range(days):
        d = start + timedelta(days=i)
        # Simple variation: weekends +10%
        price = base_price
        if d.weekday() >= 4:
            price = int(round(base_price * 1.1))
        exists = (
            session.query(UnitPrice)
            .filter(UnitPrice.unit_id == unit.id, UnitPrice.date == d)
            .one_or_none()
        )
        if not exists:
            session.add(UnitPrice(unit_id=unit.id, date=d, price_cents=price))
    session.flush()


def main():
    # DB_URL comes from apps/stays/app/config.py default (localhost:5441/stays)
    print("Seeding demo data for Stays…")
    with SessionLocal() as session:
        # Create missing tables
        try:
            Base.metadata.create_all(bind=session.bind)
        except Exception:
            pass
        # Ensure dev columns exist if DB was created with older schema
        try:
            session.execute(text("ALTER TABLE properties ADD COLUMN IF NOT EXISTS address VARCHAR(256)"))
            session.execute(text("ALTER TABLE properties ADD COLUMN IF NOT EXISTS latitude VARCHAR(32)"))
            session.execute(text("ALTER TABLE properties ADD COLUMN IF NOT EXISTS longitude VARCHAR(32)"))
            session.execute(text("ALTER TABLE units ADD COLUMN IF NOT EXISTS min_nights INTEGER NOT NULL DEFAULT 1"))
            session.execute(text("ALTER TABLE units ADD COLUMN IF NOT EXISTS cleaning_fee_cents INTEGER NOT NULL DEFAULT 0"))
            session.execute(text("ALTER TABLE units ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE"))
            session.commit()
        except Exception:
            session.rollback()
        
        host = ensure_user(session, "+963900000100", "Demo Host", "host")

        # Damascus — Hotel
        p1 = ensure_property(
            session,
            host,
            name="Sunrise Hotel",
            city="Damascus",
            ptype="hotel",
            description="Central location, modern rooms",
            lat="33.5138",
            lon="36.2765",
        )
        u11 = add_unit(session, p1, name="Deluxe Room", capacity=2, total=5, price=60000, min_nights=1, amenities=["wifi", "ac", "parking"])
        u12 = add_unit(session, p1, name="Family Suite", capacity=4, total=2, price=110000, min_nights=2, amenities=["wifi", "kitchen"])
        add_image(session, p1, "https://images.unsplash.com/photo-1551776235-dde6d4829808?w=1200", 0)
        add_image(session, p1, "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=1200", 1)
        add_prices_for_next_days(session, u11, base_price=60000)
        add_prices_for_next_days(session, u12, base_price=110000)

        # Aleppo — Apartment
        p2 = ensure_property(
            session,
            host,
            name="Old City Apartment",
            city="Aleppo",
            ptype="apartment",
            description="Cozy 2BR near the Citadel",
            lat="36.2154",
            lon="37.1593",
        )
        u21 = add_unit(session, p2, name="2BR Apartment", capacity=4, total=3, price=80000, min_nights=2, amenities=["wifi", "kitchen"])
        add_image(session, p2, "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1200", 0)
        add_prices_for_next_days(session, u21, base_price=80000)

        # Latakia — Apartments
        p3 = ensure_property(
            session,
            host,
            name="Seaside Apartments",
            city="Latakia",
            ptype="apartment",
            description="Sea view studio & 1BR",
            lat="35.5167",
            lon="35.7833",
        )
        u31 = add_unit(session, p3, name="Studio", capacity=2, total=4, price=50000, min_nights=1, amenities=["wifi", "ac"]) 
        u32 = add_unit(session, p3, name="1BR Apartment", capacity=3, total=2, price=70000, min_nights=1, amenities=["wifi", "kitchen", "parking"]) 
        add_image(session, p3, "https://images.unsplash.com/photo-1521783988139-893ce3a61929?w=1200", 0)
        add_prices_for_next_days(session, u31, base_price=50000)
        add_prices_for_next_days(session, u32, base_price=70000)

        # Homs — Hotel
        p4 = ensure_property(
            session,
            host,
            name="Orchard Hotel",
            city="Homs",
            ptype="hotel",
            description="Green views, quiet area",
            lat="34.7324",
            lon="36.7134",
        )
        u41 = add_unit(session, p4, name="Standard", capacity=2, total=6, price=45000, amenities=["wifi"]) 
        add_image(session, p4, "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=1200", 0)
        add_prices_for_next_days(session, u41, base_price=45000)

        # Hama — Riverside Apartment
        p5 = ensure_property(
            session,
            host,
            name="Riverside Apartment",
            city="Hama",
            ptype="apartment",
            description="1BR near the river",
            lat="35.1318",
            lon="36.7578",
        )
        u51 = add_unit(session, p5, name="1BR", capacity=2, total=2, price=60000, amenities=["wifi", "kitchen"]) 
        add_image(session, p5, "https://images.unsplash.com/photo-1616596870420-4c2f5b91db97?w=1200", 0)
        add_prices_for_next_days(session, u51, base_price=60000)

        # Demo guests, favorites, and reviews
        g1 = ensure_user(session, "+963900000201", "Alice", "guest")
        g2 = ensure_user(session, "+963900000202", "Bob", "guest")
        
        # Favorites
        if session.query(FavoriteProperty).filter(FavoriteProperty.user_id == g1.id).count() == 0:
            session.add(FavoriteProperty(user_id=g1.id, property_id=p1.id))
            session.add(FavoriteProperty(user_id=g1.id, property_id=p3.id))
        if session.query(FavoriteProperty).filter(FavoriteProperty.user_id == g2.id).count() == 0:
            session.add(FavoriteProperty(user_id=g2.id, property_id=p2.id))
        
        # Reviews
        session.add(Review(property_id=p1.id, user_id=g1.id, rating=5, comment="Great location and staff!"))
        session.add(Review(property_id=p2.id, user_id=g2.id, rating=4, comment="Cozy apartment, clean and comfy."))

        session.commit()
    print("Done.")


if __name__ == "__main__":
    # Respect external DB_URL via env for SessionLocal
    if not os.getenv("DB_URL"):
        os.environ["DB_URL"] = "postgresql+psycopg2://postgres:postgres@localhost:5441/stays"
    main()
