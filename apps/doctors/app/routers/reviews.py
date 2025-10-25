from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import DoctorReview, DoctorProfile, User
from ..schemas import ReviewCreateIn, ReviewOut, ReviewsListOut
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks


router = APIRouter(prefix="/doctors", tags=["reviews"])


@router.post("/{doctor_id}/reviews", response_model=ReviewOut)
def create_review(doctor_id: str, payload: ReviewCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(DoctorProfile, doctor_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    r = DoctorReview(doctor_id=d.id, user_id=user.id, rating=payload.rating, comment=payload.comment)
    db.add(r)
    db.flush()
    try:
        notify("doctors.review.created", {"review_id": str(r.id), "doctor_id": str(d.id), "user_id": str(user.id), "rating": r.rating})
        send_webhooks(db, "doctors.review.created", {"review_id": str(r.id), "doctor_id": str(d.id), "user_id": str(user.id), "rating": r.rating})
    except Exception:
        pass
    return ReviewOut(id=str(r.id), doctor_id=str(r.doctor_id), user_id=str(r.user_id), rating=r.rating, comment=r.comment, created_at=r.created_at)


@router.get("/{doctor_id}/reviews", response_model=ReviewsListOut)
def list_reviews(doctor_id: str, db: Session = Depends(get_db)):
    d = db.get(DoctorProfile, doctor_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    rs = db.query(DoctorReview).filter(DoctorReview.doctor_id == d.id).order_by(DoctorReview.created_at.desc()).all()
    return ReviewsListOut(reviews=[ReviewOut(id=str(r.id), doctor_id=str(r.doctor_id), user_id=str(r.user_id), rating=r.rating, comment=r.comment, created_at=r.created_at) for r in rs])

