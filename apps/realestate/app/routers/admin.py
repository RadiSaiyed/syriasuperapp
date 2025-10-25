from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Listing, ListingImage


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    if db.query(Listing).count() > 0:
        return {"detail": "exists"}
    data = [
        ("Bright 3‑room apartment", "Damascus", "Al‑Malki", "rent", "apartment", 2500000, 3, 1, 90.0, "+963900000101"),
        ("House with garden", "Homs", None, "sale", "house", 120000000, 5, 2, 220.0, "+963900000102"),
        ("Plot of land", "Latakia", None, "sale", "land", 75000000, None, None, 400.0, "+963900000103"),
    ]
    for t, city, dist, typ, ptyp, price, bed, bath, sqm, owner_phone in data:
        l = Listing(title=t, city=city, district=dist, type=typ, property_type=ptyp, price_cents=price, bedrooms=bed, bathrooms=bath, size_sqm=sqm, owner_phone=owner_phone)
        db.add(l)
        db.flush()
        db.add(ListingImage(listing_id=l.id, url="https://placehold.co/600x400", sort_order=0))
    return {"detail": "seeded"}


@router.post("/listings")
def create_listing(title: str, city: str, type: str = "rent", property_type: str = "apartment", price_cents: int = 0, owner_phone: str | None = None, db: Session = Depends(get_db)):
    l = Listing(title=title, city=city, type=type, property_type=property_type, price_cents=price_cents, owner_phone=owner_phone)
    db.add(l)
    db.flush()
    return {"id": str(l.id)}
