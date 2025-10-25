from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth import get_current_user, get_db
from ..models import ProductReview, Product, OrderItem, Order, User
from ..schemas import ReviewIn, ReviewOut


router = APIRouter(prefix="/reviews", tags=["reviews"]) 


def _purchased(db: Session, user_id: str, product_id: str) -> bool:
    q = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.user_id == user_id)
        .filter(OrderItem.product_id == product_id)
    )
    return db.query(q.exists()).scalar()


@router.post("/{product_id}", response_model=ReviewOut)
def add_review(product_id: str, payload: ReviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not _purchased(db, user.id, p.id):
        raise HTTPException(status_code=400, detail="You must purchase before reviewing")
    r = ProductReview(product_id=p.id, user_id=user.id, rating=payload.rating, comment=payload.comment or None)
    db.add(r)
    db.flush()
    return ReviewOut(id=str(r.id), product_id=str(p.id), rating=r.rating, comment=r.comment, created_at=r.created_at)


@router.get("/{product_id}", response_model=list[ReviewOut])
def list_reviews(product_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ProductReview).filter(ProductReview.product_id == product_id).order_by(ProductReview.created_at.desc()).limit(100).all()
    return [ReviewOut(id=str(r.id), product_id=str(r.product_id), rating=r.rating, comment=r.comment, created_at=r.created_at) for r in rows]

