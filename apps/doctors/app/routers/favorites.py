from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import FavoriteDoctor, DoctorProfile, User
from ..schemas import DoctorOut


router = APIRouter(prefix="/doctors", tags=["favorites"])


@router.post("/{doctor_id}/favorite")
def favorite_doctor(doctor_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(DoctorProfile, doctor_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    existing = db.query(FavoriteDoctor).filter(FavoriteDoctor.user_id == user.id, FavoriteDoctor.doctor_id == d.id).one_or_none()
    if existing:
        return {"detail": "already_favorited"}
    fav = FavoriteDoctor(user_id=user.id, doctor_id=d.id)
    db.add(fav)
    db.flush()
    return {"detail": "ok"}


@router.delete("/{doctor_id}/favorite")
def unfavorite_doctor(doctor_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(DoctorProfile, doctor_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    existing = db.query(FavoriteDoctor).filter(FavoriteDoctor.user_id == user.id, FavoriteDoctor.doctor_id == d.id).one_or_none()
    if not existing:
        return {"detail": "not_favorited"}
    db.delete(existing)
    return {"detail": "ok"}


@router.get("/favorites", response_model=list[DoctorOut])
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favs = db.query(FavoriteDoctor).filter(FavoriteDoctor.user_id == user.id).all()
    ids = [f.doctor_id for f in favs]
    if not ids:
        return []
    docs = db.query(DoctorProfile).filter(DoctorProfile.id.in_(ids)).all()
    out: list[DoctorOut] = []
    for d in docs:
        u = db.get(User, d.user_id)
        out.append(DoctorOut(id=str(d.id), user_id=str(d.user_id), name=u.name if u else None, specialty=d.specialty, city=d.city, clinic_name=d.clinic_name))
    return out

