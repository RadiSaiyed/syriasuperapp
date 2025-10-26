from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import FavoriteProperty, Property, User
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
    return [PropertyOut(id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description) for p in props]
