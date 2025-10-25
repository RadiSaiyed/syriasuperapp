from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, selectinload
import httpx

from ..auth import get_current_user
from ..config import settings
from ..models import User, Cart, CartItem, MenuItem, Order, OrderItem, Restaurant
from ..schemas import OrderOut, OrdersListOut, OrderItemOut, TrackingOut
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks
from ..database import get_db


router = APIRouter(prefix="/orders", tags=["orders"])


def _to_order_out(db: Session, o: Order) -> OrderOut:
    return OrderOut(
        id=str(o.id),
        status=o.status,
        restaurant_id=str(o.restaurant_id),
        total_cents=o.total_cents,
        delivery_address=o.delivery_address,
        created_at=o.created_at,
        payment_request_id=o.payment_request_id,
        items=[
            OrderItemOut(
                menu_item_id=str(oi.menu_item_id),
                name=oi.name_snapshot,
                qty=oi.qty,
                price_cents=oi.price_cents_snapshot,
                subtotal_cents=oi.subtotal_cents,
            )
            for oi in o.items
        ],
    )


@router.post("/checkout", response_model=OrderOut)
def checkout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = db.query(Cart).filter(Cart.user_id == user.id).order_by(Cart.created_at.desc()).first()
    if cart is None or len(cart.items) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart empty")
    # Single-restaurant cart for MVP
    first_item = db.get(MenuItem, cart.items[0].menu_item_id)
    if first_item is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cart")
    restaurant_id = first_item.restaurant_id
    total = 0
    order = Order(user_id=user.id, restaurant_id=restaurant_id, status="created", total_cents=0)
    db.add(order)
    db.flush()

    for it in cart.items:
        mi = db.get(MenuItem, it.menu_item_id)
        if mi is None or mi.restaurant_id != restaurant_id or not mi.available:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item in cart")
        # Inventory auto-decrement (if managed)
        if getattr(mi, "stock_qty", None) is not None:
            if mi.stock_qty < it.qty:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")
            mi.stock_qty -= it.qty
            try:
                from ..config import settings as _settings
                if mi.stock_qty <= 0:
                    mi.available = False
                if mi.stock_qty <= max(0, getattr(_settings, "STOCK_LOW_THRESHOLD", 3)):
                    notify("food.stock.low", {"menu_item_id": str(mi.id), "stock_qty": int(mi.stock_qty)})
                    send_webhooks(db, "food.stock.low", {"menu_item_id": str(mi.id), "stock_qty": int(mi.stock_qty)})
            except Exception:
                pass
        sub = mi.price_cents * it.qty
        total += sub
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=mi.id,
                name_snapshot=mi.name,
                price_cents_snapshot=mi.price_cents,
                qty=it.qty,
                subtotal_cents=sub,
                station_snapshot=getattr(mi, 'station', None),
            )
        )
        db.delete(it)
    cart.updated_at = datetime.utcnow()
    order.total_cents = total
    db.flush()

    # Optional: create payment request via Payments service
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and total > 0:
            rest = db.get(Restaurant, restaurant_id)
            # Payments semantics: requester receives funds; target pays upon acceptance.
            # For checkout, the restaurant owner (or fee wallet) should be requester,
            # and the current user should be target (payer).
            owner_phone = None
            if rest and rest.owner_user_id:
                owner = db.get(User, rest.owner_user_id)
                owner_phone = owner.phone if owner else None
            requester_phone = owner_phone or settings.FEE_WALLET_PHONE
            target_phone = user.phone
            payload_json = {
                "from_phone": requester_phone,
                "to_phone": target_phone,
                "amount_cents": total,
                "metadata": {"order_id": str(order.id), "service": "food"},
            }
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
    except Exception:
        pass

    db.flush()
    try:
        notify("food.order.created", {"order_id": str(order.id), "restaurant_id": str(order.restaurant_id), "total_cents": order.total_cents})
        send_webhooks(db, "food.order.created", {"order_id": str(order.id), "restaurant_id": str(order.restaurant_id), "total_cents": order.total_cents})
    except Exception:
        pass
    return _to_order_out(db, order)


@router.get("", response_model=OrdersListOut)
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(100)
        .all()
    )
    return OrdersListOut(orders=[_to_order_out(db, o) for o in rows])


@router.get("/{order_id}/tracking", response_model=TrackingOut)
def tracking(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return TrackingOut(lat=o.courier_lat or 0.0, lon=o.courier_lon or 0.0, updated_at=o.courier_loc_updated_at)
