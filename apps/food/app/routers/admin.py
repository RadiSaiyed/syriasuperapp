from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Restaurant, Order, MenuItem, RestaurantImage, RestaurantReview
from ..schemas import OrdersListOut, OrderOut, OrderItemOut, RestaurantImageCreateIn, RestaurantImageOut, RestaurantOut, MenuItemOut
from ..utils.notify import notify
from ..utils.webhooks import send_webhooks
from ..utils.audit import audit
from ..utils.print_escpos import print_ticket


router = APIRouter(prefix="/admin", tags=["admin"])


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


@router.post("/dev/become_owner")
def dev_become_owner(restaurant_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    r.owner_user_id = user.id
    return {"detail": "ok"}


@router.get("/restaurants/mine", response_model=list[RestaurantOut])
def list_my_restaurants(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Restaurant)
        .filter(Restaurant.owner_user_id == user.id)
        .order_by(Restaurant.created_at.desc())
        .all()
    )
    out: list[RestaurantOut] = []
    for r in rows:
        avg, cnt = (
            db.query(func.avg(RestaurantReview.rating), func.count(RestaurantReview.id))
            .filter(RestaurantReview.restaurant_id == r.id)
            .one()
        )
        out.append(
            RestaurantOut(
                id=str(r.id),
                name=r.name,
                city=r.city,
                description=r.description,
                address=r.address,
                rating_avg=float(avg) if avg is not None else None,
                rating_count=int(cnt) if cnt is not None else 0,
            )
        )
    return out


@router.patch("/restaurants/{restaurant_id}")
def update_restaurant(restaurant_id: str, name: str | None = None, city: str | None = None, description: str | None = None, address: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    before = {"name": r.name, "city": r.city, "description": r.description, "address": r.address}
    if name is not None:
        r.name = name
    if city is not None:
        r.city = city
    if description is not None:
        r.description = description
    if address is not None:
        r.address = address
    audit(db, user_id=str(user.id), action="restaurant.update", entity_type="restaurant", entity_id=str(restaurant_id), before=before, after={"name": r.name, "city": r.city, "description": r.description, "address": r.address})
    return {"detail": "ok"}


@router.post("/restaurants/{restaurant_id}/menu")
def create_menu_item(restaurant_id: str, name: str, price_cents: int, description: str | None = None, available: bool = True, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    mi = MenuItem(restaurant_id=r.id, name=name, description=description, price_cents=price_cents, available=available)
    db.add(mi)
    db.flush()
    audit(db, user_id=str(user.id), action="menu_item.create", entity_type="menu_item", entity_id=str(mi.id), before=None, after={"name": name, "price_cents": price_cents})
    return {"id": str(mi.id)}


@router.get("/restaurants/{restaurant_id}/menu_all")
def admin_list_menu_all(restaurant_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    rows = db.query(MenuItem).filter(MenuItem.restaurant_id == r.id).order_by(MenuItem.created_at.desc()).all()
    return [
        {
            "id": str(m.id),
            "restaurant_id": str(m.restaurant_id),
            "name": m.name,
            "description": m.description,
            "price_cents": m.price_cents,
            "available": m.available,
        }
        for m in rows
    ]


@router.patch("/menu/{menu_item_id}")
def update_menu_item(menu_item_id: str, name: str | None = None, price_cents: int | None = None, description: str | None = None, available: bool | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mi = db.get(MenuItem, menu_item_id)
    if not mi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    r = db.get(Restaurant, mi.restaurant_id)
    if not r or r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    if name is not None:
        mi.name = name
    if price_cents is not None:
        mi.price_cents = price_cents
    if description is not None:
        mi.description = description
    if available is not None:
        mi.available = bool(available)
    return {"detail": "ok"}


@router.delete("/menu/{menu_item_id}")
def delete_menu_item(menu_item_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mi = db.get(MenuItem, menu_item_id)
    if not mi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    r = db.get(Restaurant, mi.restaurant_id)
    if not r or r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    db.delete(mi)
    return {"detail": "ok"}


@router.post("/restaurants/{restaurant_id}/images", response_model=list[RestaurantImageOut])
def add_images(restaurant_id: str, images: list[RestaurantImageCreateIn], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    created: list[RestaurantImageOut] = []
    for im in images:
        pi = RestaurantImage(restaurant_id=r.id, url=im.url, sort_order=im.sort_order)
        db.add(pi)
        db.flush()
        created.append(RestaurantImageOut(id=str(pi.id), url=pi.url, sort_order=pi.sort_order))
    audit(db, user_id=str(user.id), action="restaurant.images.create", entity_type="restaurant", entity_id=str(restaurant_id), before=None, after=[i.model_dump() for i in created])
    return created


@router.get("/restaurants/{restaurant_id}/images", response_model=list[RestaurantImageOut])
def list_images(restaurant_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    imgs = db.query(RestaurantImage).filter(RestaurantImage.restaurant_id == r.id).order_by(RestaurantImage.sort_order.asc(), RestaurantImage.created_at.asc()).all()
    return [RestaurantImageOut(id=str(i.id), url=i.url, sort_order=i.sort_order) for i in imgs]


@router.delete("/images/{image_id}")
def delete_image(image_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    img = db.get(RestaurantImage, image_id)
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    r = db.get(Restaurant, img.restaurant_id)
    if not r or r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    db.delete(img)
    audit(db, user_id=str(user.id), action="restaurant.images.delete", entity_type="restaurant_image", entity_id=str(image_id), before={"url": img.url}, after=None)
    return {"detail": "ok"}


@router.get("/orders", response_model=OrdersListOut)
def list_my_restaurant_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # find restaurants owned by user
    rs = db.query(Restaurant.id).filter(Restaurant.owner_user_id == user.id).all()
    if not rs:
        return OrdersListOut(orders=[])
    rest_ids = [rid for (rid,) in rs]
    orders = db.query(Order).filter(Order.restaurant_id.in_(rest_ids)).order_by(Order.created_at.desc()).limit(200).all()
    return OrdersListOut(orders=[_to_order_out(o) for o in orders])


@router.get("/restaurants/{restaurant_id}/stats")
def restaurant_stats(restaurant_id: str, range: str = "day", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import datetime as _dt
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    now = _dt.datetime.utcnow()
    if range == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range == "week":
        # ISO week start (Monday)
        start = (now - _dt.timedelta(days=(now.isoweekday() - 1))).replace(hour=0, minute=0, second=0, microsecond=0)
    elif range == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now - _dt.timedelta(days=30)
    q = db.query(Order).filter(Order.restaurant_id == r.id, Order.created_at >= start)
    total_orders = q.count()
    total_cents = sum(o.total_cents for o in q.all())
    by_status = {}
    for st in ["created", "accepted", "preparing", "out_for_delivery", "delivered", "canceled"]:
        by_status[st] = db.query(Order).filter(Order.restaurant_id == r.id, Order.created_at >= start, Order.status == st).count()
    return {
        "range": range,
        "from": start.isoformat() + "Z",
        "to": now.isoformat() + "Z",
        "total_orders": total_orders,
        "total_cents": total_cents,
        "by_status": by_status,
    }


@router.get("/restaurants/{restaurant_id}/orders_export")
def restaurant_orders_export(restaurant_id: str, range: str = "day", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import datetime as _dt
    r = db.get(Restaurant, restaurant_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    if r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    now = _dt.datetime.utcnow()
    if range == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range == "week":
        start = (now - _dt.timedelta(days=(now.isoweekday() - 1))).replace(hour=0, minute=0, second=0, microsecond=0)
    elif range == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now - _dt.timedelta(days=30)
    rows = (
        db.query(Order)
        .filter(Order.restaurant_id == r.id, Order.created_at >= start)
        .order_by(Order.created_at.desc())
        .all()
    )
    import csv
    from io import StringIO
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "status", "total_cents", "payment_transfer_id"])
    for o in rows:
        w.writerow([str(o.id), o.created_at.isoformat()+"Z", o.status, o.total_cents, o.payment_transfer_id or ""])
    return Response(buf.getvalue(), media_type="text/csv")


@router.post("/orders/{order_id}/refund_partial")
def request_partial_refund(order_id: str, amount_cents: int, reason: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    r = db.get(Restaurant, o.restaurant_id)
    if not r or r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    if amount_cents <= 0 or amount_cents > (o.total_cents or 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")
    try:
        send_webhooks(db, "refund.requested", {"order_id": str(o.id), "transfer_id": o.payment_transfer_id, "amount_cents": int(amount_cents), "reason": reason or "partial_refund"})
        audit(db, user_id=str(user.id), action="order.refund_partial", entity_type="order", entity_id=str(o.id), before={"total": o.total_cents}, after={"refund_cents": amount_cents})
    except Exception:
        pass
    return {"detail": "ok"}


@router.get("/orders/{order_id}/receipt.pdf")
def order_receipt_pdf(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    r = db.get(Restaurant, o.restaurant_id)
    if not r or r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from io import BytesIO
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PDF unavailable: {e}")
    buf = BytesIO(); c = canvas.Canvas(buf, pagesize=A4); width, height = A4
    y = height - 72
    c.setFont("Helvetica-Bold", 16); c.drawString(72, y, f"Receipt — {r.name}"); y -= 18
    c.setFont("Helvetica", 12); c.drawString(72, y, f"Order: {o.id}"); y -= 16
    c.drawString(72, y, f"Created: {o.created_at}"); y -= 16
    c.drawString(72, y, f"Status: {o.status}"); y -= 18
    c.drawString(72, y, "Items:"); y -= 16
    total = 0
    for it in o.items:
        c.drawString(90, y, f"{it.qty} x {it.name_snapshot} @ {it.price_cents_snapshot} = {it.subtotal_cents}"); y -= 14
        total += it.subtotal_cents
    y -= 10; c.setFont("Helvetica-Bold", 12); c.drawString(72, y, f"Total: {total}")
    c.showPage(); c.save()
    return Response(buf.getvalue(), media_type="application/pdf")


@router.get("/kds/orders")
def kds_orders(status: str = "accepted", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rs = db.query(Restaurant.id).filter(Restaurant.owner_user_id == user.id).all()
    if not rs:
        return []
    ids = [rid for (rid,) in rs]
    from sqlalchemy import or_
    st = [status] if status else ["accepted", "preparing"]
    rows = db.query(Order).filter(Order.restaurant_id.in_(ids), or_(Order.status.in_(st))).order_by(Order.created_at.asc()).limit(100).all()
    return [{"id": str(o.id), "status": o.status, "created_at": o.created_at, "items": [{"name": it.name_snapshot, "qty": it.qty, "packed": it.packed} for it in o.items]} for o in rows]


@router.post("/kds/orders/{order_id}/bump")
def kds_bump(order_id: str, to_status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    r = db.get(Restaurant, o.restaurant_id)
    if not r or r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    o.kds_bumped = True
    if to_status and to_status in ("preparing", "out_for_delivery", "delivered"):
        o.status = to_status
    audit(db, user_id=str(user.id), action="kds.bump", entity_type="order", entity_id=str(o.id), before=None, after={"status": o.status})
    try:
        lines = [f"Order {o.id}", f"Status: {o.status}"] + [f"- {it.qty} x {it.name_snapshot}" for it in o.items]
        print_ticket(lines)
    except Exception:
        pass
    return {"detail": "ok"}


ALLOWED_TRANSITIONS = {
    "created": {"accepted", "canceled"},
    "accepted": {"preparing", "canceled"},
    "preparing": {"out_for_delivery", "canceled"},
    "out_for_delivery": {"delivered", "canceled"},
}


@router.post("/orders/{order_id}/status")
def update_order_status(order_id: str, status_value: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    r = db.get(Restaurant, o.restaurant_id)
    if not r or r.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your restaurant")
    if o.status in ("delivered", "canceled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Final state")
    allowed = ALLOWED_TRANSITIONS.get(o.status, set())
    if status_value not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid transition")
    prev = o.status
    o.status = status_value
    # Stamp status timeline
    from datetime import datetime as _dt
    now = _dt.utcnow()
    o.last_status_at = now
    if status_value == "accepted":
        o.accepted_at = now
    elif status_value == "preparing":
        o.preparing_at = now
    elif status_value == "out_for_delivery":
        o.out_for_delivery_at = now
    elif status_value == "delivered":
        o.delivered_at = now
    elif status_value == "canceled":
        o.canceled_at = now
    try:
        notify("food.order.status_changed", {"order_id": str(o.id), "status": o.status})
        send_webhooks(db, "food.order.status_changed", {"order_id": str(o.id), "status": o.status})
    except Exception:
        pass
    # If canceled after acceptance, request refund
    if o.status == "canceled" and prev in ("accepted", "preparing", "out_for_delivery") and o.payment_transfer_id:
        try:
            send_webhooks(db, "refund.requested", {"order_id": str(o.id), "transfer_id": o.payment_transfer_id, "amount_cents": int(o.total_cents)})
            o.refund_status = "requested"
            db.flush()
        except Exception:
            pass
    return {"detail": "ok"}
