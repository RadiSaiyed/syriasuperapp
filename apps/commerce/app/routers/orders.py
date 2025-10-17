from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from sqlalchemy import func, select
from ..models import User, Cart, CartItem, Product, Order, OrderItem, Shop, PromoCode, PromoRedemption
from ..schemas import OrderOut, OrdersListOut, OrderItemOut, CheckoutIn
from prometheus_client import Counter


router = APIRouter(prefix="/orders", tags=["orders"]) 

# App-specific metrics
ORDERS_COUNTER = Counter("commerce_orders_total", "Commerce orders", ["status"]) 


def _to_order_out(db: Session, o: Order) -> OrderOut:
    return OrderOut(
        id=str(o.id),
        status=o.status,
        shop_id=str(o.shop_id),
        total_cents=o.total_cents,
        shipping_name=o.shipping_name,
        shipping_phone=o.shipping_phone,
        shipping_address=o.shipping_address,
        created_at=o.created_at,
        payment_request_id=o.payment_request_id,
        items=[
            OrderItemOut(
                product_id=str(oi.product_id),
                name=oi.name_snapshot,
                qty=oi.qty,
                price_cents=oi.price_cents_snapshot,
                subtotal_cents=oi.subtotal_cents,
            )
            for oi in o.items
        ],
    )


@router.post("/checkout", response_model=OrderOut)
def checkout(request: Request, payload: CheckoutIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = db.query(Cart).filter(Cart.user_id == user.id).order_by(Cart.created_at.desc()).first()
    if cart is None or len(cart.items) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart empty")
    # Order is per single shop for MVP; enforce same shop
    first_prod = db.get(Product, cart.items[0].product_id)
    if first_prod is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cart")
    shop_id = first_prod.shop_id
    total = 0
    order = Order(user_id=user.id, shop_id=shop_id, status="created", total_cents=0)
    if payload:
        order.shipping_name = payload.shipping_name or None
        order.shipping_phone = payload.shipping_phone or None
        order.shipping_address = payload.shipping_address or None
    db.add(order)
    db.flush()

    for it in cart.items:
        p = db.get(Product, it.product_id)
        if p is None or p.shop_id != shop_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mixed-shop cart not allowed")
        if p.stock_qty < it.qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")
        p.stock_qty -= it.qty
        sub = p.price_cents * it.qty
        total += sub
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=p.id,
                name_snapshot=p.name,
                price_cents_snapshot=p.price_cents,
                qty=it.qty,
                subtotal_cents=sub,
            )
        )
        db.delete(it)
    cart.updated_at = datetime.utcnow()
    # Promo application
    discount = 0
    applied_code = None
    if payload and payload.promo_code:
        pc = db.query(PromoCode).filter(PromoCode.code == payload.promo_code).one_or_none()
        if pc and pc.active:
            now = datetime.utcnow()
            if not ((pc.valid_from and now < pc.valid_from) or (pc.valid_until and now > pc.valid_until)):
                if pc.max_uses is None or pc.uses_count < pc.max_uses:
                    per_user_ok = True
                    if pc.per_user_max_uses:
                        cnt = db.query(func.count(PromoRedemption.id)).filter(PromoRedemption.promo_code_id == pc.id, PromoRedemption.user_id == user.id).scalar() or 0
                        per_user_ok = cnt < pc.per_user_max_uses
                    if per_user_ok and (pc.min_total_cents is None or total >= pc.min_total_cents):
                        if pc.percent_off_bps:
                            discount = max(discount, int((total * pc.percent_off_bps + 5000) // 10000))
                        if pc.amount_off_cents:
                            discount = max(discount, int(pc.amount_off_cents))
                        discount = min(discount, total)
                        applied_code = pc.code
    order.total_cents = max(0, total - discount)
    db.flush()

    # Optional: create payment request via Payments service
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and total > 0:
            # For MVP, send to fee wallet as placeholder merchant account
            to_phone = settings.FEE_WALLET_PHONE
            payload_json = {"from_phone": user.phone, "to_phone": to_phone, "amount_cents": order.total_cents}
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.PAYMENTS_BASE_URL}/internal/requests",
                    headers=headers,
                    json=payload_json,
                )
                if r.status_code < 400:
                    order.payment_request_id = r.json().get("id")
                    order.status = "created"  # keep created; paid once accepted in Payments client
    except Exception:
        pass

    # Record promo redemption
    if applied_code and discount > 0:
        pc = db.query(PromoCode).filter(PromoCode.code == applied_code).one_or_none()
        if pc:
            pc.uses_count = (pc.uses_count or 0) + 1
            db.add(PromoRedemption(promo_code_id=pc.id, order_id=order.id, user_id=user.id))
    db.flush()
    try:
        ORDERS_COUNTER.labels(status=order.status).inc()
    except Exception:
        pass
    return _to_order_out(db, order)


@router.post("/{order_id}/cancel")
def cancel_order(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.execute(select(Order).where(Order.id == order_id).with_for_update()).scalars().first()
    if o is None or o.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.status in ("shipped",):
        raise HTTPException(status_code=400, detail="Cannot cancel shipped order")
    if o.status == "canceled":
        return {"detail": "canceled"}
    # restore stock
    for it in o.items:
        p = db.get(Product, it.product_id)
        if p:
            p.stock_qty += it.qty
    o.status = "canceled"
    db.flush()
    return {"detail": "canceled"}


@router.post("/{order_id}/mark_paid")
def mark_paid(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # DEV helper to simulate payments
    o = db.execute(select(Order).where(Order.id == order_id).with_for_update()).scalars().first()
    if o is None or o.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    o.status = "paid"
    db.flush()
    return {"detail": "paid"}


@router.post("/{order_id}/mark_shipped")
def mark_shipped(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.execute(select(Order).where(Order.id == order_id).with_for_update()).scalars().first()
    if o is None or o.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.status not in ("created", "paid"):
        raise HTTPException(status_code=400, detail="Invalid status")
    o.status = "shipped"
    db.flush()
    return {"detail": "shipped"}


@router.get("", response_model=OrdersListOut)
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(100).all()
    return OrdersListOut(orders=[_to_order_out(db, o) for o in rows])
