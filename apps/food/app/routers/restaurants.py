from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Restaurant, MenuItem, User, RestaurantReview, RestaurantImage
from ..schemas import RestaurantOut, MenuItemOut, RestaurantImageOut


router = APIRouter(prefix="/restaurants", tags=["restaurants"])


def _seed_dev(db: Session):
    if db.query(Restaurant).count() > 0:
        return
    r1 = Restaurant(name="Damascus Eats", city="Damascus", description="Local favorites")
    r2 = Restaurant(name="Aleppo Grill", city="Aleppo", description="Grilled goodness")
    db.add_all([r1, r2])
    db.flush()
    items = [
        MenuItem(restaurant_id=r1.id, name="Shawarma", description="Chicken shawarma wrap", price_cents=15000),
        MenuItem(restaurant_id=r1.id, name="Falafel", description="Crispy falafel", price_cents=8000),
        MenuItem(restaurant_id=r2.id, name="Kebab Plate", description="Mixed kebabs", price_cents=22000),
        MenuItem(restaurant_id=r2.id, name="Hummus", description="With olive oil", price_cents=7000),
    ]
    db.add_all(items)
    db.flush()


@router.get("", response_model=list[RestaurantOut])
def list_restaurants(user: User = Depends(get_current_user), db: Session = Depends(get_db), city: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0):
    _seed_dev(db)
    query = db.query(Restaurant)
    if city:
        query = query.filter(Restaurant.city == city)
    rows = query.order_by(Restaurant.created_at.desc()).limit(limit).offset(offset).all()
    out: list[RestaurantOut] = []
    from sqlalchemy import func
    def _compute_is_open(hours: dict | None, override: bool | None, specials: dict | None = None) -> bool | None:
        if override is not None:
            return bool(override)
        if not hours:
            return None
        try:
            import datetime as _dt
            now = _dt.datetime.utcnow()
            if specials:
                key = now.strftime("%Y-%m-%d")
                if key in specials:
                    slots = specials.get(key) or []
                    if slots in ([], None, "closed"):
                        return False
                    hm = now.hour * 60 + now.minute
                    for s in slots:
                        if not isinstance(s, (list, tuple)) or len(s) != 2:
                            continue
                        a, b = s
                        ah, am = map(int, str(a).split(":"))
                        bh, bm = map(int, str(b).split(":"))
                        if (ah*60+am) <= hm <= (bh*60+bm):
                            return True
                    return False
            weekday = ["mon","tue","wed","thu","fri","sat","sun"][now.weekday()]
            slots = hours.get(weekday) or []
            hm = now.hour * 60 + now.minute
            for s in slots:
                if not isinstance(s, (list, tuple)) or len(s) != 2:
                    continue
                a, b = s
                ah, am = map(int, str(a).split(":"))
                bh, bm = map(int, str(b).split(":"))
                if (ah*60+am) <= hm <= (bh*60+bm):
                    return True
            return False
        except Exception:
            return None

    for r in rows:
        if q and q.lower() not in ((r.name or "") + " " + (r.description or "")).lower():
            continue
        avg, cnt = db.query(func.avg(RestaurantReview.rating), func.count(RestaurantReview.id)).filter(RestaurantReview.restaurant_id == r.id).one()
        hours_dict = None
        if getattr(r, "hours_json", None):
            try:
                import json as _json
                hours_dict = _json.loads(r.hours_json)
            except Exception:
                hours_dict = None
        specials = None
        if getattr(r, "special_hours_json", None):
            try:
                import json as _json
                specials = _json.loads(r.special_hours_json)
            except Exception:
                specials = None
        is_open = _compute_is_open(hours_dict, getattr(r, "is_open_override", None), specials)
        out.append(RestaurantOut(id=str(r.id), name=r.name, city=r.city, description=r.description, address=r.address, rating_avg=float(avg) if avg is not None else None, rating_count=int(cnt) if cnt is not None else 0, is_open=is_open))
    return out


@router.get("/{restaurant_id}/menu", response_model=list[MenuItemOut])
def list_menu(restaurant_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _seed_dev(db)
    rows = (
        db.query(MenuItem)
        .filter(MenuItem.restaurant_id == restaurant_id)
        .order_by(MenuItem.created_at.desc())
        .all()
    )
    return [
        MenuItemOut(id=str(m.id), restaurant_id=str(m.restaurant_id), name=m.name, description=m.description, price_cents=m.price_cents, available=m.available)
        for m in rows
    ]


@router.get("/{restaurant_id}/images", response_model=list[RestaurantImageOut])
def public_list_images(restaurant_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Public listing of restaurant images (no owner restriction)
    imgs = (
        db.query(RestaurantImage)
        .filter(RestaurantImage.restaurant_id == restaurant_id)
        .order_by(RestaurantImage.sort_order.asc(), RestaurantImage.created_at.asc())
        .all()
    )
    return [RestaurantImageOut(id=str(i.id), url=i.url, sort_order=i.sort_order) for i in imgs]
