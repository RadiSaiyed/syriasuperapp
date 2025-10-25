from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database import get_db
from ..models import Listing, ListingImage
from ..schemas import ListingsListOut, ListingOut


router = APIRouter(prefix="/listings", tags=["listings"])


def _to_out(db: Session, l: Listing) -> ListingOut:
    imgs = db.query(ListingImage).filter(ListingImage.listing_id == l.id).order_by(ListingImage.sort_order.asc()).all()
    return ListingOut(
        id=str(l.id),
        title=l.title,
        city=l.city,
        district=l.district,
        type=l.type,
        property_type=l.property_type,
        price_cents=l.price_cents,
        bedrooms=l.bedrooms,
        bathrooms=l.bathrooms,
        size_sqm=l.size_sqm,
        owner_phone=l.owner_phone,
        images=[im.url for im in imgs] or None,
    )


@router.get("", response_model=ListingsListOut)
def list_listings(q: str | None = None, city: str | None = None, type: str | None = None, min_price: int | None = None, max_price: int | None = None, db: Session = Depends(get_db)):
    qry = db.query(Listing)
    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter((Listing.title.ilike(like)) | (Listing.description.ilike(like)))
    if city:
        qry = qry.filter(Listing.city.ilike(city))
    if type in ("rent", "sale"):
        qry = qry.filter(Listing.type == type)
    if min_price is not None:
        qry = qry.filter(Listing.price_cents >= int(min_price))
    if max_price is not None:
        qry = qry.filter(Listing.price_cents <= int(max_price))
    rows = qry.order_by(Listing.created_at.desc()).limit(100).all()
    return ListingsListOut(listings=[_to_out(db, l) for l in rows])


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: str, db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return _to_out(db, l)
