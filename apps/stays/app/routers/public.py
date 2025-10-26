from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Property, Unit, Reservation, UnitAmenity, Review, PropertyImage, UnitBlock, UnitPrice, FavoriteProperty
from ..schemas import (
    PropertyOut,
    PropertyDetailOut,
    UnitOut,
    SearchAvailabilityIn,
    SearchAvailabilityOut,
    AvailableUnitOut,
    SearchFacetsOut,
    UnitCalendarOut,
    UnitCalendarDayOut,
    PropertyCalendarOut,
    PropertyCalendarDayOut,
    SuggestOut,
    SuggestItemOut,
    CityPopularOut,
)


router = APIRouter(tags=["public"])  # no auth required


@router.get("/properties", response_model=list[PropertyOut])
def list_properties(
    request: Request,
    response: Response,
    city: str | None = None,
    type: str | None = None,
    q: str | None = None,
    min_rating: int | None = None,
    sort_by: str = "rating",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    include_favorites_count: bool = False,
    include_price_preview: bool = False,
    check_in: str | None = None,
    check_out: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_, func

    def _to_float(v: str | None) -> float | None:
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    def _in_bounds(lat: float | None, lon: float | None) -> bool:
        if any(x is not None for x in (min_lat, max_lat, min_lon, max_lon)):
            if lat is None or lon is None:
                return False
            if min_lat is not None and lat < min_lat:
                return False
            if max_lat is not None and lat > max_lat:
                return False
            if min_lon is not None and lon < min_lon:
                return False
            if max_lon is not None and lon > max_lon:
                return False
        return True

    query = db.query(Property)
    if city:
        query = query.filter(Property.city == city)
    if type:
        query = query.filter(Property.type == type)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Property.name.ilike(like), Property.description.ilike(like)))
    props = query.order_by(Property.created_at.desc()).limit(1000).all()
    if not props:
        return []

    prop_ids = [p.id for p in props]
    aggs = (
        db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
        .filter(Review.property_id.in_(prop_ids))
        .group_by(Review.property_id)
        .all()
    )
    rating_map = {pid: (float(avg) if avg is not None else None, int(cnt) if cnt is not None else 0) for (pid, avg, cnt) in aggs}
    pops = (
        db.query(Reservation.property_id, func.count(Reservation.id))
        .filter(Reservation.property_id.in_(prop_ids))
        .group_by(Reservation.property_id)
        .all()
    )
    pop_map = {pid: int(cnt) for (pid, cnt) in pops}

    # Favorites for optional user
    fav_map: dict = {}
    try:
        if request is not None:
            from ..auth import try_get_user
            user = try_get_user(request, db)
            if user:
                from ..models import FavoriteProperty
                favs = db.query(FavoriteProperty.property_id).filter(FavoriteProperty.user_id == user.id, FavoriteProperty.property_id.in_(prop_ids)).all()
                fav_map = {pid: True for (pid,) in favs}
    except Exception:
        pass

    # First image per property (for list)
    imgs = db.query(PropertyImage).filter(PropertyImage.property_id.in_(prop_ids)).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
    first_img: dict = {}
    for im in imgs:
        if im.property_id not in first_img:
            first_img[im.property_id] = im.url

    rows = []
    for p in props:
        lat = _to_float(p.latitude)
        lon = _to_float(p.longitude)
        if not _in_bounds(lat, lon):
            continue
        avg, cnt = rating_map.get(p.id, (None, 0))
        popularity = pop_map.get(p.id, 0)
        rows.append((p, avg if avg is not None else -1.0, cnt, popularity, lat, lon))

    if min_rating is not None:
        rows = [r for r in rows if r[1] is not None and r[1] >= float(min_rating)]

    key = (sort_by or "rating").lower()
    reverse = (sort_order or "desc").lower() == "desc"
    if key == "rating":
        rows.sort(key=lambda r: (r[1], r[2], r[3]), reverse=reverse)
    elif key == "popularity":
        rows.sort(key=lambda r: (r[3], r[1], r[2]), reverse=reverse)
    elif key == "name":
        rows.sort(key=lambda r: (r[0].name or ""), reverse=reverse)
    elif key == "created":
        rows.sort(key=lambda r: (r[0].created_at,), reverse=reverse)
    else:
        rows.sort(key=lambda r: (r[1], r[2], r[3]), reverse=True)

    total = len(rows)
    sliced = rows[offset: offset + limit]
    # favorites count map (optional)
    fav_count_map: dict = {}
    if include_favorites_count and props:
        try:
            counts = (
                db.query(FavoriteProperty.property_id, func.count(FavoriteProperty.id))
                .filter(FavoriteProperty.property_id.in_(prop_ids))
                .group_by(FavoriteProperty.property_id)
                .all()
            )
            fav_count_map = {pid: int(c) for (pid, c) in counts}
        except Exception:
            fav_count_map = {}

    out: list[PropertyOut] = []
    # Optional price preview for provided dates
    preview_map: dict = {}
    if include_price_preview and check_in and check_out:
        try:
            from datetime import date as _date, timedelta as _td
            ci = _date.fromisoformat(check_in)
            co = _date.fromisoformat(check_out)
            if co > ci:
                for (p, _a, _c, _pop, _lat, _lon) in sliced:
                    units = db.query(Unit).filter(Unit.property_id == p.id, Unit.active == True).all()  # noqa: E712
                    if not units:
                        continue
                    unit_ids = [u.id for u in units]
                    blocks = db.query(UnitBlock).filter(UnitBlock.unit_id.in_(unit_ids)).all() if unit_ids else []
                    prices = db.query(UnitPrice).filter(UnitPrice.unit_id.in_(unit_ids), UnitPrice.date >= ci, UnitPrice.date < co).all() if unit_ids else []
                    blocks_by_unit = {}
                    for b in blocks:
                        blocks_by_unit.setdefault(b.unit_id, []).append(b)
                    prices_by_unit = {}
                    for pr in prices:
                        prices_by_unit.setdefault(pr.unit_id, {})[pr.date] = pr.price_cents
                    nights = int((co - ci).days)
                    best_total = None
                    best_avg = None
                    for u in units:
                        # compute availability and cost
                        rs = db.query(Reservation).filter(Reservation.unit_id == u.id, Reservation.status.in_(["created", "confirmed"]))
                        res_days = [(r.check_in, r.check_out) for r in rs]
                        date_iter = ci
                        min_avail = u.total_units
                        total_cost = int(u.cleaning_fee_cents)
                        blks = blocks_by_unit.get(u.id, [])
                        while date_iter < co:
                            occ = sum(1 for (ci2, co2) in res_days if ci2 <= date_iter and date_iter < co2)
                            blk = sum(b.blocked_units for b in blks if b.start_date <= date_iter and date_iter < b.end_date)
                            avail_today = max(0, u.total_units - occ - blk)
                            if avail_today < min_avail:
                                min_avail = avail_today
                            nightly = prices_by_unit.get(u.id, {}).get(date_iter, u.price_cents_per_night)
                            total_cost += int(nightly)
                            date_iter = date_iter + _td(days=1)
                        if min_avail <= 0:
                            continue
                        if best_total is None or total_cost < best_total:
                            best_total = int(total_cost)
                            best_avg = int((total_cost - int(u.cleaning_fee_cents)) / float(nights)) if nights > 0 else int(u.price_cents_per_night)
                    if best_total is not None:
                        preview_map[p.id] = (best_total, best_avg)
        except Exception:
            preview_map = {}

    for (p, avg, cnt, _pop, _lat, _lon) in sliced:
        out.append(PropertyOut(
            id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description,
            address=p.address, latitude=p.latitude, longitude=p.longitude,
            rating_avg=(avg if avg != -1.0 else None), rating_count=cnt,
            is_favorite=bool(fav_map.get(p.id)) if fav_map else None,
            image_url=first_img.get(p.id),
            favorites_count=fav_count_map.get(p.id) if fav_count_map else None,
            price_preview_total_cents=preview_map.get(p.id, (None, None))[0] if preview_map else None,
            price_preview_nightly_cents=preview_map.get(p.id, (None, None))[1] if preview_map else None,
        ))
    # Pagination headers
    if response is not None and request is not None:
        try:
            response.headers["X-Total-Count"] = str(total)
            # build prev/next links
            from starlette.datastructures import URL
            base = URL(str(request.url))
            links = []
            if offset > 0:
                prev_off = max(0, offset - limit)
                prev_url = str(base.include_query_params(offset=prev_off, limit=limit))
                links.append(f"<{prev_url}>; rel=\"prev\"")
            if offset + limit < total:
                next_off = offset + limit
                next_url = str(base.include_query_params(offset=next_off, limit=limit))
                links.append(f"<{next_url}>; rel=\"next\"")
            if links:
                response.headers["Link"] = ", ".join(links)
        except Exception:
            pass
    return out


@router.get("/properties/{property_id}", response_model=PropertyDetailOut)
def get_property(property_id: str, db: Session = Depends(get_db)):
    from ..utils.ids import as_uuid
    from sqlalchemy import func
    p = db.get(Property, as_uuid(property_id))
    if not p:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    units = db.query(Unit).filter(Unit.property_id == p.id, Unit.active == True).all()  # noqa: E712
    unit_ids = [u.id for u in units]
    tags_map = {uid: [] for uid in unit_ids}
    if unit_ids:
        for a in db.query(UnitAmenity).filter(UnitAmenity.unit_id.in_(unit_ids)).all():
            tags_map[a.unit_id].append(a.tag)
    imgs = db.query(PropertyImage).filter(PropertyImage.property_id == p.id).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
    avg, cnt = db.query(func.avg(Review.rating), func.count(Review.id)).filter(Review.property_id == p.id).one()
    # ratings histogram
    hist_rows = db.query(Review.rating, func.count(Review.id)).filter(Review.property_id == p.id).group_by(Review.rating).all()
    hist: dict[str, int] = {}
    for r, c in hist_rows:
        try:
            hist[str(int(r))] = int(c)
        except Exception:
            pass
    # similar properties (same city/type)
    similar_out: list[PropertyOut] = []
    if p.city:
        others = db.query(Property).filter(Property.city == p.city, Property.id != p.id)
        if p.type:
            others = others.filter(Property.type == p.type)
        others = others.order_by(Property.created_at.desc()).limit(64).all()
        if others:
            opids = [o.id for o in others]
            oaggs = (
                db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
                .filter(Review.property_id.in_(opids))
                .group_by(Review.property_id)
                .all()
            )
            rmap = {pid: (float(a) if a is not None else None, int(c) if c is not None else 0) for (pid, a, c) in oaggs}
            rows = []
            for o in others:
                ravg, rcnt = rmap.get(o.id, (None, 0))
                rows.append((o, ravg or -1.0, rcnt))
            rows.sort(key=lambda t: (t[1], t[2], t[0].created_at), reverse=True)
            for (o, ravg, rcnt) in rows[:6]:
                similar_out.append(PropertyOut(
                    id=str(o.id), name=o.name, type=o.type, city=o.city, description=o.description,
                    address=o.address, latitude=o.latitude, longitude=o.longitude,
                    rating_avg=(ravg if ravg != -1.0 else None), rating_count=rcnt,
                ))
    return PropertyDetailOut(
        id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description, address=p.address, latitude=p.latitude, longitude=p.longitude,
        rating_avg=float(avg) if avg is not None else None, rating_count=int(cnt) if cnt is not None else 0,
        units=[UnitOut(id=str(u.id), property_id=str(u.property_id), name=u.name, capacity=u.capacity, total_units=u.total_units, price_cents_per_night=u.price_cents_per_night, min_nights=u.min_nights, cleaning_fee_cents=u.cleaning_fee_cents, active=u.active, amenities=tags_map.get(u.id, [])) for u in units],
        images=[{"id": str(i.id), "url": i.url, "sort_order": i.sort_order} for i in imgs],
        rating_histogram=hist,
        similar=similar_out,
    )


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


@router.post("/search_availability", response_model=SearchAvailabilityOut)
def search_availability(payload: SearchAvailabilityIn, db: Session = Depends(get_db), request: Request = None):
    from sqlalchemy import func
    # naive availability: total_units - overlapping reservations
    props_q = db.query(Property)
    if payload.city:
        props_q = props_q.filter(Property.city == payload.city)
    if payload.property_ids:
        try:
            from uuid import UUID
            ids = [UUID(x) for x in payload.property_ids]
            props_q = props_q.filter(Property.id.in_(ids))
        except Exception:
            pass
    props = props_q.all()
    results: list[AvailableUnitOut] = []

    nights = (payload.check_out - payload.check_in) // timedelta(days=1)
    if nights <= 0:
        return SearchAvailabilityOut(results=[])

    from datetime import timedelta as _td

    def _to_float(v: str | None) -> float | None:
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    def _in_bounds(lat: float | None, lon: float | None) -> bool:
        if any(x is not None for x in (payload.min_lat, payload.max_lat, payload.min_lon, payload.max_lon)):
            if lat is None or lon is None:
                return False
            if payload.min_lat is not None and lat < payload.min_lat:
                return False
            if payload.max_lat is not None and lat > payload.max_lat:
                return False
            if payload.min_lon is not None and lon < payload.min_lon:
                return False
            if payload.max_lon is not None and lon > payload.max_lon:
                return False
        return True

    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        from math import radians, sin, cos, asin, sqrt
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6371.0 * c

    # Preload ratings and popularity for sorting/filters
    prop_ids = [p.id for p in props]
    rating_map: dict = {}
    if prop_ids:
        aggs = (
            db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
            .filter(Review.property_id.in_(prop_ids))
            .group_by(Review.property_id)
            .all()
        )
        rating_map = {pid: (float(avg) if avg is not None else None, int(cnt) if cnt is not None else 0) for (pid, avg, cnt) in aggs}
    pops = (
        db.query(Reservation.property_id, func.count(Reservation.id))
        .filter(Reservation.property_id.in_(prop_ids))
        .group_by(Reservation.property_id)
        .all()
    )
    pop_map = {pid: int(cnt) for (pid, cnt) in pops}

    fav_map: dict = {}
    try:
        if request is not None:
            from ..auth import try_get_user
            user = try_get_user(request, db)
            if user:
                from ..models import FavoriteProperty
                favs = db.query(FavoriteProperty.property_id).filter(FavoriteProperty.user_id == user.id, FavoriteProperty.property_id.in_(prop_ids)).all()
                fav_map = {pid: True for (pid,) in favs}
    except Exception:
        pass

    # Facet aggregators
    amenities_counts: dict[str, int] = {}
    rating_bands: dict[str, int] = {}
    price_min: int | None = None
    price_max: int | None = None
    price_hist_data: list[int] = []

    for p in props:
        plat = _to_float(p.latitude)
        plon = _to_float(p.longitude)
        if not _in_bounds(plat, plon):
            continue
        if payload.min_rating is not None:
            avg, _cnt = rating_map.get(p.id, (None, 0))
            if avg is None or avg < float(payload.min_rating):
                continue
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
            if payload.guests > u.capacity:
                continue
            if payload.capacity_min is not None and u.capacity < payload.capacity_min:
                continue
            if payload.amenities:
                unit_tags = set(tags_map.get(u.id, []))
                query_tags = set(payload.amenities)
                if payload.amenities_mode == "all":
                    if not query_tags.issubset(unit_tags):
                        continue
                else:
                    if unit_tags.isdisjoint(query_tags):
                        continue
            # Popular UX filters via amenities
            if payload.free_cancellation:
                norm_tags = {t.replace('-', '_').lower() for t in tags_map.get(u.id, [])}
                if 'free_cancellation' not in norm_tags:
                    continue
            if payload.breakfast_included:
                norm_tags = {t.replace('-', '_').lower() for t in tags_map.get(u.id, [])}
                if 'breakfast' not in norm_tags and 'breakfast_included' not in norm_tags:
                    continue
            if payload.non_refundable:
                norm_tags = {t.replace('-', '_').lower() for t in tags_map.get(u.id, [])}
                if 'non_refundable' not in norm_tags:
                    continue
            if payload.pay_at_property:
                norm_tags = {t.replace('-', '_').lower() for t in tags_map.get(u.id, [])}
                if 'pay_at_property' not in norm_tags:
                    continue
            if payload.no_prepayment:
                norm_tags = {t.replace('-', '_').lower() for t in tags_map.get(u.id, [])}
                if 'no_prepayment' not in norm_tags:
                    continue
            if nights < u.min_nights:
                continue
            rs = db.query(Reservation).filter(Reservation.unit_id == u.id, Reservation.status.in_(["created", "confirmed"]))
            res_days = [(r.check_in, r.check_out) for r in rs]
            blks = blocks_by_unit.get(u.id, [])
            date_iter = payload.check_in
            min_avail = u.total_units
            total_cost = int(u.cleaning_fee_cents)
            while date_iter < payload.check_out:
                occ = sum(1 for (ci, co) in res_days if ci <= date_iter and date_iter < co)
                blk = sum(b.blocked_units for b in blks if b.start_date <= date_iter and date_iter < b.end_date)
                avail_today = max(0, u.total_units - occ - blk)
                if avail_today < min_avail:
                    min_avail = avail_today
                price_map = prices_by_unit.get(u.id, {})
                nightly = price_map.get(date_iter, u.price_cents_per_night)
                total_cost += int(nightly)
                date_iter = date_iter + _td(days=1)
            if min_avail <= 0:
                continue
            avg_nightly = (total_cost - int(u.cleaning_fee_cents)) / float(nights)
            if payload.min_price_cents is not None and avg_nightly < payload.min_price_cents:
                continue
            if payload.max_price_cents is not None and avg_nightly > payload.max_price_cents:
                continue
            # Track facets
            unit_tags = tags_map.get(u.id, [])
            for t in unit_tags:
                amenities_counts[t] = amenities_counts.get(t, 0) + 1
            # nightly average is used for price facets
            nightly_avg_int = int(avg_nightly)
            price_min = nightly_avg_int if price_min is None else min(price_min, nightly_avg_int)
            price_max = nightly_avg_int if price_max is None else max(price_max, nightly_avg_int)
            price_hist_data.append(nightly_avg_int)
            # rating bands
            r_avg, _r_cnt = rating_map.get(p.id, (None, 0))
            if r_avg is not None:
                band = "5" if r_avg >= 5 else "4+" if r_avg >= 4 else "3+" if r_avg >= 3 else "2+" if r_avg >= 2 else "1+"
                rating_bands[band] = rating_bands.get(band, 0) + 1

            dist_val = None
            if payload.center_lat is not None and payload.center_lon is not None and plat is not None and plon is not None:
                try:
                    dist_val = _haversine_km(payload.center_lat, payload.center_lon, plat, plon)
                except Exception:
                    dist_val = None

            badges: list[str] = []
            if min_avail <= 1:
                badges.append("limited_availability")
            unit_tags_norm = {t.replace('-', '_').lower() for t in tags_map.get(u.id, [])}
            if 'free_cancellation' in unit_tags_norm:
                badges.append("free_cancellation")
            if 'breakfast' in unit_tags_norm or 'breakfast_included' in unit_tags_norm:
                badges.append("breakfast_included")
            ravg, _rc = rating_map.get(p.id, (None, 0))
            if ravg is not None and ravg >= 4.7:
                badges.append("top_rated")
            popscore = pop_map.get(p.id, 0)
            if popscore >= 5:
                badges.append("popular_choice")

            # policy flags
            results.append(AvailableUnitOut(
                property_id=str(p.id), property_name=p.name,
                unit_id=str(u.id), unit_name=u.name,
                capacity=u.capacity, available_units=min_avail,
                nightly_price_cents=u.price_cents_per_night, total_cents=int(total_cost),
                property_rating_avg=rating_map.get(p.id, (None, 0))[0] if rating_map else None,
                property_rating_count=rating_map.get(p.id, (None, 0))[1] if rating_map else None,
                distance_km=dist_val,
                is_favorite=bool(fav_map.get(p.id)) if fav_map else None,
                badges=badges,
                policy_free_cancellation=('free_cancellation' in unit_tags_norm),
                policy_non_refundable=('non_refundable' in unit_tags_norm),
                policy_no_prepayment=('no_prepayment' in unit_tags_norm),
                policy_pay_at_property=('pay_at_property' in unit_tags_norm),
            ))

    def _sort_key(item: AvailableUnitOut):
        if (payload.sort_by or "price") == "price":
            return (item.total_cents, item.nightly_price_cents)
        if payload.sort_by == "rating":
            avg, cnt = rating_map.get(item.property_id, (0.0, 0))
            return (avg or 0.0, cnt)
        if payload.sort_by == "popularity":
            pop = pop_map.get(item.property_id, 0)
            avg, cnt = rating_map.get(item.property_id, (0.0, 0))
            return (pop, avg or 0.0, cnt)
        if payload.sort_by == "best_value":
            avg, cnt = rating_map.get(item.property_id, (0.0, 0))
            price_per_night = max(1.0, float(item.total_cents) / float(nights))
            ratio = (avg or 0.0) / price_per_night
            return (ratio, cnt)
        if payload.sort_by == "distance" and payload.center_lat is not None and payload.center_lon is not None:
            p = next((pp for pp in props if str(pp.id) == item.property_id), None)
            lat = _to_float(p.latitude) if p else None
            lon = _to_float(p.longitude) if p else None
            if lat is None or lon is None:
                return (float("inf"),)
            return (_haversine_km(payload.center_lat, payload.center_lon, lat, lon),)
        if payload.sort_by == "recommended":
            # Weighted score: rating and popularity per price
            avg, cnt = rating_map.get(item.property_id, (0.0, 0))
            pop = pop_map.get(item.property_id, 0)
            price_per_night = max(1.0, float(item.total_cents) / float(nights))
            score = (avg or 0.0) * 0.6 + min(pop, 100) / 100.0 * 0.3 + min(cnt, 50) / 50.0 * 0.1
            return (score / price_per_night,)
        return (item.total_cents, item.nightly_price_cents)

    reverse = (payload.sort_order or "asc").lower() == "desc"
    # Group by property if requested (cheapest unit per property)
    if getattr(payload, "group_by_property", False):
        best_by_prop: dict[str, AvailableUnitOut] = {}
        for item in results:
            cur = best_by_prop.get(item.property_id)
            if cur is None:
                best_by_prop[item.property_id] = item
            else:
                if item.total_cents < cur.total_cents:
                    best_by_prop[item.property_id] = item
                elif item.total_cents == cur.total_cents:
                    # tie-breaker: higher rating, then lower nightly base
                    ir = rating_map.get(item.property_id, (0.0, 0))[0] or 0.0
                    cr = rating_map.get(cur.property_id, (0.0, 0))[0] or 0.0
                    if ir > cr or (ir == cr and item.nightly_price_cents < cur.nightly_price_cents):
                        best_by_prop[item.property_id] = item
        results = list(best_by_prop.values())

    results.sort(key=_sort_key, reverse=reverse)

    # Attach primary image URLs in batch
    try:
        from ..utils.ids import as_uuid
        pid_set = {as_uuid(x.property_id) for x in results}
        imgs = db.query(PropertyImage).filter(PropertyImage.property_id.in_(pid_set)).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
        first_img: dict = {}
        for im in imgs:
            if im.property_id not in first_img:
                first_img[im.property_id] = im.url
        for x in results:
            try:
                x.property_image_url = first_img.get(as_uuid(x.property_id))
            except Exception:
                pass
    except Exception:
        pass

    total = len(results)
    sliced = results[payload.offset: payload.offset + payload.limit]
    next_off = payload.offset + payload.limit if (payload.offset + payload.limit) < total else None
    # Build price histogram (5 buckets) if range available
    price_hist: dict[str, int] = {}
    try:
        if price_min is not None and price_max is not None and price_max >= price_min:
            buckets = 5
            width = max(1, (price_max - price_min) // buckets)
            edges = [price_min + i * width for i in range(buckets)]
            edges.append(price_max + 1)
            counts = [0] * buckets
            for v in price_hist_data:
                # find bucket
                idx = 0
                while idx < buckets and not (edges[idx] <= v < edges[idx+1]):
                    idx += 1
                if idx >= buckets:
                    idx = buckets - 1
                counts[idx] += 1
            for i in range(buckets):
                label = f"{edges[i]}-{edges[i+1]-1}"
                price_hist[label] = counts[i]
    except Exception:
        price_hist = {}

    facets = SearchFacetsOut(
        amenities_counts=amenities_counts,
        rating_bands=rating_bands,
        price_min_cents=price_min,
        price_max_cents=price_max,
        price_histogram=price_hist,
    )
    return SearchAvailabilityOut(results=sliced, total=total, next_offset=next_off, facets=facets)


@router.get("/properties/top", response_model=list[PropertyOut])
def top_properties(city: str | None = None, limit: int = 12, db: Session = Depends(get_db), request: Request = None):
    from sqlalchemy import func
    if settings.CACHE_ENABLED:
        ck = ("top_props", city or "_all_", int(limit))
        c = cache.get(ck)
        if c is not None:
            return c
    query = db.query(Property)
    if city:
        query = query.filter(Property.city == city)
    props = query.order_by(Property.created_at.desc()).limit(1000).all()
    if not props:
        return []
    prop_ids = [p.id for p in props]
    # ratings
    aggs = (
        db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
        .filter(Review.property_id.in_(prop_ids))
        .group_by(Review.property_id)
        .all()
    )
    rating_map = {pid: (float(avg) if avg is not None else None, int(cnt) if cnt is not None else 0) for (pid, avg, cnt) in aggs}
    # popularity
    pops = (
        db.query(Reservation.property_id, func.count(Reservation.id))
        .filter(Reservation.property_id.in_(prop_ids))
        .group_by(Reservation.property_id)
        .all()
    )
    pop_map = {pid: int(cnt) for (pid, cnt) in pops}
    # first image
    imgs = db.query(PropertyImage).filter(PropertyImage.property_id.in_(prop_ids)).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
    first_img: dict = {}
    for im in imgs:
        if im.property_id not in first_img:
            first_img[im.property_id] = im.url
    # favorites for user
    fav_map: dict = {}
    try:
        if request is not None:
            from ..auth import try_get_user
            user = try_get_user(request, db)
            if user:
                favs = db.query(FavoriteProperty.property_id).filter(FavoriteProperty.user_id == user.id, FavoriteProperty.property_id.in_(prop_ids)).all()
                fav_map = {pid: True for (pid,) in favs}
    except Exception:
        pass

    rows = []
    for p in props:
        ravg, rcnt = rating_map.get(p.id, (0.0, 0))
        pop = pop_map.get(p.id, 0)
        score = (ravg or 0.0) * 0.7 + min(pop, 100) / 100.0 * 0.3
        rows.append((p, score, ravg or None, rcnt))
    rows.sort(key=lambda t: (t[1], t[2] or 0.0, t[3]), reverse=True)
    out: list[PropertyOut] = []
    for (p, _score, ravg, rcnt) in rows[:limit]:
        out.append(PropertyOut(
            id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description,
            address=p.address, latitude=p.latitude, longitude=p.longitude,
            rating_avg=ravg, rating_count=rcnt, is_favorite=bool(fav_map.get(p.id)) if fav_map else None,
            image_url=first_img.get(p.id),
        ))
    if settings.CACHE_ENABLED:
        try:
            cache.set(ck, out, settings.CACHE_DEFAULT_TTL_SECS)
        except Exception:
            pass
    return out


@router.get("/units/{unit_id}/calendar", response_model=UnitCalendarOut)
def unit_calendar(unit_id: str, start: str | None = None, end: str | None = None, db: Session = Depends(get_db)):
    from datetime import date as _date, timedelta as _td
    from ..utils.ids import as_uuid
    u = db.get(Unit, as_uuid(unit_id))
    if not u:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    s = _date.fromisoformat(start) if start else _date.today()
    e = _date.fromisoformat(end) if end else (s + _td(days=30))
    if e <= s:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid range")
    rs = db.query(Reservation).filter(Reservation.unit_id == u.id, Reservation.status.in_(["created", "confirmed"]))
    res_days = [(r.check_in, r.check_out) for r in rs]
    blocks = db.query(UnitBlock).filter(UnitBlock.unit_id == u.id).all()
    prices = db.query(UnitPrice).filter(UnitPrice.unit_id == u.id, UnitPrice.date >= s, UnitPrice.date < e).all()
    price_map = {p.date: p.price_cents for p in prices}
    days: list[UnitCalendarDayOut] = []
    d = s
    while d < e:
        occ = sum(1 for (ci, co) in res_days if ci <= d and d < co)
        blk = sum(b.blocked_units for b in blocks if b.start_date <= d and d < b.end_date)
        avail_today = max(0, u.total_units - occ - blk)
        price_cents = int(price_map.get(d, u.price_cents_per_night))
        days.append(UnitCalendarDayOut(date=d, available_units=avail_today, price_cents=price_cents))
        d = d + _td(days=1)
    return UnitCalendarOut(unit_id=str(u.id), days=days)


@router.get("/properties/{property_id}/calendar", response_model=PropertyCalendarOut)
def property_calendar(property_id: str, start: str | None = None, end: str | None = None, db: Session = Depends(get_db)):
    from datetime import date as _date, timedelta as _td
    from ..utils.ids import as_uuid
    p = db.get(Property, as_uuid(property_id))
    if not p:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    s = _date.fromisoformat(start) if start else _date.today()
    e = _date.fromisoformat(end) if end else (s + _td(days=30))
    if e <= s:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid range")
    units = db.query(Unit).filter(Unit.property_id == p.id, Unit.active == True).all()  # noqa: E712
    if not units:
        return PropertyCalendarOut(property_id=str(p.id), days=[])
    unit_ids = [u.id for u in units]
    rs = db.query(Reservation).filter(Reservation.unit_id.in_(unit_ids), Reservation.status.in_(["created", "confirmed"]))
    res_days_by_unit = {}
    for r in rs:
        res_days_by_unit.setdefault(r.unit_id, []).append((r.check_in, r.check_out))
    blocks = db.query(UnitBlock).filter(UnitBlock.unit_id.in_(unit_ids)).all()
    blocks_by_unit = {}
    for b in blocks:
        blocks_by_unit.setdefault(b.unit_id, []).append(b)
    prices = db.query(UnitPrice).filter(UnitPrice.unit_id.in_(unit_ids), UnitPrice.date >= s, UnitPrice.date < e).all()
    prices_by_unit = {}
    for pr in prices:
        prices_by_unit.setdefault(pr.unit_id, {})[pr.date] = pr.price_cents
    days: list[PropertyCalendarDayOut] = []
    d = s
    while d < e:
        total_avail = 0
        min_price = None
        for u in units:
            occ = sum(1 for (ci, co) in res_days_by_unit.get(u.id, []) if ci <= d and d < co)
            blk = sum(b.blocked_units for b in blocks_by_unit.get(u.id, []) if b.start_date <= d and d < b.end_date)
            avail_today = max(0, u.total_units - occ - blk)
            total_avail += avail_today
            nightly = prices_by_unit.get(u.id, {}).get(d, u.price_cents_per_night)
            if min_price is None or nightly < min_price:
                min_price = int(nightly)
        days.append(PropertyCalendarDayOut(date=d, available_units_total=total_avail, min_price_cents=int(min_price or 0)))
        d = d + _td(days=1)
    return PropertyCalendarOut(property_id=str(p.id), days=days)


@router.get("/suggest", response_model=SuggestOut)
def suggest(q: str, limit: int = 10, db: Session = Depends(get_db)):
    from sqlalchemy import or_, func
    q = (q or "").strip()
    if not q:
        return SuggestOut(items=[])
    if settings.CACHE_ENABLED:
        cache_key = ("suggest", q.lower(), int(limit))
        cached = cache.get(cache_key)
        if cached is not None:
            return SuggestOut(items=cached)
    like = f"%{q}%"
    items: list[SuggestItemOut] = []
    # Top cities by property count matching query
    try:
        cities = (
            db.query(Property.city, func.count(Property.id))
            .filter(Property.city.isnot(None), Property.city.ilike(like))
            .group_by(Property.city)
            .order_by(func.count(Property.id).desc())
            .limit(max(1, limit // 2))
            .all()
        )
        for (city, _cnt) in cities:
            if city:
                items.append(SuggestItemOut(type="city", name=city))
    except Exception:
        pass
    # Properties matching by name/description
    try:
        props = (
            db.query(Property)
            .filter(or_(Property.name.ilike(like), Property.description.ilike(like)))
            .order_by(Property.created_at.desc())
            .limit(limit)
            .all()
        )
        if props:
            prop_ids = [p.id for p in props]
            aggs = (
                db.query(Review.property_id, func.avg(Review.rating))
                .filter(Review.property_id.in_(prop_ids))
                .group_by(Review.property_id)
                .all()
            )
            rmap = {pid: (float(avg) if avg is not None else None) for (pid, avg) in aggs}
            imgs = (
                db.query(PropertyImage)
                .filter(PropertyImage.property_id.in_(prop_ids))
                .order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc())
                .all()
            )
            first_img: dict = {}
            for im in imgs:
                if im.property_id not in first_img:
                    first_img[im.property_id] = im.url
            for p in props:
                items.append(
                    SuggestItemOut(
                        type="property",
                        id=str(p.id),
                        name=p.name,
                        city=p.city,
                        rating_avg=rmap.get(p.id),
                        image_url=first_img.get(p.id),
                    )
                )
    except Exception:
        pass
    # Trim to limit
    items = items[:limit]
    if settings.CACHE_ENABLED:
        try:
            cache.set(cache_key, items, settings.CACHE_DEFAULT_TTL_SECS // 2 or 30)
        except Exception:
            pass
    return SuggestOut(items=items)


@router.get("/cities/popular", response_model=list[CityPopularOut])
def popular_cities(limit: int = 8, db: Session = Depends(get_db)):
    from sqlalchemy import func
    if settings.CACHE_ENABLED:
        ck = ("cities_popular", int(limit))
        c = cache.get(ck)
        if c is not None:
            return c
    rows = (
        db.query(Property.city, func.count(Property.id))
        .filter(Property.city.isnot(None))
        .group_by(Property.city)
        .order_by(func.count(Property.id).desc())
        .limit(limit)
        .all()
    )
    out: list[CityPopularOut] = []
    for (city, cnt) in rows:
        if not city:
            continue
        # Avg rating per city
        try:
            avg = (
                db.query(func.avg(Review.rating))
                .filter(Review.property_id.in_(db.query(Property.id).filter(Property.city == city)))
                .scalar()
            )
            avg_rating = float(avg) if avg is not None else None
        except Exception:
            avg_rating = None
        # Min base price among units in city
        try:
            from sqlalchemy import select
            prop_ids = [pid for (pid,) in db.query(Property.id).filter(Property.city == city).all()]
            min_price = None
            if prop_ids:
                unit_min = db.query(func.min(Unit.price_cents_per_night)).filter(Unit.property_id.in_(prop_ids)).scalar()
                min_price = int(unit_min) if unit_min is not None else None
        except Exception:
            min_price = None
        # Representative image: first image of a property in city
        try:
            img = (
                db.query(PropertyImage)
                .join(Property, Property.id == PropertyImage.property_id)
                .filter(Property.city == city)
                .order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc())
                .first()
            )
            image_url = img.url if img else None
        except Exception:
            image_url = None
        out.append(CityPopularOut(city=city, property_count=int(cnt), avg_rating=avg_rating, image_url=image_url, min_price_cents=min_price))
    if settings.CACHE_ENABLED:
        try:
            cache.set(ck, out, settings.CACHE_DEFAULT_TTL_SECS)
        except Exception:
            pass
    return out


@router.get("/properties/nearby", response_model=list[PropertyOut])
def properties_nearby(lat: float, lon: float, radius_km: float = 10.0, limit: int = 100, db: Session = Depends(get_db), request: Request = None):
    from sqlalchemy import func
    # Load candidates (bounded to a reasonable set; actual distance computed in Python)
    props = db.query(Property).limit(2000).all()
    if not props:
        return []
    def _to_float(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None
    def _haversine_km(lat1, lon1, lat2, lon2):
        from math import radians, sin, cos, asin, sqrt
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        return 2 * asin(sqrt(a)) * 6371.0
    # Aggregates
    prop_ids = [p.id for p in props]
    aggs = (
        db.query(Review.property_id, func.avg(Review.rating), func.count(Review.id))
        .filter(Review.property_id.in_(prop_ids))
        .group_by(Review.property_id)
        .all()
    )
    rating_map = {pid: (float(avg) if avg is not None else None, int(cnt) if cnt is not None else 0) for (pid, avg, cnt) in aggs}
    imgs = db.query(PropertyImage).filter(PropertyImage.property_id.in_(prop_ids)).order_by(PropertyImage.sort_order.asc(), PropertyImage.created_at.asc()).all()
    first_img: dict = {}
    for im in imgs:
        if im.property_id not in first_img:
            first_img[im.property_id] = im.url
    # Favorites
    fav_map: dict = {}
    try:
        if request is not None:
            from ..auth import try_get_user
            user = try_get_user(request, db)
            if user:
                from ..models import FavoriteProperty
                favs = db.query(FavoriteProperty.property_id).filter(FavoriteProperty.user_id == user.id, FavoriteProperty.property_id.in_(prop_ids)).all()
                fav_map = {pid: True for (pid,) in favs}
    except Exception:
        pass
    # Distance filter/sort
    rows = []
    for p in props:
        plat = _to_float(p.latitude)
        plon = _to_float(p.longitude)
        if plat is None or plon is None:
            continue
        dkm = _haversine_km(lat, lon, plat, plon)
        if dkm <= radius_km:
            ravg, rcnt = rating_map.get(p.id, (None, 0))
            rows.append((dkm, p, ravg, rcnt))
    rows.sort(key=lambda t: (t[0], t[2] if t[2] is not None else -1.0, t[3]))
    out: list[PropertyOut] = []
    for (dkm, p, ravg, rcnt) in rows[:limit]:
        out.append(PropertyOut(
            id=str(p.id), name=p.name, type=p.type, city=p.city, description=p.description,
            address=p.address, latitude=p.latitude, longitude=p.longitude,
            rating_avg=ravg, rating_count=rcnt, is_favorite=bool(fav_map.get(p.id)) if fav_map else None,
            image_url=first_img.get(p.id),
        ))
    return out
