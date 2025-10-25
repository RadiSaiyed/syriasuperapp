from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from ..auth import get_current_user, get_db
from ..models import Shop, Product, User
from sqlalchemy import func
from ..schemas import ShopOut, ProductOut
from ..models import ProductReview


router = APIRouter(prefix="/shops", tags=["shops"])


def _seed_dev(db: Session):
    if db.query(Shop).count() > 0:
        return
    s1 = Shop(name="Damascus Market", description="Everyday essentials")
    s2 = Shop(name="Aleppo Crafts", description="Handmade goods")
    db.add_all([s1, s2])
    db.flush()
    prods = [
        Product(shop_id=s1.id, name="Rice 1kg", description="Syrian rice", price_cents=8000, stock_qty=100, category="grocery"),
        Product(shop_id=s1.id, name="Olive Oil 1L", description="Extra virgin", price_cents=22000, stock_qty=50, category="grocery"),
        Product(shop_id=s2.id, name="Wooden Bowl", description="Hand carved", price_cents=15000, stock_qty=20, category="home"),
        Product(shop_id=s2.id, name="Damask Scarf", description="Traditional pattern", price_cents=12000, stock_qty=30, category="fashion"),
    ]
    db.add_all(prods)
    db.flush()


@router.get("", response_model=list[ShopOut])
def list_shops(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _seed_dev(db)
    rows = db.query(Shop).order_by(Shop.created_at.desc()).all()
    return [ShopOut(id=str(s.id), name=s.name, description=s.description) for s in rows]


@router.get("/{shop_id}/products", response_model=list[ProductOut])
def list_products(shop_id: str, q: str | None = None, category: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _seed_dev(db)
    qset = db.query(Product).filter(Product.shop_id == shop_id, Product.active == True)  # noqa: E712
    if q:
        qs = f"%{q}%"
        qset = qset.filter(Product.name.ilike(qs) | Product.description.ilike(qs))
    if category:
        qset = qset.filter(Product.category == category)
    rows = qset.order_by(Product.created_at.desc()).all()
    out = []
    for p in rows:
        # aggregate rating
        agg = db.query(func.avg(ProductReview.rating), func.count(ProductReview.id)).filter(ProductReview.product_id == p.id).one()
        avg = float(agg[0]) if agg[0] is not None else None
        cnt = int(agg[1] or 0)
        out.append(ProductOut(
            id=str(p.id), shop_id=str(p.shop_id), name=p.name, description=p.description, price_cents=p.price_cents, stock_qty=p.stock_qty, category=p.category, avg_rating=avg, ratings_count=cnt
        ))
    return out
