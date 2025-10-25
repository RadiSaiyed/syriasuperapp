from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, FavoritePlace
from ..schemas import FavoriteIn, FavoriteOut, FavoriteUpdateIn


router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteOut])
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(FavoritePlace).filter(FavoritePlace.user_id == user.id).order_by(FavoritePlace.created_at.desc()).limit(100).all()
    return [
        FavoriteOut(id=str(r.id), label=r.label, lat=r.lat, lon=r.lon) for r in rows
    ]


@router.post("", response_model=FavoriteOut)
def create_favorite(payload: FavoriteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fav = FavoritePlace(user_id=user.id, label=payload.label.strip(), lat=payload.lat, lon=payload.lon)
    db.add(fav)
    db.flush()
    return FavoriteOut(id=str(fav.id), label=fav.label, lat=fav.lat, lon=fav.lon)


@router.delete("/{fav_id}")
def delete_favorite(fav_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fav = db.get(FavoritePlace, fav_id)
    if fav is None or fav.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")
    db.delete(fav)
    return {"detail": "deleted"}


@router.put("/{fav_id}", response_model=FavoriteOut)
def update_favorite(fav_id: str, payload: FavoriteUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fav = db.get(FavoritePlace, fav_id)
    if fav is None or fav.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")
    if payload.label is not None:
        label = payload.label.strip()
        if not label:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid label")
        fav.label = label
    if payload.lat is not None:
        fav.lat = float(payload.lat)
    if payload.lon is not None:
        fav.lon = float(payload.lon)
    db.flush()
    return FavoriteOut(id=str(fav.id), label=fav.label, lat=fav.lat, lon=fav.lon)
