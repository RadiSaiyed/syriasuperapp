from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import PromoCode, PromoRedemption, User
from ..schemas import PromoCreateIn, PromoOut


router = APIRouter(prefix="/promos", tags=["promos"])


def _require_dev():
    if settings.ENV != 'dev':
        raise HTTPException(status_code=403, detail="Not allowed")


@router.get("", response_model=list[PromoOut])
def list_promos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_dev()
    rows = db.query(PromoCode).order_by(PromoCode.created_at.desc()).limit(200).all()
    out = []
    for p in rows:
        out.append(PromoOut(
            id=str(p.id),
            code=p.code,
            percent_off_bps=p.percent_off_bps,
            amount_off_cents=p.amount_off_cents,
            valid_from=p.valid_from,
            valid_until=p.valid_until,
            max_uses=p.max_uses,
            per_user_max_uses=p.per_user_max_uses,
            uses_count=p.uses_count or 0,
            min_total_cents=p.min_total_cents,
            active=p.active,
        ))
    return out


@router.post("", response_model=PromoOut)
def create_promo(payload: PromoCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_dev()
    if not payload.percent_off_bps and not payload.amount_off_cents:
        raise HTTPException(status_code=400, detail="Provide percent_off_bps or amount_off_cents")
    pc = db.query(PromoCode).filter(PromoCode.code == payload.code).one_or_none()
    if pc is None:
        pc = PromoCode(code=payload.code)
        db.add(pc)
    pc.percent_off_bps = payload.percent_off_bps
    pc.amount_off_cents = payload.amount_off_cents
    pc.valid_from = payload.valid_from
    pc.valid_until = payload.valid_until
    pc.max_uses = payload.max_uses
    pc.per_user_max_uses = payload.per_user_max_uses
    pc.min_total_cents = payload.min_total_cents
    pc.active = payload.active
    db.flush()
    return PromoOut(
        id=str(pc.id),
        code=pc.code,
        percent_off_bps=pc.percent_off_bps,
        amount_off_cents=pc.amount_off_cents,
        valid_from=pc.valid_from,
        valid_until=pc.valid_until,
        max_uses=pc.max_uses,
        per_user_max_uses=pc.per_user_max_uses,
        uses_count=pc.uses_count or 0,
        min_total_cents=pc.min_total_cents,
        active=pc.active,
    )


@router.get("/stats")
def promo_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_dev()
    rows = db.query(PromoRedemption.promo_code_id, func.count(PromoRedemption.id)).group_by(PromoRedemption.promo_code_id).all()
    by_code = {str(pid): cnt for pid, cnt in rows}
    last = db.query(PromoRedemption).order_by(PromoRedemption.created_at.desc()).limit(50).all()
    last_out = [{
        'id': str(r.id),
        'promo_code_id': str(r.promo_code_id),
        'booking_id': str(r.booking_id),
        'user_id': str(r.user_id),
        'created_at': r.created_at.isoformat() + 'Z',
    } for r in last]
    return {'by_code': by_code, 'last_redemptions': last_out}

