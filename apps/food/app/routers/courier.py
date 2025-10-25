from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Order
from ..schemas import OrdersListOut, OrderOut, OrderItemOut, TrackingUpdateIn
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks
from datetime import datetime


router = APIRouter(prefix="/courier", tags=["courier"])


def _to_order_out(o: Order) -> OrderOut:
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


@router.get("/available", response_model=OrdersListOut)
def available_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Orders ready for pickup (preparing done) and not assigned
    rows = db.query(Order).filter(Order.status == "preparing", Order.courier_user_id.is_(None)).order_by(Order.created_at.asc()).limit(100).all()
    return OrdersListOut(orders=[_to_order_out(o) for o in rows])


@router.post("/orders/{order_id}/accept")
def accept(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.status not in ("accepted", "preparing"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order not available")
    if o.courier_user_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already assigned")
    o.courier_user_id = user.id
    # If accepted, mark preparing as next; pickup will set out_for_delivery
    return {"detail": "ok"}


@router.get("/orders", response_model=OrdersListOut)
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Order).filter(Order.courier_user_id == user.id).order_by(Order.created_at.desc()).limit(100).all()
    return OrdersListOut(orders=[_to_order_out(o) for o in rows])


@router.post("/orders/{order_id}/picked_up")
def picked_up(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.courier_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")
    if o.status not in ("accepted", "preparing"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
    o.status = "out_for_delivery"
    try:
        notify("food.order.out_for_delivery", {"order_id": str(o.id)})
        send_webhooks(db, "food.order.out_for_delivery", {"order_id": str(o.id)})
    except Exception:
        pass
    return {"detail": "ok"}


@router.post("/orders/{order_id}/delivered")
def delivered(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.courier_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")
    if o.status != "out_for_delivery":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
    o.status = "delivered"
    try:
        notify("food.order.delivered", {"order_id": str(o.id)})
        send_webhooks(db, "food.order.delivered", {"order_id": str(o.id)})
    except Exception:
        pass
    return {"detail": "ok"}


@router.post("/orders/{order_id}/location")
def update_location(order_id: str, payload: TrackingUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.courier_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")
    o.courier_lat = float(payload.lat)
    o.courier_lon = float(payload.lon)
    o.courier_loc_updated_at = datetime.utcnow()
    try:
        notify("food.courier.location", {"order_id": str(o.id), "lat": o.courier_lat, "lon": o.courier_lon})
    except Exception:
        pass
    return {"detail": "ok"}
