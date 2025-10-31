from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import httpx

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Ranch, AnimalListing, ProductListing, Order, FavoriteAnimal, FavoriteProduct, AnimalAuction, AuctionBid
from uuid import UUID
from ..schemas import (
    AnimalsListOut,
    AnimalOut,
    ProductsListOut,
    ProductOut,
    OrderCreateIn,
    OrdersListOut,
    OrderOut,
    AuctionsListOut,
    AuctionOut,
    BidIn,
)
from ..utils import notify
from ..config import settings
from superapp_shared.internal_hmac import sign_internal_request_headers


router = APIRouter(prefix="/market", tags=["market"]) 


@router.get("/animals", response_model=AnimalsListOut)
def browse_animals(
    q: str | None = None,
    species: str | None = None,
    breed: str | None = None,
    sex: str | None = None,
    location: str | None = None,
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(AnimalListing).filter(AnimalListing.status == "available")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(AnimalListing.species.ilike(like), AnimalListing.breed.ilike(like)))
    if species:
        query = query.filter(AnimalListing.species == species)
    if breed:
        query = query.filter(AnimalListing.breed == breed)
    if sex:
        query = query.filter(AnimalListing.sex == sex)
    if location:
        ranch_ids = [r.id for r in db.query(Ranch).filter(Ranch.location.ilike(f"%{location}%")).all()]
        if ranch_ids:
            query = query.filter(AnimalListing.ranch_id.in_(ranch_ids))
        else:
            return AnimalsListOut(animals=[], total=0)
    if min_price is not None:
        query = query.filter(AnimalListing.price_cents >= min_price)
    if max_price is not None:
        query = query.filter(AnimalListing.price_cents <= max_price)
    total = query.count()
    rows = query.order_by(AnimalListing.created_at.desc()).limit(limit).offset(offset).all()
    return AnimalsListOut(animals=[
        AnimalOut(id=str(a.id), ranch_id=str(a.ranch_id), species=a.species, breed=a.breed, sex=a.sex, age_months=a.age_months, weight_kg=a.weight_kg, price_cents=a.price_cents, status=a.status, created_at=a.created_at)
        for a in rows
    ], total=total)


@router.get("/animals/favorites", response_model=AnimalsListOut)
def animals_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(FavoriteAnimal).filter(FavoriteAnimal.user_id == user.id).all()
    ids = [r.animal_id for r in rows]
    if not ids:
        return AnimalsListOut(animals=[], total=0)
    animals = db.query(AnimalListing).filter(AnimalListing.id.in_(ids), AnimalListing.status != "sold").all()
    return AnimalsListOut(animals=[
        AnimalOut(id=str(a.id), ranch_id=str(a.ranch_id), species=a.species, breed=a.breed, sex=a.sex, age_months=a.age_months, weight_kg=a.weight_kg, price_cents=a.price_cents, status=a.status, created_at=a.created_at)
        for a in animals
    ], total=len(animals))


@router.get("/animals/{animal_id}", response_model=AnimalOut)
def animal_details(animal_id: UUID, db: Session = Depends(get_db)):
    a = db.get(AnimalListing, animal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Animal not found")
    return AnimalOut(id=str(a.id), ranch_id=str(a.ranch_id), species=a.species, breed=a.breed, sex=a.sex, age_months=a.age_months, weight_kg=a.weight_kg, price_cents=a.price_cents, status=a.status, created_at=a.created_at)


@router.post("/animals/{animal_id}/order", response_model=OrderOut)
def order_animal(animal_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(AnimalListing, animal_id)
    if not a or a.status != "available":
        raise HTTPException(status_code=404, detail="Animal not available")
    o = Order(buyer_user_id=user.id, type="animal", animal_id=a.id, qty=1, total_cents=a.price_cents, status="created")
    db.add(o)
    a.status = "sold"
    db.flush()
    # Optional Payments handoff
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and o.total_cents > 0:
            to_phone = settings.FEE_WALLET_PHONE
            payload_json = {"from_phone": user.phone, "to_phone": to_phone, "amount_cents": o.total_cents}
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, "")
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", headers=headers, json=payload_json)
                if r.status_code < 400:
                    o.payment_request_id = r.json().get("id")
                    db.flush()
    except Exception:
        pass
    notify("order.created", {"order_id": str(o.id), "type": "animal", "animal_id": str(a.id)})
    return OrderOut(id=str(o.id), type=o.type, product_id=None, animal_id=str(o.animal_id), qty=o.qty, total_cents=o.total_cents, status=o.status, created_at=o.created_at)


@router.get("/products", response_model=ProductsListOut)
def browse_products(
    q: str | None = None,
    type: str | None = None,
    unit: str | None = None,
    location: str | None = None,
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ProductListing).filter(ProductListing.status == "active")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ProductListing.product_type.ilike(like), ProductListing.unit.ilike(like)))
    if type:
        query = query.filter(ProductListing.product_type == type)
    if unit:
        query = query.filter(ProductListing.unit == unit)
    if location:
        ranch_ids = [r.id for r in db.query(Ranch).filter(Ranch.location.ilike(f"%{location}%")).all()]
        if ranch_ids:
            query = query.filter(ProductListing.ranch_id.in_(ranch_ids))
        else:
            return ProductsListOut(products=[], total=0)
    if min_price is not None:
        query = query.filter(ProductListing.price_per_unit_cents >= min_price)
    if max_price is not None:
        query = query.filter(ProductListing.price_per_unit_cents <= max_price)
    total = query.count()
    rows = query.order_by(ProductListing.created_at.desc()).limit(limit).offset(offset).all()
    return ProductsListOut(products=[
        ProductOut(id=str(p.id), ranch_id=str(p.ranch_id), product_type=p.product_type, unit=p.unit, quantity=p.quantity, price_per_unit_cents=p.price_per_unit_cents, status=p.status, created_at=p.created_at)
        for p in rows
    ], total=total)


# Favorites — Products
@router.get("/products/favorites", response_model=ProductsListOut)
def products_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(FavoriteProduct).filter(FavoriteProduct.user_id == user.id).all()
    ids = [r.product_id for r in rows]
    if not ids:
        return ProductsListOut(products=[], total=0)
    prods = db.query(ProductListing).filter(ProductListing.id.in_(ids), ProductListing.status != "sold_out").all()
    return ProductsListOut(products=[
        ProductOut(id=str(p.id), ranch_id=str(p.ranch_id), product_type=p.product_type, unit=p.unit, quantity=p.quantity, price_per_unit_cents=p.price_per_unit_cents, status=p.status, created_at=p.created_at)
        for p in prods
    ], total=len(prods))


@router.get("/products/{product_id}", response_model=ProductOut)
def product_details(product_id: UUID, db: Session = Depends(get_db)):
    p = db.get(ProductListing, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut(id=str(p.id), ranch_id=str(p.ranch_id), product_type=p.product_type, unit=p.unit, quantity=p.quantity, price_per_unit_cents=p.price_per_unit_cents, status=p.status, created_at=p.created_at)


@router.post("/products/{product_id}/order", response_model=OrderOut)
def order_product(product_id: UUID, payload: OrderCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(ProductListing, product_id)
    if not p or p.status != "active":
        raise HTTPException(status_code=404, detail="Product not available")
    if payload.qty > p.quantity:
        raise HTTPException(status_code=400, detail="Insufficient quantity")
    total = payload.qty * int(p.price_per_unit_cents)
    o = Order(buyer_user_id=user.id, type="product", product_id=p.id, qty=payload.qty, total_cents=total, status="created")
    db.add(o)
    p.quantity -= payload.qty
    if p.quantity <= 0:
        p.status = "sold_out"
    db.flush()
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and total > 0:
            to_phone = settings.FEE_WALLET_PHONE
            payload_json = {"from_phone": user.phone, "to_phone": to_phone, "amount_cents": o.total_cents}
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, "")
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", headers=headers, json=payload_json)
                if r.status_code < 400:
                    o.payment_request_id = r.json().get("id")
                    db.flush()
    except Exception:
        pass
    notify("order.created", {"order_id": str(o.id), "type": "product", "product_id": str(p.id)})
    return OrderOut(id=str(o.id), type=o.type, product_id=str(o.product_id), animal_id=None, qty=o.qty, total_cents=o.total_cents, status=o.status, created_at=o.created_at)


@router.get("/orders", response_model=OrdersListOut)
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Order).filter(Order.buyer_user_id == user.id).order_by(Order.created_at.desc()).all()
    return OrdersListOut(orders=[
        OrderOut(id=str(o.id), type=o.type, product_id=str(o.product_id) if o.product_id else None, animal_id=str(o.animal_id) if o.animal_id else None, qty=o.qty, total_cents=o.total_cents, status=o.status, created_at=o.created_at)
        for o in rows
    ])

@router.post("/animals/{animal_id}/favorite")
def add_fav_animal(animal_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(AnimalListing, animal_id)
    if not a:
        raise HTTPException(status_code=404, detail="Not found")
    exists = db.query(FavoriteAnimal).filter(FavoriteAnimal.user_id == user.id, FavoriteAnimal.animal_id == a.id).one_or_none()
    if exists:
        return {"detail": "ok"}
    db.add(FavoriteAnimal(user_id=user.id, animal_id=a.id))
    return {"detail": "ok"}


@router.delete("/animals/{animal_id}/favorite")
def del_fav_animal(animal_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(FavoriteAnimal).filter(FavoriteAnimal.user_id == user.id, FavoriteAnimal.animal_id == animal_id).one_or_none()
    if row:
        db.delete(row)
    return {"detail": "ok"}


@router.post("/products/{product_id}/favorite")
def add_fav_product(product_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(ProductListing, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    exists = db.query(FavoriteProduct).filter(FavoriteProduct.user_id == user.id, FavoriteProduct.product_id == p.id).one_or_none()
    if exists:
        return {"detail": "ok"}
    db.add(FavoriteProduct(user_id=user.id, product_id=p.id))
    return {"detail": "ok"}


@router.delete("/products/{product_id}/favorite")
def del_fav_product(product_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(FavoriteProduct).filter(FavoriteProduct.user_id == user.id, FavoriteProduct.product_id == product_id).one_or_none()
    if row:
        db.delete(row)
    return {"detail": "ok"}


# Auctions — Market
@router.get("/auctions", response_model=AuctionsListOut)
def list_auctions(db: Session = Depends(get_db)):
    rows = db.query(AnimalAuction).filter(AnimalAuction.status == "open").order_by(AnimalAuction.created_at.desc()).all()
    return AuctionsListOut(auctions=[
        AuctionOut(id=str(a.id), animal_id=str(a.animal_id), ranch_id=str(a.ranch_id), starting_price_cents=a.starting_price_cents, current_price_cents=a.current_price_cents, highest_bid_user_id=str(a.highest_bid_user_id) if a.highest_bid_user_id else None, ends_at=a.ends_at, status=a.status, created_at=a.created_at)
        for a in rows
    ], total=len(rows))


@router.get("/auctions/{auction_id}", response_model=AuctionOut)
def auction_details(auction_id: str, db: Session = Depends(get_db)):
    a = db.get(AnimalAuction, auction_id)
    if not a:
        raise HTTPException(status_code=404, detail="Not found")
    return AuctionOut(id=str(a.id), animal_id=str(a.animal_id), ranch_id=str(a.ranch_id), starting_price_cents=a.starting_price_cents, current_price_cents=a.current_price_cents, highest_bid_user_id=str(a.highest_bid_user_id) if a.highest_bid_user_id else None, ends_at=a.ends_at, status=a.status, created_at=a.created_at)


@router.post("/auctions/{auction_id}/bid", response_model=AuctionOut)
def place_bid(auction_id: str, payload: BidIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(AnimalAuction, auction_id)
    if not a or a.status != "open":
        raise HTTPException(status_code=404, detail="Auction not open")
    import datetime as dt
    if a.ends_at <= dt.datetime.now(dt.timezone.utc):
        a.status = "closed"
        db.flush()
        raise HTTPException(status_code=400, detail="Auction ended")
    min_next = max(a.starting_price_cents, a.current_price_cents) + 1
    if payload.amount_cents < min_next:
        raise HTTPException(status_code=400, detail=f"Bid too low; min {min_next}")
    db.add(AuctionBid(auction_id=a.id, user_id=user.id, amount_cents=payload.amount_cents))
    a.current_price_cents = payload.amount_cents
    a.highest_bid_user_id = user.id
    db.flush()
    return AuctionOut(id=str(a.id), animal_id=str(a.animal_id), ranch_id=str(a.ranch_id), starting_price_cents=a.starting_price_cents, current_price_cents=a.current_price_cents, highest_bid_user_id=str(a.highest_bid_user_id), ends_at=a.ends_at, status=a.status, created_at=a.created_at)
