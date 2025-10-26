from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Property, Unit, Reservation, UnitAmenity, PropertyImage, UnitBlock, UnitPrice, Review
from ..schemas import (
    PropertyCreateIn,
    PropertyOut,
    UnitCreateIn,
    UnitOut,
    ReservationsListOut,
    ReservationOut,
    PropertyUpdateIn,
    UnitUpdateIn,
    PropertyImageCreateIn,
    PropertyImageOut,
    UnitBlockCreateIn,
    UnitBlockOut,
    UnitPriceIn,
    UnitPriceOut,
)
from ..utils.notify import notify
from ..utils.ids import as_uuid
from ..utils.webhooks import send_webhooks


router = APIRouter(prefix="/host", tags=["host"])


@router.post("/properties", response_model=PropertyOut)
def create_property(payload: PropertyCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("host", "guest"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
    if user.role != "host":
        user.role = "host"
    prop = Property(
        owner_user_id=user.id,
        name=payload.name,
        type=payload.type,
        city=payload.city,
        description=payload.description,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(prop)
    db.flush()
    return PropertyOut(id=str(prop.id), name=prop.name, type=prop.type, city=prop.city, description=prop.description, address=prop.address, latitude=prop.latitude, longitude=prop.longitude)


@router.get("/properties", response_model=list[PropertyOut])
def list_my_properties(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import func
    props = db.query(Property).filter(Property.owner_user_id == user.id).all()
    out: list[PropertyOut] = []
    for p in props:
        avg, cnt = db.query(func.avg(Review.rating), func.count(Review.id)).filter(Review.property_id == p.id).one()
        out.append(PropertyOut(
            id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description,
            address=p.address, latitude=p.latitude, longitude=p.longitude,
            rating_avg=float(avg) if avg is not None else None, rating_count=int(cnt) if cnt is not None else 0,
        ))
    return out


@router.post("/properties/{property_id}/units", response_model=UnitOut)
def create_unit(property_id: str, payload: UnitCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prop = db.get(Property, as_uuid(property_id))
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    u = Unit(
        property_id=prop.id,
        name=payload.name,
        capacity=payload.capacity,
        total_units=payload.total_units,
        price_cents_per_night=payload.price_cents_per_night,
        min_nights=payload.min_nights,
        cleaning_fee_cents=payload.cleaning_fee_cents,
        active=True,
    )
    db.add(u)
    db.flush()
    if payload.amenities:
        for t in payload.amenities:
            if t:
                db.add(UnitAmenity(unit_id=u.id, tag=t.strip()[:32]))
    return UnitOut(
        id=str(u.id), property_id=str(u.property_id), name=u.name, capacity=u.capacity,
        total_units=u.total_units, price_cents_per_night=u.price_cents_per_night,
        min_nights=u.min_nights, cleaning_fee_cents=u.cleaning_fee_cents, active=u.active,
        amenities=[a.tag for a in db.query(UnitAmenity).filter(UnitAmenity.unit_id == u.id).all()],
    )


@router.get("/properties/{property_id}/units", response_model=list[UnitOut])
def list_units(property_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prop = db.get(Property, as_uuid(property_id))
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    units = db.query(Unit).filter(Unit.property_id == prop.id).all()
    unit_ids = [u.id for u in units]
    tags_map = {uid: [] for uid in unit_ids}
    if unit_ids:
        for a in db.query(UnitAmenity).filter(UnitAmenity.unit_id.in_(unit_ids)).all():
            tags_map[a.unit_id].append(a.tag)
    return [
        UnitOut(
            id=str(u.id), property_id=str(u.property_id), name=u.name, capacity=u.capacity,
            total_units=u.total_units, price_cents_per_night=u.price_cents_per_night, min_nights=u.min_nights,
            cleaning_fee_cents=u.cleaning_fee_cents, active=u.active, amenities=tags_map.get(u.id, []),
        )
        for u in units
    ]


@router.patch("/properties/{property_id}", response_model=PropertyOut)
def update_property(property_id: str, payload: PropertyUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prop = db.get(Property, as_uuid(property_id))
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    if payload.name is not None:
        prop.name = payload.name
    if payload.type is not None:
        prop.type = payload.type
    if payload.city is not None:
        prop.city = payload.city
    if payload.description is not None:
        prop.description = payload.description
    db.flush()
    return PropertyOut(id=str(prop.id), name=prop.name, type=prop.type, city=prop.city, description=prop.description, address=prop.address, latitude=prop.latitude, longitude=prop.longitude)


@router.patch("/units/{unit_id}", response_model=UnitOut)
def update_unit(unit_id: str, payload: UnitUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(Unit, unit_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    prop = db.get(Property, u.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    if payload.name is not None:
        u.name = payload.name
    if payload.capacity is not None:
        u.capacity = payload.capacity
    if payload.total_units is not None:
        u.total_units = payload.total_units
    if payload.price_cents_per_night is not None:
        u.price_cents_per_night = payload.price_cents_per_night
    if payload.min_nights is not None:
        u.min_nights = payload.min_nights
    if payload.cleaning_fee_cents is not None:
        u.cleaning_fee_cents = payload.cleaning_fee_cents
    if payload.active is not None:
        u.active = bool(payload.active)
    if payload.amenities is not None:
        db.query(UnitAmenity).filter(UnitAmenity.unit_id == u.id).delete()
        for t in payload.amenities:
            if t:
                db.add(UnitAmenity(unit_id=u.id, tag=t.strip()[:32]))
    db.flush()
    return UnitOut(
        id=str(u.id), property_id=str(u.property_id), name=u.name, capacity=u.capacity,
        total_units=u.total_units, price_cents_per_night=u.price_cents_per_night,
        min_nights=u.min_nights, cleaning_fee_cents=u.cleaning_fee_cents, active=u.active,
        amenities=[a.tag for a in db.query(UnitAmenity).filter(UnitAmenity.unit_id == u.id).all()],
    )


@router.post("/properties/{property_id}/images", response_model=list[PropertyImageOut])
def add_property_images(property_id: str, images: list[PropertyImageCreateIn], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prop = db.get(Property, as_uuid(property_id))
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    created = []
    for im in images:
        pi = PropertyImage(property_id=prop.id, url=im.url, sort_order=im.sort_order)
        db.add(pi)
        db.flush()
        created.append({"id": str(pi.id), "url": pi.url, "sort_order": pi.sort_order})
    return created


@router.get("/properties/{property_id}/images")
def list_property_images(property_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prop = db.get(Property, as_uuid(property_id))
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    imgs = db.query(PropertyImage).filter(PropertyImage.property_id == prop.id).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
    return [{"id": str(i.id), "url": i.url, "sort_order": i.sort_order} for i in imgs]


@router.delete("/images/{image_id}")
def delete_property_image(image_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    img = db.get(PropertyImage, as_uuid(image_id))
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    prop = db.get(Property, img.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    db.delete(img)
    return {"detail": "ok"}


@router.post("/units/{unit_id}/blocks", response_model=UnitBlockOut)
def create_block(unit_id: str, payload: UnitBlockCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(Unit, as_uuid(unit_id))
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    prop = db.get(Property, u.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    if payload.start_date >= payload.end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date range")
    b = UnitBlock(unit_id=u.id, start_date=payload.start_date, end_date=payload.end_date, blocked_units=payload.blocked_units, reason=payload.reason)
    db.add(b)
    db.flush()
    return UnitBlockOut(id=str(b.id), unit_id=str(b.unit_id), start_date=b.start_date, end_date=b.end_date, blocked_units=b.blocked_units, reason=b.reason)


@router.get("/units/{unit_id}/blocks", response_model=list[UnitBlockOut])
def list_blocks(unit_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(Unit, as_uuid(unit_id))
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    prop = db.get(Property, u.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    blks = db.query(UnitBlock).filter(UnitBlock.unit_id == u.id).order_by(UnitBlock.start_date.desc()).all()
    return [UnitBlockOut(id=str(b.id), unit_id=str(b.unit_id), start_date=b.start_date, end_date=b.end_date, blocked_units=b.blocked_units, reason=b.reason) for b in blks]


@router.delete("/blocks/{block_id}")
def delete_block(block_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(UnitBlock, as_uuid(block_id))
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    u = db.get(Unit, b.unit_id)
    prop = db.get(Property, u.property_id) if u else None
    if not u or not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    db.delete(b)
    return {"detail": "ok"}


@router.put("/units/{unit_id}/prices", response_model=list[UnitPriceOut])
def upsert_prices(unit_id: str, prices: list[UnitPriceIn], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(Unit, as_uuid(unit_id))
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    prop = db.get(Property, u.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    out: list[UnitPriceOut] = []
    for p in prices:
        existing = db.query(UnitPrice).filter(UnitPrice.unit_id == u.id, UnitPrice.date == p.date).one_or_none()
        if existing:
            existing.price_cents = p.price_cents
        else:
            db.add(UnitPrice(unit_id=u.id, date=p.date, price_cents=p.price_cents))
        out.append(UnitPriceOut(unit_id=str(u.id), date=p.date, price_cents=p.price_cents))
    db.flush()
    return out


@router.get("/units/{unit_id}/prices", response_model=list[UnitPriceOut])
def list_prices(unit_id: str, start: str | None = None, end: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import date as _date
    u = db.get(Unit, unit_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    prop = db.get(Property, u.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")
    q = db.query(UnitPrice).filter(UnitPrice.unit_id == u.id)
    if start:
        q = q.filter(UnitPrice.date >= _date.fromisoformat(start))
    if end:
        q = q.filter(UnitPrice.date <= _date.fromisoformat(end))
    q = q.order_by(UnitPrice.date.asc()).all()
    return [UnitPriceOut(unit_id=str(x.unit_id), date=x.date, price_cents=x.price_cents) for x in q]


@router.get("/reservations", response_model=ReservationsListOut)
def list_my_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Reservations across my properties
    props = db.query(Property.id).filter(Property.owner_user_id == user.id).subquery()
    rs = db.query(Reservation).filter(Reservation.property_id.in_(props)).all()
    return ReservationsListOut(reservations=[
        ReservationOut(id=str(r.id), property_id=str(r.property_id), unit_id=str(r.unit_id), status=r.status, check_in=r.check_in, check_out=r.check_out, guests=r.guests, total_cents=r.total_cents, created_at=r.created_at, payment_request_id=r.payment_request_id) for r in rs
    ])


@router.post("/reservations/{reservation_id}/confirm", response_model=ReservationOut)
def confirm_reservation(reservation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Reservation, as_uuid(reservation_id))
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    prop = db.get(Property, r.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reservation")
    if r.status == "canceled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already canceled")
    r.status = "confirmed"
    db.flush()
    try:
        notify("reservation.confirmed", {"reservation_id": str(r.id)})
    except Exception:
        pass
    try:
        send_webhooks(db, "reservation.confirmed", {"reservation_id": str(r.id)})
    except Exception:
        pass
    return ReservationOut(id=str(r.id), property_id=str(r.property_id), unit_id=str(r.unit_id), status=r.status, check_in=r.check_in, check_out=r.check_out, guests=r.guests, total_cents=r.total_cents, created_at=r.created_at, payment_request_id=r.payment_request_id)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationOut)
def cancel_reservation(reservation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Reservation, as_uuid(reservation_id))
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    prop = db.get(Property, r.property_id)
    if not prop or prop.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reservation")
    r.status = "canceled"
    db.flush()
    try:
        notify("reservation.canceled", {"reservation_id": str(r.id), "by": "host"})
    except Exception:
        pass
    try:
        if r.payment_transfer_id:
            send_webhooks(db, "refund.requested", {"reservation_id": str(r.id), "transfer_id": r.payment_transfer_id, "amount_cents": int(r.total_cents)})
            r.refund_status = "requested"
            db.flush()
    except Exception:
        pass
    try:
        send_webhooks(db, "reservation.canceled", {"reservation_id": str(r.id), "by": "host"})
    except Exception:
        pass
    return ReservationOut(id=str(r.id), property_id=str(r.property_id), unit_id=str(r.unit_id), status=r.status, check_in=r.check_in, check_out=r.check_out, guests=r.guests, total_cents=r.total_cents, created_at=r.created_at, payment_request_id=r.payment_request_id)
