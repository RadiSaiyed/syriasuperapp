from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import httpx

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Farm, Listing, Order
from ..schemas import ListingOut, ListingsListOut, OrderCreateIn, OrderOut, OrdersListOut
from ..utils import notify
from ..config import settings
from superapp_shared.internal_hmac import sign_internal_request_headers


router = APIRouter(prefix="/market", tags=["market"])


@router.get("/listings", response_model=ListingsListOut)
def browse_listings(
    q: str | None = None,
    category: str | None = None,
    location: str | None = None,
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Listing).filter(Listing.status == "active")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Listing.produce_name.ilike(like), Listing.category.ilike(like)))
    if category:
        query = query.filter(Listing.category == category)
    if location:
        # Join via farms to filter by location
        farm_ids = [f.id for f in db.query(Farm).filter(Farm.location.ilike(f"%{location}%")).all()]
        if farm_ids:
            query = query.filter(Listing.farm_id.in_(farm_ids))
        else:
            return ListingsListOut(listings=[], total=0)
    total = query.count()
    rows = query.order_by(Listing.created_at.desc()).limit(limit).offset(offset).all()
    return ListingsListOut(
        listings=[
            ListingOut(
                id=str(l.id), farm_id=str(l.farm_id), produce_name=l.produce_name,
                category=l.category, quantity_kg=l.quantity_kg, price_per_kg_cents=l.price_per_kg_cents,
                status=l.status, created_at=l.created_at,
            )
            for l in rows
        ],
        total=total,
    )


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: str, db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if not l:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingOut(
        id=str(l.id), farm_id=str(l.farm_id), produce_name=l.produce_name, category=l.category,
        quantity_kg=l.quantity_kg, price_per_kg_cents=l.price_per_kg_cents, status=l.status, created_at=l.created_at,
    )


@router.post("/listings/{listing_id}/order", response_model=OrderOut)
def place_order(listing_id: str, payload: OrderCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if not l or l.status != "active":
        raise HTTPException(status_code=404, detail="Listing not available")
    if payload.qty_kg > l.quantity_kg:
        raise HTTPException(status_code=400, detail="Insufficient quantity")
    total = payload.qty_kg * int(l.price_per_kg_cents)
    o = Order(buyer_user_id=user.id, listing_id=l.id, qty_kg=payload.qty_kg, total_cents=total, status="created")
    db.add(o)
    # Deduct reserved quantity for simplicity
    l.quantity_kg -= payload.qty_kg
    if l.quantity_kg <= 0:
        l.status = "sold_out"
    db.flush()
    # Optional Payments handoff (best-effort)
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and total > 0:
            to_phone = settings.FEE_WALLET_PHONE
            payload_json = {"from_phone": user.phone, "to_phone": to_phone, "amount_cents": o.total_cents}
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, "")
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/requests", headers=headers, json=payload_json)
                if r.status_code < 400:
                    o.payment_request_id = r.json().get("id")
                    # Keep order status 'created'; actual payment confirmation happens in Payments app
                    db.flush()
    except Exception:
        pass

    notify("order.created", {"order_id": str(o.id), "listing_id": str(l.id)})
    return OrderOut(id=str(o.id), listing_id=str(o.listing_id), qty_kg=o.qty_kg, total_cents=o.total_cents, status=o.status, created_at=o.created_at)


@router.get("/orders", response_model=OrdersListOut)
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Order).filter(Order.buyer_user_id == user.id).order_by(Order.created_at.desc()).all()
    return OrdersListOut(orders=[
        OrderOut(id=str(o.id), listing_id=str(o.listing_id), qty_kg=o.qty_kg, total_cents=o.total_cents, status=o.status, created_at=o.created_at)
        for o in rows
    ])
