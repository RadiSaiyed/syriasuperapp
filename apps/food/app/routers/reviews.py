from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Restaurant, RestaurantReview, User
from ..schemas import ReviewCreateIn, ReviewOut, ReviewsListOut
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks


router = APIRouter(prefix="/restaurants", tags=["reviews"])


@router.post("/{restaurant_id}/reviews", response_model=ReviewOut)
def create_review(restaurant_id: str, payload: ReviewCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    rv = RestaurantReview(restaurant_id=r.id, user_id=user.id, rating=payload.rating, comment=payload.comment)
    db.add(rv)
    db.flush()
    try:
        notify("food.review.created", {"review_id": str(rv.id), "restaurant_id": str(r.id), "user_id": str(user.id), "rating": rv.rating})
        send_webhooks(db, "food.review.created", {"review_id": str(rv.id), "restaurant_id": str(r.id), "user_id": str(user.id), "rating": rv.rating})
    except Exception:
        pass
    return ReviewOut(id=str(rv.id), restaurant_id=str(rv.restaurant_id), user_id=str(rv.user_id), rating=rv.rating, comment=rv.comment, created_at=rv.created_at)


@router.get("/{restaurant_id}/reviews", response_model=ReviewsListOut)
def list_reviews(restaurant_id: str, db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    rs = db.query(RestaurantReview).filter(RestaurantReview.restaurant_id == r.id).order_by(RestaurantReview.created_at.desc()).all()
    return ReviewsListOut(reviews=[ReviewOut(id=str(x.id), restaurant_id=str(x.restaurant_id), user_id=str(x.user_id), rating=x.rating, comment=x.comment, created_at=x.created_at) for x in rs])

