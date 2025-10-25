from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, Cart, CartItem, Product
from ..schemas import AddCartItemIn, CartOut, CartItemOut


router = APIRouter(prefix="/cart", tags=["cart"])


def _get_or_create_cart(db: Session, user: User) -> Cart:
    c = db.query(Cart).filter(Cart.user_id == user.id).order_by(Cart.created_at.desc()).first()
    if c is None:
        c = Cart(user_id=user.id)
        db.add(c)
        db.flush()
    return c


def _to_cart_out(db: Session, c: Cart) -> CartOut:
    items = []
    total = 0
    for it in c.items:
        # Fetch product explicitly to avoid lazy-load edge cases
        prod = db.get(Product, it.product_id)
        price = prod.price_cents if prod else 0
        sub = price * it.qty
        total += sub
        items.append(
            CartItemOut(
                id=str(it.id),
                product_id=str(it.product_id),
                product_name=prod.name if prod else "",
                price_cents=price,
                qty=it.qty,
                subtotal_cents=sub,
            )
        )
    return CartOut(id=str(c.id), items=items, total_cents=total)


@router.get("", response_model=CartOut)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _get_or_create_cart(db, user)
    return _to_cart_out(db, c)


@router.post("/items", response_model=CartOut)
def add_item(payload: AddCartItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _get_or_create_cart(db, user)
    p = db.get(Product, payload.product_id)
    if p is None or not p.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if p.stock_qty < payload.qty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")
    existing = db.query(CartItem).filter(CartItem.cart_id == c.id, CartItem.product_id == p.id).one_or_none()
    if existing:
        existing.qty = min(existing.qty + payload.qty, 20)
    else:
        db.add(CartItem(cart_id=c.id, product_id=p.id, qty=payload.qty))
    c.updated_at = datetime.utcnow()
    db.flush()
    return _to_cart_out(db, c)


@router.put("/items/{item_id}", response_model=CartOut)
def update_item(item_id: str, qty: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _get_or_create_cart(db, user)
    it = db.get(CartItem, item_id)
    if it is None or it.cart_id != c.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if qty <= 0:
        db.delete(it)
    else:
        p = db.get(Product, it.product_id)
        if p is None or p.stock_qty < qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")
        it.qty = min(qty, 20)
    c.updated_at = datetime.utcnow()
    db.flush()
    return _to_cart_out(db, c)


@router.post("/clear")
def clear_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = _get_or_create_cart(db, user)
    for it in list(c.items):
        db.delete(it)
    c.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "cleared"}
