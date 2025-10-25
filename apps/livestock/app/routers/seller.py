from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Ranch, AnimalListing, ProductListing, Order, AnimalAuction
from ..schemas import (
    RanchCreateIn,
    RanchOut,
    AnimalCreateIn,
    AnimalUpdateIn,
    AnimalOut,
    ProductCreateIn,
    ProductUpdateIn,
    ProductOut,
    OrdersListOut,
    OrderOut,
    AuctionCreateIn,
    AuctionOut,
)
from ..utils import notify


router = APIRouter(prefix="/seller", tags=["seller"]) 


def _require_seller(user: User):
    if user.role not in ("seller",):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller role required")


@router.post("/ranch", response_model=RanchOut)
def create_ranch(payload: RanchCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    existing = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Ranch already exists")
    r = Ranch(owner_user_id=user.id, name=payload.name, location=payload.location, description=payload.description)
    db.add(r)
    db.flush()
    notify("ranch.created", {"ranch_id": str(r.id), "owner_user_id": str(user.id)})
    return RanchOut(id=str(r.id), name=r.name, location=r.location, description=r.description, created_at=r.created_at)


@router.get("/ranch", response_model=RanchOut)
def get_ranch(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Ranch not found")
    return RanchOut(id=str(r.id), name=r.name, location=r.location, description=r.description, created_at=r.created_at)


@router.post("/animals", response_model=AnimalOut)
def create_animal(payload: AnimalCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r:
        raise HTTPException(status_code=400, detail="Ranch required")
    a = AnimalListing(ranch_id=r.id, species=payload.species, breed=payload.breed, sex=payload.sex, age_months=payload.age_months, weight_kg=payload.weight_kg, price_cents=payload.price_cents)
    db.add(a)
    db.flush()
    notify("animal.created", {"animal_id": str(a.id), "ranch_id": str(r.id)})
    return AnimalOut(id=str(a.id), ranch_id=str(a.ranch_id), species=a.species, breed=a.breed, sex=a.sex, age_months=a.age_months, weight_kg=a.weight_kg, price_cents=a.price_cents, status=a.status, created_at=a.created_at)


@router.get("/animals", response_model=list[AnimalOut])
def list_my_animals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r:
        return []
    rows = db.query(AnimalListing).filter(AnimalListing.ranch_id == r.id).order_by(AnimalListing.created_at.desc()).all()
    return [
        AnimalOut(id=str(a.id), ranch_id=str(a.ranch_id), species=a.species, breed=a.breed, sex=a.sex, age_months=a.age_months, weight_kg=a.weight_kg, price_cents=a.price_cents, status=a.status, created_at=a.created_at)
        for a in rows
    ]


@router.patch("/animals/{animal_id}", response_model=AnimalOut)
def update_animal(animal_id: str, payload: AnimalUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    a = db.get(AnimalListing, animal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Animal not found")
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r or a.ranch_id != r.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.breed is not None:
        a.breed = payload.breed
    if payload.sex is not None:
        a.sex = payload.sex
    if payload.age_months is not None:
        a.age_months = payload.age_months
    if payload.weight_kg is not None:
        a.weight_kg = payload.weight_kg
    if payload.price_cents is not None:
        a.price_cents = payload.price_cents
    if payload.status is not None:
        a.status = payload.status
    db.flush()
    notify("animal.updated", {"animal_id": str(a.id)})
    return AnimalOut(id=str(a.id), ranch_id=str(a.ranch_id), species=a.species, breed=a.breed, sex=a.sex, age_months=a.age_months, weight_kg=a.weight_kg, price_cents=a.price_cents, status=a.status, created_at=a.created_at)


@router.post("/products", response_model=ProductOut)
def create_product(payload: ProductCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r:
        raise HTTPException(status_code=400, detail="Ranch required")
    p = ProductListing(ranch_id=r.id, product_type=payload.product_type, unit=payload.unit, quantity=payload.quantity, price_per_unit_cents=payload.price_per_unit_cents)
    db.add(p)
    db.flush()
    notify("product.created", {"product_id": str(p.id), "ranch_id": str(r.id)})
    return ProductOut(id=str(p.id), ranch_id=str(p.ranch_id), product_type=p.product_type, unit=p.unit, quantity=p.quantity, price_per_unit_cents=p.price_per_unit_cents, status=p.status, created_at=p.created_at)


@router.get("/products", response_model=list[ProductOut])
def list_my_products(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r:
        return []
    rows = db.query(ProductListing).filter(ProductListing.ranch_id == r.id).order_by(ProductListing.created_at.desc()).all()
    return [
        ProductOut(id=str(p.id), ranch_id=str(p.ranch_id), product_type=p.product_type, unit=p.unit, quantity=p.quantity, price_per_unit_cents=p.price_per_unit_cents, status=p.status, created_at=p.created_at)
        for p in rows
    ]


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    p = db.get(ProductListing, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r or p.ranch_id != r.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if payload.unit is not None:
        p.unit = payload.unit
    if payload.quantity is not None:
        p.quantity = payload.quantity
    if payload.price_per_unit_cents is not None:
        p.price_per_unit_cents = payload.price_per_unit_cents
    if payload.status is not None:
        p.status = payload.status
    db.flush()
    notify("product.updated", {"product_id": str(p.id)})
    return ProductOut(id=str(p.id), ranch_id=str(p.ranch_id), product_type=p.product_type, unit=p.unit, quantity=p.quantity, price_per_unit_cents=p.price_per_unit_cents, status=p.status, created_at=p.created_at)


@router.get("/orders", response_model=OrdersListOut)
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r:
        return OrdersListOut(orders=[])
    # orders for my ranch items
    animal_ids = [a.id for a in db.query(AnimalListing).filter(AnimalListing.ranch_id == r.id).all()]
    product_ids = [p.id for p in db.query(ProductListing).filter(ProductListing.ranch_id == r.id).all()]
    rows = db.query(Order).filter(((Order.type == "animal") & (Order.animal_id.in_(animal_ids))) | ((Order.type == "product") & (Order.product_id.in_(product_ids)))).order_by(Order.created_at.desc()).all()
    return OrdersListOut(orders=[
        OrderOut(id=str(o.id), type=o.type, product_id=str(o.product_id) if o.product_id else None, animal_id=str(o.animal_id) if o.animal_id else None, qty=o.qty, total_cents=o.total_cents, status=o.status, created_at=o.created_at)
        for o in rows
    ])


@router.delete("/animals/{animal_id}")
def delete_animal(animal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    a = db.get(AnimalListing, animal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Not found")
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r or a.ranch_id != r.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if a.status in ("sold", "auction"):
        raise HTTPException(status_code=400, detail="Cannot delete sold or auctioned animal")
    db.delete(a)
    return {"detail": "deleted"}


@router.delete("/products/{product_id}")
def delete_product(product_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    p = db.get(ProductListing, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r or p.ranch_id != r.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    db.delete(p)
    return {"detail": "deleted"}


@router.post("/auctions", response_model=AuctionOut)
def create_auction(payload: AuctionCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    a = db.get(AnimalListing, payload.animal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Animal not found")
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r or a.ranch_id != r.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    import datetime as dt
    try:
        ends_at = dt.datetime.fromisoformat(payload.ends_at_iso.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ends_at_iso")
    if ends_at <= dt.datetime.utcnow():
        raise HTTPException(status_code=400, detail="ends_at must be in future")
    if a.status != "available":
        raise HTTPException(status_code=400, detail="Animal not available")
    a.status = "auction"
    au = AnimalAuction(animal_id=a.id, ranch_id=r.id, starting_price_cents=payload.starting_price_cents, current_price_cents=payload.starting_price_cents, ends_at=ends_at, status="open")
    db.add(au)
    db.flush()
    return AuctionOut(id=str(au.id), animal_id=str(au.animal_id), ranch_id=str(au.ranch_id), starting_price_cents=au.starting_price_cents, current_price_cents=au.current_price_cents, highest_bid_user_id=None, ends_at=au.ends_at, status=au.status, created_at=au.created_at)


@router.get("/auctions", response_model=list[AuctionOut])
def list_my_auctions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r:
        return []
    rows = db.query(AnimalAuction).filter(AnimalAuction.ranch_id == r.id).order_by(AnimalAuction.created_at.desc()).all()
    return [
        AuctionOut(id=str(a.id), animal_id=str(a.animal_id), ranch_id=str(a.ranch_id), starting_price_cents=a.starting_price_cents, current_price_cents=a.current_price_cents, highest_bid_user_id=str(a.highest_bid_user_id) if a.highest_bid_user_id else None, ends_at=a.ends_at, status=a.status, created_at=a.created_at)
        for a in rows
    ]


@router.post("/auctions/{auction_id}/close", response_model=AuctionOut)
def close_auction(auction_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_seller(user)
    au = db.get(AnimalAuction, auction_id)
    if not au:
        raise HTTPException(status_code=404, detail="Not found")
    r = db.query(Ranch).filter(Ranch.owner_user_id == user.id).one_or_none()
    if not r or au.ranch_id != r.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if au.status == "closed":
        return AuctionOut(id=str(au.id), animal_id=str(au.animal_id), ranch_id=str(au.ranch_id), starting_price_cents=au.starting_price_cents, current_price_cents=au.current_price_cents, highest_bid_user_id=str(au.highest_bid_user_id) if au.highest_bid_user_id else None, ends_at=au.ends_at, status=au.status, created_at=au.created_at)
    au.status = "closed"
    # finalize sale if there is a highest bid
    if au.highest_bid_user_id:
        # mark animal sold and create order for highest bidder
        a = db.get(AnimalListing, au.animal_id)
        if a:
            a.status = "sold"
        o = Order(buyer_user_id=au.highest_bid_user_id, type="animal", animal_id=au.animal_id, qty=1, total_cents=au.current_price_cents, status="created")
        db.add(o)
    db.flush()
    return AuctionOut(id=str(au.id), animal_id=str(au.animal_id), ranch_id=str(au.ranch_id), starting_price_cents=au.starting_price_cents, current_price_cents=au.current_price_cents, highest_bid_user_id=str(au.highest_bid_user_id) if au.highest_bid_user_id else None, ends_at=au.ends_at, status=au.status, created_at=au.created_at)
