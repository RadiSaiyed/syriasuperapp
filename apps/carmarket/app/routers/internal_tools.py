from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..auth import get_current_user, get_db
from ..models import User, Listing
from ..schemas import ListingOut
from ..config import settings
from superapp_shared.internal_hmac import verify_internal_hmac_with_replay


router = APIRouter(prefix="/internal/tools", tags=["internal_tools"])  # HMAC + user auth required


class CreateListingIn(BaseModel):
    user_id: str
    title: str
    make: str
    model: str
    year: int
    price_cents: int
    city: str | None = None
    mileage_km: int | None = None
    condition: str | None = None
    description: str | None = None


@router.post("/create_listing", response_model=ListingOut)
def create_listing_internal(payload: CreateListingIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ts = request.headers.get("X-Internal-Ts") or ""
    sign = request.headers.get("X-Internal-Sign") or ""
    ok = verify_internal_hmac_with_replay(ts, payload.model_dump(), sign, settings.INTERNAL_API_SECRET, redis_url=settings.REDIS_URL, ttl_secs=60)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if str(user.id) != str(payload.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user mismatch")

    l = Listing(
        seller_user_id=user.id,
        title=payload.title,
        make=payload.make,
        model=payload.model,
        year=payload.year,
        price_cents=payload.price_cents,
        description=(payload.description or "").strip(),
        mileage_km=payload.mileage_km,
        condition=payload.condition,
        city=(payload.city or "").strip(),
    )
    db.add(l)
    db.flush()
    return ListingOut(
        id=str(l.id),
        title=l.title,
        make=l.make,
        model=l.model,
        year=l.year,
        price_cents=l.price_cents,
        seller_user_id=str(l.seller_user_id),
        mileage_km=l.mileage_km,
        condition=l.condition,
        city=l.city,
        status=l.status,
        images=[],
    )
