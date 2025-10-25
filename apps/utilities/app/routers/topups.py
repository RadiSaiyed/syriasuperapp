from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from sqlalchemy import func
from ..models import User, Biller, Topup, PromoCode, PromoRedemption
from ..schemas import TopupIn, TopupOut, TopupsListOut


router = APIRouter(prefix="/topups", tags=["topups"])


def _to_out(t: Topup, applied_code: str | None = None, discount_cents: int | None = None, final_amount: int | None = None) -> TopupOut:
    return TopupOut(
        id=str(t.id), operator_biller_id=str(t.operator_biller_id), target_phone=t.target_phone, amount_cents=t.amount_cents, status=t.status, payment_request_id=t.payment_request_id,
        applied_promo_code=applied_code, discount_cents=discount_cents, final_amount_cents=final_amount
    )


@router.post("", response_model=TopupOut)
def create_topup(payload: TopupIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    biller = db.get(Biller, payload.operator_biller_id)
    if biller is None or biller.category != "mobile":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid operator")
    t = Topup(user_id=user.id, operator_biller_id=biller.id, target_phone=payload.target_phone, amount_cents=payload.amount_cents, status="created")
    db.add(t)
    db.flush()

    # Create payment request
    payment_request_id = None
    applied_code = None
    discount_cents = 0
    final_amount = t.amount_cents
    # Apply promo if provided
    if getattr(payload, 'promo_code', None):
        pc = db.query(PromoCode).filter(PromoCode.code == payload.promo_code).one_or_none()
        if pc and pc.active:
            from datetime import datetime as _dt
            now = _dt.utcnow()
            if not ((pc.valid_from and now < pc.valid_from) or (pc.valid_until and now > pc.valid_until)) and (pc.max_uses is None or pc.uses_count < pc.max_uses):
                per_user_ok = True
                if pc.per_user_max_uses:
                    cnt = db.query(func.count(PromoRedemption.id)).filter(PromoRedemption.promo_code_id == pc.id, PromoRedemption.user_id == user.id).scalar() or 0
                    per_user_ok = cnt < pc.per_user_max_uses
                if per_user_ok and (pc.min_total_cents is None or t.amount_cents >= pc.min_total_cents):
                    if pc.percent_off_bps:
                        discount_cents = max(discount_cents, int((t.amount_cents * pc.percent_off_bps + 5000)//10000))
                    if pc.amount_off_cents:
                        discount_cents = max(discount_cents, int(pc.amount_off_cents))
                    discount_cents = min(discount_cents, t.amount_cents)
                    applied_code = pc.code
                    final_amount = t.amount_cents - discount_cents
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and final_amount > 0:
            to_phone = settings.FEE_WALLET_PHONE
            payload_json = {"from_phone": user.phone, "to_phone": to_phone, "amount_cents": final_amount}
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            with httpx.Client(timeout=5.0) as client:
                r = client.post(
                    f"{settings.PAYMENTS_BASE_URL}/internal/requests",
                    headers=headers,
                    json=payload_json,
                )
                if r.status_code < 400:
                    payment_request_id = r.json().get("id")
    except Exception:
        pass

    if payment_request_id:
        t.payment_request_id = payment_request_id
    # Record promo redemption
    if applied_code and discount_cents > 0:
        pc = db.query(PromoCode).filter(PromoCode.code == applied_code).one_or_none()
        if pc:
            pc.uses_count = (pc.uses_count or 0) + 1
            db.add(PromoRedemption(promo_code_id=pc.id, topup_id=t.id, user_id=user.id))
    db.flush()
    return _to_out(t, applied_code, discount_cents or None, final_amount)


@router.get("", response_model=TopupsListOut)
def list_topups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Topup).filter(Topup.user_id == user.id).order_by(Topup.created_at.desc()).limit(100).all()
    return TopupsListOut(topups=[_to_out(t) for t in rows])
