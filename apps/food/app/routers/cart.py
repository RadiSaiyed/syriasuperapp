from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Cart, CartItem, MenuItem
from ..schemas import AddCartItemIn, CartOut, CartItemOut


router = APIRouter(prefix="/cart", tags=["cart"])


def _to_cart_out(db: Session, c: Cart) -> CartOut:
    total = 0
    items: list[CartItemOut] = []
    for it in c.items:
        mi = db.get(MenuItem, it.menu_item_id)
        if not mi:
            continue
        sub = mi.price_cents * it.qty
        total += sub
        items.append(CartItemOut(id=str(it.id), menu_item_id=str(mi.id), name=mi.name, price_cents=mi.price_cents, qty=it.qty, subtotal_cents=sub))
    return CartOut(id=str(c.id), items=items, total_cents=total)


def _get_or_create_cart(db: Session, user_id):
    cart = db.query(Cart).filter(Cart.user_id == user_id).order_by(Cart.created_at.desc()).first()
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()
    return cart


@router.get("", response_model=CartOut)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = _get_or_create_cart(db, user.id)
    return _to_cart_out(db, cart)


@router.post("/items", response_model=CartOut)
def add_item(payload: AddCartItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = _get_or_create_cart(db, user.id)
    mi = db.get(MenuItem, payload.menu_item_id)
    if not mi or not mi.available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid menu item")
    it = CartItem(cart_id=cart.id, menu_item_id=mi.id, qty=payload.qty)
    db.add(it)
    cart.updated_at = datetime.utcnow()
    db.flush()
    return _to_cart_out(db, cart)


@router.put("/items/{item_id}", response_model=CartOut)
def update_item(item_id: str, payload: AddCartItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = _get_or_create_cart(db, user.id)
    it = db.get(CartItem, item_id)
    if not it or it.cart_id != cart.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    it.qty = payload.qty
    cart.updated_at = datetime.utcnow()
    db.flush()
    return _to_cart_out(db, cart)


@router.delete("/items/{item_id}", response_model=CartOut)
def delete_item(item_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = _get_or_create_cart(db, user.id)
    it = db.get(CartItem, item_id)
    if not it or it.cart_id != cart.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    db.delete(it)
    cart.updated_at = datetime.utcnow()
    db.flush()
    return _to_cart_out(db, cart)

