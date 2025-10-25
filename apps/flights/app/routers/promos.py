from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from ..auth import get_current_user, get_db
from ..models import PromoCode, PromoRedemption, User
from ..schemas import PromoCreateIn, PromoOut


router = APIRouter(prefix="/promos", tags=["promos"])


@router.post("", response_model=PromoOut)
def create_promo(payload: PromoCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # In MVP, any authenticated user can create; later restrict to admins.
    pc = PromoCode(
        code=payload.code,
        percent_off_bps=payload.percent_off_bps,
        amount_off_cents=payload.amount_off_cents,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        max_uses=payload.max_uses,
        per_user_max_uses=payload.per_user_max_uses,
        min_total_cents=payload.min_total_cents,
        active=payload.active,
    )
    db.add(pc)
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
        uses_count=pc.uses_count,
        min_total_cents=pc.min_total_cents,
        active=pc.active,
    )

