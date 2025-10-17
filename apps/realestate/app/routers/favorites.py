from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Favorite, Listing
from sqlalchemy import select
from ..auth import get_current_user


router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("")
def list_favorites(user=Depends(get_current_user), db: Session = Depends(get_db)):
    favs = (
        db.query(Favorite)
        .filter(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .limit(200)
        .all()
    )
    if not favs:
        return {"items": []}
    ids = {f.listing_id for f in favs}
    lst = db.execute(select(Listing).where(Listing.id.in_(ids))).scalars().all()
    lmap = {l.id: l for l in lst}
    out = []
    for f in favs:
        l = lmap.get(f.listing_id)
        if l:
            out.append({
                "listing_id": str(l.id),
                "title": l.title,
                "city": l.city,
                "type": l.type,
                "price_cents": l.price_cents,
            })
    return {"items": out}


@router.post("/{listing_id}")
def add_favorite(listing_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    exists = db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.listing_id == l.id).one_or_none()
    if exists:
        return {"detail": "exists"}
    db.add(Favorite(user_id=user.id, listing_id=l.id))
    db.flush()
    return {"detail": "ok"}


@router.delete("/{listing_id}")
def remove_favorite(listing_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.listing_id == listing_id).one_or_none()
    if not f:
        return {"detail": "not_found"}
    db.delete(f)
    db.flush()
    return {"detail": "ok"}
