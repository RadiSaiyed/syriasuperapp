# carmarket
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..auth import get_current_user, get_db
from ..models import User, Listing, ListingImage
from ..schemas import ListingCreateIn, ListingOut, ListingsListOut, ListingImageIn
from fastapi import HTTPException, status
import os
import httpx


router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("", response_model=ListingOut)
def create_listing(payload: ListingCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = Listing(
        seller_user_id=user.id,
        title=payload.title,
        make=payload.make,
        model=payload.model,
        year=payload.year,
        price_cents=payload.price_cents,
        description=payload.description,
        mileage_km=payload.mileage_km,
        condition=payload.condition,
        city=payload.city,
    )
    db.add(l)
    db.flush()
    return ListingOut(id=str(l.id), title=l.title, make=l.make, model=l.model, year=l.year, price_cents=l.price_cents, seller_user_id=str(l.seller_user_id), mileage_km=l.mileage_km, condition=l.condition, city=l.city, status=l.status, images=[])


@router.get("", response_model=ListingsListOut)
def browse_listings(
    q: str | None = Query(None),
    make: str | None = Query(None),
    model: str | None = Query(None),
    city: str | None = Query(None),
    year_min: int | None = Query(None),
    year_max: int | None = Query(None),
    min_price: int | None = Query(None),
    max_price: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    qry = db.query(Listing)
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(Listing.title.ilike(like), Listing.make.ilike(like), Listing.model.ilike(like), Listing.city.ilike(like)))
    if make:
        conds.append(Listing.make.ilike(make))
    if model:
        conds.append(Listing.model.ilike(model))
    if city:
        conds.append(Listing.city.ilike(city))
    if year_min is not None:
        conds.append(Listing.year >= year_min)
    if year_max is not None:
        conds.append(Listing.year <= year_max)
    if min_price is not None:
        conds.append(Listing.price_cents >= min_price)
    if max_price is not None:
        conds.append(Listing.price_cents <= max_price)
    if conds:
        qry = qry.filter(and_(*conds))
    rows = qry.order_by(Listing.created_at.desc()).offset(offset).limit(limit).all()
    return ListingsListOut(listings=[ListingOut(id=str(l.id), title=l.title, make=l.make, model=l.model, year=l.year, price_cents=l.price_cents, seller_user_id=str(l.seller_user_id), mileage_km=l.mileage_km, condition=l.condition, city=l.city, status=l.status) for l in rows])


@router.get("/mine", response_model=ListingsListOut)
def my_listings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Listing).filter(Listing.seller_user_id == user.id).order_by(Listing.created_at.desc()).limit(100).all()
    return ListingsListOut(listings=[ListingOut(id=str(l.id), title=l.title, make=l.make, model=l.model, year=l.year, price_cents=l.price_cents, seller_user_id=str(l.seller_user_id), mileage_km=l.mileage_km, condition=l.condition, city=l.city, status=l.status) for l in rows])


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    imgs = db.query(ListingImage).filter(ListingImage.listing_id == l.id).order_by(ListingImage.created_at.asc()).all()
    return ListingOut(
        id=str(l.id), title=l.title, make=l.make, model=l.model, year=l.year, price_cents=l.price_cents,
        seller_user_id=str(l.seller_user_id), mileage_km=l.mileage_km, condition=l.condition, city=l.city, status=l.status,
        images=[im.url for im in imgs]
    )


@router.get("/{listing_id}/recommendations", response_model=ListingsListOut)
def recommend_similar(listing_id: str, limit: int = Query(10, ge=1, le=50), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return similar listings using AI ranking over title/make/model/city.

    Fallbacks gracefully if the AI gateway is unavailable.
    """
    src = db.get(Listing, listing_id)
    if src is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    query = f"{src.title} {src.make} {src.model} {src.city}"
    # Candidate pool: recent active listings excluding the source
    candidates = (
        db.query(Listing)
        .filter(Listing.id != src.id)
        .filter(Listing.status == "active")
        .order_by(Listing.created_at.desc())
        .limit(200)
        .all()
    )
    items = [{"id": str(l.id), "text": f"{l.title} {l.make} {l.model} {l.city}"} for l in candidates]
    base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
    scores: list[dict] = []
    try:
        with httpx.Client(base_url=base) as client:
            r = client.post("/v1/rank", json={"query": query, "items": items})
            r.raise_for_status()
            data = r.json()
            scores = data.get("scores", [])
    except Exception:
        scores = []
    by_id = {str(l.id): l for l in candidates}
    ordered: list[Listing] = []
    for s in scores:
        l = by_id.get(str(s.get("id")))
        if l:
            ordered.append(l)
    # If AI didn’t return anything, fall back to recents
    if not ordered:
        ordered = candidates
    rows = ordered[:limit]
    return ListingsListOut(listings=[
        ListingOut(
            id=str(l.id), title=l.title, make=l.make, model=l.model, year=l.year, price_cents=l.price_cents,
            seller_user_id=str(l.seller_user_id), mileage_km=l.mileage_km, condition=l.condition, city=l.city, status=l.status
        ) for l in rows
    ])


@router.post("/{listing_id}/images")
def add_listing_image(listing_id: str, payload: ListingImageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if l.seller_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    db.add(ListingImage(listing_id=l.id, url=payload.url.strip()))
    db.flush()
    return {"detail": "ok"}


@router.post("/{listing_id}/mark_sold")
def mark_sold(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if l.seller_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    l.status = "sold"
    db.flush()
    return {"detail": "sold"}


@router.post("/{listing_id}/hide")
def hide_listing(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if l.seller_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    l.status = "hidden"
    db.flush()
    return {"detail": "hidden"}


@router.post("/{listing_id}/activate")
def activate_listing(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if l.seller_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    l.status = "active"
    db.flush()
    return {"detail": "active"}


@router.get("/{listing_id}/price_estimate")
def price_estimate(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
    try:
        with httpx.Client(base_url=base, timeout=4.0) as client:
            r = client.post("/v1/estimate/car", json={
                "title": l.title,
                "make": l.make,
                "model": l.model,
                "year": l.year,
                "mileage_km": l.mileage_km,
                "city": l.city,
            })
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Price estimate unavailable: {e}")
