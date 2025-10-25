from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import FavoriteRestaurant, Restaurant, User
from ..schemas import RestaurantOut


router = APIRouter(prefix="/restaurants", tags=["favorites"])


@router.post("/{restaurant_id}/favorite")
def favorite_restaurant(restaurant_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    existing = db.query(FavoriteRestaurant).filter(FavoriteRestaurant.user_id == user.id, FavoriteRestaurant.restaurant_id == r.id).one_or_none()
    if existing:
        return {"detail": "already_favorited"}
    fav = FavoriteRestaurant(user_id=user.id, restaurant_id=r.id)
    db.add(fav)
    db.flush()
    return {"detail": "ok"}


@router.delete("/{restaurant_id}/favorite")
def unfavorite_restaurant(restaurant_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    existing = db.query(FavoriteRestaurant).filter(FavoriteRestaurant.user_id == user.id, FavoriteRestaurant.restaurant_id == r.id).one_or_none()
    if not existing:
        return {"detail": "not_favorited"}
    db.delete(existing)
    return {"detail": "ok"}


@router.get("/favorites", response_model=list[RestaurantOut])
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favs = db.query(FavoriteRestaurant).filter(FavoriteRestaurant.user_id == user.id).all()
    ids = [f.restaurant_id for f in favs]
    if not ids:
        return []
    rows = db.query(Restaurant).filter(Restaurant.id.in_(ids)).all()
    return [RestaurantOut(id=str(r.id), name=r.name, city=r.city, description=r.description, address=r.address) for r in rows]

