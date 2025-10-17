from datetime import timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Property, Unit, Reservation, UnitAmenity, Review, PropertyImage, UnitBlock, UnitPrice
from ..schemas import PropertyOut, PropertyDetailOut, UnitOut, SearchAvailabilityIn, SearchAvailabilityOut, AvailableUnitOut


router = APIRouter(tags=["public"])  # no auth required


@router.get("/properties", response_model=list[PropertyOut])
def list_properties(city: str | None = None, type: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    from sqlalchemy import or_, func
    query = db.query(Property)
    if city:
        query = query.filter(Property.city == city)
    if type:
        query = query.filter(Property.type == type)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Property.name.ilike(like), Property.description.ilike(like)))
    props = query.order_by(Property.created_at.desc()).limit(200).all()
    out: list[PropertyOut] = []
    if not props:
        return out
    # Batch rating aggregates to avoid N+1
    prop_ids = [p.id for p in props]
    aggs = (
        db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
        .filter(Review.property_id.in_(prop_ids))
        .group_by(Review.property_id)
        .all()
    )
    rating_map = {pid: (float(avg) if avg is not None else None, int(cnt) if cnt is not None else 0) for (pid, avg, cnt) in aggs}
    for p in props:
        avg, cnt = rating_map.get(p.id, (None, 0))
        out.append(PropertyOut(
            id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description,
            address=p.address, latitude=p.latitude, longitude=p.longitude,
            rating_avg=avg, rating_count=cnt,
        ))
    return out


@router.get("/properties/{property_id}", response_model=PropertyDetailOut)
def get_property(property_id: str, db: Session = Depends(get_db)):
    p = db.get(Property, property_id)
    if not p:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    from sqlalchemy import func
    units = db.query(Unit).filter(Unit.property_id == p.id, Unit.active == True).all()  # noqa: E712
    unit_ids = [u.id for u in units]
    tags_map = {uid: [] for uid in unit_ids}
    if unit_ids:
        for a in db.query(UnitAmenity).filter(UnitAmenity.unit_id.in_(unit_ids)).all():
            tags_map[a.unit_id].append(a.tag)
    imgs = db.query(PropertyImage).filter(PropertyImage.property_id == p.id).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
    avg, cnt = db.query(func.avg(Review.rating), func.count(Review.id)).filter(Review.property_id == p.id).one()
    return PropertyDetailOut(
        id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description, address=p.address, latitude=p.latitude, longitude=p.longitude,
        rating_avg=float(avg) if avg is not None else None, rating_count=int(cnt) if cnt is not None else 0,
        units=[UnitOut(id=str(u.id), property_id=str(u.property_id), name=u.name, capacity=u.capacity, total_units=u.total_units, price_cents_per_night=u.price_cents_per_night, min_nights=u.min_nights, cleaning_fee_cents=u.cleaning_fee_cents, active=u.active, amenities=tags_map.get(u.id, [])) for u in units],
        images=[{"id": str(i.id), "url": i.url, "sort_order": i.sort_order} for i in imgs],
    )


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


@router.post("/search_availability", response_model=SearchAvailabilityOut)
def search_availability(payload: SearchAvailabilityIn, db: Session = Depends(get_db)):
    # naive availability: total_units - overlapping reservations
    props_q = db.query(Property)
    if payload.city:
        props_q = props_q.filter(Property.city == payload.city)
    props = props_q.all()
    results: list[AvailableUnitOut] = []

    nights = (payload.check_out - payload.check_in) // timedelta(days=1)
    if nights <= 0:
        return SearchAvailabilityOut(results=[])

    from datetime import timedelta as _td
    for p in props:
        if payload.property_type and p.type != payload.property_type:
            continue
        units = db.query(Unit).filter(Unit.property_id == p.id, Unit.active == True).all()  # noqa: E712
        unit_ids = [u.id for u in units]
        tags_map = {uid: [] for uid in unit_ids}
        if unit_ids:
            for a in db.query(UnitAmenity).filter(UnitAmenity.unit_id.in_(unit_ids)).all():
                tags_map[a.unit_id].append(a.tag)
        # Load blocks and prices for units for the period
        if unit_ids:
            blocks = db.query(UnitBlock).filter(UnitBlock.unit_id.in_(unit_ids)).all()
            prices = db.query(UnitPrice).filter(UnitPrice.unit_id.in_(unit_ids), UnitPrice.date >= payload.check_in, UnitPrice.date < payload.check_out).all()
        else:
            blocks = []
            prices = []
        blocks_by_unit = {}
        for b in blocks:
            blocks_by_unit.setdefault(b.unit_id, []).append(b)
        prices_by_unit = {}
        for pr in prices:
            prices_by_unit.setdefault(pr.unit_id, {})[pr.date] = pr.price_cents
        for u in units:
            # Capacity filter quick
            if payload.guests > u.capacity:
                continue
            if payload.capacity_min is not None and u.capacity < payload.capacity_min:
                continue
            # Amenities filter
            if payload.amenities:
                unit_tags = set(tags_map.get(u.id, []))
                query_tags = set(payload.amenities)
                if payload.amenities_mode == "all":
                    if not query_tags.issubset(unit_tags):
                        continue
                else:
                    if unit_tags.isdisjoint(query_tags):
                        continue
            # Min nights
            if nights < u.min_nights:
                continue
            # Day-by-day availability and pricing
            rs = db.query(Reservation).filter(Reservation.unit_id == u.id, Reservation.status.in_(["created", "confirmed"]))
            res_days = [(r.check_in, r.check_out) for r in rs]
            blks = blocks_by_unit.get(u.id, [])
            date_iter = payload.check_in
            min_avail = u.total_units
            total_cost = int(u.cleaning_fee_cents)
            while date_iter < payload.check_out:
                # reservations overlapping that specific date
                occ = sum(1 for (ci, co) in res_days if ci <= date_iter and date_iter < co)
                # blocked units overlapping
                blk = sum(b.blocked_units for b in blks if b.start_date <= date_iter and date_iter < b.end_date)
                avail_today = max(0, u.total_units - occ - blk)
                if avail_today < min_avail:
                    min_avail = avail_today
                # price for that night
                price_map = prices_by_unit.get(u.id, {})
                nightly = price_map.get(date_iter, u.price_cents_per_night)
                total_cost += int(nightly)
                date_iter = date_iter + _td(days=1)
            if min_avail <= 0:
                continue
            # Price filters based on average nightly rate over the period
            avg_nightly = (total_cost - int(u.cleaning_fee_cents)) / float(nights)
            if payload.min_price_cents is not None and avg_nightly < payload.min_price_cents:
                continue
            if payload.max_price_cents is not None and avg_nightly > payload.max_price_cents:
                continue
            results.append(AvailableUnitOut(
                property_id=str(p.id), property_name=p.name,
                unit_id=str(u.id), unit_name=u.name,
                capacity=u.capacity, available_units=min_avail,
                nightly_price_cents=u.price_cents_per_night, total_cents=int(total_cost),
            ))
    # Pagination for results
    total = len(results)
    sliced = results[payload.offset: payload.offset + payload.limit]
    next_off = payload.offset + payload.limit if (payload.offset + payload.limit) < total else None
    return SearchAvailabilityOut(results=sliced, total=total, next_offset=next_off)
