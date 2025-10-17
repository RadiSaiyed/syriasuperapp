from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import FavoriteProduct, Product, User
from sqlalchemy import select


router = APIRouter(prefix="/wishlist", tags=["wishlist"]) 


@router.get("")
def list_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(FavoriteProduct)
        .filter(FavoriteProduct.user_id == user.id)
        .order_by(FavoriteProduct.created_at.desc())
        .limit(100)
        .all()
    )
    if not rows:
        return []
    pids = {r.product_id for r in rows}
    prows = db.execute(select(Product).where(Product.id.in_(pids))).scalars().all()
    pmap = {p.id: p for p in prows}
    return [
        {
            "id": str(r.id),
            "product_id": str(r.product_id),
            "product_name": pmap.get(r.product_id).name if pmap.get(r.product_id) else "",
            "price_cents": pmap.get(r.product_id).price_cents if pmap.get(r.product_id) else 0,
            "stock_qty": pmap.get(r.product_id).stock_qty if pmap.get(r.product_id) else 0,
        }
        for r in rows
    ]


@router.post("")
def add_wishlist(product_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Product not found")
    existing = db.query(FavoriteProduct).filter(FavoriteProduct.user_id == user.id, FavoriteProduct.product_id == p.id).one_or_none()
    if existing:
        return {"detail": "exists"}
    fav = FavoriteProduct(user_id=user.id, product_id=p.id)
    db.add(fav)
    db.flush()
    return {"id": str(fav.id)}


@router.delete("/{fav_id}")
def delete_wishlist(fav_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fav = db.get(FavoriteProduct, fav_id)
    if fav is None or fav.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(fav)
    return {"detail": "deleted"}
