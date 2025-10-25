from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, Listing, Favorite
from ..schemas import FavoritesListOut, ListingOut


router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.post("/{listing_id}")
def add_favorite(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    exists = db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.listing_id == l.id).one_or_none()
    if exists is None:
        db.add(Favorite(user_id=user.id, listing_id=l.id))
        db.flush()
    return {"detail": "ok"}


@router.delete("/{listing_id}")
def remove_favorite(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fav = db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.listing_id == listing_id).one_or_none()
    if fav:
        db.delete(fav)
        db.flush()
    return {"detail": "ok"}


@router.get("", response_model=FavoritesListOut)
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Listing)
        .join(Favorite, Favorite.listing_id == Listing.id)
        .filter(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    return FavoritesListOut(listings=[ListingOut(id=str(l.id), title=l.title, make=l.make, model=l.model, year=l.year, price_cents=l.price_cents, seller_user_id=str(l.seller_user_id), mileage_km=l.mileage_km, condition=l.condition, city=l.city) for l in rows])
