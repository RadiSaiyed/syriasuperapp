from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import FavoriteProperty, Property, User, Review, PropertyImage
from ..utils.ids import as_uuid
from ..schemas import PropertyOut


router = APIRouter(prefix="/properties", tags=["favorites"])


@router.post("/{property_id}/favorite")
def favorite_property(property_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Property, as_uuid(property_id))
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    existing = db.query(FavoriteProperty).filter(FavoriteProperty.user_id == user.id, FavoriteProperty.property_id == p.id).one_or_none()
    if existing:
        return {"detail": "already_favorited"}
    fav = FavoriteProperty(user_id=user.id, property_id=p.id)
    db.add(fav)
    db.flush()
    return {"detail": "ok"}


@router.delete("/{property_id}/favorite")
def unfavorite_property(property_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Property, as_uuid(property_id))
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    existing = db.query(FavoriteProperty).filter(FavoriteProperty.user_id == user.id, FavoriteProperty.property_id == p.id).one_or_none()
    if not existing:
        return {"detail": "not_favorited"}
    db.delete(existing)
    return {"detail": "ok"}


@router.get("/favorites", response_model=list[PropertyOut])
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favs = db.query(FavoriteProperty).filter(FavoriteProperty.user_id == user.id).all()
    prop_ids = [f.property_id for f in favs]
    if not prop_ids:
        return []
    props = db.query(Property).filter(Property.id.in_(prop_ids)).order_by(Property.created_at.desc()).all()
    # Ratings
    from sqlalchemy import func
    aggs = (
        db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
        .filter(Review.property_id.in_(prop_ids))
        .group_by(Review.property_id)
        .all()
    )
    rmap = {pid: (float(avg) if avg is not None else None, int(cnt) if cnt is not None else 0) for (pid, avg, cnt) in aggs}
    # First images
    imgs = db.query(PropertyImage).filter(PropertyImage.property_id.in_(prop_ids)).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
    first_img: dict = {}
    for im in imgs:
        if im.property_id not in first_img:
            first_img[im.property_id] = im.url
    out: list[PropertyOut] = []
    for p in props:
        avg, cnt = rmap.get(p.id, (None, 0))
        out.append(PropertyOut(
            id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description,
            address=p.address, latitude=p.latitude, longitude=p.longitude,
            rating_avg=avg, rating_count=cnt, is_favorite=True, image_url=first_img.get(p.id),
        ))
    return out
