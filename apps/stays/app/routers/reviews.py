from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Review, Property, User
from ..schemas import ReviewCreateIn, ReviewOut, ReviewsListOut
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks


router = APIRouter(prefix="/properties", tags=["reviews"])


@router.post("/{property_id}/reviews", response_model=ReviewOut)
def create_review(property_id: str, payload: ReviewCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Property, property_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    r = Review(property_id=p.id, user_id=user.id, rating=payload.rating, comment=payload.comment)
    db.add(r)
    db.flush()
    try:
        notify("review.created", {"review_id": str(r.id), "property_id": str(p.id), "user_id": str(user.id), "rating": r.rating})
    except Exception:
        pass
    try:
        send_webhooks(db, "review.created", {"review_id": str(r.id), "property_id": str(p.id), "user_id": str(user.id), "rating": r.rating})
    except Exception:
        pass
    return ReviewOut(id=str(r.id), property_id=str(r.property_id), user_id=str(r.user_id), rating=r.rating, comment=r.comment, created_at=r.created_at)


@router.get("/{property_id}/reviews", response_model=ReviewsListOut)
def list_reviews(property_id: str, db: Session = Depends(get_db)):
    p = db.get(Property, property_id)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    rs = db.query(Review).filter(Review.property_id == p.id).order_by(Review.created_at.desc()).all()
    return ReviewsListOut(reviews=[ReviewOut(id=str(r.id), property_id=str(r.property_id), user_id=str(r.user_id), rating=r.rating, comment=r.comment, created_at=r.created_at) for r in rs])
