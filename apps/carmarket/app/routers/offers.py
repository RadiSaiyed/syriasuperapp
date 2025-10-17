from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from sqlalchemy import func, select
from ..models import User, Listing, Offer, SellerReview
from ..schemas import OfferCreateIn, OfferOut, OffersListOut, ReviewIn, ReviewOut


router = APIRouter(prefix="/offers", tags=["offers"])


def _to_out(o: Offer) -> OfferOut:
    return OfferOut(id=str(o.id), listing_id=str(o.listing_id), buyer_user_id=str(o.buyer_user_id), amount_cents=o.amount_cents, status=o.status, payment_request_id=o.payment_request_id)


@router.post("/listing/{listing_id}", response_model=OfferOut)
def create_offer(listing_id: str, payload: OfferCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if l.seller_user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot offer on your own listing")
    o = Offer(listing_id=l.id, buyer_user_id=user.id, amount_cents=payload.amount_cents, status="pending")
    db.add(o)
    db.flush()
    return _to_out(o)


@router.get("", response_model=OffersListOut)
def my_offers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Offer).filter(Offer.buyer_user_id == user.id).order_by(Offer.created_at.desc()).limit(100).all()
    return OffersListOut(offers=[_to_out(o) for o in rows])


@router.get("/listing/{listing_id}", response_model=OffersListOut)
def offers_for_listing(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if l.seller_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your listing")
    rows = db.query(Offer).filter(Offer.listing_id == l.id).order_by(Offer.created_at.desc()).limit(100).all()
    return OffersListOut(offers=[_to_out(o) for o in rows])


@router.post("/{offer_id}/accept", response_model=OfferOut)
def accept_offer(offer_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.execute(select(Offer).where(Offer.id == offer_id).with_for_update()).scalars().first()
    if o is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    l = db.get(Listing, o.listing_id)
    if l is None or l.seller_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your listing")
    if o.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    o.status = "accepted"
    db.flush()

    # Payment request
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and o.amount_cents:
            buyer = db.get(User, o.buyer_user_id)
            seller = db.get(User, l.seller_user_id)
            payload_json = {"from_phone": buyer.phone, "to_phone": seller.phone, "amount_cents": o.amount_cents}
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.PAYMENTS_BASE_URL}/internal/requests",
                    headers=headers,
                    json=payload_json,
                )
                if r.status_code < 400:
                    o.payment_request_id = r.json().get("id")
                    db.flush()
    except Exception:
        pass
    return _to_out(o)


@router.post("/{offer_id}/reject", response_model=OfferOut)
def reject_offer(offer_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.execute(select(Offer).where(Offer.id == offer_id).with_for_update()).scalars().first()
    if o is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    l = db.get(Listing, o.listing_id)
    if l is None or l.seller_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your listing")
    o.status = "rejected"
    db.flush()
    return _to_out(o)


@router.post("/{offer_id}/cancel", response_model=OfferOut)
def cancel_offer(offer_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.execute(select(Offer).where(Offer.id == offer_id).with_for_update()).scalars().first()
    if o is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    if o.buyer_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if o.status != "pending":
        raise HTTPException(status_code=400, detail="Cannot cancel now")
    o.status = "canceled"
    db.flush()
    return _to_out(o)


@router.post("/{offer_id}/rate", response_model=ReviewOut)
def rate_seller(offer_id: str, payload: ReviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Offer, offer_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    l = db.get(Listing, o.listing_id)
    if o.buyer_user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if o.status != "accepted":
        raise HTTPException(status_code=400, detail="Offer not accepted")
    existing = db.query(SellerReview).filter(SellerReview.offer_id == o.id).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Already rated")
    r = SellerReview(offer_id=o.id, seller_user_id=l.seller_user_id, buyer_user_id=o.buyer_user_id, rating=payload.rating, comment=payload.comment or None)
    db.add(r)
    db.flush()
    return ReviewOut(id=str(r.id), offer_id=str(o.id), seller_user_id=str(r.seller_user_id), buyer_user_id=str(r.buyer_user_id), rating=r.rating, comment=r.comment, created_at=r.created_at)
